from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum, F, Case, When, Value, DecimalField
from django.core.exceptions import ObjectDoesNotExist

from rest_framework import serializers, status
from rest_framework.decorators import permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from contacts.models import Ledger
from global_vars import VoucherType
from inventory.views import ClosingStockCal
from sales.models import SalesVou
from sales.serializers import SalesVouSerializer
from purchase.models import PurchaseVoucher

from ..fine_gold_service import FineGoldRateService
from ..models import *
from ..models import Account, VoucherDetail
from ..serializers import PurchaseVoucherSerializer
from ..utils import *

from django.db.models.functions import Coalesce, Abs

# Import helpers from ledger module (they are defined there since they appear first)
from .ledger import (
    get_all_descendants,
    _get_retail_for_report,
    _get_retail_ids_for_report,
)


def calcuate_pnl(start_date, end_date, retail=None, retail_ids=None):
    """
    Standard Trading & P&L calculation.

    COGS = Opening Stock + Purchases − Purchase Returns − Closing Stock
    Gross Profit = Sales Revenue − COGS
    Net Profit = Gross Profit − Direct Expenses (excl. Purchases) − Indirect Expenses

    Opening Stock  : Opening balance of ledgers under CA-STK (Stock-in-Hand).
    Purchases      : Period debits to ledgers under EXP-DIR-PUR (Purchase Account).
    Purchase Returns: Period credits to ledgers under EXP-DIR-PUR.
    Closing Stock  : Current physical inventory value as of end_date, sourced from
                     ClosingStockCal (weighted average method), same as the balance sheet.
    Expenses       : All Expense account descendants EXCLUDING EXP-DIR-PUR, so that
                     purchases are not counted twice.
    """
    # Normalise scope: retail_ids (list) is the canonical input.
    # Legacy callers pass a single `retail` object — convert to a 1-element list.
    if retail_ids is None and retail is not None:
        retail_ids = [retail.id if hasattr(retail, 'id') else retail]

    base_filter = {'voucher_main__date__range': [start_date, end_date]}
    if retail_ids:
        base_filter['voucher_main__retail_id__in'] = retail_ids

    # ── Opening Stock ─────────────────────────────────────────────────────────
    # Calculated from physical inventory: barcoded stock (op_stk=True),
    # unbarcoded stock (op_stk=True), and raw material inventory,
    # each valued at the item's weighted average rate.
    opening_stock = calculate_opening_stock(retail_ids=retail_ids)

    # ── Purchases & Purchase Returns ──────────────────────────────────────────
    # Read directly from the Purchase Account ledger group (EXP-DIR-PUR) to avoid
    # including GST / other line items from purchase vouchers.
    pur_exclude_ids: frozenset = frozenset()
    try:
        pur_group = Account.objects.get(code='EXP-DIR-PUR')
        pur_descendants = get_all_descendants(pur_group)
        pur_ldgrs = Ledger.objects.filter(ac_group__in=[pur_group] + pur_descendants)
        pur_agg = VoucherDetail.objects.filter(
            account__in=pur_ldgrs, **base_filter
        ).aggregate(
            purchases=Sum('debit', output_field=DecimalField()),
            purchase_returns=Sum('credit', output_field=DecimalField()),
        )
        purchases = pur_agg['purchases'] or Decimal(0)
        purchase_returns = pur_agg['purchase_returns'] or Decimal(0)
        pur_exclude_ids = frozenset([pur_group.id] + [a.id for a in pur_descendants])
        pur_group_name = pur_group.name
    except Account.DoesNotExist:
        purchases = Decimal(0)
        purchase_returns = Decimal(0)
        pur_group_name = None

    # ── Closing Stock ─────────────────────────────────────────────────────────
    # Derived from physical inventory (same source the balance sheet uses), not
    # from manual journal entries, so the value is always current.
    import logging
    logger = logging.getLogger(__name__)
    from inventory.views import ClosingStockCal
    from inventory.models import InterRetailTransferItem, InterRetailTransferVoucher

    try:
        closing_stock = ClosingStockCal().calculate_closing_stock(
            from_date="2000-01-01", to_date=str(end_date), retail_ids=retail_ids
        )['total_value'] or Decimal(0)
    except (ValueError, TypeError, ArithmeticError, LookupError) as e:
        logger.warning("P&L closing-stock calculation failed: %s", e, exc_info=True)
        closing_stock = Decimal(0)

    # ── Inter-retail Transfers (period) ───────────────────────────────────────
    # Include Transfers In / Out on each retail's COGS so per-retail P&L stays correct
    # when stock moves between retails at different weighted-avg rates. At consolidated
    # level these net to zero across retails.
    transfer_in_total = Decimal(0)
    transfer_out_total = Decimal(0)
    try:
        transfer_base = InterRetailTransferItem.objects.filter(
            voucher__status=InterRetailTransferVoucher.STATUS_RECEIVED,
            voucher__transfer_date__range=[start_date, end_date],
        )
        if retail_ids:
            transfer_in_total = transfer_base.filter(
                voucher__to_retail_id__in=retail_ids
            ).aggregate(t=Sum('transfer_value'))['t'] or Decimal(0)
            transfer_out_total = transfer_base.filter(
                voucher__from_retail_id__in=retail_ids
            ).aggregate(t=Sum('transfer_value'))['t'] or Decimal(0)
            # Transfers whose both endpoints are inside the selected scope are
            # internal — they net to zero, don't let them inflate COGS.
            internal = transfer_base.filter(
                voucher__to_retail_id__in=retail_ids,
                voucher__from_retail_id__in=retail_ids,
            ).aggregate(t=Sum('transfer_value'))['t'] or Decimal(0)
            transfer_in_total -= internal
            transfer_out_total -= internal
        # When no retail scope: both sums cover the whole company — they would cancel.
        # Leave as zero so consolidated COGS line is unaffected.
    except (ValueError, TypeError, LookupError) as e:
        logger.warning("P&L inter-retail transfer aggregation failed: %s", e, exc_info=True)

    # ── COGS & Gross Profit ───────────────────────────────────────────────────
    # COGS = Opening + Purchases − Purchase Returns + Transfers In − Transfers Out − Closing
    # Transfer lines ensure per-retail P&L is correct; they cancel at consolidated scope.
    cogs = (opening_stock + purchases - purchase_returns
            + transfer_in_total - transfer_out_total - closing_stock)

    # Sales Revenue — read from Sales Account ledger group (INC-DIR-SAL).
    # Credits = sales, Debits = sales returns.  Net = credits − debits.
    try:
        sal_group = Account.objects.get(code='INC-DIR-SAL')
        sal_descendants = get_all_descendants(sal_group)
        sal_ldgrs = Ledger.objects.filter(ac_group__in=[sal_group] + sal_descendants)
        sal_agg = VoucherDetail.objects.filter(
            account__in=sal_ldgrs, **base_filter
        ).aggregate(
            total_credit=Sum('credit', output_field=DecimalField()),
            total_debit=Sum('debit', output_field=DecimalField()),
        )
        sales_credit = sal_agg['total_credit'] or Decimal(0)
        sales_debit = sal_agg['total_debit'] or Decimal(0)
        sales_revenue = sales_credit - sales_debit
        sales_return = sales_debit
    except Account.DoesNotExist:
        sales_revenue = Decimal(0)
        sales_return = Decimal(0)

    # ── Direct Expenses (excluding Purchase Account) ────────────────────────
    try:
        dir_exp_root = Account.objects.get(name='Direct Expenses')
        dir_exp_children = get_all_descendants(dir_exp_root)
        dir_exp_children_filtered = [c for c in [dir_exp_root] + dir_exp_children if c.id not in pur_exclude_ids]
        dir_ldgrs = Ledger.objects.filter(ac_group__in=dir_exp_children_filtered)

        dir_txn = VoucherDetail.objects.filter(
            account__in=dir_ldgrs, **base_filter
        ).aggregate(total=Sum(F('debit') - F('credit')))['total'] or Decimal(0)

        dir_ob_filter = {'ldgr__in': dir_ldgrs}
        if retail_ids:
            dir_ob_filter['retail_id__in'] = retail_ids
        dir_ob = LedgerOpenBalance.objects.filter(**dir_ob_filter).aggregate(
            total=Sum(F('debit') - F('credit'), output_field=DecimalField())
        )['total'] or Decimal(0)

        direct_expenses_total = dir_txn + dir_ob
    except Account.DoesNotExist:
        direct_expenses_total = Decimal(0)

    # Gross Profit = Sales Revenue - COGS - Direct Expenses
    gross_profit = sales_revenue - cogs - direct_expenses_total

    # ── Indirect Expenses ─────────────────────────────────────────────────────
    try:
        ind_exp_root = Account.objects.get(name='Indirect Expenses')
        ind_exp_children = get_all_descendants(ind_exp_root)
        ind_ldgrs = Ledger.objects.filter(ac_group__in=[ind_exp_root] + ind_exp_children)

        ind_txn = VoucherDetail.objects.filter(
            account__in=ind_ldgrs, **base_filter
        ).aggregate(total=Sum(F('debit') - F('credit')))['total'] or Decimal(0)

        ind_ob_filter = {'ldgr__in': ind_ldgrs}
        if retail_ids:
            ind_ob_filter['retail_id__in'] = retail_ids
        ind_ob = LedgerOpenBalance.objects.filter(**ind_ob_filter).aggregate(
            total=Sum(F('debit') - F('credit'), output_field=DecimalField())
        )['total'] or Decimal(0)

        indirect_expenses_total = ind_txn + ind_ob
    except Account.DoesNotExist:
        indirect_expenses_total = Decimal(0)

    total_expenses = direct_expenses_total + indirect_expenses_total
    net_profit = gross_profit - indirect_expenses_total

    return {
        "opening_stock": opening_stock,
        "purchases": purchases,
        "purchase_returns": purchase_returns,
        "transfer_in": transfer_in_total,
        "transfer_out": transfer_out_total,
        "closing_stock": closing_stock,
        "cogs": cogs,
        "gross_sales": sales_revenue + sales_return,
        "sales_return": sales_return,
        "sales_revenue": sales_revenue,
        "direct_expenses_total": direct_expenses_total,
        "gross_profit": gross_profit,
        "indirect_expenses_total": indirect_expenses_total,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "income": get_accounts_tree('Income', retail_ids=retail_ids, start_date=start_date, end_date=end_date),
        # Purchase account tree (EXP-DIR-PUR) — shown interactively in COGS section
        "purchases_tree": get_accounts_tree(pur_group_name, retail_ids=retail_ids, start_date=start_date, end_date=end_date) if pur_group_name else [],
        # Direct Expenses tree excluding Purchase Account (already in COGS)
        "direct_expenses": get_accounts_tree(
            'Direct Expenses', retail_ids=retail_ids,
            start_date=start_date, end_date=end_date,
            exclude_codes=['EXP-DIR-PUR'],
        ),
        # Indirect Expenses tree
        "indirect_expenses": get_accounts_tree(
            'Indirect Expenses', retail_ids=retail_ids,
            start_date=start_date, end_date=end_date,
        ),
    }


class BankbookReportView(APIView):
    def get(self, request, *args, **kwargs):
        from_date_str = request.query_params.get("from_date")
        to_date_str = request.query_params.get("to_date")
        bank_ldgr_id = request.query_params.get("bank_ldgr")

        if not all([from_date_str, to_date_str, bank_ldgr_id]):
            return Response({"error": "Missing required parameters."}, status=status.HTTP_400_BAD_REQUEST)

        from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()

        try:
            bank_ldgr = Ledger.objects.get(pk=bank_ldgr_id)
        except Ledger.DoesNotExist:
            return Response({"error": "Ledger not found."}, status=status.HTTP_404_NOT_FOUND)

        # Opening balance from LedgerOpenBalance for this specific bank ledger
        ledger_opening_balance = LedgerOpenBalance.objects.filter(
            ldgr=bank_ldgr, retail=request.retail
        ).aggregate(
            total=Coalesce(Sum(F('debit') - F('credit'), output_field=DecimalField(max_digits=20, decimal_places=4)), Value(Decimal('0')))
        )['total'] or Decimal('0')

        # Transactions before from_date
        bank_transactions_before = VoucherDetail.objects.filter(
            voucher_main__date__lt=from_date,
            voucher_main__retail=request.retail,
            account=bank_ldgr
        ).aggregate(
            total=Coalesce(Sum(F('debit') - F('credit'), output_field=DecimalField(max_digits=20, decimal_places=4)), Value(Decimal('0')))
        )['total'] or Decimal('0')

        # Final Opening Balance
        opening_balance = ledger_opening_balance + bank_transactions_before

        # Transactions in date range
        transactions = VoucherDetail.objects.filter(
            voucher_main__date__range=(from_date, to_date),
            voucher_main__retail=request.retail,
            account=bank_ldgr
        ).annotate(
            txn_date=F('voucher_main__date'),
            txn_voucher_no=F('voucher_main__voucher_no'),  # renamed to avoid conflict
            txn_voucher_type=F('voucher_main__voucher_type'),  # renamed to avoid conflict
            ledger=F('account__ac_name'),
            debit_val=Case(
                When(debit__gt=0, then=F('debit')),
                default=Value(0),
                output_field=DecimalField()
            ),
            credit_val=Case(
                When(credit__gt=0, then=F('credit')),
                default=Value(0),
                output_field=DecimalField()
            ),
            narration=F('voucher_main__narration')
        ).values(
            'txn_date', 'txn_voucher_no', 'txn_voucher_type', 'ledger',
            'chq_no', 'debit_val', 'credit_val', 'narration'
        ).order_by('txn_date')

        txn_list = list(transactions)

        totals = VoucherDetail.objects.filter(
            voucher_main__date__range=(from_date, to_date),
            voucher_main__retail=request.retail,
            account=bank_ldgr
        ).aggregate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit'),
        )
        total_debit = totals['total_debit'] or Decimal(0)
        total_credit = totals['total_credit'] or Decimal(0)
        closing_balance = opening_balance + total_debit - total_credit

        return Response({
            "opening_balance": opening_balance,
            "transactions": txn_list,
            "closing_balance": closing_balance
        }, status=status.HTTP_200_OK)

class TrialBalanceReportView(APIView):
    def get(self, request: Request):
        try:
            retail = _get_retail_for_report(request)
            if retail == 'FORBIDDEN':
                return Response({"error": "You do not have permission to view combined reports."},
                                status=status.HTTP_403_FORBIDDEN)

            from_date = request.query_params.get("from_date")
            to_date = request.query_params.get("to_date")

            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()

            # Determine which fiscal year contains from_date so we can use its stored OB
            # and only scan transactions within that FY (not all history).
            from mastersconfig.models import FiscalYearMaster
            fy_filter = dict(fy_start__lte=from_date_obj, fy_end__gte=from_date_obj)
            if retail:
                fy_filter['retail'] = retail
            fy = FiscalYearMaster.objects.filter(**fy_filter).first()

            # Batch query 1: Opening balances for the relevant fiscal year
            ob_filter = {}
            if retail:
                ob_filter['retail'] = retail
            if fy:
                ob_filter['acc_year'] = fy.fy_code
            _D = lambda v: Decimal(str(v)) if v is not None else Decimal('0')

            ob_raw = LedgerOpenBalance.objects.filter(**ob_filter).values('ldgr').annotate(
                total_debit=Sum("debit", default=0),
                total_credit=Sum("credit", default=0)
            )
            ob_dict = {row['ldgr']: (_D(row['total_debit']), _D(row['total_credit'])) for row in ob_raw}

            # Batch query 2: Transactions within the FY before from_date (not all history)
            before_filter = dict(voucher_main__date__lt=from_date_obj)
            if retail:
                before_filter['voucher_main__retail'] = retail
            if fy:
                before_filter['voucher_main__date__gte'] = fy.fy_start
            before_raw = VoucherDetail.objects.filter(**before_filter).values('account').annotate(
                total=Sum(F('debit') - F('credit'))
            )
            before_dict = {row['account']: _D(row['total']) for row in before_raw}

            # Batch query 3: All transactions in date range grouped by account
            in_range_filter = dict(voucher_main__date__range=(from_date, to_date))
            if retail:
                in_range_filter['voucher_main__retail'] = retail
            in_range_raw = VoucherDetail.objects.filter(**in_range_filter).values('account').annotate(
                total_debit=Sum("debit", default=0),
                total_credit=Sum("credit", default=0)
            )
            in_range_dict = {row['account']: (_D(row['total_debit']), _D(row['total_credit'])) for row in in_range_raw}

            # Batch query 4: All ledgers and all account groups.
            # Do NOT filter by retail_code — system ledgers (Sales, Purchase, GST, etc.)
            # have retail_code=NULL and are shared across all retails. Transaction data
            # is already scoped to the selected retail via voucher_main__retail above.
            all_ledgers = Ledger.objects.select_related('ac_group').all()
            all_groups = {g.id: g for g in Account.objects.all()}
            # Pre-compute children_by_parent so _build_group_node does an
            # O(1) dict lookup instead of scanning all_groups on every call.
            # Previously this was O(N²) in the number of account groups.
            children_by_parent = {}
            for _g in all_groups.values():
                children_by_parent.setdefault(_g.parent_id, []).append(_g)

            # Map group_id → list of ledgers
            group_ledgers_map = {}
            for ledger in all_ledgers:
                gid = ledger.ac_group_id
                if gid not in group_ledgers_map:
                    group_ledgers_map[gid] = []
                group_ledgers_map[gid].append(ledger)

            def _build_group_node(group):
                """Recursively build a group node with ledgers and child groups."""
                ledger_rows = []
                for ledger in group_ledgers_map.get(group.id, []):
                    ob_debit, ob_credit = ob_dict.get(ledger.id, (0, 0))
                    before_total = before_dict.get(ledger.id, 0)
                    ir_debit, ir_credit = in_range_dict.get(ledger.id, (0, 0))
                    opening_balance_amount = (ob_debit - ob_credit) + before_total
                    closing_balance = opening_balance_amount + ir_debit - ir_credit
                    if not any([opening_balance_amount, ir_debit, ir_credit, closing_balance]):
                        continue
                    ledger_rows.append({
                        "ledger_id": ledger.id,
                        "ledger_name": ledger.ac_name,
                        "opening_balance": opening_balance_amount,
                        "total_debit": ir_debit,
                        "total_credit": ir_credit,
                        "closing_balance": closing_balance,
                    })

                children = []
                for child_group in children_by_parent.get(group.id, []):
                    child_node = _build_group_node(child_group)
                    if child_node:
                        children.append(child_node)

                if not ledger_rows and not children:
                    return None

                return {
                    "group_name": group.name,
                    "ledgers": ledger_rows,
                    "children": children,
                }

            # Only top-level groups (no parent) form the root of the tree
            report_data = []
            for group in children_by_parent.get(None, []):
                node = _build_group_node(group)
                if node:
                    report_data.append(node)

            return Response({"from_date": from_date, "to_date": to_date, "trial_balance": report_data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _to_gold_grams(amount, rate):
    """Convert a rupee amount to fine-gold grams. Returns None if no rate."""
    if rate is None or amount is None:
        return None
    try:
        return Decimal(str(amount)) / rate
    except (InvalidOperation, ZeroDivisionError):
        return None


def _attach_gold_grams(payload, rate):
    """Walk the BS payload and attach `gold_grams` to every monetary node."""
    side_keys = ("assets", "liabilities")
    for key in side_keys:
        side = payload.get(key)
        if not isinstance(side, dict):
            continue
        side["gold_grams"] = _to_gold_grams(side.get("total"), rate)
        for grp in side.get("groups", []) or []:
            grp["gold_grams"] = _to_gold_grams(grp.get("total"), rate)
            for acc in grp.get("accounts", []) or []:
                acc["gold_grams"] = _to_gold_grams(acc.get("balance"), rate)
    if "net_worth" in payload:
        payload["net_worth_gold_grams"] = _to_gold_grams(payload["net_worth"], rate)


class FineGoldRateBreakdownView(APIView):
    """Expose the per-source rows that feed the fine-gold rate.

    Used by the frontend to let the user audit how the weighted-average rate
    was derived: which purchase lines, which opening-stock rows, which transfers
    contributed how many fine grams and how many rupees.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        retail_ids = _get_retail_ids_for_report(request)
        if retail_ids == 'FORBIDDEN':
            return Response({"error": "You do not have permission to view combined reports."},
                            status=status.HTTP_403_FORBIDDEN)
        end_date = request.query_params.get("end_date", str(date.today()))
        data = FineGoldRateService(retail_ids, end_date).breakdown()
        return Response(data, status=status.HTTP_200_OK)


class BalanceSheetAPIView(APIView):
    def get(self, request: Response):
        retail_ids = _get_retail_ids_for_report(request)
        if retail_ids == 'FORBIDDEN':
            return Response({"error": "You do not have permission to view combined reports."},
                            status=status.HTTP_403_FORBIDDEN)

        end_date = request.query_params.get("end_date", date.today())

        # Aggregate transaction balances grouped by ledger's account group
        txn_filter = dict(voucher_main__date__lte=end_date)
        if retail_ids:
            txn_filter['voucher_main__retail_id__in'] = retail_ids
        txn_by_group = {}
        for row in VoucherDetail.objects.filter(**txn_filter).values(
            'account__ac_group'
        ).annotate(
            balance=Sum(F('debit')) - Sum(F('credit'))
        ):
            gid = row['account__ac_group']
            if gid is not None:
                txn_by_group[gid] = row['balance'] or Decimal(0)

        # Aggregate opening balances grouped by ledger's account group
        ob_filter = {}
        if retail_ids:
            ob_filter['retail_id__in'] = retail_ids
        ob_by_group = {}
        for row in LedgerOpenBalance.objects.filter(**ob_filter).values(
            'ldgr__ac_group'
        ).annotate(
            balance=Sum(F('debit') - F('credit'), output_field=DecimalField())
        ):
            gid = row['ldgr__ac_group']
            if gid is not None:
                ob_by_group[gid] = row['balance'] or Decimal(0)

        # Load all accounts in one query and build parent-child map
        all_accounts = list(Account.objects.all())
        children_map = {}
        account_by_id = {}
        for acc in all_accounts:
            account_by_id[acc.id] = acc
            pid = acc.parent_id
            if pid not in children_map:
                children_map[pid] = []
            children_map[pid].append(acc)

        def get_descendants(parent_id):
            result = []
            for child in children_map.get(parent_id, []):
                result.append(child)
                result.extend(get_descendants(child.id))
            return result

        def get_balance(account):
            """Get the combined txn + opening balance for an account group."""
            return txn_by_group.get(account.id, Decimal(0)) + ob_by_group.get(account.id, Decimal(0))

        def get_group_balance(group_name):
            """Return the group broken down into its immediate subgroups.

            Each subgroup (e.g. "Current Assets" under "Assets") gets a nested
            block with its own total and the list of descendant accounts that
            carry balances. This preserves the chart-of-accounts hierarchy on
            the report instead of flattening every leaf directly under Assets /
            Liabilities.
            """
            try:
                parent = next(a for a in all_accounts if a.name == group_name)
            except StopIteration:
                return {"total": Decimal(0), "groups": []}

            subgroups = []
            total = Decimal(0)
            for sub in children_map.get(parent.id, []):
                descendants = get_descendants(sub.id)
                sub_accounts = []
                sub_total = Decimal(0)
                # Include the subgroup's own direct balance (rare: most subgroups
                # are pure headers with no ledgers pointing directly at them).
                own_bal = get_balance(sub)
                sub_total += own_bal
                if own_bal:
                    sub_accounts.append({"id": sub.id, "name": sub.name, "balance": own_bal})
                for acc in descendants:
                    bal = get_balance(acc)
                    if bal:
                        sub_accounts.append({"id": acc.id, "name": acc.name, "balance": bal})
                    sub_total += bal
                subgroups.append({
                    "id": sub.id,
                    "name": sub.name,
                    "total": sub_total,
                    "accounts": sub_accounts,
                })
                total += sub_total
            return {"total": total, "groups": subgroups}

        def _ensure_subgroup(side, name):
            """Find or synthesise a subgroup bucket on the given side."""
            for g in side["groups"]:
                if g["name"] == name:
                    return g
            bucket = {"id": f"synthetic_{name.lower().replace(' ', '_')}",
                      "name": name, "total": Decimal(0), "accounts": []}
            side["groups"].append(bucket)
            return bucket

        assets = get_group_balance("Assets")
        liabilities = get_group_balance("Liabilities")

        # Capital Account (Owner's Capital, Reserves & Surplus) is a root group
        # separate from Liabilities in the chart of accounts, but belongs on the
        # right-hand side of the balance sheet (equity = owner's stake). Fold
        # its subgroups into liabilities so the right side shows a single tree.
        capital = get_group_balance("Capital Account")
        liabilities["total"] += capital["total"]
        liabilities["groups"].extend(capital["groups"])

        # ── Closing stock (one call, reused for both assets and P&L) ────────────
        closing_stock_value = Decimal(0)
        try:
            raw_cs = ClosingStockCal().calculate_closing_stock(
                from_date="2000-01-01", to_date=str(end_date), retail_ids=retail_ids
            )
            closing_stock_value = Decimal(str(raw_cs.get('total_value') or 0))
            if closing_stock_value:
                assets["total"] += closing_stock_value
                stock_bucket = _ensure_subgroup(assets, "Stock-in-Hand")
                stock_bucket["total"] += closing_stock_value
                stock_bucket["accounts"].append({
                    "id": "closing_stock",
                    "name": "Closing Stock",
                    "balance": closing_stock_value,
                })
        except Exception:
            pass

        # ── Opening stock from physical inventory ─────────────────────────────
        opening_stock = calculate_opening_stock(retail_ids=retail_ids)

        # ── Net profit: reuse already-fetched group data (zero extra queries) ─
        # income["total"] is negative (credit-normal Dr-Cr convention)
        # expenses["total"] is positive (debit-normal Dr-Cr convention)
        # Adjust for inventory: +closing_stock (asset, not journaled) −opening_stock
        income_total   = get_group_balance("Income")["total"]
        expenses_total = get_group_balance("Expenses")["total"]
        net_profit = -income_total - expenses_total + closing_stock_value - opening_stock

        liabilities["total"] -= net_profit
        reserves_bucket = _ensure_subgroup(liabilities, "Reserves & Surplus")
        reserves_bucket["total"] -= net_profit
        reserves_bucket["accounts"].append({
            "id": "net_profit",
            "name": "Net Profit / Loss",
            "balance": -net_profit  # negative = credit side = equity
        })

        # net_worth = assets + liabilities:
        #   assets["total"]      is positive  (debit-normal accounts)
        #   liabilities["total"] is negative  (credit-normal accounts stored as Dr-Cr)
        # A perfectly balanced set of books gives net_worth = 0.
        data = {
            "assets": assets,
            "liabilities": liabilities,
            "net_worth": assets["total"] + liabilities["total"]
        }

        unit = (request.query_params.get("unit") or "inr").lower()
        if unit == "gold":
            rate = FineGoldRateService(retail_ids, end_date).compute()
            data["unit"] = "gold"
            data["fine_gold_rate"] = rate
            _attach_gold_grams(data, rate)
        else:
            data["unit"] = "inr"

        return Response(data, status=status.HTTP_200_OK)

class BsGroupLedgersView(APIView):
    """Ledger-level drill-down for the Balance Sheet.

    Returns each ledger's cumulative closing balance (opening + all transactions
    up to end_date) using the same debit-minus-credit convention as the main
    balance sheet view: positive = debit balance, negative = credit balance.
    """

    def get(self, request):
        retail = _get_retail_for_report(request)
        if retail == 'FORBIDDEN':
            return Response({"error": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        group_id = request.query_params.get("group_id")
        end_date  = request.query_params.get("end_date", str(date.today()))

        if not group_id:
            return Response({"error": "group_id is required."}, status=400)

        try:
            group = Account.objects.get(pk=group_id)
        except Account.DoesNotExist:
            return Response({"ledgers": [], "group_name": ""})

        all_groups = [group] + get_all_descendants(group)
        ledgers    = Ledger.objects.filter(ac_group__in=all_groups)

        # Transactions up to end_date (debit - credit)
        txn_filter = {'account__in': ledgers, 'voucher_main__date__lte': end_date}
        if retail:
            txn_filter['voucher_main__retail'] = retail
        txn_map = {
            row['account_id']: row['net'] or Decimal(0)
            for row in VoucherDetail.objects.filter(**txn_filter)
            .values('account_id')
            .annotate(net=Sum(F('debit') - F('credit'), output_field=DecimalField()))
        }

        # Opening balances (debit - credit)
        ob_filter = {'ldgr__in': ledgers}
        if retail:
            ob_filter['retail'] = retail
        ob_map = {
            row['ldgr_id']: row['net'] or Decimal(0)
            for row in LedgerOpenBalance.objects.filter(**ob_filter)
            .values('ldgr_id')
            .annotate(net=Sum(F('debit') - F('credit'), output_field=DecimalField()))
        }

        result = []
        for ldgr in ledgers.order_by('ac_name'):
            balance = txn_map.get(ldgr.id, Decimal(0)) + ob_map.get(ldgr.id, Decimal(0))
            if balance:
                result.append({'id': ldgr.id, 'ac_name': ldgr.ac_name, 'balance': balance})

        unit = (request.query_params.get("unit") or "inr").lower()
        response = {'group_name': group.name, 'ledgers': result}
        if unit == "gold":
            retail_ids = [retail.id] if retail else None
            rate = FineGoldRateService(retail_ids, end_date).compute()
            response["unit"] = "gold"
            response["fine_gold_rate"] = rate
            for row in result:
                row["gold_grams"] = _to_gold_grams(row["balance"], rate)
        else:
            response["unit"] = "inr"
        return Response(response)


class ProfitLossAPIView(APIView):

    def get(self, request):
        retail_ids = _get_retail_ids_for_report(request)
        if retail_ids == 'FORBIDDEN':
            return Response({"error": "You do not have permission to view combined reports."},
                            status=status.HTTP_403_FORBIDDEN)

        start_date = request.GET.get("start_date", "2000-01-01")
        end_date = request.GET.get("end_date", date.today())

        data = calcuate_pnl(start_date=start_date, end_date=end_date, retail_ids=retail_ids)

        return Response(data, status=status.HTTP_200_OK)


def get_accounts_tree(root=None, retail=None, start_date=None, end_date=None, exclude_codes=None, retail_ids=None):
    """Fetch Chart of Accounts as a nested tree — optimized with batch queries.

    Args:
        root: Name of the root account group (e.g. 'Expenses', 'Income').
        retail: RetailMaster instance to filter by; None = all retails.
        start_date / end_date: Date range for VoucherDetail transactions.
            Opening balances are always included regardless of date range.
        exclude_codes: List of Account.code strings whose sub-trees are omitted
            from both the rendered tree and the balance totals (e.g. ['EXP-DIR-PUR']).
    """
    all_accounts = list(Account.objects.all())
    root_account = next((a for a in all_accounts if a.name == root), None)
    if not root_account:
        return []

    # Compute IDs to exclude (the account and all its descendants)
    exclude_ids: set = set()
    if exclude_codes:
        code_map = {a.code: a for a in all_accounts}
        for code in exclude_codes:
            if code in code_map:
                excl_root = code_map[code]
                exclude_ids.add(excl_root.id)
                exclude_ids.update(a.id for a in get_all_descendants(excl_root))

    # Build parent-child map in memory
    children_map: dict = {}
    for acc in all_accounts:
        pid = acc.parent_id
        if pid not in children_map:
            children_map[pid] = []
        children_map[pid].append(acc)

    # Normalise retail scope — retail_ids (list) wins over legacy single retail.
    if retail_ids is None and retail is not None:
        retail_ids = [retail.id if hasattr(retail, 'id') else retail]

    # Batch query: net balances (debit - credit) grouped by ac_group, date-filtered
    txn_filter = {}
    if retail_ids:
        txn_filter['voucher_main__retail_id__in'] = retail_ids
    if start_date and end_date:
        txn_filter['voucher_main__date__range'] = [start_date, end_date]
    balance_raw = VoucherDetail.objects.filter(**txn_filter).values('account__ac_group').annotate(
        total_balance=Sum(F('debit') - F('credit'))
    )
    balance_dict = {row['account__ac_group']: row['total_balance'] or Decimal(0) for row in balance_raw}

    # Add opening balances grouped by ac_group (always included — period-independent)
    ob_filter = {}
    if retail_ids:
        ob_filter['retail_id__in'] = retail_ids
    ob_raw = LedgerOpenBalance.objects.filter(**ob_filter).values('ldgr__ac_group').annotate(
        total_balance=Sum(F('debit') - F('credit'), output_field=DecimalField())
    )
    for row in ob_raw:
        gid = row['ldgr__ac_group']
        if gid is not None:
            balance_dict[gid] = balance_dict.get(gid, Decimal(0)) + (row['total_balance'] or Decimal(0))

    def _build_tree(parent_id):
        tree = []
        for account in children_map.get(parent_id, []):
            if account.id in exclude_ids:
                continue
            tree.append({
                "id": account.id,
                "name": account.name,
                "balance": balance_dict.get(account.id, Decimal(0)),
                "children": _build_tree(account.id)
            })
        return tree

    return _build_tree(root_account.id)


class DueAdvanceReportView(APIView):
    def post(self, request):
        karigar = request.data.get("karigar", [])
        doc_type = request.data.get("doc_type", "due")
        retail = getattr(request, 'retail', None)
        # Filter ledger accounts for the selected karigars
        ledger_accounts = Ledger.objects.filter(ldgr_code__in=karigar)
        # Compute opening balances — use correct field names: ldgr (FK), retail
        ob_filter = {'ldgr__in': ledger_accounts}
        if retail:
            ob_filter['retail'] = retail
        opening_balances = LedgerOpenBalance.objects.filter(**ob_filter).values(
            "ldgr"
        ).annotate(
            net_dbt_opbal=Sum(F("debit") - F("credit"), output_field=DecimalField()),
            net_crdt_opbal=Sum(F("credit") - F("debit"), output_field=DecimalField()),
        )
        # Compute voucher transactions — use correct field names: account (FK), debit, credit
        vt_filter = {'account__in': ledger_accounts}
        if retail:
            vt_filter['voucher_main__retail'] = retail
        voucher_transactions = VoucherDetail.objects.filter(**vt_filter).values(
            "account"
        ).annotate(
            net_dbt=Sum(F("debit") - F("credit"), output_field=DecimalField()),
            net_crdt=Sum(F("credit") - F("debit"), output_field=DecimalField()),
        )
        # Merge data
        report_data = []
        for ledger in ledger_accounts:
            lob = next((b for b in opening_balances if b["ldgr"] == ledger.id), {})
            vt = next((t for t in voucher_transactions if t["account"] == ledger.id), {})
            net_dbt_opbal = lob.get("net_dbt_opbal", 0)
            net_crdt_opbal = lob.get("net_crdt_opbal", 0)
            net_dbt = vt.get("net_dbt", 0)
            net_crdt = vt.get("net_crdt", 0)
            if doc_type == "due":
                balance = max(net_dbt_opbal + net_dbt - net_crdt - net_crdt_opbal, 0)
            else:
                balance = max(net_crdt_opbal + net_crdt - net_dbt - net_dbt_opbal, 0)
            if balance > 0:
                report_data.append({
                    "ldgr": ledger.ldgr_code,
                    "ac_name": ledger.ac_name,
                    "net_dbt_opbal": net_dbt_opbal,
                    "net_crdt_opbal": net_crdt_opbal,
                    "net_dbt": net_dbt,
                    "net_crdt": net_crdt,
                    "balance": balance
                })
        serializer = DueAdvanceReportSerializer(report_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CashbookReportView(APIView):
    def get(self, request, *args, **kwargs):

        from_date_str = request.query_params.get("from_date")
        to_date_str = request.query_params.get("to_date")



        from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()

        opening_balance = Decimal('0')

        # Use retail's configured cash ledger
        cash_ledger = request.retail.cash_ldgr
        if not cash_ledger:
            return Response({"error": "Cash ledger not configured for this retail."}, status=status.HTTP_400_BAD_REQUEST)

        ledger_opening_balance = LedgerOpenBalance.objects.filter(
            ldgr=cash_ledger, retail=request.retail
        ).aggregate(total=Sum('debit'))['total'] or 0
        opening_balance += ledger_opening_balance

        cash_transactions_before_from_date = VoucherDetail.objects.filter(
            voucher_main__date__lt=from_date,
            voucher_main__retail=request.retail,
            account=cash_ledger
        ).aggregate(total=Sum(F('debit')-F('credit')))['total'] or 0

        opening_balance += cash_transactions_before_from_date

        transactions_queryset = VoucherDetail.objects.filter(
            voucher_main__date__range=(from_date, to_date),
            voucher_main__retail=request.retail,
            account=cash_ledger
        ).select_related("voucher_main", "account").order_by("voucher_main__date").annotate(
            # Annotate the display debit and credit based on your logic
            # Assuming 'debit' is stored as positive for debits, and 'credit' might be negative for credits
            # or it's simply the credit amount. Adjust 'Abs(F('credit'))' if 'credit' is always positive.
            display_debit=ExpressionWrapper(
                Coalesce(F('debit'), 0),
                output_field=DecimalField()
            ),
            display_credit=ExpressionWrapper(
                Coalesce(Abs(F('credit')), 0), # Use Abs if credit is stored as negative for credit entries
                output_field=DecimalField()
            )
        ).values(
            "voucher_main__date",
            "voucher_main__voucher_no",
            "voucher_main__voucher_type",

            "account__ac_name",
            "display_debit",
            "display_credit",
            "voucher_main__narration"
        )

        totals = transactions_queryset.aggregate(
            total_debit=Sum('display_debit'),
            total_credit=Sum('display_credit')
        )
        total_debit = totals['total_debit'] or 0
        total_credit = totals['total_credit'] or 0

        # Convert the QuerySet of dictionaries to a list of dictionaries
        transaction_data = list(transactions_queryset)
        response_data = {
        "opening_balance": opening_balance,
        "transactions": transaction_data,
        "closing_balance": opening_balance + total_debit - total_credit
        }

        return Response(response_data, status=status.HTTP_200_OK)


class PurchaseVoucherView(ListAPIView):
    serializer_class = PurchaseVoucherSerializer

    def get_queryset(self):
        ldgr_id = self.request.query_params.get("ldgr_id")

        return self.serializer_class.Meta.model.objects.filter(retail =self.request.retail ,ldgr_id=ldgr_id, due_amt__gt=0)


class SaleVoucherView(ListAPIView):
    serializer_class = SalesVouSerializer

    def get_queryset(self):
        ldgr_id = self.request.query_params.get("ldgr_id")
        return self.serializer_class.Meta.model.objects.filter(retail =self.request.retail ,ldgr=ldgr_id, due_amt__gt=0)


class DayBookView(APIView):
    """Sectioned day book: bills + voucher summaries grouped by type."""

    def get(self, request):
        from_date_str = request.query_params.get("from_date")
        to_date_str = request.query_params.get("to_date")

        if not all([from_date_str, to_date_str]):
            return Response({"error": "from_date and to_date are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
        retail = request.retail

        from sales.models import SaleReturn, SalesApproval
        from purchase.models import PurchaseReturn

        def _dec(v):
            try:
                return Decimal(str(v or 0))
            except (InvalidOperation, TypeError):
                return Decimal('0')

        # ---- Bills: Sale / Purchase / Sale Return / Purchase Return ----
        def bills_section(qs, party_attr, billno_attr, dis_attr, amount_attr):
            rows, total = [], Decimal('0')
            for obj in qs:
                party = getattr(obj, party_attr, None)
                party_name = party.ac_name if party else ''
                amt = _dec(getattr(obj, amount_attr))
                dis = _dec(getattr(obj, dis_attr, 0))
                rows.append({
                    "party": party_name,
                    "billno": getattr(obj, billno_attr) or '',
                    "dis": dis,
                    "amount": amt,
                })
                total += amt
            return {"rows": rows, "grand_total": total}

        sale_qs = SalesVou.objects.filter(
            retail=retail, date1__range=(from_date, to_date)
        ).select_related('ldgr').order_by('date1', 'billno')

        purchase_qs = PurchaseVoucher.objects.filter(
            retail=retail, date1__range=(from_date, to_date), voucher_type='Vendor'
        ).select_related('ldgr').order_by('date1', 'billno')

        sale_return_qs = SaleReturn.objects.filter(
            retail=retail, date1__range=(from_date, to_date)
        ).select_related('ldgr').order_by('date1', 'billno')

        purchase_return_qs = PurchaseReturn.objects.filter(
            retail=retail, date1__range=(from_date, to_date)
        ).select_related('ldgr').order_by('date1', 'billno')

        sale_section = {"rows": [], "grand_total": Decimal('0')}
        for sv in sale_qs:
            amt = _dec(sv.total_bill_value)
            sale_section["rows"].append({
                "party": sv.ldgr.ac_name if sv.ldgr else '',
                "billno": sv.billno or '',
                "dis": _dec(getattr(sv, 'discount', 0)),
                "amount": amt,
            })
            sale_section["grand_total"] += amt

        purchase_section = bills_section(
            purchase_qs, 'ldgr', 'billno', 'discount_amt', 'bill_value'
        )

        sale_return_section = {"rows": [], "grand_total": Decimal('0')}
        for sr in sale_return_qs:
            amt = _dec(sr.total_bill_value)
            sale_return_section["rows"].append({
                "party": sr.ldgr.ac_name if sr.ldgr else '',
                "billno": sr.billno or '',
                "dis": _dec(getattr(sr, 'discount', 0)),
                "amount": amt,
            })
            sale_return_section["grand_total"] += amt

        purchase_return_section = bills_section(
            purchase_return_qs, 'ldgr', 'billno', 'discount', 'bill_value'
        )

        # ---- Voucher summaries: PMNT / RCPT(+RCPT-SALE) / CNTR / JRNL ----
        vm_qs = VoucherMain.objects.filter(
            retail=retail, date__range=(from_date, to_date)
        ).prefetch_related('transactions__account').order_by('date', 'voucher_no')

        def counter_party(voucher, side):
            """side='debit' → pick line with max debit; 'credit' → max credit."""
            best, best_val = None, Decimal('-1')
            for t in voucher.transactions.all():
                val = _dec(t.debit if side == 'debit' else t.credit)
                if val > best_val:
                    best, best_val = t, val
            return best.account.ac_name if (best and best.account) else ''

        def both_sides(voucher):
            dr = counter_party(voucher, 'debit')
            cr = counter_party(voucher, 'credit')
            return f"{dr} → {cr}" if (dr or cr) else ''

        def voucher_section(vouchers, party_fn):
            rows, total = [], Decimal('0')
            for v in vouchers:
                amt = _dec(v.amount)
                rows.append({
                    "party": party_fn(v),
                    "voucher_no": v.voucher_no,
                    "narration": v.narration or '',
                    "amount": amt,
                })
                total += amt
            return {"rows": rows, "grand_total": total}

        pmnt_v = [v for v in vm_qs if v.voucher_type == VoucherType.pmnt]
        rcpt_v = [v for v in vm_qs if v.voucher_type in (VoucherType.rcpt, VoucherType.rcpt_sale)]
        cntr_v = [v for v in vm_qs if v.voucher_type == VoucherType.cntr]
        jrnl_v = [v for v in vm_qs if v.voucher_type == VoucherType.journal]

        payment_section = voucher_section(pmnt_v, lambda v: counter_party(v, 'debit'))
        receipt_section = voucher_section(rcpt_v, lambda v: counter_party(v, 'credit'))
        contra_section = voucher_section(cntr_v, both_sides)
        journal_section = voucher_section(
            jrnl_v, lambda v: counter_party(v, 'debit')
        )

        # ---- Sale Approvals ----
        approvals_qs = SalesApproval.objects.filter(
            retail=retail, date1__range=(from_date, to_date)
        ).select_related('ldgr').order_by('date1', 'billno')

        sale_approvals = {"rows": [], "grand_total": Decimal('0')}
        for ap in approvals_qs:
            amt = _dec(ap.total_bill_value)
            sale_approvals["rows"].append({
                "party": ap.ldgr.ac_name if ap.ldgr else '',
                "billno": ap.billno or '',
                "amount": amt,
            })
            sale_approvals["grand_total"] += amt

        return Response({
            "from_date": from_date,
            "to_date": to_date,
            "sale": sale_section,
            "purchase": purchase_section,
            "sale_return": sale_return_section,
            "purchase_return": purchase_return_section,
            "payment": payment_section,
            "receipt": receipt_section,
            "contra": contra_section,
            "journal": journal_section,
            "sale_approvals": sale_approvals,
        }, status=status.HTTP_200_OK)


class PnlDrilldownView(APIView):
    """Return the voucher-level detail behind a P&L line item."""

    def get(self, request):
        retail = _get_retail_for_report(request)
        if retail == 'FORBIDDEN':
            return Response({"error": "You do not have permission to view combined reports."},
                            status=status.HTTP_403_FORBIDDEN)

        metric = request.query_params.get("metric")          # sales, purchases, purchase_returns, expenses
        start_date = request.query_params.get("start_date", "2000-01-01")
        end_date = request.query_params.get("end_date", str(date.today()))
        account_group_id = request.query_params.get("account_group_id")  # for expense sub-groups

        base_filter = {
            'voucher_main__date__range': [start_date, end_date],
        }
        retail_filter = {}
        if retail:
            base_filter['voucher_main__retail'] = retail
            retail_filter['retail'] = retail

        if metric == "sales":
            base_filter['voucher_main__voucher_type'] = VoucherType.sale
            qs = VoucherDetail.objects.filter(**base_filter).select_related(
                'voucher_main', 'account'
            ).order_by('voucher_main__date')

            # Group by voucher (bill) — sum debits per voucher = bill total
            from django.db.models import Min
            vm_filter = dict(
                voucher_type=VoucherType.sale,
                date__range=[start_date, end_date],
                **retail_filter,
            )
            rows = VoucherMain.objects.filter(**vm_filter).annotate(
                total=Sum('transactions__debit'),
                party=Min('transactions__account__ac_name'),
            ).order_by('-date').values('voucher_no', 'date', 'narration', 'total', 'party')

            return Response({"metric": "Sales Revenue", "vouchers": list(rows)})

        elif metric == "purchases":
            vm_filter = dict(
                voucher_type=VoucherType.purc_sc,
                date__range=[start_date, end_date],
                **retail_filter,
            )
            rows = VoucherMain.objects.filter(**vm_filter).annotate(
                total=Sum('transactions__debit'),
                party=Min('transactions__account__ac_name'),
            ).order_by('-date').values('voucher_no', 'date', 'narration', 'total', 'party')

            return Response({"metric": "Purchases", "vouchers": list(rows)})

        elif metric == "purchase_returns":
            rows = VoucherMain.objects.filter(
                voucher_type=VoucherType.purc_ret,
                date__range=[start_date, end_date],
                **retail_filter,
            ).annotate(
                total=Sum('transactions__credit'),
                party=Min('transactions__account__ac_name'),
            ).order_by('-date').values('voucher_no', 'date', 'narration', 'total', 'party')

            return Response({"metric": "Purchase Returns", "vouchers": list(rows)})

        elif metric == "expenses":
            children = get_all_descendants(Account.objects.get(name="Expenses"))
            ldgrs = Ledger.objects.filter(ac_group__in=children)

            if account_group_id:
                try:
                    specific_group = Account.objects.get(pk=account_group_id)
                    sub_descendants = [specific_group] + get_all_descendants(specific_group)
                    ldgrs = ldgrs.filter(ac_group__in=sub_descendants)
                except Account.DoesNotExist:
                    pass

            rows = VoucherDetail.objects.filter(
                account__in=ldgrs,
                **base_filter
            ).select_related('voucher_main', 'account').order_by(
                'voucher_main__date'
            ).values(
                'voucher_main__voucher_no', 'voucher_main__date',
                'voucher_main__narration', 'account__ac_name',
                'debit', 'credit'
            )

            return Response({"metric": "Expenses", "vouchers": list(rows)})

        return Response({"error": "Invalid metric. Use: sales, purchases, purchase_returns, expenses"}, status=status.HTTP_400_BAD_REQUEST)


class PnlGroupLedgersView(APIView):
    """Return ledger-level balances for a given account group within a date range."""

    def get(self, request):
        retail = _get_retail_for_report(request)
        if retail == 'FORBIDDEN':
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        group_id = request.query_params.get("group_id")
        start_date = request.query_params.get("start_date", "2000-01-01")
        end_date = request.query_params.get("end_date", str(date.today()))

        if not group_id:
            return Response({"error": "group_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            group = Account.objects.get(pk=group_id)
        except Account.DoesNotExist:
            return Response({"error": "Account group not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get all descendant groups (including this one) to find all ledgers
        descendants = [group] + get_all_descendants(group)
        desc_ids = [a.id for a in descendants]

        ledgers = Ledger.objects.filter(ac_group_id__in=desc_ids)
        # Do NOT filter ledgers by retail here — ledgers are company-wide and may
        # not have a retail assigned even though they carry transactions for a
        # specific retail (e.g. making charge ledgers).  Retail scoping is applied
        # on the transaction side below, consistent with the main P&L calculation.

        # Transaction balances within date range
        txn_filter = {
            'account__in': ledgers,
            'voucher_main__date__range': [start_date, end_date],
        }
        if retail:
            txn_filter['voucher_main__retail'] = retail

        txn_balances = VoucherDetail.objects.filter(**txn_filter).values('account').annotate(
            balance=Sum(F('debit') - F('credit'))
        )
        txn_dict = {r['account']: r['balance'] or Decimal(0) for r in txn_balances}

        # Opening balances
        ob_filter = {'ldgr__in': ledgers}
        if retail:
            ob_filter['retail'] = retail
        ob_balances = LedgerOpenBalance.objects.filter(**ob_filter).values('ldgr').annotate(
            balance=Sum(F('debit') - F('credit'), output_field=DecimalField())
        )
        ob_dict = {r['ldgr']: r['balance'] or Decimal(0) for r in ob_balances}

        result = []
        for ldgr in ledgers:
            bal = txn_dict.get(ldgr.id, Decimal(0)) + ob_dict.get(ldgr.id, Decimal(0))
            if bal != 0:
                result.append({
                    "id": ldgr.id,
                    "ac_name": ldgr.ac_name,
                    "balance": str(bal),
                })

        result.sort(key=lambda x: abs(Decimal(x['balance'])), reverse=True)
        return Response({"group": group.name, "ledgers": result})


class PnlLedgerTransactionsView(APIView):
    """Return transactions for a specific ledger within a date range."""

    def get(self, request):
        retail = _get_retail_for_report(request)
        if retail == 'FORBIDDEN':
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        ledger_id = request.query_params.get("ledger_id")
        start_date = request.query_params.get("start_date", "2000-01-01")
        end_date = request.query_params.get("end_date", str(date.today()))

        if not ledger_id:
            return Response({"error": "ledger_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ledger = Ledger.objects.get(pk=ledger_id)
        except Ledger.DoesNotExist:
            return Response({"error": "Ledger not found"}, status=status.HTTP_404_NOT_FOUND)

        txn_filter = {
            'account': ledger,
            'voucher_main__date__range': [start_date, end_date],
        }
        if retail:
            txn_filter['voucher_main__retail'] = retail

        rows = VoucherDetail.objects.filter(**txn_filter).select_related(
            'voucher_main'
        ).order_by('voucher_main__date').values(
            'voucher_main__voucher_no',
            'voucher_main__date',
            'voucher_main__voucher_type',
            'voucher_main__narration',
            'debit',
            'credit',
        )

        return Response({
            "ledger": ledger.ac_name,
            "transactions": list(rows),
        })


class FinancialRatiosView(APIView):
    """Compute standard financial ratios from P&L + Balance Sheet data."""

    def get(self, request):
        retail = _get_retail_for_report(request)
        if retail == 'FORBIDDEN':
            return Response({"error": "You do not have permission to view combined reports."},
                            status=status.HTTP_403_FORBIDDEN)

        active_fy = getattr(retail, 'active_fy', None) if retail and retail != 'FORBIDDEN' else None
        default_start = str(active_fy.fy_start) if active_fy else f"{date.today().year if date.today().month >= 4 else date.today().year - 1}-04-01"
        start_date_str = request.query_params.get("start_date", default_start)
        end_date_str = request.query_params.get("end_date", str(date.today()))

        # ── P&L data ─────────────────────────────────────────────────────
        pnl = calcuate_pnl(start_date_str, end_date_str, retail=retail)
        sales_revenue = pnl["sales_revenue"]
        gross_profit  = pnl["gross_profit"]
        net_profit    = pnl["net_profit"]
        cogs          = pnl["cogs"]
        total_expenses = pnl["total_expenses"]
        closing_stock  = pnl["closing_stock"]
        purchases      = pnl["purchases"]
        opening_stock  = pnl["opening_stock"]

        # Average inventory for turnover (opening + closing / 2)
        avg_inventory = (opening_stock + closing_stock) / 2 if (opening_stock + closing_stock) else Decimal(0)

        # ── Balance Sheet totals ──────────────────────────────────────────
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        txn_filter = dict(voucher_main__date__lte=end_date)
        if retail:
            txn_filter['voucher_main__retail'] = retail
        txn_by_group = {}
        for row in VoucherDetail.objects.filter(**txn_filter).values(
            "account__ac_group"
        ).annotate(
            balance=Sum(F("debit")) - Sum(F("credit"))
        ):
            gid = row["account__ac_group"]
            if gid is not None:
                txn_by_group[gid] = row["balance"] or Decimal(0)

        ob_filter = {}
        if retail:
            ob_filter['retail'] = retail
        ob_by_group = {}
        for row in LedgerOpenBalance.objects.filter(**ob_filter).values(
            "ldgr__ac_group"
        ).annotate(
            balance=Sum(F("debit") - F("credit"), output_field=DecimalField())
        ):
            gid = row["ldgr__ac_group"]
            if gid is not None:
                ob_by_group[gid] = row["balance"] or Decimal(0)

        all_accounts = list(Account.objects.all())
        children_map = {}
        for acc in all_accounts:
            pid = acc.parent_id
            children_map.setdefault(pid, []).append(acc)

        def get_descendants(parent_id):
            result = []
            for child in children_map.get(parent_id, []):
                result.append(child)
                result.extend(get_descendants(child.id))
            return result

        def get_group_total(group_name):
            try:
                parent = next(a for a in all_accounts if a.name == group_name)
            except StopIteration:
                return Decimal(0)
            return sum(
                txn_by_group.get(acc.id, Decimal(0)) + ob_by_group.get(acc.id, Decimal(0))
                for acc in get_descendants(parent.id)
            )

        total_assets      = get_group_total("Assets")
        total_liabilities = get_group_total("Liabilities") + get_group_total("Capital Account") + net_profit
        equity            = total_assets - total_liabilities

        # ── Outstanding debtors / creditors ──────────────────────────────
        total_debtors = SalesVou.objects.filter(
            retail=request.retail, due_amt__gt=0
        ).aggregate(total=Sum("due_amt"))["total"] or Decimal(0)

        total_creditors = PurchaseVoucher.objects.filter(
            retail=request.retail, due_amt__gt=0
        ).aggregate(total=Sum("due_amt"))["total"] or Decimal(0)

        # ── Ratio helpers ────────────────────────────────────────────────
        def ratio(num, den, pct=False, dp=2):
            try:
                if not den or Decimal(str(den)) == 0:
                    return None
                r = float(num) / float(den)
                return round(r * 100 if pct else r, dp)
            except (ZeroDivisionError, InvalidOperation, TypeError, ValueError):
                return None

        def days(r):
            return round(365 / r, 2) if r else None

        # ── Profitability ────────────────────────────────────────────────
        gpm  = ratio(gross_profit,   sales_revenue, pct=True)
        npm  = ratio(net_profit,     sales_revenue, pct=True)
        cogsr = ratio(cogs,          sales_revenue, pct=True)
        expr  = ratio(total_expenses, sales_revenue, pct=True)
        roa   = ratio(net_profit,    total_assets,   pct=True)
        roe   = ratio(net_profit,    equity,         pct=True)
        ros   = ratio(net_profit + total_expenses, sales_revenue, pct=True)  # EBIT margin approx

        # ── Efficiency / Activity ────────────────────────────────────────
        inv_turn  = ratio(cogs, avg_inventory) if avg_inventory else ratio(cogs, closing_stock)
        dio       = days(inv_turn)
        asset_turn = ratio(sales_revenue, total_assets)
        rec_turn  = ratio(sales_revenue, total_debtors)
        dso       = days(rec_turn)
        pay_turn  = ratio(purchases, total_creditors)
        dpo       = days(pay_turn)
        cash_conv = (dio or 0) + (dso or 0) - (dpo or 0)  # Cash Conversion Cycle

        # ── Leverage / Solvency ──────────────────────────────────────────
        debt_ratio = ratio(total_liabilities, total_assets)
        d2e        = ratio(total_liabilities, equity)
        eq_ratio   = ratio(equity, total_assets)

        return Response({
            "period": {"start_date": start_date_str, "end_date": end_date_str},
            "base_data": {
                "sales_revenue":    sales_revenue,
                "cogs":             cogs,
                "gross_profit":     gross_profit,
                "net_profit":       net_profit,
                "total_expenses":   total_expenses,
                "opening_stock":    opening_stock,
                "closing_stock":    closing_stock,
                "avg_inventory":    avg_inventory,
                "total_assets":     total_assets,
                "total_liabilities": total_liabilities,
                "equity":           equity,
                "total_debtors":    total_debtors,
                "total_creditors":  total_creditors,
                "purchases":        purchases,
            },
            "profitability": {
                "gross_profit_margin":   {"value": gpm,   "label": "Gross Profit Margin",   "unit": "%", "desc": "Gross Profit / Sales × 100"},
                "net_profit_margin":     {"value": npm,   "label": "Net Profit Margin",      "unit": "%", "desc": "Net Profit / Sales × 100"},
                "cogs_ratio":            {"value": cogsr, "label": "COGS Ratio",             "unit": "%", "desc": "COGS / Sales × 100"},
                "expense_ratio":         {"value": expr,  "label": "Expense Ratio",          "unit": "%", "desc": "Total Expenses / Sales × 100"},
                "ebit_margin":           {"value": ros,   "label": "EBIT Margin (approx.)",  "unit": "%", "desc": "(Net Profit + Expenses) / Sales × 100"},
                "return_on_assets":      {"value": roa,   "label": "Return on Assets (ROA)", "unit": "%", "desc": "Net Profit / Total Assets × 100"},
                "return_on_equity":      {"value": roe,   "label": "Return on Equity (ROE)", "unit": "%", "desc": "Net Profit / Equity × 100"},
            },
            "efficiency": {
                "inventory_turnover":      {"value": inv_turn, "label": "Inventory Turnover",       "unit": "×",    "desc": "COGS / Avg Inventory"},
                "days_inventory_outstanding": {"value": dio,   "label": "Days Inventory Outstanding","unit": "days", "desc": "365 / Inventory Turnover"},
                "asset_turnover":          {"value": asset_turn, "label": "Asset Turnover",         "unit": "×",    "desc": "Sales / Total Assets"},
                "receivables_turnover":    {"value": rec_turn, "label": "Receivables Turnover",     "unit": "×",    "desc": "Sales / Total Debtors"},
                "days_sales_outstanding":  {"value": dso,     "label": "Days Sales Outstanding",    "unit": "days", "desc": "365 / Receivables Turnover"},
                "payables_turnover":       {"value": pay_turn, "label": "Payables Turnover",        "unit": "×",    "desc": "Purchases / Total Creditors"},
                "days_payable_outstanding":{"value": dpo,     "label": "Days Payable Outstanding",  "unit": "days", "desc": "365 / Payables Turnover"},
                "cash_conversion_cycle":   {"value": round(cash_conv, 2) if cash_conv else None,
                                            "label": "Cash Conversion Cycle", "unit": "days",
                                            "desc": "DIO + DSO − DPO"},
            },
            "leverage": {
                "debt_ratio":     {"value": debt_ratio, "label": "Debt Ratio",     "unit": "×", "desc": "Total Liabilities / Total Assets"},
                "debt_to_equity": {"value": d2e,        "label": "Debt-to-Equity", "unit": "×", "desc": "Total Liabilities / Equity"},
                "equity_ratio":   {"value": eq_ratio,   "label": "Equity Ratio",   "unit": "×", "desc": "Equity / Total Assets"},
            },
        }, status=status.HTTP_200_OK)


def _is_auditor(request):
    """Staff, superusers, or users with any role named 'Auditor' (case-insensitive)."""
    if request.user.is_staff or request.user.is_superuser:
        return True
    from userauth.models import UserRole
    try:
        return request.user.userrole.role.name.lower() == 'auditor'
    except ObjectDoesNotExist:
        return False


class AuditQueueView(APIView):
    """
    GET  /accounting/api/audit-queue/?from_date=&to_date=&show=unaudited|audited|all
    Returns VoucherMain entries with audit status annotated.
    """
    def get(self, request):
        from ..models import AuditMark
        from_date_str = request.query_params.get('from_date')
        to_date_str   = request.query_params.get('to_date')
        show          = request.query_params.get('show', 'unaudited')  # unaudited | audited | all

        if not all([from_date_str, to_date_str]):
            return Response({'error': 'from_date and to_date are required.'}, status=status.HTTP_400_BAD_REQUEST)

        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
        to_date   = datetime.strptime(to_date_str,   '%Y-%m-%d').date()

        qs = VoucherMain.objects.filter(
            date__range=(from_date, to_date),
            retail=request.retail,
        ).prefetch_related(
            'transactions__account',
            'audit_mark__audited_by',
            'attachments',
        ).order_by('date', 'voucher_no')

        # Collect audit marks for this retail in one query
        audit_marks = {
            am.voucher_id: am
            for am in AuditMark.objects.filter(
                retail=request.retail,
                voucher__date__range=(from_date, to_date),
            ).select_related('audited_by')
        }

        result = []
        for v in qs:
            am = audit_marks.get(v.id)
            is_audited = am is not None

            if show == 'unaudited' and is_audited:
                continue
            if show == 'audited' and not is_audited:
                continue

            lines = [
                {
                    'account':        t.account.ac_name,
                    'debit':          t.debit,
                    'credit':         t.credit,
                    'ref_bill_no':    t.ref_bill_no or '',
                    'party_bank_name': t.party_bank_name or '',
                    'chq_no':         t.chq_no or '',
                }
                for t in v.transactions.all()
            ]

            result.append({
                'id':            v.id,
                'date':          v.date,
                'voucher_no':    v.voucher_no,
                'voucher_type':  v.voucher_type,
                'narration':     v.narration,
                'amount':        v.amount,
                'lines':         lines,
                'is_audited':    is_audited,
                'audited_by':    am.audited_by.get_full_name() or am.audited_by.username if am else None,
                'audited_at':    am.audited_at.strftime('%Y-%m-%d %H:%M') if am else None,
                'audit_notes':   am.notes if am else '',
                'attachments':   [
                    request.build_absolute_uri(att.file.url)
                    for att in v.attachments.all() if att.file
                ],
            })

        return Response({
            'from_date': from_date_str,
            'to_date':   to_date_str,
            'show':      show,
            'count':     len(result),
            'vouchers':  result,
        })


class AuditMarkView(APIView):
    """
    POST   /accounting/api/audit-mark/   { voucher_ids: [...], notes: "" }  → mark as audited
    DELETE /accounting/api/audit-mark/   { voucher_ids: [...] }              → unmark
    """
    def post(self, request):
        if not _is_auditor(request):
            return Response({'error': 'Auditor access required.'}, status=403)

        from ..models import AuditMark
        voucher_ids = request.data.get('voucher_ids', [])
        notes       = request.data.get('notes', '')

        if not voucher_ids:
            return Response({'error': 'voucher_ids is required.'}, status=status.HTTP_400_BAD_REQUEST)

        vouchers = VoucherMain.objects.filter(
            id__in=voucher_ids, retail=request.retail
        )

        created = 0
        for v in vouchers:
            _, was_created = AuditMark.objects.get_or_create(
                voucher=v,
                defaults={
                    'audited_by': request.user,
                    'notes':      notes,
                    'retail':     request.retail,
                }
            )
            if was_created:
                created += 1

        return Response({'marked': created, 'already_marked': len(voucher_ids) - created})

    def delete(self, request):
        if not _is_auditor(request):
            return Response({'error': 'Auditor access required.'}, status=403)

        from ..models import AuditMark
        voucher_ids = request.data.get('voucher_ids', [])

        if not voucher_ids:
            return Response({'error': 'voucher_ids is required.'}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = AuditMark.objects.filter(
            voucher_id__in=voucher_ids,
            retail=request.retail,
        ).delete()

        return Response({'unmarked': deleted})
