from django.shortcuts import render, redirect
from django.db.models import Prefetch
from datetime import date
from django.utils import timezone
import mimetypes
import os

from purchase.filters import PurchaseItemFilterSet
from purchase.serializers import PurchaseApprovalSerializer, PurchaseOrderForPostSerializer, PurchaseOrderSerializer, PurchaseReturnSerializer, PurchaseVoucherItemsSerializer, PurchaseVoucherPostSerializer, PurchaseVoucherSerializer, PurchaseVoucherToReturnSerializer
from userauth.views import RetailBaseViewset
from .models import *
import json
from rest_framework.viewsets import ModelViewSet
from django.urls import reverse
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .utils import *
from django.shortcuts import get_object_or_404
from jewel_test.utils import *
from rest_framework.generics import ListCreateAPIView,ListAPIView
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
# Create your views here.
from global_vars import STATES_OF_INDIA
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def purchase_voucher_number_view(request):
    try:
        order_no = generate_pv_no()
        return Response({"bill_no": order_no}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def purchase_order_number_view(request):
    try:
        order_no = generate_po_no()
        return Response({"bill_no": order_no}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
 

def _scope_list_to_retail_and_fy(qs, request):
    """Scope a list queryset to the active retail and (unless ?all_fy) the active
    fiscal year. Used by the plain ListCreateAPIView list endpoints that don't
    inherit RetailBaseViewset."""
    retail = getattr(request, 'retail', None)
    qs = qs.filter(retail=retail)
    if (
        getattr(retail, 'active_fy_id', None)
        and request.query_params.get('all_fy', '').lower() not in ('1', 'true')
    ):
        qs = qs.filter(fiscal_year_id=retail.active_fy_id)
    return qs


class PurchaseOrderView(ListCreateAPIView):
    serializer_class = PurchaseOrderSerializer
    queryset = PurchaseOrder.objects.all()

    def get_queryset(self):
        return _scope_list_to_retail_and_fy(PurchaseOrder.objects.all(), self.request)


class PurchaseVoucherView(ListCreateAPIView):
    serializer_class = PurchaseVoucherSerializer
    queryset = PurchaseVoucher.objects.all()

    def get_queryset(self):
        return _scope_list_to_retail_and_fy(PurchaseVoucher.objects.all(), self.request)

class PurchaseReturnViewset(RetailBaseViewset):
    queryset = PurchaseReturn.objects.select_related('ldgr', 'ac_voucher', 'retail').prefetch_related(
        'purchasereturnitems_set__purchasereturndetails_set'
    ).all()
    serializer_class = PurchaseReturnSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ["billno", "ldgr__ac_name"]
    ordering = ['-date1', '-id']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    def get_serializer_context(self):
        """Pass request explicitly so the serializer can access request.retail
        when creating the accounting journal entry."""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def _resolve_fiscal_year(self, retail, voucher_date):
        from mastersconfig.models import FiscalYearMaster
        if voucher_date:
            fy = FiscalYearMaster.objects.filter(
                fy_start__lte=voucher_date, fy_end__gte=voucher_date,
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

    def _check_purchase_return_mutable(self, instance, action):
        from rest_framework.exceptions import ValidationError
        if instance.ac_voucher is not None and instance.ac_voucher.status == 'posted':
            raise ValidationError(
                f"Purchase return '{instance.billno}' cannot be {action} because its accounting entry is posted."
            )

    def perform_destroy(self, instance):
        from accounting.utils import release_last_bill_number
        from inventory.utils import guard_no_later_barcode_transaction
        barcode_ids = list(
            instance.purchasereturnitems_set.filter(barcode__isnull=False)
            .values_list('barcode_id', flat=True)
        )
        guard_no_later_barcode_transaction(barcode_ids, instance.billno)
        retail = instance.retail
        fiscal_year = instance.fiscal_year
        billno = instance.billno
        # Delete the linked accounting journal entry first — the FK is
        # SET_NULL, so Django won't cascade-delete it. Without this the
        # VoucherMain row outlives the PR and leaves a phantom entry in the
        # day book.
        if instance.ac_voucher_id:
            instance.ac_voucher.delete()
        super().perform_destroy(instance)
        release_last_bill_number(retail, 'PR', billno, fiscal_year)

    def perform_update(self, serializer):
        from rest_framework.exceptions import ValidationError
        retail = getattr(self.request, 'retail', None)
        if not retail:
            raise ValidationError({"retail": "Missing or invalid X-RETAIL-ID header."})
        self._check_purchase_return_mutable(serializer.instance, 'edited')
        voucher_date = serializer.validated_data.get('date1') or serializer.instance.date1
        fiscal_year = self._resolve_fiscal_year(retail, voucher_date)
        serializer.save(retail=retail, fiscal_year=fiscal_year)

class PurchaseVoucherViewset(RetailBaseViewset):
    queryset = PurchaseVoucher.objects.select_related(
        'ldgr', 'retail', 'hsn'
    ).prefetch_related(
        # Eagerly load all FK fields accessed by PurchaseVoucherItemsSerializer
        # (item, purity, barcode, order_no) so each row doesn't issue a separate query.
        Prefetch(
            'purchasevoucheritems_set',
            queryset=PurchaseVoucherItems.objects.select_related(
                'item', 'purity', 'barcode', 'order_no'
            ).order_by('id'),
        ),
        # Eagerly load all FK fields accessed by PurchaseVoucherDetailsSerializer.
        # sub_item was already here; metal_purity and packet are new additions.
        Prefetch(
            'purchasevoucheritems_set__purchasevoucherdetails_set',
            queryset=PurchaseVoucherDetails.objects.select_related(
                'sub_item', 'metal_purity', 'packet'
            ).order_by('id'),
        ),
    ).all()
    serializer_class = PurchaseVoucherPostSerializer
    filter_backends = [DjangoFilterBackend,OrderingFilter, SearchFilter]
    filterset_fields = ['voucher_type']
    search_fields = ["billno","ldgr__ac_name"]

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['-date1', 'ldgr__ac_name', '-billno']

    def _resolve_fiscal_year(self, retail, voucher_date):
        """Return the FiscalYearMaster whose date range covers voucher_date.
        Falls back to retail.active_fy when no matching FY is found."""
        from mastersconfig.models import FiscalYearMaster
        if voucher_date:
            fy = FiscalYearMaster.objects.filter(
                fy_start__lte=voucher_date,
                fy_end__gte=voucher_date,
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

    def _check_purchase_vou_mutable(self, instance, action):
        from rest_framework.exceptions import ValidationError
        if getattr(instance, 'source', 'standalone') == 'sales_inline':
            raise ValidationError(
                f"Purchase voucher '{instance.billno}' cannot be {action} directly because it was created from a sales voucher. Edit the linked sales voucher instead."
            )
        if instance.purchase_returns.exists():
            raise ValidationError(
                f"Purchase voucher '{instance.billno}' cannot be {action} because a purchase return exists against it."
            )
        if (instance.due_amt is not None and instance.bill_value is not None
                and instance.due_amt < instance.bill_value):
            raise ValidationError(
                f"Purchase voucher '{instance.billno}' cannot be {action} because a payment has been made against it."
            )

    def perform_destroy(self, instance):
        self._check_purchase_vou_mutable(instance, 'deleted')
        from accounting.utils import release_last_bill_number
        from inventory.utils import guard_no_later_barcode_transaction
        barcode_ids = list(
            instance.purchasevoucheritems_set.filter(barcode__isnull=False)
            .values_list('barcode_id', flat=True)
        )
        guard_no_later_barcode_transaction(barcode_ids, instance.billno)
        retail = instance.retail
        fiscal_year = instance.fiscal_year
        billno = instance.billno
        prefix = 'PVC' if instance.voucher_type == 'Customer' else 'PVV'
        # Delete linked accounting journals before the purchase voucher so that
        # VoucherMain/VoucherDetail entries don't outlive the inventory records.
        # (The FK is SET_NULL, so Django won't cascade-delete them automatically.)
        if instance.ac_voucher_id:
            instance.ac_voucher.delete()
        if instance.tds_ac_voucher_id:
            instance.tds_ac_voucher.delete()
        super().perform_destroy(instance)
        release_last_bill_number(retail, prefix, billno, fiscal_year)

    def perform_update(self, serializer):
        from rest_framework.exceptions import ValidationError
        retail = getattr(self.request, 'retail', None)
        if not retail:
            raise ValidationError({"retail": "Missing or invalid X-RETAIL-ID header."})
        self._check_purchase_vou_mutable(serializer.instance, 'edited')
        voucher_date = serializer.validated_data.get('date1') or serializer.instance.date1
        fiscal_year = self._resolve_fiscal_year(retail, voucher_date)
        serializer.save(retail=retail, fiscal_year=fiscal_year)

class PurchaseOrderViewset(RetailBaseViewset):
    queryset = PurchaseOrder.objects.select_related('ldgr', 'retail').prefetch_related(
        'purchaseorderitems_set'
    ).all()
    serializer_class = PurchaseOrderForPostSerializer 
    filter_backends=[DjangoFilterBackend,OrderingFilter,SearchFilter]

    search_fields=["po_no","ldgr__ac_name"]

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['-date1', '-po_no']



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_purchase_for_return(request, po_no):
    if not request.retail:
        return Response({"error": "Missing or invalid X-RETAIL-ID header"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        pv = PurchaseVoucher.objects.get(billno=po_no)
        serializer = PurchaseVoucherToReturnSerializer(pv)
        return Response(serializer.data)
    except PurchaseVoucher.DoesNotExist:
        try:
            pr = PurchaseReturn.objects.get(billno=po_no)
            serializer = PurchaseReturnSerializer(pr)
            return Response(serializer.data)
        except PurchaseReturn.DoesNotExist:
            return Response({"error": "No purchase voucher or return found for this bill number."}, status=404)

class PurchaseItemView(ListAPIView):
    serializer_class = PurchaseVoucherItemsSerializer
    queryset = PurchaseVoucherItems.objects.all()
    filter_backends = [DjangoFilterBackend , OrderingFilter]

    filterset_class = PurchaseItemFilterSet

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_pv_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response({"error": "Missing or invalid X-RETAIL-ID header"}, status=status.HTTP_400_BAD_REQUEST)
    voucher_type = request.query_params.get('voucher_type', 'Vendor')
    prefix = 'PVC' if voucher_type == 'Customer' else 'PVV'
    bill_no = peek_next_bill_number(request.retail, prefix)
    return Response({"billno": bill_no})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_pr_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response({"error": "Missing or invalid X-RETAIL-ID header"}, status=status.HTTP_400_BAD_REQUEST)
    bill_no = peek_next_bill_number(request.retail, "PR")
    return Response({"billno": bill_no})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_po_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response({"error": "Missing or invalid X-RETAIL-ID header"}, status=status.HTTP_400_BAD_REQUEST)
    bill_no = peek_next_bill_number(request.retail, "PO")
    return Response({"billno": bill_no})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def purchase_return_initial_data(request):
    """Combined initial data for the PurchaseReturn form."""
    from mastersconfig.models import Item, Packet
    from mastersconfig.serializers import ItemSerializer, PacketSerializer
    from goldrates.serializer import PurityMasterSerializer
    from contacts.models import Ledger
    from accounting.serializers import LedgerLightSerializer
    from goldrates.models import PurityMaster

    if not request.retail:
        return Response(
            {"error": "Missing or invalid X-RETAIL-ID header"},
            status=status.HTTP_400_BAD_REQUEST
        )

    from accounting.utils import peek_next_bill_number
    bill_no = peek_next_bill_number(request.retail, "PR")
    ledgers_qs = (Ledger.objects
                  .filter(roles__role='VD')
                  .select_related('ac_group')
                  .prefetch_related('roles')
                  .only('id', 'ac_name', 'ac_group', 'state', 'ship_state')
                  .distinct())
    items_qs = Item.objects.select_related('grp', 'hsn_no', 'purchase_ledger', 'sale_ledger').all()
    purity_qs = PurityMaster.objects.all()
    packets_qs = Packet.objects.select_related('stone_item_id').all()

    retail_state = None
    if request.retail and request.retail.state:
        retail_state = request.retail.state.name

    return Response({
        "billno": bill_no,
        "ledgers": LedgerLightSerializer(ledgers_qs, many=True).data,
        "items": ItemSerializer(items_qs, many=True).data,
        "purity": PurityMasterSerializer(purity_qs, many=True).data,
        "packets": PacketSerializer(packets_qs, many=True).data,
        "retail_state": retail_state,
    })


class PurchaseAttachmentListCreate(ListCreateAPIView):
    from .serializers import PurchaseAttachmentSerializer
    serializer_class = PurchaseAttachmentSerializer
    from rest_framework.parsers import MultiPartParser
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        from .models import PurchaseAttachment
        purchase_id = self.request.query_params.get('purchase')
        if purchase_id:
            return PurchaseAttachment.objects.filter(purchase_id=purchase_id).order_by('-uploaded_at')
        return PurchaseAttachment.objects.none()


class PurchaseAttachmentDelete(APIView):
    def delete(self, request, pk):
        from .models import PurchaseAttachment
        try:
            att = PurchaseAttachment.objects.get(pk=pk)
            att.file.delete(save=False)
            att.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PurchaseAttachment.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_attachment_file(request, name):
    """
    Stream an attachment file from the configured (dynamic) storage root.
    Authentication is intentionally not enforced here — consistent with Django's
    default MEDIA_URL behaviour for local deployments. The URL contains an
    opaque hashed name (Django's default collision-avoidance) which provides
    de-facto obscurity.
    """
    from urllib.parse import unquote
    from mastersconfig.storage import _configured_root

    # Decode percent-encoded characters and normalise separators
    name = unquote(name)
    root = _configured_root()
    abs_root = os.path.abspath(root)
    full_path = os.path.normpath(os.path.join(abs_root, name))

    # Path-traversal guard: resolved path must start with the storage root
    if not full_path.startswith(abs_root + os.sep) and full_path != abs_root:
        return Response({'error': 'Forbidden'}, status=403)

    if not os.path.isfile(full_path):
        return Response({'error': 'File not found'}, status=404)

    content_type, _ = mimetypes.guess_type(full_path)
    content_type = content_type or 'application/octet-stream'

    with open(full_path, 'rb') as f:
        from django.http import HttpResponse
        response = HttpResponse(f.read(), content_type=content_type)

    basename = os.path.basename(full_path)
    response['Content-Disposition'] = f'inline; filename="{basename}"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stock_matching_report(request):
    """
    Bill-wise reconciliation of Purchase Voucher sub-items vs Barcode sub-items.

    For every Purchase Voucher in the selected date range, aggregates
    PurchaseVoucherDetails (sub_ct, sub_gw) per item and compares it against
    the aggregated BarcodeDetails (ct, gw) of the barcodes that were created
    from that PV (linked via BarcodeMain.voucher_no == PurchaseVoucher.billno).

    A tolerance (default 0.05) is applied — differences within ±tolerance are
    treated as zero. Supports ?from=YYYY-MM-DD&to=YYYY-MM-DD&tolerance=0.05
    &mismatches_only=1.
    """
    from decimal import Decimal
    from datetime import date, datetime, timedelta
    from collections import defaultdict
    from django.db.models import Sum
    from inventory.models import BarcodeDetails

    retail = getattr(request, 'retail', None)
    if not retail:
        return Response({'error': 'Retail context missing'}, status=400)

    today = date.today()
    default_from = today.replace(day=1)
    try:
        from_date = datetime.strptime(request.GET.get('from') or default_from.isoformat(), '%Y-%m-%d').date()
        to_date = datetime.strptime(request.GET.get('to') or today.isoformat(), '%Y-%m-%d').date()
    except ValueError:
        return Response({'error': 'Invalid date — expected YYYY-MM-DD'}, status=400)

    try:
        tolerance = Decimal(str(request.GET.get('tolerance') or '0.05'))
    except Exception:
        tolerance = Decimal('0.05')

    mismatches_only = (request.GET.get('mismatches_only') or '').lower() in ('1', 'true', 'yes')

    # --- Stock side: PurchaseVoucherDetails aggregated per (bill, item) ---
    pv_rows = (
        PurchaseVoucherDetails.objects
        .filter(
            billno__retail=retail,
            billno__date1__range=[from_date, to_date],
            billno__is_return=False,
            sub_item__isnull=False,
        )
        .values(
            'billno_id',
            'billno__billno',
            'billno__date1',
            'billno__ldgr__ac_name',
            'sub_item_id',
            'sub_item__item_name',
        )
        .annotate(stock_ct=Sum('sub_ct'), stock_gw=Sum('sub_gw'))
        .order_by('billno__date1', 'billno__billno', 'sub_item__item_name')
    )

    # Collect the set of bill numbers for the barcode lookup.
    bill_numbers = {r['billno__billno'] for r in pv_rows}
    if not bill_numbers:
        return Response({
            'tolerance': float(tolerance),
            'from': from_date.isoformat(),
            'to': to_date.isoformat(),
            'bills': [],
        })

    # --- Barcode side: BarcodeDetails aggregated per (voucher_no, item) ---
    bc_rows = (
        BarcodeDetails.objects
        .filter(
            barcode__retail=retail,
            barcode__voucher_no__in=bill_numbers,
            item__isnull=False,
        )
        .values('barcode__voucher_no', 'item_id', 'item__item_name')
        .annotate(bc_ct=Sum('ct'), bc_gw=Sum('gw'))
    )
    bc_lookup = {}
    for r in bc_rows:
        bc_lookup[(r['barcode__voucher_no'], r['item_id'])] = {
            'ct': r['bc_ct'] or Decimal('0'),
            'gw': r['bc_gw'] or Decimal('0'),
        }

    # --- Per-bill barcode list (for clickable chips on the frontend) ---
    from inventory.models import BarcodeMain
    barcode_rows = (
        BarcodeMain.objects
        .filter(retail=retail, voucher_no__in=bill_numbers)
        .select_related('item')
        .values('id', 'barcode', 'voucher_no', 'stk_status',
                'pcs', 'gw', 'item__item_name', 'item__short_code', 'created_date')
        .order_by('voucher_no', 'created_date', 'id')
    )
    barcodes_by_bill = defaultdict(list)
    for b in barcode_rows:
        barcodes_by_bill[b['voucher_no']].append({
            'id': b['id'],
            'barcode': b['barcode'],
            'item_name': b['item__item_name'] or '',
            'item': b['item__short_code'] or '',
            'pcs': b['pcs'],
            'gw': float(b['gw']) if b['gw'] is not None else None,
            'stk_status': bool(b['stk_status']),
            'created_date': b['created_date'].isoformat() if b['created_date'] else None,
        })

    # --- Combine + apply tolerance ---
    bills_map = {}
    for r in pv_rows:
        billno = r['billno__billno']
        item_id = r['sub_item_id']
        stk_ct = r['stock_ct'] or Decimal('0')
        stk_gw = r['stock_gw'] or Decimal('0')
        bc = bc_lookup.get((billno, item_id), {'ct': Decimal('0'), 'gw': Decimal('0')})

        diff_ct = (stk_ct - bc['ct']).quantize(Decimal('0.001'))
        diff_gw = (stk_gw - bc['gw']).quantize(Decimal('0.001'))
        if abs(diff_ct) <= tolerance:
            diff_ct = Decimal('0')
        if abs(diff_gw) <= tolerance:
            diff_gw = Decimal('0')

        if billno not in bills_map:
            bills_map[billno] = {
                'billno': billno,
                'date': r['billno__date1'].isoformat() if r['billno__date1'] else None,
                'vendor': r['billno__ldgr__ac_name'] or '',
                'items': [],
                'barcodes': barcodes_by_bill.get(billno, []),
                'has_issue': False,
            }
        bills_map[billno]['items'].append({
            'item_id': item_id,
            'item_name': r['sub_item__item_name'] or '',
            'stock_ct': float(stk_ct),
            'barcode_ct': float(bc['ct']),
            'diff_ct': float(diff_ct),
            'stock_gw': float(stk_gw),
            'barcode_gw': float(bc['gw']),
            'diff_gw': float(diff_gw),
            'row_issue': diff_ct != 0 or diff_gw != 0,
        })
        if diff_ct != 0 or diff_gw != 0:
            bills_map[billno]['has_issue'] = True

    bills = sorted(bills_map.values(), key=lambda b: (b['date'] or '', b['billno']))
    if mismatches_only:
        bills = [b for b in bills if b['has_issue']]

    # Overall totals for a summary header
    summary = {
        'total_bills': len(bills),
        'bills_with_issues': sum(1 for b in bills if b['has_issue']),
    }

    return Response({
        'tolerance': float(tolerance),
        'from': from_date.isoformat(),
        'to': to_date.isoformat(),
        'mismatches_only': mismatches_only,
        'summary': summary,
        'bills': bills,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_po_items_by_vendor(request):
    """
    Purchase-order line items for a given vendor that have not yet been
    billed on any Purchase Voucher. Used by the Purchase Voucher screen to
    auto-open a picker when the vendor is selected.
    """
    retail = getattr(request, 'retail', None)
    if not retail:
        return Response({'error': 'Retail context missing'}, status=400)

    vendor_id = request.GET.get('vendor')
    if not vendor_id:
        return Response({'error': 'vendor param required'}, status=400)

    # Filter via the parent voucher's retail FK — `PurchaseVoucherItems.retail`
    # is not populated by the create path, so a direct `retail=retail` filter
    # would silently match nothing and let already-billed PO lines reappear.
    vouchered = set(
        PurchaseVoucherItems.objects
        .filter(billno__retail=retail, po_no__isnull=False)
        .exclude(po_no='')
        .values_list('po_no', 'po_sl_no')
    )

    # Also exclude PO lines whose linked customer-order item has already been
    # consumed via the direct CO → PV path (which doesn't set po_no/po_sl_no).
    co_items_consumed = set(
        PurchaseVoucherItems.objects
        .filter(billno__retail=retail, customer_order_item__isnull=False)
        .values_list('customer_order_item_id', flat=True)
    )

    qs = (
        PurchaseOrderItems.objects
        .select_related('po_slip', 'po_slip__ldgr', 'item', 'item__hsn_no', 'purity')
        .filter(po_slip__retail=retail, po_slip__ldgr_id=vendor_id)
        .order_by('po_slip__date1', 'po_slip__po_no', 'po_sl_no')
    )

    data = []
    for r in qs:
        po_no = r.po_slip.po_no if r.po_slip else None
        if (po_no, r.po_sl_no) in vouchered:
            continue
        if r.customer_order_item_id and r.customer_order_item_id in co_items_consumed:
            continue
        data.append({
            'po_item_id': r.id,
            'po_id': r.po_slip_id,
            'po_no': po_no,
            'po_date': r.po_slip.date1.isoformat() if r.po_slip and r.po_slip.date1 else None,
            'po_sl_no': r.po_sl_no,
            'item_id': r.item.id if r.item else None,
            'item': r.item.short_code if r.item else None,
            'item_name': r.item.item_name if r.item else None,
            'purity_id': r.purity.id if r.purity else None,
            'purity': r.purity.purity if r.purity else None,
            'pcs': r.pcs,
            'approx_wt': float(r.approx_wt) if r.approx_wt is not None else None,
            'design_code': r.design_code,
            'size': r.size,
            'remarks': r.remarks,
            'due_date': r.due_date.isoformat() if r.due_date else None,
            'cgst': float(r.item.hsn_no.cgst) if r.item and r.item.hsn_no and r.item.hsn_no.cgst is not None else 0,
            'sgst': float(r.item.hsn_no.sgst) if r.item and r.item.hsn_no and r.item.hsn_no.sgst is not None else 0,
            'igst': float(r.item.hsn_no.igst) if r.item and r.item.hsn_no and r.item.hsn_no.igst is not None else 0,
        })
    return Response(data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_purchases_for_adjustment(request):
    """Return customer-type purchase vouchers for a given ledger that have unadjusted balance."""
    from django.db.models import Sum, F, DecimalField, Value
    from django.db.models.functions import Coalesce

    ldgr_id = request.GET.get('ldgr')
    if not ldgr_id or not request.retail:
        return Response([])

    qs = PurchaseVoucher.objects.filter(
        voucher_type='Customer',
        ldgr_id=ldgr_id,
        retail=request.retail,
        is_return=False,
        source='standalone',
    ).annotate(
        legacy_adjusted=Coalesce(
            Sum('linked_sales_vouchers__old_gold_adjusted'),
            Value(0), output_field=DecimalField()
        ),
        multi_adjusted=Coalesce(
            Sum('sale_adjustments__amount'),
            Value(0), output_field=DecimalField()
        ),
    ).annotate(
        total_adjusted=F('legacy_adjusted') + F('multi_adjusted'),
        available_balance=F('bill_value') - F('legacy_adjusted') - F('multi_adjusted'),
    ).filter(
        available_balance__gt=0
    ).values('id', 'billno', 'date1', 'bill_value', 'total_adjusted', 'available_balance')

    return Response(list(qs))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tds_register(request):
    retail = request.retail
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    section = request.GET.get('section')

    qs = PurchaseVoucher.objects.filter(
        retail=retail,
        tds_amt__gt=0
    ).select_related('ldgr', 'tds_section')

    if from_date:
        qs = qs.filter(date1__gte=from_date)
    if to_date:
        qs = qs.filter(date1__lte=to_date)
    if section:
        qs = qs.filter(tds_section__section_code=section)

    data = [{
        'bill_no': v.billno,
        'date': v.date1,
        'vendor': v.ldgr.ac_name if v.ldgr else '',
        'pan': v.ldgr.pan or '' if v.ldgr else '',
        'section': v.tds_section.section_code if v.tds_section else '',
        'description': v.tds_section.description if v.tds_section else '',
        'taxable_value': float(v.tds_taxable_value),
        'tds_rate': float(v.tds_rate),
        'tds_amt': float(v.tds_amt),
    } for v in qs]

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rcm_register(request):
    """RCM liability register — old gold purchased from unregistered individuals."""
    retail = request.retail
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    qs = PurchaseVoucher.objects.filter(
        retail=retail,
        is_rcm=True,
    ).select_related('ldgr')

    if from_date:
        qs = qs.filter(date1__gte=from_date)
    if to_date:
        qs = qs.filter(date1__lte=to_date)

    data = [{
        'bill_no': v.billno,
        'date': v.date1,
        'party': v.ldgr.ac_name if v.ldgr else '',
        'item_total': float(v.item_total or 0),
        'cgst': float(v.cgst or 0),
        'sgst': float(v.sgst or 0),
        'igst': float(v.igst or 0),
        'bill_value': float(v.bill_value or 0),
    } for v in qs]

    return Response(data)






# ── GSTR-2B Reconciliation ────────────────────────────────────────────────────

class GSTR2BReconcileView(APIView):
    """
    POST /purchase/api/gstr2b-reconcile/
    Body: multipart, field 'file' = GSTR-2B JSON downloaded from GST portal.
    Matches portal invoices against PurchaseVoucher records by supplier GSTIN + invoice number.
    Returns: { summary, results[] }
    """
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)

        try:
            raw = json.loads(file.read().decode('utf-8-sig'))
        except Exception:
            return Response({'error': 'Invalid JSON file'}, status=400)

        retail = request.retail

        # Navigate GSTR-2B structure — try common paths
        try:
            b2b_list = (
                raw.get('data', raw).get('docdata', {}).get('b2b', [])
                or raw.get('b2b', [])
            )
        except AttributeError:
            return Response({'error': 'Unexpected GSTR-2B JSON structure'}, status=400)

        results = []
        for supplier in b2b_list:
            ctin = supplier.get('ctin', '')
            for inv in supplier.get('inv', []):
                inum    = (inv.get('inum') or '').strip()
                dt_str  = inv.get('dt', '')
                val     = float(inv.get('val') or 0)
                itms    = inv.get('itms', [])
                itm_det = itms[0].get('itm_det', {}) if itms else {}
                cgst_2b = float(itm_det.get('cgst', 0))
                sgst_2b = float(itm_det.get('sgst', 0))
                igst_2b = float(itm_det.get('igst', 0))
                txval   = float(itm_det.get('txval', 0))

                # Match PurchaseVoucher: same retail, supplier GSTIN, bill/ref number
                from django.db.models import Q
                pv = PurchaseVoucher.objects.filter(
                    retail=retail,
                    ldgr__gst__iexact=ctin,
                ).filter(
                    Q(billno__iexact=inum) | Q(ref_no__iexact=inum)
                ).select_related('ldgr').first()

                if pv:
                    our_cgst = float(pv.cgst or 0)
                    our_sgst = float(pv.sgst or 0)
                    our_igst = float(pv.igst or 0)
                    cgst_diff = round(our_cgst - cgst_2b, 2)
                    sgst_diff = round(our_sgst - sgst_2b, 2)
                    igst_diff = round(our_igst - igst_2b, 2)
                    has_diff  = abs(cgst_diff) > 1 or abs(sgst_diff) > 1 or abs(igst_diff) > 1
                    status_flag = 'MISMATCH' if has_diff else 'MATCHED'
                else:
                    our_cgst = our_sgst = our_igst = None
                    cgst_diff = sgst_diff = igst_diff = None
                    status_flag = 'MISSING'

                results.append({
                    'status':          status_flag,
                    'supplier_gstin':  ctin,
                    'supplier_name':   pv.ldgr.ac_name if pv else None,
                    'invoice_no_2b':   inum,
                    'invoice_date_2b': dt_str,
                    'val_2b':          val,
                    'txval_2b':        txval,
                    'cgst_2b':         cgst_2b,
                    'sgst_2b':         sgst_2b,
                    'igst_2b':         igst_2b,
                    'our_billno':      pv.billno if pv else None,
                    'our_date':        str(pv.date1) if pv else None,
                    'our_bill_value':  float(pv.bill_value) if pv else None,
                    'our_cgst':        our_cgst,
                    'our_sgst':        our_sgst,
                    'our_igst':        our_igst,
                    'cgst_diff':       cgst_diff,
                    'sgst_diff':       sgst_diff,
                    'igst_diff':       igst_diff,
                    'pv_id':           pv.id if pv else None,
                })

        matched  = sum(1 for r in results if r['status'] == 'MATCHED')
        mismatch = sum(1 for r in results if r['status'] == 'MISMATCH')
        missing  = sum(1 for r in results if r['status'] == 'MISSING')

        return Response({
            'summary': {
                'total': len(results),
                'matched':  matched,
                'mismatch': mismatch,
                'missing':  missing,
            },
            'results': results,
        })


class PurchaseApprovalViewset(RetailBaseViewset):
    """Goods held on approval from a vendor. Lines are later bought (pulled into a
    Purchase Voucher via `to_purchase_voucher`) or sent back (`return_items`)."""
    queryset = PurchaseApproval.objects.select_related('ldgr', 'retail').prefetch_related(
        'items__item', 'items__purity', 'items__details__sub_item',
        'items__details__metal_purity', 'items__details__packet', 'items__purchase_lines',
    ).all()
    serializer_class = PurchaseApprovalSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['billno', 'ldgr__ac_name', 'narration']
    ordering_fields = ['date1', 'billno', 'ldgr__ac_name']
    ordering = ['-date1', '-id']

    def _check_fy_open(self, fiscal_year, action):
        from mastersconfig.fy_utils import check_fy_allows_change
        check_fy_allows_change(fiscal_year, 'PA', action)

    def perform_update(self, serializer):
        self._check_fy_open(serializer.instance.fiscal_year, 'edited')
        serializer.save()

    def perform_destroy(self, instance):
        from rest_framework.exceptions import ValidationError
        self._check_fy_open(instance.fiscal_year, 'deleted')
        settled = [i.sl_no for i in instance.items.all() if i.status != PurchaseApprovalItem.PENDING]
        if settled:
            raise ValidationError(
                f"Approval '{instance.billno}' cannot be deleted: lines {settled} are already purchased or returned.")
        from accounting.utils import release_last_bill_number
        from purchase.approval_stock import reverse_stock
        retail, fy, billno = instance.retail, instance.fiscal_year, instance.billno
        with transaction.atomic():
            for line in instance.items.all():
                reverse_stock(line, 'PURCHASE_APPR_DEL')
            super().perform_destroy(instance)
        release_last_bill_number(retail, 'PAP', billno, fy)

    def _pending_lines(self, approval, ids=None):
        lines = [i for i in approval.items.all() if i.status == PurchaseApprovalItem.PENDING]
        if ids is not None:
            lines = [i for i in lines if i.id in set(ids)]
        return lines

    @action(detail=True, methods=['get'], url_path='to-purchase-voucher')
    def to_purchase_voucher(self, request, pk=None):
        """Prefill payload for the Purchase Voucher form: the approval's lines that are
        still undecided (optionally narrowed with ?items=1,2). Saving the voucher with
        `approval_item` set on a line is what marks that approval line as purchased."""
        approval = self.get_object()
        ids = request.query_params.get('items')
        ids = [int(x) for x in ids.split(',') if x.strip().isdigit()] if ids else None
        lines = self._pending_lines(approval, ids)
        if not lines:
            return Response({"detail": "No pending lines left on this approval."}, status=400)
        return Response({
            "approval": approval.billno,
            "ldgr": approval.ldgr_id,
            "voucher_type": "Vendor",
            "narration": f"Against approval {approval.billno}",
            "items": [{
                "approval_item": i.id,
                "item": i.item.short_code,
                "item_name": i.item.item_name,
                "pcs": i.pcs,
                "gw": str(i.gw),
                "purity": i.purity.purity if i.purity else None,
                "making_type": i.making_type,
                "making": str(i.making),
                "making_value": int(i.making_value or 0),
                "item_value": str(i.amount),
                "remarks": i.remarks,
                "purchasevoucherdetails_set": [{
                    "sub_item": d.sub_item.short_code,
                    "sub_item_name": d.sub_item.item_name,
                    "sub_pcs": d.sub_pcs,
                    "sub_gw": str(d.sub_gw),
                    "sub_ct": str(d.sub_ct),
                    "metal_purity": d.metal_purity.purity if d.metal_purity else None,
                    "packet": d.packet.pckt_no if d.packet else None,
                    "rate": str(d.rate),
                    "value": str(d.value),
                } for d in i.details.all()],
            } for i in lines],
        })

    @action(detail=True, methods=['post'], url_path='return-items')
    def return_items(self, request, pk=None):
        """Send lines back to the vendor. Body: {"items": [line ids], "returned_on": "YYYY-MM-DD"}."""
        from rest_framework.exceptions import ValidationError
        approval = self.get_object()
        self._check_fy_open(approval.fiscal_year, 'returned')
        ids = request.data.get('items') or []
        returned_on = parse_date(str(request.data.get('returned_on') or '')) or date.today()
        lines = self._pending_lines(approval, ids)
        if not ids or len(lines) != len(set(ids)):
            raise ValidationError("Choose lines that are still pending (not already purchased or returned).")
        from purchase.approval_stock import reverse_stock
        with transaction.atomic():
            for line in lines:
                line.returned_on = returned_on
                line.save(update_fields=['returned_on'])
                reverse_stock(line, 'PURCHASE_APPR_RET')
        return Response(self.get_serializer(self.get_object()).data)

    @action(detail=True, methods=['post'], url_path='undo-return')
    def undo_return(self, request, pk=None):
        """Put returned lines back on approval. Body: {"items": [line ids]}."""
        approval = self.get_object()
        self._check_fy_open(approval.fiscal_year, 'changed')
        ids = request.data.get('items') or []
        from purchase.approval_stock import apply_stock
        with transaction.atomic():
            for line in approval.items.filter(pk__in=ids, returned_on__isnull=False):
                line.returned_on = None
                line.save(update_fields=['returned_on'])
                apply_stock(line, 'PURCHASE_APPR_UNRET')
        return Response(self.get_serializer(self.get_object()).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_pap_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response({"error": "Missing or invalid X-RETAIL-ID header"}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"billno": peek_next_bill_number(request.retail, 'PAP')})
