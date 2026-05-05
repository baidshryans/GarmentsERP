from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import json

from django.db import transaction
from django.db.models import Sum, F, Case, When, Value, DecimalField, FloatField, Prefetch
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.utils import timezone

from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import ListCreateAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from contacts.models import Ledger
from global_vars import VoucherType
from inventory.views import ClosingStockCal
from sales.models import SalesVou
from sales.serializers import SalesVouSerializer
from userauth.views import RetailBaseViewset
from purchase.models import PurchaseVoucher

from .fine_gold_service import FineGoldRateService
from .models import *
from .models import Account, VoucherDetail
from .serializers import (
    AccountSerializer,
    CashbookTransactionSerializer,
    GoldCashSerializder,
    JournalEntrySerializer,
    LedgerSerializer,
    LedgerLightSerializer,
    LedgerOpenBalanceSerializer,
    PurchaseVoucherSerializer,
)
from .utils import generate_voucher_no
from accounting.utils import *


class DueAdvanceReportSerializer(serializers.Serializer):
    ldgr = serializers.CharField()
    ac_name = serializers.CharField()
    net_dbt_opbal = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_crdt_opbal = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_dbt = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_crdt = serializers.DecimalField(max_digits=15, decimal_places=2)
    balance = serializers.DecimalField(max_digits=15, decimal_places=2)



def get_all_descendants(account: Account):
    """Return all descendant Account objects in a single DB query.

    Fetches the full account table once and walks the tree in-memory,
    avoiding the O(n^depth) recursive queries of the previous approach.
    """
    all_accounts = list(Account.objects.all())
    children_map = {}
    for acc in all_accounts:
        children_map.setdefault(acc.parent_id, []).append(acc)

    descendants = []
    stack = list(children_map.get(account.pk, []))
    while stack:
        node = stack.pop()
        descendants.append(node)
        stack.extend(children_map.get(node.pk, []))
    return descendants


def _can_view_combined(user):
    """Return True if the user is allowed to view combined (all-retail) financial reports."""
    if user.is_superuser:
        return True
    from userauth.models import UserRole
    try:
        user_role = UserRole.objects.select_related('role').get(user=user)
        return user_role.role.name.lower() in ('admin', 'super admin')
    except UserRole.DoesNotExist:
        return False


def _get_retail_for_report(request):
    """Return retail or None based on ?combined=true param and user permissions."""
    combined = request.query_params.get('combined', '').lower() in ('true', '1')
    if combined:
        if not _can_view_combined(request.user):
            return 'FORBIDDEN'
        return None  # None means all retails
    return request.retail


def _get_retail_ids_for_report(request):
    """Multi-retail scope resolver for BS / P&L / Closing Stock.

    Access rules:
      - Admin / superadmin (``_can_view_combined``): may freely scope via
        ``?combined=true`` or ``?retail_ids=<ids>``.
      - Everyone else: scope is pinned to ``request.retail`` regardless of
        query params, so they can never read another retail's data by crafting
        a URL. Any explicit scope params they send are ignored.

    Returns:
      - ``'FORBIDDEN'`` if a non-admin requested multi/combined scope.
      - ``None`` for all-retails combined (admin only).
      - ``[retail_id, ...]`` for a specific subset.
    """
    is_admin = _can_view_combined(request.user)

    combined = request.query_params.get('combined', '').lower() in ('true', '1')
    raw_ids = request.query_params.getlist('retail_ids')
    if not raw_ids:
        single = request.query_params.get('retail_ids')
        if single:
            raw_ids = [single]
    parsed = []
    for chunk in raw_ids:
        for part in str(chunk).split(','):
            part = part.strip()
            if part:
                try:
                    parsed.append(int(part))
                except ValueError:
                    pass

    # Non-admins: ignore any scope params and pin to their own retail. If they
    # tried to scope explicitly (combined or multiple retails), return FORBIDDEN
    # so the UI can surface the error clearly instead of silently swapping.
    if not is_admin:
        if combined or len(set(parsed)) > 1:
            return 'FORBIDDEN'
        r = getattr(request, 'retail', None)
        return [r.id] if r else None

    # Admin path.
    if combined:
        return None
    if parsed:
        return sorted(set(parsed))
    r = getattr(request, 'retail', None)
    return [r.id] if r else None


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
    except Account.DoesNotExist:
        purchases = Decimal(0)
        purchase_returns = Decimal(0)

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


from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import PermissionDenied

class AccountViewSet(ModelViewSet):
    serializer_class = AccountSerializer
    queryset = Account.objects.select_related('parent').prefetch_related('ledger_set__roles').all()
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def perform_create(self, serializer):
        parent_id = self.request.data.get('parent')
        if parent_id:
            serializer.save_with_parent_account(parent_id=parent_id)
        else:
            serializer.save()
        # Mark every user-created group as editable/deletable
        serializer.instance.can_be_deleted = True
        serializer.instance.save(update_fields=['can_be_deleted'])

    def perform_update(self, serializer):
        if not serializer.instance.can_be_deleted:
            raise PermissionDenied("System account groups cannot be modified.")
        parent_id = self.request.data.get('parent')
        if parent_id:
            serializer.save_with_parent_account(parent_id=parent_id)
        else:
            serializer.save(parent=None)

    def perform_destroy(self, instance):
        if not instance.can_be_deleted:
            raise PermissionDenied("This account group cannot be deleted.")
        # Block if any ledgers are assigned to this group
        from contacts.models import Ledger
        ledger_count = Ledger.objects.filter(ac_group=instance).count()
        if ledger_count > 0:
            raise PermissionDenied(
                f"Cannot delete: {ledger_count} ledger(s) are assigned to this group. "
                "Reassign or remove them first."
            )
        # Block if it has child groups
        if instance.children.exists():
            raise PermissionDenied(
                "Cannot delete: this group has sub-groups. Delete the sub-groups first."
            )
        instance.delete()


class LedgerOpenBalanceViewSet(RetailBaseViewset):
    serializer_class = LedgerOpenBalanceSerializer
    queryset = LedgerOpenBalance.objects.select_related('ldgr').all()
    pagination_class = None

    def perform_update(self, serializer):
        serializer.save()


# Keep backward-compatible list/create view for any existing callers
class AccountAPIView(ListCreateAPIView):
    serializer_class = AccountSerializer
    queryset = Account.objects.select_related('parent').prefetch_related('ledger_set__roles').all()
    pagination_class = None

    def perform_create(self, serializer):
        parent_id = self.request.data.get('parent')
        if parent_id:
            serializer.save_with_parent_account(parent_id=parent_id)
        else:
            serializer.save()

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Q
from datetime import datetime
from .models import  VoucherDetail, LedgerOpenBalance
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce, Abs


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




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def account_tree(request):
    from contacts.models import Ledger
    from django.db.models import Count

    # Pre-compute ledger counts per account group in one query
    ledger_counts = dict(
        Ledger.objects.values('ac_group_id')
                      .annotate(cnt=Count('id'))
                      .values_list('ac_group_id', 'cnt')
    )

    def build_tree(account):
        children = list(account.children.all())
        ledger_count = ledger_counts.get(account.id, 0)
        return {
            'id': account.id,
            'name': f"{account.code} - {account.name}",
            'code': account.code,
            'can_be_deleted': account.can_be_deleted,
            'ledger_count': ledger_count,
            'can_delete': account.can_be_deleted and ledger_count == 0 and len(children) == 0,
            'children': [build_tree(child) for child in children],
        }

    root_accounts = Account.objects.filter(parent__isnull=True).prefetch_related('children__children__children')
    tree_data = [build_tree(account) for account in root_accounts]
    return Response(tree_data)


def _voucher_source_document(voucher):
    """If `voucher` was auto-posted from a business document (karigar receive,
    sales voucher, purchase voucher, depreciation approval, scheme payment,
    cheque deposit, credit/debit note), return (label, identifier).
    Otherwise return None — meaning it was created directly via the journal API
    and is fair game for editing through the journal list.

    Lazy imports avoid circular dependencies between the accounting app and
    the apps that point back at it.
    """
    # ── Manufacturing ────────────────────────────────────────────────────────
    from manufacturing.models import KarigarReceive
    kr = KarigarReceive.objects.filter(making_vid=voucher).first()
    if kr:
        return ('Karigar Receive', kr.receive_slip_no)

    # ── Sales ────────────────────────────────────────────────────────────────
    from sales.models import SalesVou, SaleReturn, BankDetail
    sv = SalesVou.objects.filter(ac_voucher=voucher).first()
    if sv:
        return ('Sales Voucher', sv.billno)
    sv_rcpt = SalesVou.objects.filter(ac_rec_voucher=voucher).first()
    if sv_rcpt:
        return ('Sales Receipt', sv_rcpt.billno)
    sr = SaleReturn.objects.filter(ac_voucher=voucher).first()
    if sr:
        return ('Sale Return', sr.billno)
    chq = BankDetail.objects.filter(deposit_voucher=voucher).select_related('sales_vou').first()
    if chq:
        return ('Cheque Deposit', f"{chq.chq_no or ''} (Sales {chq.sales_vou.billno})")

    # ── Purchase ─────────────────────────────────────────────────────────────
    from purchase.models import PurchaseVoucher, PurchaseReturn
    pv = PurchaseVoucher.objects.filter(ac_voucher=voucher).first()
    if pv:
        return ('Purchase Voucher', pv.billno)
    pv_tds = PurchaseVoucher.objects.filter(tds_ac_voucher=voucher).first()
    if pv_tds:
        return ('Purchase Voucher TDS', pv_tds.billno)
    pr = PurchaseReturn.objects.filter(ac_voucher=voucher).first()
    if pr:
        return ('Purchase Return', pr.billno)

    # ── Accounting (credit/debit notes, depreciation) ───────────────────────
    from accounting.models import CreditDebitNote, DepreciationSuggestion
    cn = CreditDebitNote.objects.filter(ac_voucher=voucher).first()
    if cn:
        return ('Credit/Debit Note', cn.note_no)
    dep = DepreciationSuggestion.objects.filter(voucher=voucher).first()
    if dep:
        return ('Depreciation Suggestion', dep.label)

    # ── Gold Scheme ──────────────────────────────────────────────────────────
    from goldscheme.models import SchemePayment
    sp = SchemePayment.objects.filter(voucher=voucher).first()
    if sp:
        return ('Scheme Payment', f"#{sp.id}")

    return None


class JournalEntryViewSet(RetailBaseViewset):
    serializer_class = JournalEntrySerializer
class JournalEntryViewSet(RetailBaseViewset):
    serializer_class = JournalEntrySerializer
    queryset = VoucherMain.objects.select_related('retail').prefetch_related('transactions__account').all()
    filter_backends = [DjangoFilterBackend,OrderingFilter,SearchFilter]
    filterset_fields = ['voucher_no', 'voucher_type']
    search_fields=['voucher_no','voucher_type']
    ordering = ['-date', '-id']

    def get_queryset(self):
        qs = super().get_queryset()
        # Exclude sale/purchase voucher types from the accounting list
        # (those are already visible in their respective apps)
        excluded = [
            VoucherType.sale, VoucherType.purc_sc, VoucherType.purc_ret,
            VoucherType.sale_ret, VoucherType.rcpt_sale,
        ]
        return qs.exclude(voucher_type__in=excluded)

    def _check_voucher_mutable(self, instance, action):
        from rest_framework.exceptions import ValidationError

        # System-posted vouchers (those created by a business document like a
        # karigar receive, sales voucher, purchase voucher, depreciation
        # approval, etc.) must be edited via their source document — never
        # directly through the journal list.
        source = _voucher_source_document(instance)
        if source is not None:
            label, identifier = source
            raise ValidationError(
                f"Voucher '{instance.voucher_no}' was posted from {label} "
                f"'{identifier}'. Edit the {label} to change this entry."
            )

        if instance.status == 'posted':
            raise ValidationError(
                f"Voucher '{instance.voucher_no}' cannot be {action} while it is posted. Cancel it first."
            )

    def perform_destroy(self, instance):
        self._check_voucher_mutable(instance, 'deleted')
        from .utils import release_last_bill_number
        retail = instance.retail
        fiscal_year = instance.fiscal_year
        voucher_no = instance.voucher_no
        prefix = instance.voucher_type  # e.g. 'JRNL', 'PMNT', 'RCPT', 'CONTRA'
        super().perform_destroy(instance)
        release_last_bill_number(retail, prefix, voucher_no, fiscal_year)

    def perform_update(self, serializer):
        self._check_voucher_mutable(serializer.instance, 'edited')
        super().perform_update(serializer)

    from rest_framework.decorators import action as _drf_action
    @_drf_action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """
        Soft-cancel a posted voucher: reverse its invoice `due_amt` effects
        and mark status='cancelled'. The row is preserved for audit —
        prefer this over DELETE in production.
        """
        from .signals import cancel_voucher
        voucher = self.get_object()
        if voucher.status == 'cancelled':
            return Response(
                {'detail': 'Voucher is already cancelled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cancel_voucher(voucher, user=request.user)
        return Response({
            'id':        voucher.id,
            'voucher_no': voucher.voucher_no,
            'status':    voucher.status,
            'detail':    'Voucher cancelled and ledger effects reversed.',
        })
    def perform_create(self, serializer):
        with transaction.atomic():
            serializer.save(retail=self.request.retail)

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            response = super().create(request, *args, **kwargs)
            if response.status_code == status.HTTP_201_CREATED:
                return Response({'success': True}, status=status.HTTP_201_CREATED)
            return Response({'success': False, 'errors': response.data}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def initial_data_view(request):
    # Retrieve ledgers, voucher number, and default date
    ledgers = LedgerLightSerializer(
        Ledger.objects.select_related('ac_group').prefetch_related('roles').only('id', 'ac_name', 'ac_group'),
        many=True
    ).data
    from accounting.utils import peek_next_bill_number
    voucher_no = peek_next_bill_number(request.retail, 'JRNL')
    default_date = timezone.localdate()

    return Response({
        'ledgers': ledgers,
        'voucher_no': voucher_no,
        'default_date': default_date
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_gc_no(request):
    from accounting.utils import peek_next_bill_number
    bill_no = peek_next_bill_number(request.retail, "GC")
    return Response({"billno":bill_no})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_vou_no(request,type):
    from accounting.utils import peek_next_bill_number
    type_map = {
        "PMNT": VoucherType.pmnt,
        "CONTRA": VoucherType.cntr,
        "RCPT": VoucherType.rcpt,
        "RCPT-SALE": VoucherType.rcpt_sale,
        "SALE": VoucherType.sale,
        "PURC-RET": VoucherType.purc_ret,
        "PURC-SC": VoucherType.purc_sc,
        "SALE-RET": VoucherType.sale_ret,
        "JRNL": VoucherType.journal,
    }
    prefix = type_map.get(type)
    if not prefix:
        return Response({"error": f"Unknown voucher type: {type}"}, status=status.HTTP_400_BAD_REQUEST)
    bill_no = peek_next_bill_number(request.retail, prefix)
    return Response({"billno":bill_no})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_cg_no(request):
    from accounting.utils import peek_next_bill_number
    bill_no = peek_next_bill_number(request.retail, "CG")
    return Response({"billno":bill_no})

class VoucherAttachmentListCreate(ListCreateAPIView):
    from .serializers import VoucherAttachmentSerializer
    serializer_class = VoucherAttachmentSerializer
    from rest_framework.parsers import MultiPartParser
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        from .models import VoucherAttachment
        voucher_id = self.request.query_params.get('voucher')
        if voucher_id and str(voucher_id).isdigit():
            return VoucherAttachment.objects.filter(voucher_id=int(voucher_id)).order_by('-uploaded_at')
        # Non-numeric or missing voucher param → empty queryset (don't 500)
        return VoucherAttachment.objects.none()


class VoucherAttachmentDelete(APIView):
    def delete(self, request, pk):
        from .models import VoucherAttachment
        try:
            att = VoucherAttachment.objects.get(pk=pk)
            att.file.delete(save=False)
            att.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except VoucherAttachment.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class GoldCashConversionView(ListCreateAPIView):
    serializer_class = GoldCashSerializder
    queryset = CashGoldConversion.objects.all()

    def perform_create(self, serializer):
        serializer.validated_data['retail'] = self.request.retail
        return super().perform_create(serializer)

class PurchaseVoucherView(ListAPIView):
    serializer_class = PurchaseVoucherSerializer

    def get_queryset(self):
        ldgr_id = self.request.query_params.get("ldgr_id")

        return self.serializer_class.Meta.model.objects.filter(retail =self.request.retail ,ldgr_id=ldgr_id, due_amt__gt=0)


class AgedReceivablesView(APIView):
    """
    GET /accounting/api/aged-receivables/?kind=sales|purchase

    Buckets outstanding invoices by age-of-due relative to today:
      0-30 / 31-60 / 61-90 / 90+ days.

    Returns one row per party with totals per bucket. Drives the
    "Aged Receivables" / "Aged Payables" dashboard report.
    """

    def get(self, request):
        from datetime import date as _date
        kind = (request.query_params.get('kind') or 'sales').lower()
        retail = request.retail
        today = _date.today()

        if kind == 'sales':
            qs = SalesVou.objects.filter(retail=retail, due_amt__gt=0) \
                .select_related('ldgr').order_by('ldgr__ac_name', 'date1')
            date_field = 'date1'
            bill_field = 'billno'
        elif kind == 'purchase':
            qs = PurchaseVoucher.objects.filter(retail=retail, due_amt__gt=0) \
                .select_related('ldgr').order_by('ldgr__ac_name', 'date1')
            date_field = 'date1'
            bill_field = 'billno'
        else:
            return Response(
                {'error': "kind must be 'sales' or 'purchase'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Party → {b0_30, b31_60, b61_90, b90_plus, total, bills[]}
        parties = {}
        for bill in qs:
            ldgr = bill.ldgr
            if not ldgr:
                continue
            age = (today - getattr(bill, date_field)).days
            if age <= 30:
                bucket = 'b0_30'
            elif age <= 60:
                bucket = 'b31_60'
            elif age <= 90:
                bucket = 'b61_90'
            else:
                bucket = 'b90_plus'

            key = ldgr.id
            if key not in parties:
                parties[key] = {
                    'ldgr_id':   ldgr.id,
                    'ldgr_name': ldgr.ac_name,
                    'b0_30':     Decimal('0'),
                    'b31_60':    Decimal('0'),
                    'b61_90':    Decimal('0'),
                    'b90_plus':  Decimal('0'),
                    'total':     Decimal('0'),
                    'bills':     [],
                }
            due = Decimal(str(bill.due_amt or 0))
            parties[key][bucket] += due
            parties[key]['total'] += due
            parties[key]['bills'].append({
                'billno':  getattr(bill, bill_field),
                'date':    getattr(bill, date_field),
                'age':     age,
                'due_amt': float(due),
            })

        # Serialize Decimals to float for JSON
        rows = []
        for p in parties.values():
            rows.append({
                'ldgr_id':   p['ldgr_id'],
                'ldgr_name': p['ldgr_name'],
                'b0_30':     float(p['b0_30']),
                'b31_60':    float(p['b31_60']),
                'b61_90':    float(p['b61_90']),
                'b90_plus':  float(p['b90_plus']),
                'total':     float(p['total']),
                'bills':     p['bills'],
            })
        rows.sort(key=lambda r: -r['total'])

        totals = {
            'b0_30':    sum(r['b0_30']    for r in rows),
            'b31_60':   sum(r['b31_60']   for r in rows),
            'b61_90':   sum(r['b61_90']   for r in rows),
            'b90_plus': sum(r['b90_plus'] for r in rows),
            'total':    sum(r['total']    for r in rows),
        }
        return Response({'as_of': today, 'kind': kind, 'rows': rows, 'totals': totals})


class AdvanceRegisterView(APIView):
    """
    GET /accounting/api/advance-register/

    Lists all Customer Orders that have ever had an advance receipt, with:
      received / reconciled / remaining columns driven by
      CustomerOrder.advance_amt (computed property) and advance_reconciled.
    """

    def get(self, request):
        from sales.models import CustomerOrder
        retail = request.retail
        orders = CustomerOrder.objects.filter(
            retail=retail, receipts__isnull=False,
        ).select_related('ldgr').distinct().order_by('-date1', '-id')

        rows = []
        for o in orders:
            received    = o.advance_amt
            reconciled  = o.advance_reconciled
            remaining   = o.advance_available
            if received <= 0:
                continue
            rows.append({
                'order_id':   o.id,
                'order_no':   o.order_no,
                'date':       o.date1,
                'ldgr_id':    o.ldgr_id,
                'ldgr_name':  o.ldgr.ac_name if o.ldgr else None,
                'status':     o.status,
                'received':   float(received),
                'reconciled': float(reconciled),
                'remaining':  float(remaining),
            })

        totals = {
            'received':   sum(r['received']   for r in rows),
            'reconciled': sum(r['reconciled'] for r in rows),
            'remaining':  sum(r['remaining']  for r in rows),
        }
        return Response({'rows': rows, 'totals': totals})


class OutstandingBillsView(APIView):
    """
    Unified bill-allocation picker endpoint.

    GET /accounting/api/outstanding-bills/?ledger={id}&type={sales|purchase}

    Returns bills with `due_amt > 0` for the given ledger, compact shape:
      [{id, billno, date, total, due_amt}, ...]

    Used by the BillAllocationTable component in the Payment/Receipt voucher UI.
    """

    def get(self, request):
        ldgr_id = request.query_params.get('ledger')
        kind    = (request.query_params.get('type') or '').lower()
        if not ldgr_id or kind not in ('sales', 'purchase'):
            return Response(
                {'error': "Query params 'ledger' and 'type' (sales|purchase) are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        retail = request.retail
        if kind == 'sales':
            qs = SalesVou.objects.filter(
                retail=retail, ldgr_id=ldgr_id, due_amt__gt=0,
            ).order_by('date1', 'id')
            data = [
                {
                    'id':       sv.id,
                    'billno':   sv.billno,
                    'date':     sv.date1,
                    'total':    float(sv.total_bill_value or 0),
                    'due_amt':  float(sv.due_amt or 0),
                }
                for sv in qs
            ]
        else:
            qs = PurchaseVoucher.objects.filter(
                retail=retail, ldgr_id=ldgr_id, due_amt__gt=0,
            ).order_by('date1', 'id')
            data = [
                {
                    'id':       pv.id,
                    'billno':   pv.billno,
                    'date':     pv.date1,
                    'total':    float(pv.bill_value or pv.item_total or 0),
                    'due_amt':  float(pv.due_amt or 0),
                }
                for pv in qs
            ]
        return Response(data)

class SaleVoucherView(ListAPIView):
    serializer_class = SalesVouSerializer

    def get_queryset(self):
        ldgr_id = self.request.query_params.get("ldgr_id")
        return self.serializer_class.Meta.model.objects.filter(retail =self.request.retail ,ldgr=ldgr_id, due_amt__gt=0)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cash_total_of_ledger(request, ledger_id):
    total_debit = VoucherDetail.objects.filter(
    voucher_main_id__in=VoucherDetail.objects.filter(account=ledger_id).values('voucher_main_id'),
    account__in=RetailMaster.objects.values_list('cash_ldgr_id', flat=True).exclude(cash_ldgr_id=None)
    ).aggregate(Sum('debit'))['debit__sum']

    return Response({'total_cash': total_debit or 0})


from django.db.models import Value
from django.db.models.functions import Coalesce


class LedgerStatementView(APIView):
    """Per-ledger account statement with running balance."""
    def get(self, request):
        ledger_id = request.query_params.get("ledger_id")
        from_date_str = request.query_params.get("from_date")
        to_date_str = request.query_params.get("to_date")

        if not all([ledger_id, from_date_str, to_date_str]):
            return Response({"error": "ledger_id, from_date and to_date are required."}, status=status.HTTP_400_BAD_REQUEST)

        from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()

        try:
            ledger = Ledger.objects.get(pk=ledger_id)
        except Ledger.DoesNotExist:
            return Response({"error": "Ledger not found."}, status=status.HTTP_404_NOT_FOUND)

        # Opening balance = stored LedgerOpenBalance for the FY containing from_date
        # + transactions within that FY before from_date (not all history).
        from mastersconfig.models import FiscalYearMaster
        fy = FiscalYearMaster.objects.filter(
            retail=request.retail,
            fy_start__lte=from_date,
            fy_end__gte=from_date,
        ).first()

        ob_filter = dict(ldgr=ledger, retail=request.retail)
        if fy:
            ob_filter['acc_year'] = fy.fy_code
        ob = LedgerOpenBalance.objects.filter(**ob_filter).aggregate(
            debit=Coalesce(Sum('debit', output_field=DecimalField(max_digits=20, decimal_places=4)), Value(Decimal('0'))),
            credit=Coalesce(Sum('credit', output_field=DecimalField(max_digits=20, decimal_places=4)), Value(Decimal('0')))
        )
        ob_balance = Decimal(str(ob['debit'])) - Decimal(str(ob['credit']))

        before_filter = dict(
            account=ledger,
            voucher_main__date__lt=from_date,
            voucher_main__retail=request.retail,
        )
        if fy:
            before_filter['voucher_main__date__gte'] = fy.fy_start
        before = VoucherDetail.objects.filter(**before_filter).aggregate(
            total=Coalesce(
                Sum(F('debit') - F('credit'), output_field=DecimalField(max_digits=20, decimal_places=4)),
                Value(Decimal('0'))
            )
        )['total']

        opening_balance = ob_balance + Decimal(str(before))

        # Transactions in range
        txns = VoucherDetail.objects.filter(
            account=ledger,
            voucher_main__date__range=(from_date, to_date),
            voucher_main__retail=request.retail
        ).select_related('voucher_main').order_by(
            'voucher_main__date', 'voucher_main__id'
        ).values(
            'voucher_main__id', 'voucher_main__date', 'voucher_main__voucher_no',
            'voucher_main__voucher_type', 'voucher_main__narration',
            'debit', 'credit', 'party_bank_name', 'chq_no', 'ref_bill_no'
        )

        # Map accounting VoucherMain → source document bill number so the ledger
        # shows the user-visible bill number (SV/.., PV/.., SR/..) instead of
        # the internal accounting voucher number (SALE/.., PUR/..).
        vm_ids = [t['voucher_main__id'] for t in txns]
        src_billno = {}
        if vm_ids:
            from sales.models import SalesVou, SaleReturn
            from purchase.models import PurchaseVoucher, PurchaseReturn
            for sv in SalesVou.objects.filter(ac_voucher_id__in=vm_ids).values('ac_voucher_id', 'billno'):
                src_billno[sv['ac_voucher_id']] = sv['billno']
            for sv in SalesVou.objects.filter(ac_rec_voucher_id__in=vm_ids).values('ac_rec_voucher_id', 'billno'):
                src_billno.setdefault(sv['ac_rec_voucher_id'], sv['billno'])
            for sr in SaleReturn.objects.filter(ac_voucher_id__in=vm_ids).values('ac_voucher_id', 'billno'):
                src_billno[sr['ac_voucher_id']] = sr['billno']
            for pv in PurchaseVoucher.objects.filter(ac_voucher_id__in=vm_ids).values('ac_voucher_id', 'billno'):
                src_billno[pv['ac_voucher_id']] = pv['billno']
            for pr in PurchaseReturn.objects.filter(ac_voucher_id__in=vm_ids).values('ac_voucher_id', 'billno'):
                src_billno[pr['ac_voucher_id']] = pr['billno']

        running_balance = opening_balance
        transactions = []
        for txn in txns:
            running_balance += Decimal(str(txn['debit'])) - Decimal(str(txn['credit']))
            vm_id = txn['voucher_main__id']
            transactions.append({
                'date': txn['voucher_main__date'],
                'voucher_no': src_billno.get(vm_id) or txn['voucher_main__voucher_no'],
                'voucher_type': txn['voucher_main__voucher_type'],
                'narration': txn['voucher_main__narration'],
                'debit': txn['debit'],
                'credit': txn['credit'],
                'party_bank_name': txn['party_bank_name'] or '',
                'chq_no': txn['chq_no'] or '',
                'ref_bill_no': txn['ref_bill_no'] or '',
                'running_balance': running_balance,
            })

        return Response({
            "ledger_id": ledger.id,
            "ledger_name": ledger.ac_name,
            "from_date": from_date,
            "to_date": to_date,
            "opening_balance": opening_balance,
            "transactions": transactions,
            "closing_balance": running_balance,
        }, status=status.HTTP_200_OK)


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


class OutstandingReportView(APIView):
    """Debtors / Creditors outstanding with aging buckets: 0-30, 31-60, 61-90, 90+."""
    def get(self, request):
        report_type = request.query_params.get("type", "debtor")  # debtor | creditor
        as_of_date_str = request.query_params.get("as_of_date", str(date.today()))
        as_of_date = datetime.strptime(as_of_date_str, "%Y-%m-%d").date()

        if report_type == "debtor":
            from sales.models import SalesVou as BillModel
            bills = BillModel.objects.filter(
                retail=request.retail, due_amt__gt=0
            ).select_related('ldgr').values('ldgr__ac_name', 'billno', 'date1', 'due_amt', 'total_bill_value')
            bill_no_key = 'billno'
            amount_key = 'total_bill_value'
        else:
            from purchase.models import PurchaseVoucher as BillModel
            bills = BillModel.objects.filter(
                retail=request.retail, due_amt__gt=0
            ).select_related('ldgr').values('ldgr__ac_name', 'billno', 'date1', 'due_amt', 'bill_value')
            bill_no_key = 'billno'
            amount_key = 'bill_value'

        result = {}
        grand_total = Decimal('0')
        grand_0_30 = Decimal('0')
        grand_31_60 = Decimal('0')
        grand_61_90 = Decimal('0')
        grand_above_90 = Decimal('0')

        for bill in bills:
            name = bill['ldgr__ac_name']
            bill_date = bill['date1']
            if isinstance(bill_date, str):
                bill_date = datetime.strptime(bill_date, "%Y-%m-%d").date()
            age = (as_of_date - bill_date).days
            due = Decimal(str(bill['due_amt']))

            if name not in result:
                result[name] = {
                    "name": name,
                    "total": Decimal('0'), "0_30": Decimal('0'),
                    "31_60": Decimal('0'), "61_90": Decimal('0'),
                    "above_90": Decimal('0'), "bills": []
                }

            result[name]["total"] += due
            grand_total += due
            if age <= 30:
                result[name]["0_30"] += due
                grand_0_30 += due
            elif age <= 60:
                result[name]["31_60"] += due
                grand_31_60 += due
            elif age <= 90:
                result[name]["61_90"] += due
                grand_61_90 += due
            else:
                result[name]["above_90"] += due
                grand_above_90 += due

            result[name]["bills"].append({
                "bill_no": bill.get(bill_no_key, ''),
                "date": bill_date.strftime("%Y-%m-%d"),
                "total_amount": str(bill.get(amount_key, 0)),
                "due_amount": str(due),
                "age_days": age,
            })

        return Response({
            "type": report_type,
            "as_of_date": as_of_date_str,
            "parties": list(result.values()),
            "summary": {
                "total": grand_total,
                "0_30": grand_0_30,
                "31_60": grand_31_60,
                "61_90": grand_61_90,
                "above_90": grand_above_90,
            }
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
        if retail:
            ledgers = ledgers.filter(retail=retail)

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


# ── Bank Reconciliation ───────────────────────────────────────────────────────

class BankStatementListCreate(ListCreateAPIView):
    """
    GET  /api/bank-statement/?bank_ledger=<id>&from_date=&to_date=
    POST /api/bank-statement/   — create a single bank statement entry
    """
    from .serializers import BankStatementSerializer

    @property
    def serializer_class(self):
        from .serializers import BankStatementSerializer
        return BankStatementSerializer

    def get_queryset(self):
        from .models import BankStatementEntry
        retail = self.request.retail
        qs = BankStatementEntry.objects.filter(retail=retail).select_related('bank_ledger', 'matched_entry')
        bank_ldgr = self.request.query_params.get('bank_ledger')
        from_date = self.request.query_params.get('from_date')
        to_date   = self.request.query_params.get('to_date')
        if bank_ldgr:
            qs = qs.filter(bank_ledger_id=bank_ldgr)
        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)
        return qs.order_by('date', 'id')

    def perform_create(self, serializer):
        serializer.save(retail=self.request.retail)


class BankStatementDetail(APIView):
    """DELETE /api/bank-statement/<pk>/"""
    def delete(self, request, pk):
        from .models import BankStatementEntry
        entry = BankStatementEntry.objects.filter(pk=pk, retail=request.retail).first()
        if not entry:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        entry.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bank_statement_match(request, pk):
    """
    POST /api/bank-statement/<pk>/match/
    Body: {"voucher_detail_id": <int>}
    Links a bank statement entry to a book entry.
    """
    from .models import BankStatementEntry
    entry = BankStatementEntry.objects.filter(pk=pk, retail=request.retail).first()
    if not entry:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    vd_id = request.data.get('voucher_detail_id')
    if vd_id:
        vd = VoucherDetail.objects.filter(pk=vd_id, voucher_main__retail=request.retail).first()
        if not vd:
            return Response({"detail": "VoucherDetail not found."}, status=status.HTTP_404_NOT_FOUND)
        entry.matched_entry = vd
    else:
        entry.matched_entry = None
    entry.save(update_fields=['matched_entry'])
    return Response({"status": "ok", "matched": bool(entry.matched_entry)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bank_book_for_recon(request):
    """
    GET /api/bank-reconciliation/book-entries/?bank_ledger=<id>&from_date=&to_date=
    Returns VoucherDetail rows for the given bank ledger (for matching).
    """
    retail = request.retail
    bank_ldgr_id = request.GET.get('bank_ledger')
    from_date    = request.GET.get('from_date')
    to_date      = request.GET.get('to_date')

    if not bank_ldgr_id:
        return Response({"detail": "bank_ledger is required."}, status=status.HTTP_400_BAD_REQUEST)

    qs = VoucherDetail.objects.filter(
        voucher_main__retail=retail,
        account_id=bank_ldgr_id,
    ).select_related('voucher_main').order_by('voucher_main__date', 'id')

    if from_date:
        qs = qs.filter(voucher_main__date__gte=from_date)
    if to_date:
        qs = qs.filter(voucher_main__date__lte=to_date)

    data = [{
        'id':         vd.id,
        'date':       str(vd.voucher_main.date),
        'voucher_no': vd.voucher_no,
        'narration':  vd.voucher_main.narration,
        'debit':      float(vd.debit),
        'credit':     float(vd.credit),
        'chq_no':     vd.chq_no or '',
        'is_matched': hasattr(vd, 'bank_statement_match'),
    } for vd in qs]

    # Annotate is_matched properly
    from .models import BankStatementEntry
    matched_vd_ids = set(
        BankStatementEntry.objects.filter(
            retail=retail, bank_ledger_id=bank_ldgr_id, matched_entry__isnull=False
        ).values_list('matched_entry_id', flat=True)
    )
    for row in data:
        row['is_matched'] = row['id'] in matched_vd_ids

    return Response(data)


# ── Audit Queue ───────────────────────────────────────────────────────────────

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
        from .models import AuditMark
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

        from .models import AuditMark
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

        from .models import AuditMark
        voucher_ids = request.data.get('voucher_ids', [])

        if not voucher_ids:
            return Response({'error': 'voucher_ids is required.'}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = AuditMark.objects.filter(
            voucher_id__in=voucher_ids,
            retail=request.retail,
        ).delete()

        return Response({'unmarked': deleted})


# ── Credit / Debit Notes ──────────────────────────────────────────────────────

class CreditDebitNoteViewSet(RetailBaseViewset):
    from .models import CreditDebitNote
    from .serializers import CreditDebitNoteSerializer
    serializer_class = CreditDebitNoteSerializer
    queryset = CreditDebitNote.objects.select_related(
        'ldgr', 'adjustment_ldgr', 'ref_sales_vou', 'ref_purchase_vou', 'ac_voucher',
    ).all()
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ['note_type']
    search_fields = ['note_no', 'ldgr__ac_name', 'reason']
    ordering = ['-date', '-id']
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def destroy(self, request, *args, **kwargs):
        note = self.get_object()
        if note.ac_voucher and note.ac_voucher.status != 'cancelled':
            from .signals import cancel_voucher
            cancel_voucher(note.ac_voucher, user=request.user)
        from .utils import release_last_bill_number
        retail = note.retail
        fiscal_year = note.fiscal_year
        note_no = note.note_no
        prefix = note.note_type  # 'CN' or 'DN'
        response = super().destroy(request, *args, **kwargs)
        release_last_bill_number(retail, prefix, note_no, fiscal_year)
        return response

    def perform_create(self, serializer):
        retail = self.request.retail
        serializer.save(
            retail=retail,
            fiscal_year=retail.active_fy,
            gstin_ref=retail.active_gstin if hasattr(retail, 'active_gstin') else None,
            branch_ref=retail.branch if hasattr(retail, 'branch') else None,
        )

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            return Response({'success': True, 'data': response.data}, status=status.HTTP_201_CREATED)
        return Response({'success': False, 'errors': response.data}, status=status.HTTP_400_BAD_REQUEST)

    from rest_framework.decorators import action as _drf_action

    @_drf_action(detail=True, methods=['get'], url_path='print-data')
    def print_data(self, request, pk=None):
        """Return all data needed by the frontend print component."""
        note = self.get_object()
        retail = request.retail

        # Company info
        company = retail.branch.company if retail.branch_id and retail.branch else None
        company_name = company.company_name if company else (retail.name if hasattr(retail, 'name') else '')
        company_address = ', '.join(filter(None, [
            getattr(retail, 'address_line1', ''),
            getattr(retail, 'address_line2', ''),
            getattr(retail, 'city', ''),
            getattr(retail, 'pincode', ''),
        ]))
        company_gstin = retail.gstin or ''
        company_state = retail.state.name if getattr(retail, 'state', None) else ''

        # Party info
        ldgr = note.ldgr
        party_address = ', '.join(filter(None, [
            ldgr.add1 or '', ldgr.add2 or '', ldgr.city or '', ldgr.pincode or '',
        ]))

        # Original invoice info
        ref_invoice_no = ''
        ref_invoice_date = ''
        if note.ref_sales_vou:
            ref_invoice_no = note.ref_sales_vou.billno
            ref_invoice_date = str(note.ref_sales_vou.date1 or '')
        elif note.ref_purchase_vou:
            ref_invoice_no = note.ref_purchase_vou.billno
            ref_invoice_date = str(note.ref_purchase_vou.date1 or '')

        data = {
            'note_type': note.note_type,
            'note_type_display': note.get_note_type_display(),
            'note_no': note.note_no,
            'date': str(note.date),
            'company_name': company_name,
            'company_address': company_address,
            'company_gstin': company_gstin,
            'company_state': company_state,
            'party_name': ldgr.ac_name,
            'party_address': party_address,
            'party_gstin': ldgr.gst or '',
            'party_state': ldgr.state or '',
            'ref_invoice_no': ref_invoice_no,
            'ref_invoice_date': ref_invoice_date,
            'reason': note.reason,
            'taxable_value': float(note.taxable_value),
            'cgst_per': float(note.cgst_per),
            'cgst_amt': float(note.cgst_amt),
            'sgst_per': float(note.sgst_per),
            'sgst_amt': float(note.sgst_amt),
            'igst_per': float(note.igst_per),
            'igst_amt': float(note.igst_amt),
            'amount': float(note.amount),
            'adjustment_ledger': note.adjustment_ldgr.ac_name,
        }
        return Response(data)

    @_drf_action(detail=True, methods=['post'], url_path='cancel')
    def cancel_note(self, request, pk=None):
        """Cancel a CN/DN: reverse the accounting voucher and mark it cancelled."""
        from .signals import cancel_voucher
        note = self.get_object()
        if not note.ac_voucher:
            return Response({'error': 'No accounting voucher linked.'}, status=status.HTTP_400_BAD_REQUEST)
        if note.ac_voucher.status == 'cancelled':
            return Response({'error': 'Already cancelled.'}, status=status.HTTP_400_BAD_REQUEST)
        cancel_voucher(note.ac_voucher, user=request.user)
        return Response({'detail': 'Credit/Debit Note cancelled and ledger effects reversed.'})


class NextCNDNNumberView(APIView):
    """GET /accounting/api/cn-dn-no/{type}/  →  next note number."""

    def get(self, request, note_type):
        note_type = note_type.upper()
        if note_type not in ('CN', 'DN'):
            return Response({'error': "type must be 'CN' or 'DN'"}, status=status.HTTP_400_BAD_REQUEST)
        from .utils import peek_next_bill_number
        retail = request.retail
        next_no = peek_next_bill_number(retail, note_type)
        return Response({'next_no': next_no})


# ---------------------------------------------------------------------------
# Fixed Assets views (merged from fixedassets app)
# ---------------------------------------------------------------------------

import datetime as _dt
from django.db.models import Sum as _Sum
from django.utils import timezone as _tz
from userauth.permissions import RBACPermission
from .models import (
    FixedAsset, DepreciationSuggestion, DepreciationSuggestionLine,
    FixedAssetSettings, IT_BLOCK_RATES,
)
from .serializers import (
    FixedAssetSerializer, DepreciationSuggestionSerializer,
    DepreciationSuggestionLineSerializer, FixedAssetSettingsSerializer,
)
from .fa_services import generate_suggestion_lines


# Maps IT block category → FA account group code
_IT_BLOCK_TO_AC_GROUP = {
    'BLDG_RES':  'FA-LB',
    'BLDG_COM':  'FA-LB',
    'FURN':      'FA-FF',
    'PLANT':     'FA-PM',
    'VEHICLE':   'FA-VH',
    'COMPUTER':  'FA-CE',
    'BOOKS':     'FA-PM',
    'INTANG':    'FA-PM',
}
_DEFAULT_FA_GROUP = 'FA-PM'


class FixedAssetViewSet(RetailBaseViewset):
    queryset         = FixedAsset.objects.all()
    serializer_class = FixedAssetSerializer
    permission_classes = [RBACPermission]

    def get_queryset(self):
        retail = getattr(self.request, 'retail', None)
        qs = FixedAsset.objects.filter(retail=retail).select_related('retail', 'asset_ledger')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_create(self, serializer):
        retail = self.request.retail
        asset = serializer.save(retail=retail)

        # Auto-create a matching ledger under the correct FA account group
        group_code = _IT_BLOCK_TO_AC_GROUP.get(asset.it_block_category or '', _DEFAULT_FA_GROUP)
        try:
            ac_group = Account.objects.get(code=group_code)
        except Account.DoesNotExist:
            ac_group = None

        ledger = Ledger.objects.create(
            ac_name=asset.asset_name,
            display_name=asset.asset_name,
            ac_group=ac_group,
            retail_code=retail,
            is_system=True,  # prevents independent edit/delete from ledger master
        )
        asset.asset_ledger = ledger
        asset.save(update_fields=['asset_ledger'])


class DepreciationSuggestionViewSet(RetailBaseViewset):
    queryset         = DepreciationSuggestion.objects.all()
    serializer_class = DepreciationSuggestionSerializer
    permission_classes = [RBACPermission]

    def get_queryset(self):
        retail = getattr(self.request, 'retail', None)
        return (
            DepreciationSuggestion.objects
            .filter(retail=retail)
            .prefetch_related('lines__asset')
            .select_related('voucher', 'approved_by', 'fiscal_year')
        )

    def create(self, request, *args, **kwargs):
        return Response({'detail': 'Use /api/fa/generate-suggestion/ to create a suggestion.'}, status=405)


class GenerateDepreciationSuggestionView(APIView):
    permission_classes = [RBACPermission]

    def post(self, request):
        retail      = getattr(request, 'retail', None)
        fiscal_year = getattr(request, 'fiscal_year', None)

        period_from_str = request.data.get('period_from')
        period_to_str   = request.data.get('period_to')
        label           = request.data.get('label', '').strip()
        fy_id           = request.data.get('fiscal_year_id')

        if not all([period_from_str, period_to_str, label]):
            return Response({'detail': 'period_from, period_to, and label are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            period_from = _dt.date.fromisoformat(period_from_str)
            period_to   = _dt.date.fromisoformat(period_to_str)
        except ValueError:
            return Response({'detail': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        if period_from > period_to:
            return Response({'detail': 'period_from must be before period_to.'}, status=status.HTTP_400_BAD_REQUEST)

        if fy_id:
            from mastersconfig.models import FiscalYearMaster
            try:
                fiscal_year = FiscalYearMaster.objects.get(pk=fy_id, retail=retail)
            except FiscalYearMaster.DoesNotExist:
                return Response({'detail': 'Fiscal year not found.'}, status=status.HTTP_404_NOT_FOUND)

        overlapping = DepreciationSuggestion.objects.filter(
            retail=retail, status='PENDING',
            period_from__lte=period_to, period_to__gte=period_from,
        ).exists()
        if overlapping:
            return Response(
                {'detail': 'A pending suggestion already covers this period. Approve or reject it first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lines_data = generate_suggestion_lines(retail, period_from, period_to)
        if not lines_data:
            return Response({'detail': 'No active fixed assets found for this retail.'}, status=status.HTTP_400_BAD_REQUEST)

        total = sum(d['calculated_amount'] for d in lines_data)

        with transaction.atomic():
            suggestion = DepreciationSuggestion.objects.create(
                retail=retail, fiscal_year=fiscal_year,
                label=label, period_from=period_from, period_to=period_to,
                total_amount=total,
            )
            DepreciationSuggestionLine.objects.bulk_create([
                DepreciationSuggestionLine(
                    suggestion=suggestion, asset=d['asset'],
                    opening_wdv=d['opening_wdv'], calculated_amount=d['calculated_amount'],
                    approved_amount=d['approved_amount'], overridden=d['overridden'],
                    narration=d['narration'],
                )
                for d in lines_data
            ])

        suggestion.refresh_from_db()
        return Response(DepreciationSuggestionSerializer(suggestion).data, status=status.HTTP_201_CREATED)


class UpdateSuggestionLineView(APIView):
    permission_classes = [RBACPermission]

    def patch(self, request, pk):
        retail = getattr(request, 'retail', None)
        try:
            line = DepreciationSuggestionLine.objects.select_related('suggestion__retail').get(pk=pk)
        except DepreciationSuggestionLine.DoesNotExist:
            return Response({'detail': 'Line not found.'}, status=status.HTTP_404_NOT_FOUND)

        if line.suggestion.retail != retail:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if line.suggestion.status != 'PENDING':
            return Response({'detail': 'Only PENDING suggestions can be edited.'}, status=status.HTTP_400_BAD_REQUEST)

        new_amount = request.data.get('approved_amount')
        narration  = request.data.get('narration')

        if new_amount is not None:
            try:
                line.approved_amount = Decimal(str(new_amount))
            except (InvalidOperation, ValueError):
                return Response({'detail': 'Invalid amount.'}, status=status.HTTP_400_BAD_REQUEST)
            line.overridden = (line.approved_amount != line.calculated_amount)

        if narration is not None:
            line.narration = narration[:200]

        line.save(update_fields=['approved_amount', 'overridden', 'narration'])

        total = (
            DepreciationSuggestionLine.objects
            .filter(suggestion=line.suggestion)
            .aggregate(t=_Sum('approved_amount'))
        )['t'] or Decimal('0')
        line.suggestion.total_amount = total
        line.suggestion.save(update_fields=['total_amount'])

        return Response(DepreciationSuggestionLineSerializer(line).data)


class ApproveDepreciationSuggestionView(APIView):
    permission_classes = [RBACPermission]

    def post(self, request, pk):
        retail      = getattr(request, 'retail', None)
        fiscal_year = getattr(request, 'fiscal_year', None)

        try:
            suggestion = (
                DepreciationSuggestion.objects
                .prefetch_related('lines__asset')
                .select_related('retail', 'fiscal_year')
                .get(pk=pk, retail=retail)
            )
        except DepreciationSuggestion.DoesNotExist:
            return Response({'detail': 'Suggestion not found.'}, status=status.HTTP_404_NOT_FOUND)

        if suggestion.status != 'PENDING':
            return Response({'detail': f'Suggestion is already {suggestion.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        if suggestion.fiscal_year:
            fiscal_year = suggestion.fiscal_year

        try:
            fa_settings = retail.fa_settings
        except FixedAssetSettings.DoesNotExist:
            return Response({'detail': 'Fixed Asset Settings not configured. Set up ledgers first.'}, status=status.HTTP_400_BAD_REQUEST)

        if not fa_settings.default_depreciation_expense_ldgr or not fa_settings.default_accum_depreciation_ldgr:
            return Response(
                {'detail': 'Both Depreciation Expense and Accumulated Depreciation ledgers must be set in Fixed Asset Settings.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lines = list(suggestion.lines.select_related(
            'asset__accum_depreciation_ledger', 'asset__depreciation_expense_ledger'
        ).all())
        total_approved = sum(l.approved_amount for l in lines)

        if total_approved <= 0:
            return Response({'detail': 'Total approved amount must be > 0.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            voucher_no = get_next_bill_number(retail, VoucherType.depreciation, fiscal_year)
            voucher = VoucherMain.objects.create(
                date=_dt.date.today(), voucher_no=voucher_no,
                narration=suggestion.label[:150], amount=total_approved,
                voucher_type=VoucherType.depreciation, retail=retail, fiscal_year=fiscal_year,
            )

            vd_rows = []
            for line in lines:
                if line.approved_amount <= 0:
                    continue
                exp_ldgr   = line.asset.depreciation_expense_ledger or fa_settings.default_depreciation_expense_ldgr
                accum_ldgr = line.asset.accum_depreciation_ledger    or fa_settings.default_accum_depreciation_ldgr
                vd_rows.append(VoucherDetail(
                    voucher_main=voucher, voucher_no=voucher_no,
                    voucher_type=VoucherType.depreciation, account=exp_ldgr,
                    debit=line.approved_amount, credit=Decimal('0'),
                ))
                vd_rows.append(VoucherDetail(
                    voucher_main=voucher, voucher_no=voucher_no,
                    voucher_type=VoucherType.depreciation, account=accum_ldgr,
                    debit=Decimal('0'), credit=line.approved_amount,
                ))
            # bulk_create_with_history ensures the historical_voucherdetail
            # rows are also written — plain bulk_create skips Django signals
            # and the audit log would otherwise miss every depreciation posting.
            VoucherDetail.objects.bulk_create_with_history(vd_rows, VoucherDetail)

            for line in lines:
                if line.approved_amount <= 0:
                    continue
                asset = line.asset
                asset.accumulated_depreciation += line.approved_amount
                if asset.is_fully_depreciated:
                    asset.status = 'FULLY_DEPRECIATED'
                asset.save(update_fields=['accumulated_depreciation', 'status'])

            suggestion.voucher      = voucher
            suggestion.status       = 'APPROVED'
            suggestion.total_amount = total_approved
            suggestion.approved_at  = _tz.now()
            suggestion.approved_by  = request.user
            suggestion.save(update_fields=['voucher', 'status', 'total_amount', 'approved_at', 'approved_by'])

        suggestion.refresh_from_db()
        return Response(DepreciationSuggestionSerializer(suggestion).data)


class RejectDepreciationSuggestionView(APIView):
    permission_classes = [RBACPermission]

    def post(self, request, pk):
        retail = getattr(request, 'retail', None)
        try:
            suggestion = DepreciationSuggestion.objects.get(pk=pk, retail=retail)
        except DepreciationSuggestion.DoesNotExist:
            return Response({'detail': 'Suggestion not found.'}, status=status.HTTP_404_NOT_FOUND)

        if suggestion.status != 'PENDING':
            return Response({'detail': f'Suggestion is already {suggestion.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        suggestion.status = 'REJECTED'
        suggestion.save(update_fields=['status'])
        return Response({'detail': 'Suggestion rejected.', 'id': suggestion.id})


class FASettingsView(APIView):
    permission_classes = [RBACPermission]

    def get(self, request):
        retail = getattr(request, 'retail', None)
        obj, _ = FixedAssetSettings.objects.get_or_create(retail=retail)
        return Response(FixedAssetSettingsSerializer(obj).data)

    def put(self, request):
        retail = getattr(request, 'retail', None)
        obj, _ = FixedAssetSettings.objects.get_or_create(retail=retail)
        ser = FixedAssetSettingsSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class ITBlockRatesView(APIView):
    permission_classes = [RBACPermission]

    def get(self, request):
        data = [
            {'key': k, 'label': v[0], 'rate': str(v[1])}
            for k, v in IT_BLOCK_RATES.items()
        ]
        return Response(data)


class PnlGroupLedgersView(APIView):
    """Return individual ledger balances for a given account group in a P&L date range."""

    def get(self, request):
        retail = _get_retail_for_report(request)
        if retail == 'FORBIDDEN':
            return Response({"error": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        group_id = request.query_params.get("group_id")
        start_date = request.query_params.get("start_date", "2000-01-01")
        end_date = request.query_params.get("end_date", str(date.today()))

        if not group_id:
            return Response({"error": "group_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            group = Account.objects.get(pk=group_id)
        except Account.DoesNotExist:
            return Response({"ledgers": []})

        # Include the group itself and all descendant groups
        all_groups = [group] + get_all_descendants(group)
        ledgers = Ledger.objects.filter(ac_group__in=all_groups)

        base_filter = {
            'account__in': ledgers,
            'voucher_main__date__range': [start_date, end_date],
        }
        if retail:
            base_filter['voucher_main__retail'] = retail

        # Net balance from voucher transactions
        txn_balances = (
            VoucherDetail.objects
            .filter(**base_filter)
            .values('account_id')
            .annotate(net=Sum(F('credit') - F('debit'), output_field=DecimalField()))
        )
        txn_map = {row['account_id']: row['net'] or Decimal(0) for row in txn_balances}

        # Opening balances
        ob_filter = {'ldgr__in': ledgers}
        if retail:
            ob_filter['retail'] = retail
        ob_balances = (
            LedgerOpenBalance.objects
            .filter(**ob_filter)
            .values('ldgr_id')
            .annotate(net=Sum(F('credit') - F('debit'), output_field=DecimalField()))
        )
        ob_map = {row['ldgr_id']: row['net'] or Decimal(0) for row in ob_balances}

        result = []
        for ldgr in ledgers.order_by('ac_name'):
            balance = txn_map.get(ldgr.id, Decimal(0)) + ob_map.get(ldgr.id, Decimal(0))
            if balance != 0:
                result.append({'id': ldgr.id, 'ac_name': ldgr.ac_name, 'balance': balance})

        return Response({"ledgers": result})


class PnlLedgerTransactionsView(APIView):
    """Return voucher-detail transactions for a single ledger in a P&L date range."""

    def get(self, request):
        retail = _get_retail_for_report(request)
        if retail == 'FORBIDDEN':
            return Response({"error": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        ledger_id = request.query_params.get("ledger_id")
        start_date = request.query_params.get("start_date", "2000-01-01")
        end_date = request.query_params.get("end_date", str(date.today()))

        if not ledger_id:
            return Response({"error": "ledger_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        txn_filter = {
            'account_id': ledger_id,
            'voucher_main__date__range': [start_date, end_date],
        }
        if retail:
            txn_filter['voucher_main__retail'] = retail

        txns = (
            VoucherDetail.objects
            .filter(**txn_filter)
            .order_by('voucher_main__date', 'voucher_main__id')
            .values(
                'voucher_main__date',
                'voucher_main__voucher_no',
                'voucher_main__voucher_type',
                'voucher_main__narration',
                'debit',
                'credit',
            )
        )

        return Response({"transactions": list(txns)})
