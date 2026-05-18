import json
import logging
import decimal
from datetime import datetime

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.db.models import F, Value, ExpressionWrapper, DecimalField, Case, When, Exists, OuterRef, Sum, Q, Subquery, CharField
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from goldrates.models import PurityMaster
from contacts.models import Ledger, LedgerRole
from mastersconfig.models import Item
from inventory.models import BarcodeTransaction
from accounting.serializers import SaleVoucherLedgerSerializer
from userauth import views

from ..models import *
from ..utils import DecimalEncoder
from ..serializers import SalesApprovalSerializer, SalesVouSerializer, SalesApprovalReturnSerializer

logger = logging.getLogger(__name__)


class SalesVoucherViewset(views.RetailBaseViewset):
    queryset = SalesVou.objects.select_related(
        'ldgr', 'sales_person', 'sales_person2', 'ac_voucher', 'retail'
    ).prefetch_related(
        'salesvouitem_set__item',
        'salesvouitem_set__barcode',
        'salesvouitem_set__main_item_set__item',
        'salesvouitem_set__main_item_set__packet',
        'salesvouitemdetails_set__item',
        'salesvouitemdetails_set__packet',
        'bank_details',
    ).all()
    serializer_class = SalesVouSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]

    search_fields = ['billno', 'ldgr__ac_name']

    def get_queryset(self):
        from ..models import EWayBill
        return super().get_queryset().annotate(
            has_eway_bill=Exists(
                EWayBill.objects.filter(sales_vou=OuterRef('pk'), status='GENERATED')
            )
        )

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    ordering = ['-date1', '-id']

    def _resolve_fiscal_year(self, retail, voucher_date):
        """Return the FiscalYearMaster whose date range covers voucher_date.
        Falls back to retail.active_fy when no matching FY is found."""
        from mastersconfig.models import FiscalYearMaster
        if voucher_date:
            fy = FiscalYearMaster.objects.filter(
                retail=retail,
                fy_start__lte=voucher_date,
                fy_end__gte=voucher_date,
            ).first()
            if fy:
                return fy
        return getattr(retail, 'active_fy', None)

    def perform_create(self, serializer):
        from accounting.utils import get_next_bill_number
        from mastersconfig.models import SystemSettings
        retail = getattr(self.request, 'retail', None)
        if not retail:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"retail": "Missing or invalid X-RETAIL-ID header."})
        voucher_date = serializer.validated_data.get('date1')
        fiscal_year = self._resolve_fiscal_year(retail, voucher_date)
        save_kwargs = dict(retail=retail, fiscal_year=fiscal_year)
        if SystemSettings.get().enable_gst_bill:
            save_kwargs['gst_billno'] = get_next_bill_number(retail, "GST", fiscal_year)
        serializer.save(**save_kwargs)

    def _check_sales_vou_mutable(self, instance, action):
        from rest_framework.exceptions import ValidationError
        if instance.ret_status or instance.sale_returns.exists():
            raise ValidationError(
                f"Sales voucher '{instance.billno}' cannot be {action} because a sale return exists against it."
            )
        # Payment-received block applies to delete only. Edits are allowed
        # because the serializer rebuilds the sale's journal entry and
        # recomputes due_amt while preserving subsequent payment receipts,
        # keeping the ledger balance consistent.
        if action == 'deleted':
            bill_value = float(instance.total_bill_value or 0)
            if instance.ac_rec_voucher is not None or (bill_value > 0 and float(instance.due_amt or 0) < bill_value):
                raise ValidationError(
                    f"Sales voucher '{instance.billno}' cannot be {action} because a payment has been received against it."
                )

    def perform_destroy(self, instance):
        self._check_sales_vou_mutable(instance, 'deleted')
        from accounting.utils import release_last_bill_number
        from inventory.utils import guard_no_later_barcode_transaction
        barcode_ids = list(instance.salesvouitem_set.values_list('barcode_id', flat=True))
        guard_no_later_barcode_transaction(barcode_ids, instance.billno)
        retail = instance.retail
        fiscal_year = instance.fiscal_year
        billno = instance.billno
        gst_billno = instance.gst_billno
        super().perform_destroy(instance)
        release_last_bill_number(retail, 'SV', billno, fiscal_year)
        if gst_billno:
            release_last_bill_number(retail, 'GST', gst_billno, fiscal_year)

    def perform_update(self, serializer):
        from rest_framework.exceptions import ValidationError
        retail = getattr(self.request, 'retail', None)
        if not retail:
            raise ValidationError({"retail": "Missing or invalid X-RETAIL-ID header."})
        self._check_sales_vou_mutable(serializer.instance, 'edited')
        voucher_date = serializer.validated_data.get('date1') or serializer.instance.date1
        fiscal_year = self._resolve_fiscal_year(retail, voucher_date)
        serializer.save(retail=retail, fiscal_year=fiscal_year)


class GSTInputRegisterView(APIView):
    def get(self, request, format=None):
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if not start_date_str or not end_date_str:
            return Response({"detail": "start_date and end_date query parameters are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."},
                            status=status.HTTP_400_BAD_REQUEST)

        from purchase.models import PurchaseVoucher
        gstin_id = request.query_params.get('gstin')
        pv_qs = PurchaseVoucher.objects.filter(date1__range=[start_date, end_date])
        if gstin_id:
            pv_qs = pv_qs.filter(gstin_ref_id=gstin_id)
        vouchers = pv_qs.select_related('ldgr').annotate(
            _party_name=F('ldgr__ac_name'),
            _gstin=F('ldgr__gst'),
            _pan=F('ldgr__pan'),
            _before_tax=Case(
                When(discount_amt__isnull=False, then=ExpressionWrapper(F('discount_amt') * -1, output_field=DecimalField())),
                default=Value(0),
                output_field=DecimalField()
            ),
            _taxable_amount=ExpressionWrapper(
                F('item_total') - Coalesce(F('discount_amt'), Value(0, output_field=DecimalField())),
                output_field=DecimalField()
            ),
            _utgst=Value(0, output_field=DecimalField()),
            _add_less=Coalesce(F('round_off'), Value(0, output_field=DecimalField())),
        ).values(
            'billno', 'bill_value', 'ref_no', 'sgst', 'cgst', 'igst', 'item_total',
            date=F('date1'),
            bill_no=F('billno'),
            party_name=F('_party_name'),
            gstin=F('_gstin'),
            pan=F('_pan'),
            group_value=F('item_total'),
            before_tax=F('_before_tax'),
            taxable_amount=F('_taxable_amount'),
            utgst=F('_utgst'),
            add_less=F('_add_less'),
        )

        return Response(list(vouchers))


class GSTOutputRegisterView(APIView):
    def get(self, request, format=None):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        gstin_id = request.query_params.get('gstin')

        # ── Subqueries: HSN, UOM, gross-weight from SalesVouItem ─────────────
        sv_hsn_sq = Subquery(
            SalesVouItem.objects.filter(billno=OuterRef('pk'))
            .values('item__hsn_no__hsn_no')[:1],
            output_field=CharField()
        )
        sv_uom_sq = Subquery(
            SalesVouItem.objects.filter(billno=OuterRef('pk'))
            .values('item__uom')[:1],
            output_field=CharField()
        )
        sv_gw_sq = Subquery(
            SalesVouItem.objects.filter(billno=OuterRef('pk'))
            .values('billno')
            .annotate(s=Sum('gw', output_field=DecimalField()))
            .values('s'),
            output_field=DecimalField()
        )

        sales_qs = SalesVou.objects.filter(
            date1__range=[start_date, end_date]
        ).select_related('ldgr', 'ac_voucher')
        if gstin_id:
            sales_qs = sales_qs.filter(gstin_ref_id=gstin_id)

        _zero = Value(0, output_field=DecimalField())
        _taxable = ExpressionWrapper(
            Coalesce(F('mrp'), _zero) - Coalesce(F('discount'), _zero),
            output_field=DecimalField()
        )

        sales_annotated = sales_qs.annotate(
            vtype=F('ac_voucher__voucher_type'),
            partyname=F("ldgr__ac_name"),
            gstin=F("ldgr__gst"),
            pan=F("ldgr__pan"),
            billvalue=F("mrp"),
            discount_amt=Coalesce(F('discount'), _zero),
            taxableamount=_taxable,
            placeofsupply=F("place_of_supply"),
            add_less=Coalesce(F("round_off"), _zero),
            hsn=sv_hsn_sq,
            uom=sv_uom_sq,
            sale_gw=sv_gw_sq,
        ).annotate(
            cgst_amt=ExpressionWrapper(
                F('taxableamount') * F('cgst_per') / Value(100),
                output_field=DecimalField()
            ),
            sgst_amt=ExpressionWrapper(
                F('taxableamount') * F('sgst_per') / Value(100),
                output_field=DecimalField()
            ),
            igst_amt=ExpressionWrapper(
                F('taxableamount') * F('igst_per') / Value(100),
                output_field=DecimalField()
            ),
        ).values(
            "date1", "vtype", "gst_billno", "partyname", "gstin", "pan",
            "billvalue", "discount_amt", "taxableamount",
            "cgst_amt", "sgst_amt", "igst_amt",
            "sgst_per", "cgst_per", "igst_per",
            "placeofsupply", "add_less", "hsn", "uom", "sale_gw"
        )

        # ── SaleReturn subqueries ─────────────────────────────────────────────
        sr_hsn_sq = Subquery(
            SaleReturnItem.objects.filter(billno=OuterRef('pk'))
            .values('item__hsn_no__hsn_no')[:1],
            output_field=CharField()
        )
        sr_uom_sq = Subquery(
            SaleReturnItem.objects.filter(billno=OuterRef('pk'))
            .values('item__uom')[:1],
            output_field=CharField()
        )
        sr_gw_sq = Subquery(
            SaleReturnItem.objects.filter(billno=OuterRef('pk'))
            .values('billno')
            .annotate(s=Sum('gw', output_field=DecimalField()))
            .values('s'),
            output_field=DecimalField()
        )

        return_qs = SaleReturn.objects.filter(
            date1__range=[start_date, end_date]
        ).select_related('ldgr', 'ac_voucher')
        if gstin_id:
            return_qs = return_qs.filter(retail__gstin_master_id=gstin_id)

        _ret_taxable = ExpressionWrapper(
            Coalesce(F('mrp'), _zero) - Coalesce(F('discount'), _zero),
            output_field=DecimalField()
        )

        return_annotated = return_qs.annotate(
            vtype=F('ac_voucher__voucher_type'),
            partyname=F("ldgr__ac_name"),
            gstin=F("ldgr__gst"),
            pan=F("ldgr__pan"),
            billvalue=F("mrp"),
            discount_amt=Coalesce(F('discount'), _zero),
            taxableamount=_ret_taxable,
            add_less=_zero,
            hsn=sr_hsn_sq,
            uom=sr_uom_sq,
            sale_gw=sr_gw_sq,
        ).annotate(
            cgst_amt=ExpressionWrapper(
                F('taxableamount') * F('cgst_per') / Value(100),
                output_field=DecimalField()
            ),
            sgst_amt=ExpressionWrapper(
                F('taxableamount') * F('sgst_per') / Value(100),
                output_field=DecimalField()
            ),
            igst_amt=ExpressionWrapper(
                F('taxableamount') * F('igst_per') / Value(100),
                output_field=DecimalField()
            ),
        ).values(
            "date1", "vtype", "billno", "partyname", "gstin", "pan",
            "billvalue", "discount_amt", "taxableamount",
            "cgst_amt", "sgst_amt", "igst_amt",
            "sgst_per", "cgst_per", "igst_per",
            "add_less", "hsn", "uom", "sale_gw"
        )

        return Response({
            "salesvoucher": list(sales_annotated),
            "salesreturn": list(return_annotated)
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tcs_register(request):
    """
    TCS Register — Section 206C(1H) sales TCS.
    Returns all sales vouchers where TCS amount > 0, filtered by date range and section.
    """
    retail = request.retail
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    section = request.GET.get('section')

    qs = SalesVou.objects.filter(
        retail=retail,
        tcs_amt__gt=0
    ).select_related('ldgr', 'tcs_section')

    if from_date:
        qs = qs.filter(date1__gte=from_date)
    if to_date:
        qs = qs.filter(date1__lte=to_date)
    if section:
        qs = qs.filter(tcs_section__section_code=section)

    data = [{
        'bill_no': v.billno,
        'gst_bill_no': v.gst_billno or '',
        'date': v.date1,
        'customer': v.ldgr.ac_name if v.ldgr else '',
        'gstin': v.ldgr.gst or '' if v.ldgr else '',
        'pan': v.ldgr.pan or '' if v.ldgr else '',
        'section': v.tcs_section.section_code if v.tcs_section else '206C1H',
        'description': v.tcs_section.description if v.tcs_section else 'TCS on Sale of Goods',
        'taxable_value': float(v.mrp or 0),
        'tcs_rate': float(v.tcs_per or 0),
        'tcs_amt': float(v.tcs_amt or 0),
        'bill_value': float(v.mrp or 0) + float(v.tcs_amt or 0),
    } for v in qs]

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gstr1_report(request):
    """
    GSTR-1 data split into B2B, B2CL, B2CS, CDNR, CDNUR sections.
    Parameters: from_date, to_date (YYYY-MM-DD)
    """
    retail = request.retail
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    if not from_date or not to_date:
        return Response({"detail": "from_date and to_date are required."}, status=400)

    retail_state_code = retail.state.code if retail and retail.state else ''

    vouchers = SalesVou.objects.filter(
        retail=retail, date1__range=[from_date, to_date]
    ).select_related('ldgr', 'ldgr__state')

    # Pre-load dealer ledger IDs (single query) so we can determine B2B status
    # without per-voucher role lookups.  Dealers are inherently GST-registered
    # businesses, so their sales are always treated as B2B.
    dealer_ldgr_ids = set(
        LedgerRole.objects.filter(role='DL').values_list('ledger_id', flat=True)
    )

    b2b = {}      # keyed by GSTIN (or "DL_<id>" for dealers missing GSTIN)
    b2cl = []     # large unregistered inter-state invoices (≥ ₹2.5L)
    b2cs = {}     # small B2C grouped by pos + rate

    for v in vouchers:
        taxable = float(v.mrp or 0) - float(v.discount or 0)
        sgst    = round(taxable * float(v.sgst_per or 0) / 100, 2)
        cgst    = round(taxable * float(v.cgst_per or 0) / 100, 2)
        igst    = round(taxable * float(v.igst_per or 0) / 100, 2)
        gst_rate = float(v.igst_per or 0) or (float(v.sgst_per or 0) + float(v.cgst_per or 0))
        bill_val = round(taxable + sgst + cgst + igst, 2)

        customer_gstin = (v.ldgr.gst or '').strip() if v.ldgr else ''
        is_dealer = (v.ldgr_id in dealer_ldgr_ids) if v.ldgr else False
        # B2B if customer has a GST number OR is a registered dealer
        is_b2b = bool(customer_gstin) or is_dealer
        pos = v.place_of_supply or ''
        is_inter = pos != retail_state_code

        inv = {
            'inum': v.gst_billno or v.billno,
            'idt': str(v.date1),
            'val': bill_val,
            'pos': pos,
            'rchrg': 'N',
            'txval': round(taxable, 2),
            'rt': gst_rate,
            'iamt': igst, 'camt': cgst, 'samt': sgst, 'csamt': 0,
        }

        if is_b2b:
            # Prefer the actual GSTIN; for dealers without a GSTIN on file use a
            # synthetic key so their invoices still appear in the B2B section with
            # a 'missing_gstin' warning prompting the user to fill it in.
            b2b_key = customer_gstin if customer_gstin else f"DL_{v.ldgr_id}"
            if b2b_key not in b2b:
                entry = {
                    'ctin':  customer_gstin,
                    'cname': v.ldgr.ac_name if v.ldgr else '',
                    'inv':   [],
                    'txval': 0, 'iamt': 0, 'camt': 0, 'samt': 0,
                }
                if is_dealer and not customer_gstin:
                    entry['missing_gstin'] = True   # frontend can warn before filing
                b2b[b2b_key] = entry
            b2b[b2b_key]['inv'].append(inv)
            b2b[b2b_key]['txval'] += round(taxable, 2)
            b2b[b2b_key]['iamt']  += igst
            b2b[b2b_key]['camt']  += cgst
            b2b[b2b_key]['samt']  += sgst
        else:
            if is_inter and taxable >= 250000:
                b2cl.append({**inv})
            else:
                stype = 'INTER' if is_inter else 'INTRA'
                key = f"{stype}_{pos}_{gst_rate}"
                if key not in b2cs:
                    b2cs[key] = {
                        'sply_tp': stype,
                        'pos': pos,
                        'rt': gst_rate,
                        'txval': 0, 'iamt': 0, 'camt': 0, 'samt': 0, 'csamt': 0,
                    }
                b2cs[key]['txval'] += round(taxable, 2)
                b2cs[key]['iamt'] += igst
                b2cs[key]['camt'] += cgst
                b2cs[key]['samt'] += sgst

    # Credit / Debit notes
    returns_qs = SaleReturn.objects.filter(
        retail=retail, date1__range=[from_date, to_date]
    ).select_related('ldgr')

    cdnr = {}
    cdnur = []

    for r in returns_qs:
        taxable = float(r.mrp or 0) - float(r.discount or 0)
        sgst = round(taxable * float(r.sgst_per or 0) / 100, 2)
        cgst = round(taxable * float(r.cgst_per or 0) / 100, 2)
        igst = round(taxable * float(r.igst_per or 0) / 100, 2)
        customer_gstin = (r.ldgr.gst or '').strip() if r.ldgr else ''
        is_dealer_return = (r.ldgr_id in dealer_ldgr_ids) if r.ldgr else False

        note = {
            'ntNum': r.billno,
            'ntDt': str(r.date1),
            'ntty': 'C',
            'val': round(taxable + sgst + cgst + igst, 2),
            'txval': round(taxable, 2),
            'iamt': igst, 'camt': cgst, 'samt': sgst, 'csamt': 0,
        }

        if customer_gstin or is_dealer_return:
            cdnr_key = customer_gstin if customer_gstin else f"DL_{r.ldgr_id}"
            if cdnr_key not in cdnr:
                entry = {
                    'ctin':  customer_gstin,
                    'cname': r.ldgr.ac_name if r.ldgr else '',
                    'nt':    [],
                }
                if is_dealer_return and not customer_gstin:
                    entry['missing_gstin'] = True
                cdnr[cdnr_key] = entry
            cdnr[cdnr_key]['nt'].append(note)
        else:
            cdnur.append(note)

    # Document summary (number of invoices per series)
    invoice_count = vouchers.count()
    return_count = returns_qs.count()

    return Response({
        'b2b':   list(b2b.values()),
        'b2cl':  b2cl,
        'b2cs':  list(b2cs.values()),
        'cdnr':  list(cdnr.values()),
        'cdnur': cdnur,
        'doc_summary': {
            'invoices': invoice_count,
            'credit_notes': return_count,
        },
        'period': {'from': from_date, 'to': to_date},
        'retail_gstin': (retail.gstin_master.gstin if retail and retail.gstin_master else ''),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gstr3b_report(request):
    """
    GSTR-3B summary: outward supplies, ITC, and net tax payable.
    Parameters: from_date, to_date (YYYY-MM-DD)
    """
    retail = request.retail
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    if not from_date or not to_date:
        return Response({"detail": "from_date and to_date are required."}, status=400)

    # ── 3.1 Outward taxable supplies ──────────────────────────────────────────
    sales_qs   = SalesVou.objects.filter(retail=retail, date1__range=[from_date, to_date])
    returns_qs = SaleReturn.objects.filter(retail=retail, date1__range=[from_date, to_date])

    from django.db.models import F, Value, DecimalField
    from django.db.models.functions import Coalesce

    def _gst_aggregates(qs):
        """Aggregate taxable value and GST components at DB level."""
        return qs.annotate(
            _taxable=Coalesce(F('mrp'), Value(0), output_field=DecimalField())
                    - Coalesce(F('discount'), Value(0), output_field=DecimalField()),
        ).aggregate(
            total_taxable=Sum('_taxable'),
            total_igst=Sum(F('_taxable') * Coalesce(F('igst_per'), Value(0), output_field=DecimalField()) / 100),
            total_cgst=Sum(F('_taxable') * Coalesce(F('cgst_per'), Value(0), output_field=DecimalField()) / 100),
            total_sgst=Sum(F('_taxable') * Coalesce(F('sgst_per'), Value(0), output_field=DecimalField()) / 100),
        )

    sales_agg = _gst_aggregates(sales_qs)
    ret_agg = _gst_aggregates(returns_qs)

    out_taxable = float(sales_agg['total_taxable'] or 0) - float(ret_agg['total_taxable'] or 0)
    out_igst = float(sales_agg['total_igst'] or 0) - float(ret_agg['total_igst'] or 0)
    out_cgst = float(sales_agg['total_cgst'] or 0) - float(ret_agg['total_cgst'] or 0)
    out_sgst = float(sales_agg['total_sgst'] or 0) - float(ret_agg['total_sgst'] or 0)

    # ── 4. Input Tax Credit (ITC) from purchases with GST supplier ────────────
    from purchase.models import PurchaseVoucher
    pur_qs = PurchaseVoucher.objects.filter(
        retail=retail, date1__range=[from_date, to_date]
    ).select_related('ldgr')

    itc_agg = pur_qs.exclude(
        ldgr__gst__isnull=True
    ).exclude(
        ldgr__gst__exact=''
    ).aggregate(
        itc_igst=Sum('igst'),
        itc_cgst=Sum('cgst'),
        itc_sgst=Sum('sgst'),
    )
    itc_igst = float(itc_agg['itc_igst'] or 0)
    itc_cgst = float(itc_agg['itc_cgst'] or 0)
    itc_sgst = float(itc_agg['itc_sgst'] or 0)

    tax_out   = out_igst + out_cgst + out_sgst
    itc_total = itc_igst + itc_cgst + itc_sgst
    net_tax   = max(0.0, tax_out - itc_total)

    return Response({
        '3_1': {
            'label': 'Outward taxable supplies (other than zero rated, nil and exempted)',
            'txval': round(out_taxable, 2),
            'iamt':  round(out_igst, 2),
            'camt':  round(out_cgst, 2),
            'samt':  round(out_sgst, 2),
            'csamt': 0,
        },
        '4': {
            'label':     'Eligible ITC',
            'itc_igst':  round(itc_igst, 2),
            'itc_cgst':  round(itc_cgst, 2),
            'itc_sgst':  round(itc_sgst, 2),
            'itc_total': round(itc_total, 2),
        },
        'summary': {
            'tax_payable':  round(tax_out, 2),
            'itc':          round(itc_total, 2),
            'net_payable':  round(net_tax, 2),
        },
        'period': {'from': from_date, 'to': to_date},
    })


class GenerateJsonView(APIView):
    def get(self, request):
        if not request.retail:
            return Response(
                {"error": "Missing or invalid X-RETAIL-ID header"},
                status=status.HTTP_400_BAD_REQUEST
            )
        bill = request.GET.get('bill')
        if not bill:
            return Response({"error": "Bill number is required"}, status=400)

        from mastersconfig.models import State as StateModel

        json_array = {}
        json_array1 = []
        sales_vou = SalesVou.objects.select_related(
            'ldgr', 'retail__state'
        ).get(billno=bill, retail=request.retail)
        ldgr_master = sales_vou.ldgr

        # ── State code for Place of Supply (Pos) ──────────────────────────────
        pos_state = StateModel.objects.filter(
            name__iexact=sales_vou.place_of_supply
        ).first()
        state_code_pos = str(pos_state.tin) if pos_state and pos_state.tin else '09'

        # ── Buyer state code (Stcd) ───────────────────────────────────────────
        buyer_state = StateModel.objects.filter(
            name__iexact=(ldgr_master.state or '')
        ).first()
        party_state_code = str(buyer_state.tin) if buyer_state and buyer_state.tin else '09'

        Catg = 'B2B' if ldgr_master.gst else 'B2C'

        date = sales_vou.date1.strftime('%d/%m/%Y')

        json_array['Version'] = '1.1'
        json_array['TranDtls'] = {
            'TaxSch': 'GST',
            'SupTyp': Catg,
            'IgstOnIntra': 'N',
            'RegRev': 'N',
            'EcmGstin': None
        }
        json_array['DocDtls'] = {
            'Typ': 'INV',
            'No': sales_vou.gst_billno,
            'Dt': date
        }

        # ── Seller details — use exhibition profile if present ─────────────────
        retail = request.retail
        ep = getattr(request, 'exhibition', None)
        _gm            = retail.gstin_master
        seller_gstin   = (ep.gstin if ep and ep.gstin else (_gm.gstin if _gm else '')) or ''
        seller_addr1   = (ep.address_line1 if ep else retail.address_line1) or ''
        seller_addr2   = (ep.address_line2 if ep else retail.address_line2) or ''
        seller_city    = (ep.city if ep else retail.city) or ''
        seller_pin     = (ep.pincode if ep else retail.pincode) or ''
        seller_state   = ep.state if ep else retail.state
        seller_stcd    = str(seller_state.tin) if seller_state and seller_state.tin else ''

        json_array['SellerDtls'] = {
            'Gstin': seller_gstin,
            'LglNm': retail.retail_name.upper(),
            'Addr1': seller_addr1,
            'Addr2': seller_addr2,
            'Loc':   seller_city,
            'Pin':   int(seller_pin) if str(seller_pin).isdigit() else 0,
            'Stcd':  seller_stcd,
            'Ph':    retail.phone or None,
            'Em':    retail.email or None,
        }

        # ── Buyer details ─────────────────────────────────────────────────────
        buyer_addr1 = ((ldgr_master.add1 or '') + ' ' + (ldgr_master.add2 or '')).strip()
        json_array['BuyerDtls'] = {
            'Gstin': ldgr_master.gst or 'URP',
            'LglNm': ldgr_master.ac_name.upper(),
            'Addr1': buyer_addr1 or 'N/A',
            'Addr2': None,
            'Loc':   ldgr_master.state or '',
            'Pin':   int(ldgr_master.pincode) if ldgr_master.pincode and str(ldgr_master.pincode).isdigit() else 0,
            'Pos':   state_code_pos,
            'Stcd':  party_state_code,
            'Ph':    ldgr_master.phone1 or None,
            'Em':    ldgr_master.email or None,
        }
        total_gross_amount = float(sales_vou.mrp or 0)
        discount = float(sales_vou.discount or 0)
        sgst_amt = sales_vou.sgst_amt
        cgst_amt = sales_vou.cgst_amt
        igst_amt = sales_vou.igst_amt
        round_off = float(sales_vou.round_off or 0)
        tcs_amt = sales_vou.tcs_amt
        TotInvVal = (total_gross_amount - discount + sgst_amt +
                        cgst_amt + igst_amt + round_off + tcs_amt)
        json_array['ValDtls'] = {
            'AssVal': round(total_gross_amount + round_off - discount, 2),
            'IgstVal': round(igst_amt, 2),
            'CgstVal': round(cgst_amt, 2),
            'SgstVal': round(sgst_amt, 2),
            'CesVal': 0.00,
            'StCesVal': 0.00,
            'Discount': 0.00,
            'OthChrg': round(float(sales_vou.other_charge or 0) + tcs_amt, 2),
            'RndOffAmt': 0.00,
            'TotInvVal': round(TotInvVal, 2)
        }
        json_array['RefDtls'] = {'InvRm': 'NICGEPP2.0'}
        item_array = []
        bill_tot_item_value = 0
        sales_items = SalesVouItem.objects.filter(billno=sales_vou)
        flag = 1
        if not sales_items.exists():
            flag = 0
            sales_details = SalesVouItemDetails.objects.filter(
                billno=sales_vou
            ).select_related('item')
        c = 0
        if flag == 1:
            for sale_main in sales_items:
                c += 1
                metal_details = SalesVouItemDetails.objects.filter(
                    billno=sales_vou,
                    main_item=sale_main,
                    item__item_name='GOLD',
                    gw__gt=0
                ).first()
                stone_details = SalesVouItemDetails.objects.filter(Q(billno=sales_vou,
                    main_item=sale_main, gw__gt=0) &
                    ~Q(item__item_name='GOLD'),
                ).select_related('item')
                stone_desc = ""
                for stone in stone_details:
                    if stone.item.uom == "Gm":
                        stone_desc += f", {stone.item.item} Wt {stone.gw} gms"
                    elif stone.item.uom == "Ct":
                        stone_desc += f", {stone.item.item} Wt {stone.ct} Ct"
                hhsn = Item.objects.get(id=sale_main.item_id).hsn_no
                freight_chrg = float(sales_vou.freight_charge or 0)
                if c == 1:
                    tot_amt = decimal.Decimal(sale_main.amount + freight_chrg + round_off -
                                round((sale_main.amount * discount) / total_gross_amount, 0))
                else:
                    tot_amt = decimal.Decimal(sale_main.amount + freight_chrg -
                                round((sale_main.amount * discount) / total_gross_amount, 0))
                tot_item_value = (tot_amt +
                                round(tot_amt * sales_vou.cgst_per / 100, 0) +
                                round(tot_amt * sales_vou.sgst_per / 100, 0) +
                                round(tot_amt * sales_vou.igst_per / 100, 0))
                item_description = (f"{metal_details.metal_purity if metal_details else ''}K "
                                    f"{sale_main.item.short_code} {sale_main.pcs} Pieces "
                                    f"(Gross wt {sale_main.gw} gms {stone_desc})")
                tot_item_value = round(tot_item_value, 2)
                bill_tot_item_value += tot_item_value
                item_array.append({
                    'SlNo': str(c),
                    'PrdDesc': item_description,
                    'IsServc': 'N',
                    'HsnCd': hhsn.hsn_no,
                    'Qty': float(round(metal_details.gw, 3)) if metal_details else 0,
                    'FreeQty': 0,
                    'Unit': 'GMS',
                    'UnitPrice': round(metal_details.rate, 0) if metal_details else 0,
                    'TotAmt': round(tot_amt, 2),
                    'Discount': 0.00,
                    'PreTaxVal': 0.00,
                    'AssAmt': round(tot_amt, 2),
                    'GstRt': (sales_vou.sgst_per) + (sales_vou.cgst_per) + (sales_vou.igst_per),
                    'IgstAmt': round(tot_amt * (sales_vou.igst_per) / 100, 0),
                    'CgstAmt': round(tot_amt * (sales_vou.sgst_per) / 100, 0),
                    'SgstAmt': round(tot_amt * (sales_vou.cgst_per) / 100, 0),
                    'CesRt': 0.00,
                    'CesAmt': 0.00,
                    'CesNonAdvlAmt': 0.00,
                    'StateCesRt': 0.00,
                    'StateCesAmt': 0.00,
                    'StateCesNonAdvlAmt': 0.00,
                    'OthChrg': 0.00,
                    'TotItemVal': round(tot_item_value, 0)
                })
        else:
            for idx, sale_detail in enumerate(sales_details, 1):
                c = idx
                from mastersconfig.models import Hsn
                hsn_no = Item.objects.get(item_id=sale_detail.item).hsn_no
                hhsn = Hsn.objects.get(id=hsn_no)
                wt = sale_detail.ct if sale_detail.item.uom == "Ct" else sale_detail.gw
                freight_chrg = float(sales_vou.freight_charge or 0)
                if c == 1:
                    tot_amt = (sale_detail.amount + freight_chrg + round_off -
                                round((sale_detail.amount * discount) / total_gross_amount, 0))
                else:
                    tot_amt = (sale_detail.amount + freight_chrg -
                                round((sale_detail.amount * discount) / total_gross_amount, 0))
                tot_item_value = (tot_amt +
                                round(tot_amt * float(sales_vou.cgst_per) / 100, 0) +
                                round(tot_amt * float(sales_vou.sgst_per) / 100, 0) +
                                round(tot_amt * float(sales_vou.igst_per) / 100, 0))
                item_description = hhsn.description
                tot_item_value = round(tot_item_value, 2)
                bill_tot_item_value += tot_item_value
                item_array.append({
                    'SlNo': str(c),
                    'PrdDesc': item_description,
                    'IsServc': 'N',
                    'HsnCd': hhsn.hsn_no,
                    'Qty': float(wt),
                    'FreeQty': 0,
                    'Unit': 'CT' if sale_detail.item.uom == "Ct" else 'GMS',
                    'UnitPrice': round(sale_detail.rate, 0),
                    'TotAmt': round(tot_amt, 2),
                    'Discount': 0.00,
                    'PreTaxVal': 0.00,
                    'AssAmt': round(tot_amt, 2),
                    'GstRt': float(sales_vou.sgst_per) + float(sales_vou.cgst_per) + float(sales_vou.igst_per),
                    'IgstAmt': round(tot_amt * float(sales_vou.igst_per) / 100, 0),
                    'CgstAmt': round(tot_amt * float(sales_vou.sgst_per) / 100, 0),
                    'SgstAmt': round(tot_amt * float(sales_vou.cgst_per) / 100, 0),
                    'CesRt': 0.00,
                    'CesAmt': 0.00,
                    'CesNonAdvlAmt': 0.00,
                    'StateCesRt': 0.00,
                    'StateCesAmt': 0.00,
                    'StateCesNonAdvlAmt': 0.00,
                    'OthChrg': 0.00,
                    'TotItemVal': round(tot_item_value, 0)
                })
        if abs(float(bill_tot_item_value) - sales_vou.total_bill_value) > 1:
            return Response({"error": "Error, please generate this using excel tool"}, status=400)
        json_array['ItemList'] = item_array
        json_array1.append(json_array)
        json_data = json.dumps(json_array1, cls=DecimalEncoder, indent=4)
        response = HttpResponse(json_data, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename=JSON_{bill}.json'
        return response


class SalesApprovalViewset(views.RetailBaseViewset):
    queryset = SalesApproval.objects.select_related(
        'ldgr', 'sales_person', 'sales_person2', 'place_of_supply', 'retail'
    ).prefetch_related(
        'items__main_item_set',
        'items__main_item_set__item',       # for item_type check in metal_purity fallback
        'items__barcode__purity',            # for metal_purity fallback from parent barcode
    ).all()
    serializer_class = SalesApprovalSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['billno', 'ldgr__ac_name']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields
    ordering = ['-date1', '-id']

    def get_queryset(self):
        qs = super().get_queryset()
        # ?pending_only=true → only approvals that have at least one non-returned item.
        if self.request.query_params.get('pending_only', '').lower() in ('true', '1', 'yes'):
            qs = qs.filter(items__ret_status=False).distinct()
        return qs

    def _resolve_fiscal_year(self, retail, voucher_date):
        """Resolve the FY for a given voucher date; fall back to retail.active_fy."""
        from mastersconfig.models import FiscalYearMaster
        if voucher_date:
            fy = FiscalYearMaster.objects.filter(
                retail=retail, fy_start__lte=voucher_date, fy_end__gte=voucher_date,
            ).first()
            if fy:
                return fy
        return getattr(retail, 'active_fy', None)

    def perform_create(self, serializer):
        """Stamp fiscal_year (and retail) on create — base class only injects retail."""
        retail = getattr(self.request, 'retail', None)
        if not retail:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"retail": "Missing or invalid X-RETAIL-ID header."})
        voucher_date = serializer.validated_data.get('date1')
        fiscal_year = self._resolve_fiscal_year(retail, voucher_date)
        serializer.save(retail=retail, fiscal_year=fiscal_year)

    def perform_update(self, serializer):
        """Prevent retail reassignment; keep fiscal_year in sync with the date."""
        retail = serializer.instance.retail
        voucher_date = serializer.validated_data.get('date1') or serializer.instance.date1
        fiscal_year = self._resolve_fiscal_year(retail, voucher_date)
        serializer.save(fiscal_year=fiscal_year)

    def perform_destroy(self, instance):
        from accounting.utils import release_last_bill_number
        retail = instance.retail
        fiscal_year = instance.fiscal_year
        billno = instance.billno
        super().perform_destroy(instance)
        release_last_bill_number(retail, 'SA', billno, fiscal_year)

    @action(detail=True, methods=['post'], url_path='return-items')
    def return_items(self, request, pk=None):
        """
        Mark individual SalesApprovalItem records as returned and restore
        their barcodes to stock.

        Request body: { "returned_item_ids": [1, 2, 3] }
        """
        approval = self.get_object()
        ids = request.data.get('returned_item_ids', [])
        if not isinstance(ids, list) or not ids:
            return Response(
                {'error': 'returned_item_ids must be a non-empty list'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            ids = list({int(i) for i in ids})  # coerce to int and deduplicate
        except (TypeError, ValueError):
            return Response(
                {'error': 'returned_item_ids must contain integers only'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate every ID belongs to this approval
        found = SalesApprovalItem.objects.filter(id__in=ids, billno=approval).count()
        if found != len(ids):
            return Response(
                {'error': 'One or more item IDs not found on this approval'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Only act on items not already returned (idempotent)
            to_return = SalesApprovalItem.objects.filter(
                id__in=ids, billno=approval, ret_status=False
            ).select_related('barcode')
            items_to_return = list(to_return)
            barcode_ids = [it.barcode_id for it in items_to_return if it.barcode_id]

            to_return.update(ret_status=True)

            if barcode_ids:
                BarcodeMain.objects.filter(id__in=barcode_ids).update(stk_status=True)

            # Audit-log each returned barcode in the barcode-wise transaction table.
            if barcode_ids:
                ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
                retail = getattr(request, 'retail', None)
                for it in items_to_return:
                    if it.barcode_id and it.barcode:
                        BarcodeTransaction.objects.create(
                            barcode=it.barcode,
                            billno=approval.billno,
                            trans_type="SALE-APP-RET",
                            user=request.user,
                            ip_address=ip,
                            retail=retail,
                        )

        approval = self.get_queryset().get(pk=approval.pk)
        serializer = self.get_serializer(approval)
        return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_sv_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response(
            {"error": "Missing or invalid X-RETAIL-ID header"},
            status=status.HTTP_400_BAD_REQUEST
        )
    bill_no = peek_next_bill_number(request.retail, "SV")
    return Response({"billno": bill_no})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_sr_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response(
            {"error": "Missing or invalid X-RETAIL-ID header"},
            status=status.HTTP_400_BAD_REQUEST
        )
    bill_no = peek_next_bill_number(request.retail, "SR")
    return Response({"billno": bill_no})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_sa_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response(
            {"error": "Missing or invalid X-RETAIL-ID header"},
            status=status.HTTP_400_BAD_REQUEST
        )
    bill_no = peek_next_bill_number(request.retail, "SA")
    return Response({"billno": bill_no})


class SalesApprovalReturnViewset(views.RetailBaseViewset):
    queryset = SalesApprovalReturn.objects.select_related(
        'ref_approval', 'retail',
    ).prefetch_related(
        'items__main_item_set',
        'items__barcode',
        'items__approval_item',
    ).all()
    serializer_class = SalesApprovalReturnSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['billno', 'ref_approval__billno']
    ordering = ['-date1', '-id']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    def _resolve_fiscal_year(self, retail, voucher_date):
        """Resolve the FY for a given voucher date; fall back to retail.active_fy."""
        from mastersconfig.models import FiscalYearMaster
        if voucher_date:
            fy = FiscalYearMaster.objects.filter(
                retail=retail, fy_start__lte=voucher_date, fy_end__gte=voucher_date,
            ).first()
            if fy:
                return fy
        return getattr(retail, 'active_fy', None)

    def perform_create(self, serializer):
        """Stamp fiscal_year (and retail) on create — base class only injects retail."""
        retail = getattr(self.request, 'retail', None)
        if not retail:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"retail": "Missing or invalid X-RETAIL-ID header."})
        voucher_date = serializer.validated_data.get('date1')
        fiscal_year = self._resolve_fiscal_year(retail, voucher_date)
        serializer.save(retail=retail, fiscal_year=fiscal_year)

    def perform_update(self, serializer):
        """Keep fiscal_year in sync with the date on update."""
        retail = serializer.instance.retail
        voucher_date = serializer.validated_data.get('date1') or serializer.instance.date1
        fiscal_year = self._resolve_fiscal_year(retail, voucher_date)
        serializer.save(fiscal_year=fiscal_year)

    def perform_destroy(self, instance):
        from accounting.utils import release_last_bill_number
        retail = instance.retail
        fiscal_year = instance.fiscal_year
        billno = instance.billno
        super().perform_destroy(instance)
        release_last_bill_number(retail, 'SAR', billno, fiscal_year)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_sar_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response(
            {"error": "Missing or invalid X-RETAIL-ID header"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    bill_no = peek_next_bill_number(request.retail, "SAR")
    return Response({"billno": bill_no})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_cash_received_view(request):
    """
    Returns the total cash already received from a customer in the active fiscal year.
    Used by the frontend to show a live indicator and warn before the 269ST limit is hit.
    Query params: customer_id (required)
    """
    from contacts.models import Ledger
    from accounting.utils import get_customer_cash_received

    customer_id = request.query_params.get('customer_id')
    if not customer_id:
        return Response({'error': 'customer_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    if not request.retail:
        return Response({'error': 'Retail not set'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        customer_ldgr = Ledger.objects.get(pk=customer_id)
    except Ledger.DoesNotExist:
        return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)

    from accounting.utils import get_company_cash_limits
    fy = request.retail.active_fy
    receipt_limit, _ = get_company_cash_limits(request.retail)

    if receipt_limit is None:
        # Enforcement disabled — return sentinel so frontend can hide the indicator
        return Response({
            'customer_id': int(customer_id),
            'customer_name': customer_ldgr.ac_name,
            'enforcement_enabled': False,
            'cash_received': None,
            'limit': None,
            'remaining': None,
        })

    limit = float(receipt_limit)
    already = float(get_customer_cash_received(request.retail, fy, customer_ldgr))

    return Response({
        'customer_id': int(customer_id),
        'customer_name': customer_ldgr.ac_name,
        'enforcement_enabled': True,
        'cash_received': already,
        'limit': limit,
        'remaining': max(0.0, limit - already),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sale_voucher_initial_data(request):
    """Combined endpoint that replaces 8 parallel API calls on the SalesVoucher form mount."""
    from global_vars import STATES_OF_INDIA
    from mastersconfig.models import Item, Packet, SalesPersonMaster, Hsn
    from mastersconfig.serializers import ItemSerializer, PacketSerializer, SalesPersonMasterSerializer, HSNListSerializer
    from goldrates.serializer import PurityMasterSerializer

    if not request.retail:
        return Response(
            {"error": "Missing or invalid X-RETAIL-ID header"},
            status=status.HTTP_400_BAD_REQUEST
        )

    from accounting.utils import peek_next_bill_number
    from mastersconfig.models import SystemSettings

    states = [{"code": code, "name": name} for code, name in STATES_OF_INDIA]
    bill_no = peek_next_bill_number(request.retail, "SV")
    sys_settings = SystemSettings.get()
    gst_bill_enabled = sys_settings.enable_gst_bill
    gst_bill_no = peek_next_bill_number(request.retail, "GST") if gst_bill_enabled else ""

    ledgers_qs = (Ledger.objects
                  .filter(roles__role='CO')
                  .only('id', 'ac_name', 'ac_group', 'mobile1', 'phone1')
                  .prefetch_related('roles')
                  .distinct())
    items_qs = Item.objects.select_related('grp', 'hsn_no', 'purchase_ledger', 'sale_ledger').all()
    purity_qs = PurityMaster.objects.all()
    packets_qs = Packet.objects.select_related('packet_group', 'stone_item_id', 'color', 'shape').all()
    salespersons_qs = SalesPersonMaster.objects.filter(
        Q(retail=request.retail) | Q(retail__isnull=True)
    )
    hsns_qs = Hsn.objects.all()

    # Derive retail state code using STATES_OF_INDIA to stay consistent
    # with the place_of_supply select options on the frontend
    retail_state_name = request.retail.state.name if request.retail.state else ""
    retail_state_code = next(
        (code for code, name in STATES_OF_INDIA if name == retail_state_name),
        request.retail.state.code if request.retail.state else ""
    )

    return Response({
        "billno": bill_no,
        "gst_billno": gst_bill_no,
        "enable_gst_bill": gst_bill_enabled,
        "retail_state_code": retail_state_code,
        "is_exhibition": request.retail.is_exhibition,
        "states": states,
        "ledgers": SaleVoucherLedgerSerializer(ledgers_qs, many=True, context={'request': request}).data,
        "items": ItemSerializer(items_qs, many=True).data,
        "purity": PurityMasterSerializer(purity_qs, many=True).data,
        "packets": PacketSerializer(packets_qs, many=True).data,
        "salespersons": SalesPersonMasterSerializer(salespersons_qs, many=True).data,
        "hsns": HSNListSerializer(hsns_qs, many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sale_return_initial_data(request):
    """Combined initial data for the SalesReturn form."""
    from mastersconfig.models import Item, Packet
    from mastersconfig.serializers import ItemSerializer, PacketSerializer
    from goldrates.serializer import PurityMasterSerializer

    if not request.retail:
        return Response(
            {"error": "Missing or invalid X-RETAIL-ID header"},
            status=status.HTTP_400_BAD_REQUEST
        )

    from accounting.utils import peek_next_bill_number

    bill_no = peek_next_bill_number(request.retail, "SR")
    ledgers_qs = (Ledger.objects
                  .filter(roles__role='CO')
                  .select_related('ac_group')
                  .only('id', 'ac_name', 'ac_group', 'mobile1', 'phone1')
                  .prefetch_related('roles')
                  .distinct())
    items_qs = Item.objects.select_related('grp', 'hsn_no', 'purchase_ledger', 'sale_ledger').all()
    purity_qs = PurityMaster.objects.all()
    packets_qs = Packet.objects.select_related('packet_group', 'stone_item_id', 'color', 'shape').all()

    return Response({
        "billno": bill_no,
        "ledgers": SaleVoucherLedgerSerializer(ledgers_qs, many=True, context={'request': request}).data,
        "items": ItemSerializer(items_qs, many=True).data,
        "purity": PurityMasterSerializer(purity_qs, many=True).data,
        "packets": PacketSerializer(packets_qs, many=True).data,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Invoice print helpers
# ─────────────────────────────────────────────────────────────────────────────

def build_sub_item_text(d):
    """Build the descriptive text line for a SalesVouItemDetails sub-row."""
    if not d.item:
        return ''
    item_type = d.item.item_type
    t = d.item.item_name or ''
    rate_val = float(d.rate or 0)
    rate_str = f' @ {round(rate_val)}' if rate_val != 0 else ''
    if item_type == 'S':
        return f'{t} Wt {d.ct} Ct{rate_str}'
    elif item_type in ('O', 'P_G'):
        return f'{t} ({d.gw} Gm) {d.pcs} Pcs{rate_str}'
    else:  # R, C, M
        if d.metal_purity and str(d.metal_purity) not in ('', '0'):
            return f'{t} {d.metal_purity}K {float(d.gw or 0):.2f} Gm{rate_str}'
        return t


def build_invoice_context(voucher, retail, request=None):
    """Build the complete data dict for the invoice print view."""
    from mastersconfig.models import State as StateModel

    def _abs_media(field):
        """Return an absolute URL for an ImageField or '' if missing."""
        try:
            url = field.url if field else ''
        except (ValueError, AttributeError):
            return ''
        if not url:
            return ''
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    # ── Company info — use exhibition profile if one was active when bill was raised ──
    exh = voucher.exhibition_profile
    if exh:
        company_address    = ', '.join(filter(None, [
            exh.address_line1, exh.address_line2, exh.address_line3, exh.city, exh.pincode,
        ]))
        company_gstin      = exh.gstin
        company_state_name = exh.state.name if exh.state else ''
        company_state_code = str(exh.state.tin) if exh.state else ''
    else:
        company_address    = ', '.join(filter(None, [
            retail.address_line1, retail.address_line2, retail.address_line3,
            retail.city, retail.pincode,
        ]))
        _gm                = retail.gstin_master
        company_gstin      = (_gm.gstin if _gm else '') or ''
        company_state_name = retail.state.name if retail.state else ''
        company_state_code = str(retail.state.tin) if retail.state else ''

    # ── Customer (ledger) info ─────────────────────────────────────────────────
    ldgr = voucher.ldgr
    customer_address = ', '.join(filter(None, [
        ldgr.add1, ldgr.add2, ldgr.city, ldgr.pincode,
    ]))
    customer_state_name = ldgr.state or ''
    customer_state_obj = StateModel.objects.filter(name__iexact=customer_state_name).first()
    customer_state_code = str(customer_state_obj.tin) if customer_state_obj else ''

    # ── Build purity PK → slug map (vi.purity stores PK; d.metal_purity stores slug) ─
    purity_pk_to_slug = {str(p.pk): p.purity for p in PurityMaster.objects.all()}

    # ── Metal rates: purity slug → rate (from R-type sub-items) ──────────────
    metal_rates = {}
    for vi in voucher.salesvouitem_set.prefetch_related('main_item_set').all():
        for d in vi.main_item_set.all():
            if d.item and d.item.item_type == 'R' and d.metal_purity and d.rate:
                key = str(d.metal_purity)   # already a slug like "14K"
                if key not in metal_rates:
                    metal_rates[key] = float(d.rate)
    metal_rate_str = ', '.join(f'{k} @ {v:.0f}' for k, v in metal_rates.items())

    # ── Line items ────────────────────────────────────────────────────────────
    items_data = []
    for vi in voucher.salesvouitem_set.select_related(
        'item', 'item__hsn_no'
    ).prefetch_related('main_item_set__item').all():

        # vi.purity is IntegerField storing PK — convert to slug for matching
        purity_str = purity_pk_to_slug.get(str(vi.purity), str(vi.purity) if vi.purity else '')
        details = list(vi.main_item_set.all())

        nw = sum(
            float(d.gw or 0) for d in details
            if d.item and d.item.item_type == 'R' and str(d.metal_purity) == purity_str
        )
        metal_value = sum(float(d.amount or 0) for d in details if d.item and d.item.item_type == 'R')
        stone_value = sum(float(d.amount or 0) for d in details if d.item and d.item.item_type == 'S')
        other_value = sum(float(d.amount or 0) for d in details if d.item and d.item.item_type not in ('R', 'S', 'M'))

        hsn_code = vi.item.hsn_no.hsn_no if (vi.item and vi.item.hsn_no) else ''

        sub_rows = [
            {
                'text': build_sub_item_text(d),
                'pcs': d.pcs,
                'gw': float(d.gw or 0),
                'ct': float(d.ct or 0),
                'rate': float(d.rate or 0),
                'amount': float(d.amount or 0),
                'item_type': d.item.item_type if d.item else '',
                'metal_purity': str(d.metal_purity) if d.metal_purity else '',
            }
            for d in details
        ]

        items_data.append({
            'sn': len(items_data) + 1,
            'pcs': vi.pcs,
            'item_name': vi.item.item_name if vi.item else '',
            'hsn': hsn_code,
            'purity': purity_str,
            'gw': float(vi.gw or 0),
            'nw': round(nw, 3),
            'rate': metal_rates.get(purity_str, 0),
            'metal_value': round(metal_value, 2),
            'stone_value': round(stone_value, 2),
            'making': float(vi.making_value or 0),
            'other_value': round(other_value, 2),
            'amount': float(vi.amount or 0),
            'sub_rows': sub_rows,
        })

    # ── Totals & tax ──────────────────────────────────────────────────────────
    items_total = sum(i['amount'] for i in items_data)
    discount = float(voucher.discount or 0)
    freight = float(voucher.freight_charge or 0)
    taxable = items_total - discount + freight

    sgst_per = float(voucher.sgst_per or 0)
    cgst_per = float(voucher.cgst_per or 0)
    igst_per = float(voucher.igst_per or 0)
    tcs_per  = float(voucher.tcs_per or 0)

    sgst_amt = round(taxable * sgst_per / 100, 2)
    cgst_amt = round(taxable * cgst_per / 100, 2)
    igst_amt = round(taxable * igst_per / 100, 2)
    tcs_amt  = round((taxable + sgst_amt + cgst_amt + igst_amt) * tcs_per / 100, 2)
    total    = round(taxable + sgst_amt + cgst_amt + igst_amt + tcs_amt, 2)

    cash = float(voucher.cash or 0)
    net_receivable = round(total - cash, 2)

    # ── Bank details ──────────────────────────────────────────────────────────
    bank_lines = []
    for bd in voucher.bank_details.all():
        parts = list(filter(None, [
            bd.bank_name,
            f'Chq: {bd.chq_no}' if bd.chq_no else '',
            f'₹{bd.amount}' if bd.amount else '',
        ]))
        bank_lines.append(' | '.join(parts))

    # ── Walk hierarchy: retail → branch → company for PAN / TAN / name ──────
    company = None
    if retail.branch_id and retail.branch and retail.branch.company_id:
        company = retail.branch.company

    return {
        # Company
        'company_name':         (company.company_name if company else retail.retail_name) or '',
        'company_legal_name':   (company.legal_name if company else '') or '',
        'company_address':      company_address,
        'company_gstin':        company_gstin,
        'company_state':        company_state_name,
        'company_state_code':   company_state_code,
        'company_phone':        (company.phone if company else retail.phone) or '',
        'company_email':        (company.email if company else retail.email) or '',
        'company_pan':          (company.pan if company else '') or '',
        'company_tan':          (company.tan if company else '') or '',
        'company_cin':          (company.cin if company else '') or '',
        'company_website':      (company.website if company else '') or '',
        # Branding logos (uploaded via Settings → Company Master)
        'bis_logo_url':     _abs_media(getattr(company, 'bis_logo', None)) if company else '',
        'company_logo_url': _abs_media(getattr(company, 'company_logo', None)) if company else '',
        # Invoice meta
        'billno':       voucher.billno or '',
        'gst_billno':   voucher.gst_billno or '',
        'date1':        str(voucher.date1) if voucher.date1 else '',
        # Customer
        'customer_name':        ldgr.ac_name or '',
        'customer_address':     customer_address,
        'customer_state':       customer_state_name,
        'customer_state_code':  customer_state_code,
        'customer_gstin':       ldgr.gst or '',
        'customer_pan':         ldgr.pan or '',
        'customer_aadhar':      ldgr.aadhar or '',
        'customer_dl':          ldgr.dl_no or '',
        # Shipping / Transport
        'mode_of_transport': voucher.mode_of_transport or '',
        'place_of_supply':   voucher.place_of_supply or '',
        'metal_rate_str':    metal_rate_str,
        # Items
        'items': items_data,
        # Totals
        'items_total':    round(items_total, 2),
        'discount':       discount,
        'freight_charge': freight,
        'taxable_value':  round(taxable, 2),
        'sgst_per': sgst_per, 'sgst_amt': sgst_amt,
        'cgst_per': cgst_per, 'cgst_amt': cgst_amt,
        'igst_per': igst_per, 'igst_amt': igst_amt,
        'tcs_per':  tcs_per,  'tcs_amt':  tcs_amt,
        'total_bill_value': total,
        'cash':            cash,
        'net_receivable':  net_receivable,
        'bank_lines':      bank_lines,
        'mrp':             float(voucher.mrp or 0),
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sale_voucher_print_data(request, pk):
    """Return fully-computed invoice JSON for the React print component."""
    try:
        voucher = SalesVou.objects.select_related(
            'ldgr', 'retail', 'retail__state',
            'exhibition_profile', 'exhibition_profile__state',
        ).prefetch_related(
            'salesvouitem_set__item__hsn_no',
            'salesvouitem_set__main_item_set__item',
            'bank_details',
        ).get(pk=pk, retail=request.retail)
    except SalesVou.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        data = build_invoice_context(voucher, request.retail, request=request)
    except Exception as exc:
        import traceback
        logger.error("build_invoice_context failed for voucher %s: %s\n%s", pk, exc, traceback.format_exc())
        return Response({'detail': f'Invoice build failed: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response(data)


# ─────────────────────────────────────────────────────────────────────────────
# E-Way Bill views
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def eway_transport_update(request, pk):
    """Save transport details onto a SalesVou so they can be used for e-way bill."""
    try:
        voucher = SalesVou.objects.get(pk=pk, retail=request.retail)
    except SalesVou.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    allowed = {
        'vehicle_no', 'transporter_name', 'transporter_id',
        'trans_distance', 'trans_doc_no', 'trans_doc_date', 'mode_of_transport',
    }
    for field in allowed:
        if field in request.data:
            setattr(voucher, field, request.data[field] or '' if field != 'trans_distance' else (int(request.data[field]) if request.data[field] else 0))
    voucher.save(update_fields=list(allowed & set(request.data.keys())))

    # Create or update an EWayBill tracking record so it appears in the E-Way Bills list
    from ..models import EWayBill
    ewb = EWayBill.objects.filter(sales_vou=voucher, retail=request.retail).order_by('-generated_date').first()
    transport_fields = {
        'party_name':       voucher.ldgr.ac_name if voucher.ldgr else '',
        'source_billno':    voucher.billno or '',
        'vehicle_no':       voucher.vehicle_no or '',
        'transporter_name': voucher.transporter_name or '',
        'transporter_id':   voucher.transporter_id or '',
        'trans_distance':   voucher.trans_distance or 0,
        'mode_of_transport': voucher.mode_of_transport or 'Road',
    }
    if ewb:
        for k, v in transport_fields.items():
            setattr(ewb, k, v)
        ewb.save(update_fields=list(transport_fields.keys()))
    else:
        EWayBill.objects.create(
            sales_vou=voucher,
            retail=request.retail,
            fiscal_year=getattr(request.retail, 'active_fy', None),
            **transport_fields,
        )

    return Response({
        'id': voucher.id,
        'vehicle_no': voucher.vehicle_no,
        'transporter_name': voucher.transporter_name,
        'transporter_id': voucher.transporter_id,
        'trans_distance': voucher.trans_distance,
        'trans_doc_no': voucher.trans_doc_no,
        'trans_doc_date': str(voucher.trans_doc_date) if voucher.trans_doc_date else None,
        'mode_of_transport': voucher.mode_of_transport,
    })


class EwayBillGenerateView(APIView):
    """Generate e-Way Bill JSON download for a given bill number."""

    def get(self, request):
        from mastersconfig.models import State as StateModel

        bill = request.query_params.get('bill')
        if not bill:
            return Response({'error': 'bill query param required'}, status=400)

        try:
            voucher = SalesVou.objects.select_related(
                'ldgr', 'retail', 'retail__state',
                'exhibition_profile', 'exhibition_profile__state',
            ).get(billno=bill, retail=request.retail)
        except SalesVou.DoesNotExist:
            return Response({'error': 'Voucher not found'}, status=404)

        retail = request.retail
        ldgr = voucher.ldgr
        ep = voucher.exhibition_profile

        # ── Seller (From) details ─────────────────────────────────────────────
        _gm          = retail.gstin_master
        seller_gstin = (ep.gstin if ep else (_gm.gstin if _gm else '')) or ''
        seller_name  = (ep.name  if ep else retail.retail_name) or ''
        seller_addr1 = (ep.address_line1 if ep else retail.address_line1) or ''
        seller_addr2 = (ep.address_line2 if ep else retail.address_line2) or ''
        seller_city  = (ep.city if ep else retail.city) or ''
        seller_pin   = (ep.pincode if ep else retail.pincode) or '0'
        seller_state = ep.state if ep else retail.state
        seller_stcd  = str(seller_state.tin) if seller_state else '0'

        # ── Buyer (To) details — use shipping address ─────────────────────────
        buyer_gstin = ldgr.gst or 'URP'
        buyer_name  = ldgr.ac_name or ''
        buyer_addr1 = ldgr.ship_add1 or ldgr.add1 or ''
        buyer_addr2 = ldgr.ship_add2 or ldgr.add2 or ''
        buyer_city  = ldgr.ship_city or ldgr.city or ''
        buyer_pin   = ldgr.ship_pincode or ldgr.pincode or '0'
        buyer_state_name = ldgr.ship_state or ldgr.state or ''
        try:
            buyer_state_obj = StateModel.objects.get(name__iexact=buyer_state_name)
            buyer_stcd = str(buyer_state_obj.tin)
        except StateModel.DoesNotExist:
            buyer_stcd = '0'

        # ── Tax values ────────────────────────────────────────────────────────
        taxable_val = round(float(voucher.taxable_value), 2)
        cgst_val    = round(float(voucher.cgst_amt), 2)
        sgst_val    = round(float(voucher.sgst_amt), 2)
        igst_val    = round(float(voucher.igst_amt), 2)
        total_val   = round(float(voucher.total_bill_value), 2)

        # ── Doc date ──────────────────────────────────────────────────────────
        doc_date = voucher.date1.strftime('%d/%m/%Y') if voucher.date1 else ''

        # ── Transport details ─────────────────────────────────────────────────
        trans_mode_map = {
            'Road': '1', 'Rail': '2', 'Air': '3', 'Ship': '4',
        }
        trans_mode = trans_mode_map.get(voucher.mode_of_transport or '', '1')
        trans_doc_date_str = voucher.trans_doc_date.strftime('%d/%m/%Y') if voucher.trans_doc_date else ''

        # ── Build item list ───────────────────────────────────────────────────
        item_list = []
        sales_items = SalesVouItem.objects.filter(billno=voucher).select_related('item__hsn_no')
        if sales_items.exists():
            for idx, si in enumerate(sales_items, 1):
                hsn_no = si.item.hsn_no.hsn_no if si.item and si.item.hsn_no else ''
                gst_rate = float(voucher.sgst_per or 0) + float(voucher.cgst_per or 0) + float(voucher.igst_per or 0)
                item_list.append({
                    'productName': si.item.item_name if si.item else '',
                    'productDesc': si.item.item_name if si.item else '',
                    'hsnCode': hsn_no,
                    'quantity': float(si.gw or 0),
                    'qtyUnit': 'GMS',
                    'taxableAmount': round(float(si.amount or 0), 2),
                    'cgstRate': float(voucher.cgst_per or 0),
                    'sgstRate': float(voucher.sgst_per or 0),
                    'igstRate': float(voucher.igst_per or 0),
                    'cessRate': 0.0,
                })
        else:
            # Fallback: single line with total
            item_list.append({
                'productName': 'Jewellery',
                'productDesc': 'Gold/Diamond Jewellery',
                'hsnCode': '7113',
                'quantity': 1.0,
                'qtyUnit': 'NOS',
                'taxableAmount': taxable_val,
                'cgstRate': float(voucher.cgst_per or 0),
                'sgstRate': float(voucher.sgst_per or 0),
                'igstRate': float(voucher.igst_per or 0),
                'cessRate': 0.0,
            })

        eway_json = {
            'supplyType': 'O',
            'subSupplyType': '1',
            'docType': 'INV',
            'docNo': voucher.gst_billno or voucher.billno,
            'docDate': doc_date,
            'fromGstin': seller_gstin,
            'fromTrdName': seller_name,
            'fromAddr1': seller_addr1,
            'fromAddr2': seller_addr2,
            'fromPlace': seller_city,
            'fromPincode': int(seller_pin) if str(seller_pin).isdigit() else 0,
            'fromStateCode': int(seller_stcd) if str(seller_stcd).isdigit() else 0,
            'toGstin': buyer_gstin,
            'toTrdName': buyer_name,
            'toAddr1': buyer_addr1,
            'toAddr2': buyer_addr2,
            'toPlace': buyer_city,
            'toPincode': int(buyer_pin) if str(buyer_pin).isdigit() else 0,
            'toStateCode': int(buyer_stcd) if str(buyer_stcd).isdigit() else 0,
            'transactionType': 1,
            'totalValue': taxable_val,
            'cgstValue': cgst_val,
            'sgstValue': sgst_val,
            'igstValue': igst_val,
            'cessValue': 0.0,
            'totInvValue': total_val,
            'transMode': trans_mode,
            'transDistance': str(voucher.trans_distance or ''),
            'transporterName': voucher.transporter_name or '',
            'transporterId': voucher.transporter_id or '',
            'transDocNo': voucher.trans_doc_no or '',
            'transDocDate': trans_doc_date_str,
            'vehicleNo': voucher.vehicle_no or '',
            'vehicleType': 'R',
            'itemList': item_list,
        }

        json_data = json.dumps(eway_json, cls=DecimalEncoder, indent=4)

        # Create or update EWayBill tracking record (deduplication: one record per voucher per retail)
        from ..models import EWayBill
        ewb_snapshot = dict(
            party_name=voucher.ldgr.ac_name if voucher.ldgr else '',
            source_billno=voucher.billno or '',
            vehicle_no=voucher.vehicle_no or '',
            transporter_name=voucher.transporter_name or '',
            transporter_id=voucher.transporter_id or '',
            trans_distance=voucher.trans_distance or 0,
            mode_of_transport=voucher.mode_of_transport or 'Road',
            json_payload=json_data,
        )
        existing_ewb = EWayBill.objects.filter(sales_vou=voucher, retail=request.retail).order_by('-generated_date').first()
        if existing_ewb:
            for k, v in ewb_snapshot.items():
                setattr(existing_ewb, k, v)
            existing_ewb.save(update_fields=list(ewb_snapshot.keys()))
        else:
            EWayBill.objects.create(
                sales_vou=voucher,
                retail=request.retail,
                fiscal_year=getattr(request.retail, 'active_fy', None),
                **ewb_snapshot,
            )

        response = HttpResponse(json_data, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename=EWAY_{bill}.json'
        return response


class EWayBillListView(APIView):
    """GET /sales/api/eway-bills/ — list all E-Way bills for the current retail."""

    def get(self, request):
        from ..models import EWayBill
        qs = EWayBill.objects.filter(retail=request.retail).select_related(
            'sales_vou', 'sales_vou__ldgr',
            'sales_approval', 'sales_approval__ldgr',
        ).order_by('-generated_date')

        search = request.query_params.get('search', '')
        if search:
            qs = qs.filter(
                Q(eway_bill_no__icontains=search) |
                Q(sales_vou__billno__icontains=search) |
                Q(sales_approval__billno__icontains=search) |
                Q(sales_vou__ldgr__ac_name__icontains=search) |
                Q(sales_approval__ldgr__ac_name__icontains=search) |
                Q(vehicle_no__icontains=search)
            )

        status_filter = request.query_params.get('status', '')
        if status_filter:
            qs = qs.filter(status=status_filter)

        from ..serializers import EWayBillSerializer
        serializer = EWayBillSerializer(qs, many=True)
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def eway_bill_cancel(request, pk):
    """POST /sales/api/eway-bills/<pk>/cancel/ — cancel an E-Way bill."""
    from ..models import EWayBill
    from django.utils import timezone
    try:
        ewb = EWayBill.objects.get(pk=pk, retail=request.retail)
    except EWayBill.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if ewb.status == 'CANCELLED':
        return Response({'detail': 'Already cancelled.'}, status=status.HTTP_400_BAD_REQUEST)

    ewb.status = 'CANCELLED'
    ewb.cancelled_date = timezone.now()
    ewb.cancel_reason = request.data.get('reason', '')
    ewb.save(update_fields=['status', 'cancelled_date', 'cancel_reason'])
    return Response({'detail': 'E-Way Bill cancelled.'})


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def eway_bill_update_ebn(request, pk):
    """PATCH /sales/api/eway-bills/<pk>/update-ebn/ — save EBN after NIC upload."""
    from ..models import EWayBill
    try:
        ewb = EWayBill.objects.get(pk=pk, retail=request.retail)
    except EWayBill.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    ewb.eway_bill_no = request.data.get('eway_bill_no', ewb.eway_bill_no)
    if request.data.get('valid_from'):
        ewb.valid_from = request.data['valid_from']
    if request.data.get('valid_until'):
        ewb.valid_until = request.data['valid_until']
    ewb.save(update_fields=['eway_bill_no', 'valid_from', 'valid_until'])
    from ..serializers import EWayBillSerializer
    return Response(EWayBillSerializer(ewb).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def eway_bill_delete(request, pk):
    """DELETE /sales/api/eway-bills/<pk>/ — hard delete (only if no EBN assigned)."""
    from ..models import EWayBill
    try:
        ewb = EWayBill.objects.get(pk=pk, retail=request.retail)
    except EWayBill.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if ewb.eway_bill_no:
        return Response(
            {'detail': 'Cannot delete an E-Way Bill with an assigned EBN. Cancel it instead.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    ewb.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ── Customer Purchase History ─────────────────────────────────────────────────

class CustomerPurchaseHistoryView(APIView):
    """
    GET /sales/api/customer-history/?ledger_id=<id>&from_date=YYYY-MM-DD&to_date=YYYY-MM-DD
    Returns all sales, returns, orders and approvals for a customer, sorted newest first.
    """
    def get(self, request):
        from itertools import chain

        ledger_id = request.query_params.get('ledger_id')
        from_date = request.query_params.get('from_date')
        to_date   = request.query_params.get('to_date')
        retail    = request.retail

        if not ledger_id:
            return Response({'error': 'ledger_id is required'}, status=400)

        date_filter = {}
        if from_date:
            date_filter['date1__gte'] = from_date
        if to_date:
            date_filter['date1__lte'] = to_date

        # ── Sales vouchers ──────────────────────────────────────────────────
        # Note: taxable_value is a @property (mrp - discount), not a DB column.
        sales = SalesVou.objects.filter(
            ldgr_id=ledger_id, retail=retail, **date_filter
        ).values('id', 'billno', 'date1', 'mrp', 'cgst_per', 'sgst_per', 'igst_per', 'discount')

        # ── Sale returns ────────────────────────────────────────────────────
        returns = SaleReturn.objects.filter(
            ldgr_id=ledger_id, retail=retail, **date_filter
        ).values('id', 'billno', 'date1', 'mrp', 'cgst_per', 'sgst_per', 'igst_per', 'discount')

        # ── Customer orders ─────────────────────────────────────────────────
        orders = CustomerOrder.objects.filter(
            ldgr_id=ledger_id, retail=retail, **date_filter
        ).values('id', 'order_no', 'date1', 'est_amount')

        # ── Sales approvals ─────────────────────────────────────────────────
        # SalesApproval has taxable_value as a real DB field (no mrp column)
        approvals = SalesApproval.objects.filter(
            ldgr_id=ledger_id, retail=retail, **date_filter
        ).values('id', 'billno', 'date1', 'taxable_value', 'cgst_per', 'sgst_per', 'igst_per', 'discount')

        def _bill_value(row):
            """For SalesVou / SaleReturn: mrp is a real DB field, taxable = mrp - discount."""
            mrp     = float(row.get('mrp') or 0)
            disc    = float(row.get('discount') or 0)
            taxable = mrp - disc
            cgst    = taxable * float(row.get('cgst_per') or 0) / 100
            sgst    = taxable * float(row.get('sgst_per') or 0) / 100
            igst    = taxable * float(row.get('igst_per') or 0) / 100
            return round(mrp, 2), round(cgst + sgst + igst, 2)

        def _approval_bill_value(row):
            """For SalesApproval: taxable_value is the real DB field (no mrp)."""
            taxable = float(row.get('taxable_value') or 0)
            disc    = float(row.get('discount') or 0)
            base    = taxable - disc
            cgst    = base * float(row.get('cgst_per') or 0) / 100
            sgst    = base * float(row.get('sgst_per') or 0) / 100
            igst    = base * float(row.get('igst_per') or 0) / 100
            total   = round(base + cgst + sgst + igst, 2)
            return total, round(cgst + sgst + igst, 2)

        rows = []
        for r in sales:
            mrp, tax = _bill_value(r)
            rows.append({'doc_type': 'Sale', 'doc_no': r['billno'], 'date': str(r['date1']), 'id': r['id'], 'amount': mrp, 'tax': tax})
        for r in returns:
            mrp, tax = _bill_value(r)
            rows.append({'doc_type': 'Return', 'doc_no': r['billno'], 'date': str(r['date1']), 'id': r['id'], 'amount': mrp, 'tax': tax})
        for r in orders:
            rows.append({'doc_type': 'Order', 'doc_no': r['order_no'], 'date': str(r['date1']), 'id': r['id'], 'amount': float(r['est_amount'] or 0), 'tax': 0})
        for r in approvals:
            amt, tax = _approval_bill_value(r)
            rows.append({'doc_type': 'Approval', 'doc_no': r['billno'], 'date': str(r['date1']), 'id': r['id'], 'amount': amt, 'tax': tax})

        rows.sort(key=lambda x: x['date'], reverse=True)

        total_sales   = sum(r['amount'] for r in rows if r['doc_type'] == 'Sale')
        total_returns = sum(r['amount'] for r in rows if r['doc_type'] == 'Return')

        try:
            ledger = Ledger.objects.get(pk=ledger_id)
            ledger_info = {'id': ledger.id, 'ac_name': ledger.ac_name, 'gst': ledger.gst or '', 'mobile': ledger.mobile1 or ''}
        except Ledger.DoesNotExist:
            ledger_info = {}

        return Response({
            'ledger': ledger_info,
            'summary': {
                'total_sales': round(total_sales, 2),
                'total_returns': round(total_returns, 2),
                'net': round(total_sales - total_returns, 2),
                'order_count': sum(1 for r in rows if r['doc_type'] == 'Order'),
            },
            'transactions': rows,
        })


# ── Cheque Management ──────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_cheques(request):
    """List all received cheques that are still pending deposit for this retail."""
    retail = getattr(request, 'retail', None)
    qs = BankDetail.objects.filter(
        payment_mode='CHEQUE',
        cheque_status='PENDING',
        sales_vou__retail=retail,
    ).select_related('sales_vou', 'sales_vou__ldgr', 'ledger')

    data = []
    for bd in qs:
        data.append({
            'id':          bd.id,
            'bill_no':     bd.sales_vou.billno,
            'sale_date':   bd.sales_vou.date1,
            'customer':    bd.sales_vou.ldgr.ac_name if bd.sales_vou.ldgr else '',
            'amount':      bd.amount,
            'chq_no':      bd.chq_no,
            'chq_date':    bd.chq_date,
            'bank_name':   bd.bank_name,
            'deposit_bank_id':   bd.ledger_id,
            'deposit_bank_name': bd.ledger.ac_name if bd.ledger else '',
        })
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deposit_cheque(request, pk):
    """
    Mark a pending cheque as deposited and create the Contra voucher:
        Dr  Bank A/c (deposit_bank_ledger_id)
        Cr  Cheques in Hand
    Body: { deposit_date, bank_ledger_id }
    """
    retail      = getattr(request, 'retail', None)
    fiscal_year = getattr(request, 'fiscal_year', None)

    try:
        bd = BankDetail.objects.select_related('sales_vou').get(
            pk=pk, sales_vou__retail=retail,
            payment_mode='CHEQUE', cheque_status='PENDING',
        )
    except BankDetail.DoesNotExist:
        return Response({'detail': 'Cheque not found or already processed.'}, status=status.HTTP_404_NOT_FOUND)

    deposit_date   = request.data.get('deposit_date')
    bank_ledger_id = request.data.get('bank_ledger_id')

    if not deposit_date or not bank_ledger_id:
        return Response({'detail': 'deposit_date and bank_ledger_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        bank_ledger = Ledger.objects.get(pk=bank_ledger_id)
    except Ledger.DoesNotExist:
        return Response({'detail': 'Bank ledger not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        cheques_in_hand = Ledger.objects.get(ac_name='Cheques in Hand', is_system=True)
    except Ledger.DoesNotExist:
        return Response({'detail': 'System ledger "Cheques in Hand" not found.'}, status=status.HTTP_400_BAD_REQUEST)

    from accounting.models import VoucherMain, VoucherDetail
    from accounting.utils import get_next_bill_number
    from global_vars import VoucherType
    from decimal import Decimal

    amount = Decimal(str(bd.amount))

    with transaction.atomic():
        voucher_no = get_next_bill_number(retail, VoucherType.cntr, fiscal_year)
        narration  = f"Cheque deposit — {bd.chq_no} — {bd.bank_name}"

        # Create the Contra voucher directly using PKs — avoids the name-based
        # SlugRelatedField lookup in JournalEntrySerializer which would fail if
        # two retails share a bank ledger name (Cheques in Hand is a single
        # global system ledger; its per-retail balance is tracked via
        # VoucherDetail → VoucherMain → retail).
        voucher = VoucherMain.objects.create(
            date=deposit_date,
            voucher_no=voucher_no,
            narration=narration[:150],
            amount=amount,
            voucher_type=VoucherType.cntr,
            retail=retail,
            fiscal_year=fiscal_year,
        )
        VoucherDetail.objects.create(
            voucher_main=voucher,
            voucher_no=voucher_no,
            voucher_type=VoucherType.cntr,
            account=bank_ledger,
            debit=amount,
            credit=0,
        )
        VoucherDetail.objects.create(
            voucher_main=voucher,
            voucher_no=voucher_no,
            voucher_type=VoucherType.cntr,
            account=cheques_in_hand,
            debit=0,
            credit=amount,
            chq_no=bd.chq_no or '',
            chq_date=bd.chq_date,
            party_bank_name=bd.bank_name or '',
        )

        bd.cheque_status   = 'DEPOSITED'
        bd.deposit_date    = deposit_date
        bd.deposit_voucher = voucher
        bd.save(update_fields=['cheque_status', 'deposit_date', 'deposit_voucher'])

    from ..serializers import BankDetails
    return Response(BankDetails(bd).data)


# ── B2B Pricelist lookup for a ledger ────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def b2b_pricelist_for_ledger(request, ledger_id):
    """Return the full B2B pricelist data for a ledger, plus wholesale packet rates."""
    ledger = get_object_or_404(Ledger, pk=ledger_id)
    if not ledger.b2b_pricelist_id:
        return Response(None, status=status.HTTP_204_NO_CONTENT)

    from mastersconfig.serializers import B2BPricelistSerializer
    from mastersconfig.models import Packet

    pricelist_data = B2BPricelistSerializer(ledger.b2b_pricelist).data
    # Include wholesale packet rates so frontend can fall back to rate_for_wholesale
    pricelist_data['wholesale_packet_rates'] = {
        p.pckt_no: p.rate_for_wholesale
        for p in Packet.objects.filter(rate_for_wholesale__isnull=False)
    }
    return Response(pricelist_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def retail_discount_pricelist_for_ledger(request, ledger_id):
    """Return the Retail Discount Pricelist for a ledger (if assigned)."""
    ledger = get_object_or_404(Ledger, pk=ledger_id)
    if not ledger.retail_discount_pricelist_id:
        return Response(None, status=status.HTTP_204_NO_CONTENT)
    from mastersconfig.serializers import RetailDiscountPricelistSerializer
    return Response(RetailDiscountPricelistSerializer(ledger.retail_discount_pricelist).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sales_register(request):
    """
    Sales Register — flat date-ranged listing of every Sales Voucher.
    Query params: from_date, to_date (YYYY-MM-DD, required), ldgr (optional FK), sales_person (optional FK).
    """
    try:
        retail = request.retail
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        ldgr_id = request.GET.get('ldgr')
        sp_id = request.GET.get('sales_person')

        if not from_date or not to_date:
            return Response({'success': False, 'data': None, 'error': 'from_date and to_date are required (YYYY-MM-DD).'}, status=status.HTTP_400_BAD_REQUEST)

        qs = (SalesVou.objects
              .filter(retail=retail, date1__range=[from_date, to_date])
              .select_related('ldgr', 'sales_person', 'sales_person2')
              .order_by('date1', 'billno'))

        if ldgr_id:
            qs = qs.filter(ldgr_id=ldgr_id)
        if sp_id:
            qs = qs.filter(sales_person_id=sp_id)

        rows = []
        totals = {
            'taxable_value': 0.0,
            'sgst_amt': 0.0,
            'cgst_amt': 0.0,
            'igst_amt': 0.0,
            'round_off': 0.0,
            'total_bill_value': 0.0,
        }
        for sv in qs:
            taxable = float(sv.taxable_value or 0)
            sgst = float(sv.sgst_amt or 0)
            cgst = float(sv.cgst_amt or 0)
            igst = float(sv.igst_amt or 0)
            round_off = float(sv.round_off or 0)
            total = float(sv.total_bill_value or 0)
            rows.append({
                'id': sv.id,
                'date': sv.date1,
                'billno': sv.billno,
                'gst_billno': sv.gst_billno or '',
                'party_name': sv.ldgr.ac_name if sv.ldgr else '',
                'gstin': (sv.ldgr.gst or '') if sv.ldgr else '',
                'place_of_supply': sv.place_of_supply or '',
                'salesperson': sv.sales_person.salesperson_name if sv.sales_person else '',
                'mrp': float(sv.mrp or 0),
                'discount': float(sv.discount or 0),
                'taxable_value': taxable,
                'sgst_per': float(sv.sgst_per or 0),
                'cgst_per': float(sv.cgst_per or 0),
                'igst_per': float(sv.igst_per or 0),
                'sgst_amt': sgst,
                'cgst_amt': cgst,
                'igst_amt': igst,
                'round_off': round_off,
                'total_bill_value': total,
                'is_return': bool(sv.ret_status),
            })
            totals['taxable_value'] += taxable
            totals['sgst_amt'] += sgst
            totals['cgst_amt'] += cgst
            totals['igst_amt'] += igst
            totals['round_off'] += round_off
            totals['total_bill_value'] += total

        for k in totals:
            totals[k] = round(totals[k], 2)

        return Response({'success': True, 'data': {'rows': rows, 'totals': totals, 'count': len(rows)}, 'error': None})
    except Exception as e:
        logging.exception("sales_register failed")
        return Response({'success': False, 'data': None, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sale_approval_register(request):
    """
    Sale Approval Register — flat date-ranged listing of every Sales Approval.
    Query params: from_date, to_date (YYYY-MM-DD, required), ldgr (optional FK), sales_person (optional FK).
    """
    try:
        retail = request.retail
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        ldgr_id = request.GET.get('ldgr')
        sp_id = request.GET.get('sales_person')
        status_filter = (request.GET.get('status') or 'all').lower()

        if not from_date or not to_date:
            return Response({'success': False, 'data': None, 'error': 'from_date and to_date are required (YYYY-MM-DD).'}, status=status.HTTP_400_BAD_REQUEST)

        qs = (SalesApproval.objects
              .filter(retail=retail, date1__range=[from_date, to_date])
              .select_related('ldgr', 'sales_person', 'sales_person2', 'place_of_supply')
              .prefetch_related('items')
              .order_by('date1', 'billno'))

        if ldgr_id:
            qs = qs.filter(ldgr_id=ldgr_id)
        if sp_id:
            qs = qs.filter(sales_person_id=sp_id)
        if status_filter == 'pending':
            qs = qs.filter(items__ret_status=False).distinct()

        rows = []
        totals = {
            'taxable_value': 0.0,
            'net_taxable': 0.0,
            'sgst_amt': 0.0,
            'cgst_amt': 0.0,
            'igst_amt': 0.0,
            'total_bill_value': 0.0,
        }
        for sa in qs:
            taxable = float(sa.taxable_value or 0)
            net_taxable = float(sa.net_taxable or 0)
            sgst = float(sa.sgst_amt or 0)
            cgst = float(sa.cgst_amt or 0)
            igst = float(sa.igst_amt or 0)
            total = float(sa.total_bill_value or 0)
            pos = sa.place_of_supply.name if sa.place_of_supply else ''
            items_list = list(sa.items.all())
            items_total = len(items_list)
            items_pending = sum(1 for it in items_list if not it.ret_status)
            is_pending = items_pending > 0
            rows.append({
                'id': sa.id,
                'date': sa.date1,
                'billno': sa.billno,
                'party_name': sa.ldgr.ac_name if sa.ldgr else '',
                'gstin': (sa.ldgr.gst or '') if sa.ldgr else '',
                'place_of_supply': pos,
                'salesperson': sa.sales_person.salesperson_name if sa.sales_person else '',
                'taxable_value': taxable,
                'discount': float(sa.discount or 0),
                'net_taxable': net_taxable,
                'sgst_per': float(sa.sgst_per or 0),
                'cgst_per': float(sa.cgst_per or 0),
                'igst_per': float(sa.igst_per or 0),
                'sgst_amt': sgst,
                'cgst_amt': cgst,
                'igst_amt': igst,
                'total_bill_value': total,
                'narration': getattr(sa, 'narration', '') or '',
                'items_total': items_total,
                'items_pending': items_pending,
                'is_pending': is_pending,
            })
            totals['taxable_value'] += taxable
            totals['net_taxable'] += net_taxable
            totals['sgst_amt'] += sgst
            totals['cgst_amt'] += cgst
            totals['igst_amt'] += igst
            totals['total_bill_value'] += total

        for k in totals:
            totals[k] = round(totals[k], 2)

        return Response({'success': True, 'data': {'rows': rows, 'totals': totals, 'count': len(rows)}, 'error': None})
    except Exception as e:
        logging.exception("sale_approval_register failed")
        return Response({'success': False, 'data': None, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
