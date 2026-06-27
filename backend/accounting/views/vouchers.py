from datetime import date, datetime

from django.db import transaction
from django.utils import timezone

from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from global_vars import VoucherType
from userauth.views import RetailBaseViewset

from ..models import *
from ..models import Account
from ..serializers import (
    GoldCashSerializder,
    JournalEntrySerializer,
    LedgerLightSerializer,
)
from ..utils import *


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
    from accounting.models import CreditDebitNote
    cn = CreditDebitNote.objects.filter(ac_voucher=voucher).first()
    if cn:
        return ('Credit/Debit Note', cn.note_no)
    if voucher.voucher_type == 'DEPR':
        return ('Depreciation', voucher.narration or voucher.voucher_no)

    # ── Gold Scheme ──────────────────────────────────────────────────────────
    from goldscheme.models import SchemePayment
    sp = SchemePayment.objects.filter(voucher=voucher).first()
    if sp:
        return ('Scheme Payment', f"#{sp.id}")

    return None


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
        from ..utils import release_last_bill_number
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
        from ..signals import cancel_voucher
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
    from rest_framework.decorators import action as _drf_action
    @_drf_action(detail=True, methods=['patch'], url_path='link-order')
    def link_order(self, request, pk=None):
        """
        Link or unlink a RCPT/RCPT-SALE voucher to/from a CustomerOrder.
          PATCH body: { "customer_order": <order_pk> }  → link
          PATCH body: { "customer_order": null }        → release back to on-account
        Releasing is blocked when the advance has already been applied to a bill.
        """
        from django.db.models import Sum as _Sum
        from ..models import ReferenceBills as _RefBills
        from sales.models import CustomerOrder

        voucher = self.get_object()
        if voucher.voucher_type not in ('RCPT', 'RCPT-SALE'):
            return Response(
                {'detail': 'Only RCPT/RCPT-SALE vouchers can be linked to a customer order.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        co_id = request.data.get('customer_order')

        if co_id is None:
            # Release — block if advance already consumed
            applied = _RefBills.objects.filter(voucher=voucher).aggregate(
                s=_Sum('amount')
            )['s'] or 0
            if applied > 0:
                return Response(
                    {'detail': 'Cannot release: this advance has already been applied to a sales bill.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            voucher.customer_order = None
            voucher.save(update_fields=['customer_order'])
            return Response({'id': voucher.id, 'customer_order': None})

        # Link — resolve order (must belong to same retail)
        try:
            order = CustomerOrder.objects.get(pk=co_id, retail=voucher.retail)
        except CustomerOrder.DoesNotExist:
            return Response(
                {'detail': f'CustomerOrder id={co_id} not found.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        voucher.customer_order = order
        voucher.save(update_fields=['customer_order'])
        return Response({
            'id': voucher.id,
            'customer_order': order.id,
            'order_no': order.order_no,
        })

    from rest_framework.decorators import action as _drf_action
    @_drf_action(detail=True, methods=['patch'], url_path='allocate-bills')
    def allocate_bills(self, request, pk=None):
        """
        Post-facto bill allocation for RCPT/PMNT vouchers.
        Body: { "kind": "sales"|"purchase", "allocations": [{"bill_id": pk, "amount": "100.00"}, ...] }
        Finds unallocated party legs, splits them per invoice, and updates due_amt.
        """
        from decimal import Decimal as _D
        from django.db.models import Q as _Q
        from ..models import VoucherDetail as _VD, ReferenceBills as _RB

        voucher = self.get_object()
        kind = request.data.get('kind')
        allocations = request.data.get('allocations', [])

        if not allocations:
            return Response({'detail': 'No allocations provided.'}, status=status.HTTP_400_BAD_REQUEST)

        if kind == 'sales' and voucher.voucher_type not in ('RCPT', 'RCPT-SALE'):
            return Response({'detail': 'Sales allocation requires a RCPT/RCPT-SALE voucher.'}, status=status.HTTP_400_BAD_REQUEST)
        if kind == 'purchase' and voucher.voucher_type != 'PMNT':
            return Response({'detail': 'Purchase allocation requires a PMNT voucher.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            if kind == 'sales':
                from sales.models import SalesVou as _SV
                unalloc_lines = list(voucher.transactions.filter(
                    credit__gt=0, ref_sales_vou__isnull=True,
                ).filter(_Q(ref_bill_no='') | _Q(ref_bill_no__isnull=True)))
                total_unalloc = sum(l.credit for l in unalloc_lines)
                alloc_total = sum(_D(str(a['amount'])) for a in allocations)
                if alloc_total > total_unalloc + _D('0.01'):
                    return Response({'detail': f'Allocation ₹{alloc_total} exceeds unallocated ₹{total_unalloc}.'}, status=status.HTTP_400_BAD_REQUEST)
                party_acct = unalloc_lines[0].account if unalloc_lines else None
                if not party_acct:
                    return Response({'detail': 'No unallocated party lines found on this voucher.'}, status=status.HTTP_400_BAD_REQUEST)
                _VD.objects.filter(id__in=[l.id for l in unalloc_lines]).delete()
                for alloc in allocations:
                    amt = _D(str(alloc['amount']))
                    if amt <= 0:
                        continue
                    try:
                        sv = _SV.objects.select_for_update().get(pk=alloc['bill_id'], retail=voucher.retail)
                    except _SV.DoesNotExist:
                        raise ValidationError(f"Invoice id={alloc['bill_id']} not found.")
                    if amt > sv.due_amt + _D('0.01'):
                        raise ValidationError(f"Allocation ₹{amt} exceeds outstanding ₹{sv.due_amt} on {sv.billno}.")
                    vd = _VD.objects.create(
                        voucher_main=voucher, voucher_no=voucher.voucher_no,
                        voucher_type=voucher.voucher_type, account=party_acct,
                        debit=_D('0'), credit=amt,
                        ref_sales_vou=sv, ref_bill_no=sv.billno,
                    )
                    _RB.objects.create(ldgr=party_acct, voucher=voucher, amount=amt, ref_bill=vd, ref_bill_txt=sv.billno)
                    sv.due_amt = max(_D('0'), sv.due_amt - amt)
                    sv.save(update_fields=['due_amt'])
                remainder = total_unalloc - alloc_total
                if remainder > _D('0.005'):
                    _VD.objects.create(
                        voucher_main=voucher, voucher_no=voucher.voucher_no,
                        voucher_type=voucher.voucher_type, account=party_acct,
                        debit=_D('0'), credit=remainder, ref_bill_no='',
                    )
            else:
                from purchase.models import PurchaseVoucher as _PV
                unalloc_lines = list(voucher.transactions.filter(
                    debit__gt=0, ref_purchase_vou__isnull=True,
                ).filter(_Q(ref_bill_no='') | _Q(ref_bill_no__isnull=True)))
                total_unalloc = sum(l.debit for l in unalloc_lines)
                alloc_total = sum(_D(str(a['amount'])) for a in allocations)
                if alloc_total > total_unalloc + _D('0.01'):
                    return Response({'detail': f'Allocation ₹{alloc_total} exceeds unallocated ₹{total_unalloc}.'}, status=status.HTTP_400_BAD_REQUEST)
                party_acct = unalloc_lines[0].account if unalloc_lines else None
                if not party_acct:
                    return Response({'detail': 'No unallocated party lines found on this voucher.'}, status=status.HTTP_400_BAD_REQUEST)
                _VD.objects.filter(id__in=[l.id for l in unalloc_lines]).delete()
                for alloc in allocations:
                    amt = _D(str(alloc['amount']))
                    if amt <= 0:
                        continue
                    try:
                        pv = _PV.objects.select_for_update().get(pk=alloc['bill_id'], retail=voucher.retail)
                    except _PV.DoesNotExist:
                        raise ValidationError(f"Purchase invoice id={alloc['bill_id']} not found.")
                    if amt > pv.due_amt + _D('0.01'):
                        raise ValidationError(f"Allocation ₹{amt} exceeds outstanding ₹{pv.due_amt} on {pv.billno}.")
                    vd = _VD.objects.create(
                        voucher_main=voucher, voucher_no=voucher.voucher_no,
                        voucher_type=voucher.voucher_type, account=party_acct,
                        debit=amt, credit=_D('0'),
                        ref_purchase_vou=pv, ref_bill_no=pv.billno,
                    )
                    _RB.objects.create(ldgr=party_acct, voucher=voucher, amount=amt, ref_bill=vd, ref_bill_txt=pv.billno)
                    pv.due_amt = max(_D('0'), pv.due_amt - amt)
                    pv.save(update_fields=['due_amt'])
                remainder = total_unalloc - alloc_total
                if remainder > _D('0.005'):
                    _VD.objects.create(
                        voucher_main=voucher, voucher_no=voucher.voucher_no,
                        voucher_type=voucher.voucher_type, account=party_acct,
                        debit=remainder, credit=_D('0'), ref_bill_no='',
                    )

        return Response({'detail': 'Allocations saved.', 'voucher_id': voucher.id})

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
    from ..utils import peek_next_bill_number
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
    from ..utils import peek_next_bill_number
    bill_no = peek_next_bill_number(request.retail, "GC")
    return Response({"billno":bill_no})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_vou_no(request,type):
    from ..utils import peek_next_bill_number
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
    from ..utils import peek_next_bill_number
    bill_no = peek_next_bill_number(request.retail, "CG")
    return Response({"billno":bill_no})

class VoucherAttachmentListCreate(ListCreateAPIView):
    from ..serializers import VoucherAttachmentSerializer
    serializer_class = VoucherAttachmentSerializer
    from rest_framework.parsers import MultiPartParser
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        from ..models import VoucherAttachment
        voucher_id = self.request.query_params.get('voucher')
        if voucher_id and str(voucher_id).isdigit():
            return VoucherAttachment.objects.filter(voucher_id=int(voucher_id)).order_by('-uploaded_at')
        # Non-numeric or missing voucher param → empty queryset (don't 500)
        return VoucherAttachment.objects.none()


class VoucherAttachmentDelete(APIView):
    def delete(self, request, pk):
        from ..models import VoucherAttachment
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


class CreditDebitNoteViewSet(RetailBaseViewset):
    from ..models import CreditDebitNote
    from ..serializers import CreditDebitNoteSerializer
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
            from ..signals import cancel_voucher
            cancel_voucher(note.ac_voucher, user=request.user)
        from ..utils import release_last_bill_number
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
        company_gstin = (retail.gstin_master.gstin if retail.gstin_master else '') if retail else ''
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
        from ..signals import cancel_voucher
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
        from ..utils import peek_next_bill_number
        retail = request.retail
        next_no = peek_next_bill_number(retail, note_type)
        return Response({'next_no': next_no})

class UnallocatedVouchersView(APIView):
    """
    GET /accounting/api/unallocated-vouchers/?type=receipt|payment
    Receipt: RCPT (advance) with customer_order=NULL. RCPT-SALE vouchers are
             excluded — they are always tied to a specific sale invoice.
    Payment: PMNT with at least one debit line that has no ref_purchase_vou.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Q
        vtype = request.query_params.get('type', 'receipt')
        retail = request.retail

        if vtype == 'receipt':
            qs = (
                VoucherMain.objects
                .filter(
                    retail=retail,
                    voucher_type='RCPT',
                    status='posted',
                    customer_order__isnull=True,
                    transactions__credit__gt=0,
                    transactions__ref_sales_vou__isnull=True,
                )
                .prefetch_related('transactions__account')
                .distinct()
                .order_by('-date', '-id')
            )
            rows = []
            for v in qs:
                credit_lines = [
                    t for t in v.transactions.all()
                    if t.credit > 0 and not t.ref_sales_vou_id
                    and not (t.ref_bill_no or '').strip()
                ]
                unalloc = sum(t.credit for t in credit_lines)
                if unalloc <= 0:
                    continue
                party_line = credit_lines[0] if credit_lines else None
                rows.append({
                    'id': v.id,
                    'voucher_no': v.voucher_no,
                    'date': v.date.isoformat(),
                    'amount': float(v.amount),
                    'unallocated_amount': float(unalloc),
                    'party': party_line.account.ac_name if party_line else '',
                    'party_id': party_line.account.id if party_line else None,
                    'narration': v.narration or '',
                })
        else:
            qs = (
                VoucherMain.objects
                .filter(
                    retail=retail,
                    voucher_type='PMNT',
                    status='posted',
                    transactions__debit__gt=0,
                    transactions__ref_purchase_vou__isnull=True,
                )
                .prefetch_related('transactions__account')
                .distinct()
                .order_by('-date', '-id')
            )
            rows = []
            for v in qs:
                debit_lines = [
                    t for t in v.transactions.all()
                    if t.debit > 0 and not t.ref_purchase_vou_id
                    and not (t.ref_bill_no or '').strip()
                ]
                unalloc = sum(t.debit for t in debit_lines)
                if unalloc <= 0:
                    continue
                party_line = debit_lines[0] if debit_lines else None
                rows.append({
                    'id': v.id,
                    'voucher_no': v.voucher_no,
                    'date': v.date.isoformat(),
                    'amount': float(v.amount),
                    'unallocated_amount': float(unalloc),
                    'party': party_line.account.ac_name if party_line else '',
                    'party_id': party_line.account.id if party_line else None,
                    'narration': v.narration or '',
                })

        return Response(rows)


class UnlinkedReceiptsView(APIView):
    """
    GET /accounting/api/unlinked-receipts/?ldgr_id=<ledger_pk>
    Returns posted RCPT/RCPT-SALE vouchers for a customer ledger that have no
    CustomerOrder FK, together with how much of each is still unallocated.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from decimal import Decimal as _D
        from django.db.models import Sum as _Sum
        from ..models import ReferenceBills as _RefBills

        ldgr_id = request.query_params.get("ldgr_id")
        if not ldgr_id:
            return Response({"detail": "ldgr_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        retail = request.retail
        vouchers = (
            VoucherMain.objects
            .filter(
                retail=retail,
                voucher_type__in=["RCPT", "RCPT-SALE"],
                status="posted",
                customer_order__isnull=True,
                transactions__account_id=ldgr_id,
            )
            .distinct()
            .order_by("date", "id")
        )

        rows = []
        for v in vouchers:
            applied = (
                _RefBills.objects.filter(voucher=v)
                .aggregate(s=_Sum("amount"))["s"] or _D("0")
            )
            remaining = _D(str(v.amount)) - _D(str(applied))
            if remaining <= 0:
                continue
            rows.append({
                "id": v.id,
                "voucher_no": v.voucher_no,
                "date": v.date.isoformat(),
                "amount": float(v.amount),
                "amount_remaining": float(remaining),
                "narration": v.narration or "",
            })
        return Response(rows)
