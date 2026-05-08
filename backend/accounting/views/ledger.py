from datetime import date, datetime
from decimal import Decimal

from django.db.models import Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce

from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from userauth.views import RetailBaseViewset

from ..models import *
from ..models import Account, VoucherDetail
from ..serializers import (
    AccountSerializer,
    LedgerOpenBalanceSerializer,
)
from ..utils import *


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
        from sales.models import SalesVou
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cash_total_of_ledger(request, ledger_id):
    total_debit = VoucherDetail.objects.filter(
    voucher_main_id__in=VoucherDetail.objects.filter(account=ledger_id).values('voucher_main_id'),
    account__in=RetailMaster.objects.values_list('cash_ldgr_id', flat=True).exclude(cash_ldgr_id=None)
    ).aggregate(Sum('debit'))['debit__sum']

    return Response({'total_cash': total_debit or 0})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ledger_current_balance(request, ledger_id):
    """
    Returns the current running balance for a ledger (opening + all posted txns).

    balance = opening(debit−credit) + sum(txn debit) − sum(txn credit)

    For asset accounts (Cash / Bank) a positive value means available funds.
    Used by the frontend to cap the payable amount in Payment vouchers.
    """
    try:
        ledger = Ledger.objects.get(pk=ledger_id, retail=request.retail)
    except Ledger.DoesNotExist:
        return Response({"error": "Ledger not found."}, status=status.HTTP_404_NOT_FOUND)

    opening = LedgerOpenBalance.objects.filter(
        ldgr=ledger, retail=request.retail
    ).aggregate(
        total=Coalesce(
            Sum(F('debit') - F('credit'), output_field=DecimalField(max_digits=20, decimal_places=4)),
            Value(Decimal('0'))
        )
    )['total'] or Decimal('0')

    txn = VoucherDetail.objects.filter(
        account=ledger,
        voucher_main__retail=request.retail,
    ).aggregate(
        total_debit=Coalesce(Sum('debit'),  Value(Decimal('0'))),
        total_credit=Coalesce(Sum('credit'), Value(Decimal('0'))),
    )

    balance = opening + txn['total_debit'] - txn['total_credit']
    return Response({
        'ledger_id':   ledger_id,
        'ledger_name': ledger.ac_name,
        'balance':     balance,
    })


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
