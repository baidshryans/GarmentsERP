import logging

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from userauth import views

from ..models import *
from ..serializers import SaleReturnSerializer, SaleVoucherToReturnSerializer

logger = logging.getLogger(__name__)


@api_view()
@permission_classes([IsAuthenticated])
def get_sale_voucher_for_return(request):
    bill_no = request.query_params.get('bill_no')
    if not bill_no:
        return Response({"error": "Bill number is required"}, status=400)
    obj = SalesVou.objects.get(billno=bill_no)
    serializer = SaleVoucherToReturnSerializer(obj)
    return Response(serializer.data)


class SalesReturnViewset(views.RetailBaseViewset):
    queryset = SaleReturn.objects.select_related('ldgr', 'ac_voucher', 'retail').prefetch_related(
        'salereturnitem_set__salereturndetails_set'
    ).all()
    serializer_class = SaleReturnSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]

    search_fields = ['billno', 'ldgr__ac_name']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    ordering = ['-date1', '-id']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def _resolve_fiscal_year(self, retail, voucher_date):
        from mastersconfig.models import FiscalYearMaster
        if voucher_date:
            fy = FiscalYearMaster.objects.filter(
                retail=retail, fy_start__lte=voucher_date, fy_end__gte=voucher_date,
            ).first()
            if fy:
                return fy
        return getattr(retail, 'active_fy', None)

    def perform_create(self, serializer):
        retail = getattr(self.request, 'retail', None)
        if not retail:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"retail": "Missing or invalid X-RETAIL-ID header."})
        voucher_date = serializer.validated_data.get('date1')
        fiscal_year = self._resolve_fiscal_year(retail, voucher_date)
        serializer.save(retail=retail, fiscal_year=fiscal_year)

    def _check_sale_return_mutable(self, instance, action):
        from rest_framework.exceptions import ValidationError
        if instance.ac_voucher is not None and instance.ac_voucher.status == 'posted':
            raise ValidationError(
                f"Sale return '{instance.billno}' cannot be {action} because its accounting entry is posted."
            )

    def perform_destroy(self, instance):
        self._check_sale_return_mutable(instance, 'deleted')
        from accounting.utils import release_last_bill_number
        from sales.serializers import _refresh_order_status
        retail = instance.retail
        fiscal_year = instance.fiscal_year
        billno = instance.billno
        # Capture customer_order reference before deletion (FK may become null after)
        _sv = instance.sales_voucher_ref
        _co = getattr(_sv, 'customer_order', None) if _sv else None
        super().perform_destroy(instance)
        release_last_bill_number(retail, 'SR', billno, fiscal_year)
        if _co:
            _refresh_order_status(_co)

    def perform_update(self, serializer):
        from rest_framework.exceptions import ValidationError
        retail = getattr(self.request, 'retail', None)
        if not retail:
            raise ValidationError({"retail": "Missing or invalid X-RETAIL-ID header."})
        self._check_sale_return_mutable(serializer.instance, 'edited')
        voucher_date = serializer.validated_data.get('date1') or serializer.instance.date1
        fiscal_year = self._resolve_fiscal_year(retail, voucher_date)
        serializer.save(retail=retail, fiscal_year=fiscal_year)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sale_return_print_data(request, pk):
    """Return fully-computed credit-note JSON for a SaleReturn (for React print)."""
    try:
        sr = SaleReturn.objects.select_related(
            'ldgr', 'retail', 'retail__state', 'retail__branch__company',
            'retail__gstin_master', 'sales_voucher_ref',
        ).prefetch_related(
            'salereturnitem_set__item',
            'salereturnitem_set__purity',
            'salereturnitem_set__salereturndetails_set__item',
            'salereturnitem_set__salereturndetails_set__metal_purity',
        ).get(pk=pk, retail=request.retail)
    except SaleReturn.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        retail = request.retail
        ldgr   = sr.ldgr

        # ── Company info ──────────────────────────────────────────────────────
        company = None
        if retail.branch_id and retail.branch and retail.branch.company_id:
            company = retail.branch.company
        company_address = ', '.join(filter(None, [
            retail.address_line1, retail.address_line2, retail.address_line3,
            retail.city, retail.pincode,
        ]))
        _gm = retail.gstin_master
        company_gstin = (_gm.gstin if _gm else '') or ''

        # ── Customer info ─────────────────────────────────────────────────────
        customer_address = ', '.join(filter(None, [ldgr.add1, ldgr.add2, ldgr.city, ldgr.pincode]))
        # Resolve 2-letter state abbreviation → full state name
        _STATE_ABBR = {
            "AN": "Andaman and Nicobar Islands", "AP": "Andhra Pradesh",
            "AR": "Arunachal Pradesh", "AS": "Assam", "BR": "Bihar",
            "CG": "Chhattisgarh", "CT": "Chhattisgarh", "CH": "Chandigarh",
            "DD": "Daman and Diu", "DL": "Delhi",
            "DN": "Dadra and Nagar Haveli", "GA": "Goa", "GJ": "Gujarat",
            "HP": "Himachal Pradesh", "HR": "Haryana", "JH": "Jharkhand",
            "JK": "Jammu and Kashmir", "KA": "Karnataka", "KL": "Kerala",
            "LA": "Ladakh", "LD": "Lakshadweep", "MH": "Maharashtra",
            "ML": "Meghalaya", "MN": "Manipur", "MP": "Madhya Pradesh",
            "MZ": "Mizoram", "NL": "Nagaland", "OD": "Odisha", "OR": "Odisha",
            "PB": "Punjab", "PY": "Puducherry", "RJ": "Rajasthan",
            "SK": "Sikkim", "TG": "Telangana", "TN": "Tamil Nadu",
            "TR": "Tripura", "UK": "Uttarakhand", "UT": "Uttarakhand",
            "UP": "Uttar Pradesh", "WB": "West Bengal",
        }
        _raw_state = ldgr.state or ''
        _state_name = _STATE_ABBR.get(_raw_state.upper(), _raw_state)

        # ── Build items list ──────────────────────────────────────────────────
        items_data = []
        for ri in sr.salereturnitem_set.all():
            sub_rows = []
            for d in ri.salereturndetails_set.all():
                parts = []
                _uom = d.item.uom if d.item else 'Gm'
                if d.item:
                    parts.append(d.item.item_name or d.item.short_code)
                if d.metal_purity:
                    parts.append(d.metal_purity.purity)
                if _uom == 'Ct':
                    if d.ct:
                        parts.append(f'CT: {float(d.ct):.3f}ct')
                elif d.gw:
                    parts.append(f'GW: {float(d.gw):.3f}g')
                if d.tunch:
                    parts.append(f'Tunch: {float(d.tunch):.2f}%')
                if d.rate:
                    parts.append(f'@ ₹{float(d.rate):.0f}')
                sub_rows.append({
                    'text':         ' | '.join(parts),
                    'uom':          _uom,
                    'pcs':          d.pcs,
                    'ct':           float(d.ct or 0),
                    'gw':           float(d.gw or 0),
                    'rate':         float(d.rate or 0),
                    'amount':       float(d.amount or 0),
                    'item_type':    d.item.item_type if d.item else '',
                    'metal_purity': d.metal_purity.purity if d.metal_purity else '',
                })

            items_data.append({
                'sn':        len(items_data) + 1,
                'item_name': ri.item.item_name if ri.item else '',
                'purity':    ri.purity.purity if ri.purity else '',
                'pcs':       ri.pcs or 0,
                'gw':        float(ri.gw or 0),
                'making':    float(ri.making_value or 0),
                'amount':    sum(r['amount'] for r in sub_rows) + float(ri.making_value or 0),
                'sub_rows':  sub_rows,
            })

        # ── Tax & totals ──────────────────────────────────────────────────────
        taxable  = float(sr.taxable_value or 0)
        cgst_amt = round(taxable * float(sr.cgst_per or 0) / 100, 2)
        sgst_amt = round(taxable * float(sr.sgst_per or 0) / 100, 2)
        igst_amt = round(taxable * float(sr.igst_per or 0) / 100, 2)
        total    = round(taxable + cgst_amt + sgst_amt + igst_amt, 2)

        # ── Original invoice reference ─────────────────────────────────────────
        ref_billno  = sr.sales_voucher_ref.billno if sr.sales_voucher_ref else ''
        ref_gst_no  = sr.original_sale_gst_billno or (
            sr.sales_voucher_ref.gst_billno if sr.sales_voucher_ref else ''
        )
        ref_date = str(sr.sales_voucher_ref.date1) if sr.sales_voucher_ref and sr.sales_voucher_ref.date1 else ''

        return Response({
            'note_type':        'CN',
            'company_name':     (company.company_name if company else retail.retail_name) or '',
            'company_legal_name': (_gm.legal_name if _gm else '') or '',
            'company_address':  company_address,
            'company_gstin':    company_gstin,
            'company_state':    getattr(retail.state, 'name', '') if retail.state else '',
            'company_phone':    retail.phone or (company.phone if company else '') or '',
            'company_email':    retail.email or (company.email if company else '') or '',
            'company_pan':      (company.pan if company else '') or '',
            'company_cin':      (company.cin if company else '') or '',
            'note_no':          sr.billno or '',
            'date':             str(sr.date1) if sr.date1 else '',
            'party_name':       ldgr.ac_name or '',
            'party_address':    customer_address,
            'party_gstin':      ldgr.gst or '',
            'party_state':      _state_name,
            'party_mobile':     ldgr.mobile1 or '',
            'ref_invoice_no':   f'{ref_billno}{(" / GST: " + ref_gst_no) if ref_gst_no else ""}',
            'ref_invoice_date': ref_date,
            'reason':           'Customer Return',
            'items':            items_data,
            'mrp':              float(sr.mrp or 0),
            'discount':         float(sr.discount or 0),
            'taxable_value':    round(taxable, 2),
            'cgst_per':         float(sr.cgst_per or 0), 'cgst_amt': cgst_amt,
            'sgst_per':         float(sr.sgst_per or 0), 'sgst_amt': sgst_amt,
            'igst_per':         float(sr.igst_per or 0), 'igst_amt': igst_amt,
            'amount':           total,
            'adjustment_ledger': '',
        })
    except Exception as exc:
        logger.exception("sale_return_print_data failed for pk=%s: %s", pk, exc)
        return Response(
            {'detail': f'Print data error: {exc}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
