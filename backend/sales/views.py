import json
import logging
logger = logging.getLogger(__name__)
from django.shortcuts import get_object_or_404, render
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.utils.timezone import make_aware
from django.utils import timezone
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter,SearchFilter
from sales.serializers import CustomerOrderSerializer, PortalCustomerOrderSerializer
from .models import *
from django.contrib.auth.decorators import login_required
from userauth import views
from rest_framework.generics import ListCreateAPIView,RetrieveUpdateDestroyAPIView
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
#import other relevant models
from goldrates.models import PurityMaster
from contacts.models import Ledger, LedgerRole
from mastersconfig.models import Item
from .models import *

# Create your views here.

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_no_view(request):
    """Return a read-only preview of the next Customer Order number (no DB write)."""
    try:
        from accounting.utils import peek_next_bill_number
        retail = request.retail
        order_no = peek_next_bill_number(retail, "CO")
        return Response({"order_no": order_no}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class CustomerOrderView(ListCreateAPIView):
    queryset = CustomerOrder.objects.all()
    serializer_class = CustomerOrderSerializer
    filter_backends = [OrderingFilter,DjangoFilterBackend]
    ordering = ['-order_no']
    

    def get_queryset(self):
        return CustomerOrder.objects.filter(retail=self.request.retail).select_related('ldgr').prefetch_related('items')

    def perform_create(self, serializer):
        serializer.save(retail=self.request.retail)

class CustomerOrderViewset(views.RetailBaseViewset):
    queryset = CustomerOrder.objects.select_related('ldgr', 'retail').prefetch_related('items', 'linked_vouchers').all()
    serializer_class = CustomerOrderSerializer
    filter_backends = [OrderingFilter, DjangoFilterBackend, SearchFilter]
    filterset_fields = ['ldgr', 'status']
    search_fields = ['order_no', 'ldgr__ac_name']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['order_no']

    def perform_create(self, serializer):
        from accounting.utils import get_next_bill_number
        retail = self.request.retail
        order_no = get_next_bill_number(retail, "CO")
        serializer.save(retail=retail, order_no=order_no)

    def perform_destroy(self, instance):
        from rest_framework.exceptions import ValidationError
        from accounting.utils import release_last_bill_number
        from accounting.models import VoucherMain
        if instance.linked_vouchers.exists():
            raise ValidationError(
                f"Customer order '{instance.order_no}' cannot be deleted because a sales voucher has been raised against it."
            )
        order_no = instance.order_no
        retail = instance.retail
        fiscal_year = getattr(retail, 'active_fy', None)
        # Detach any advance RCPT vouchers so the receipts survive as plain customer credits
        VoucherMain.objects.filter(customer_order=instance).update(customer_order=None)
        super().perform_destroy(instance)
        release_last_bill_number(retail, "CO", order_no, fiscal_year)

    _SPEC_FIELDS = ('item_id', 'pcs', 'gw', 'purity', 'making_type', 'making_amt', 'size')

    def _lock_state(self, item_row):
        from sales.serializers import _customer_order_item_lock
        return _customer_order_item_lock(item_row)[0]

    def _norm(self, v):
        if v is None or v == '':
            return None
        try:
            from decimal import Decimal
            return Decimal(str(v))
        except Exception:
            return str(v)

    def perform_update(self, serializer):
        from rest_framework.exceptions import ValidationError
        instance = serializer.instance

        # Terminal states block all edits
        if instance.delivery_status in ('delivered', 'cancelled'):
            raise ValidationError(
                f"Customer order '{instance.order_no}' cannot be edited because it is in '{instance.delivery_status}' state."
            )

        # Per-line lock validation using the raw request payload
        incoming_items = self.request.data.get('items', []) or []
        existing_by_id = {it.id: it for it in instance.items.all()}

        incoming_ids = set()
        for payload in incoming_items:
            pid = payload.get('id')
            if not pid:
                continue  # new line, no lock possible
            incoming_ids.add(pid)
            existing = existing_by_id.get(pid)
            if not existing:
                continue
            state = self._lock_state(existing)
            if state == 'unlocked':
                continue
            # locked: spec fields must be unchanged
            db_snapshot = {
                'item_id': existing.item_id.short_code if existing.item_id else None,
                'pcs':     existing.pcs,
                'gw':      existing.gw,
                'purity':  existing.purity.purity if existing.purity else None,
                'making_type': existing.making_type,
                'making_amt':  existing.making_amt,
                'size':    existing.size,
            }
            for f in self._SPEC_FIELDS:
                if self._norm(payload.get(f)) != self._norm(db_snapshot.get(f)):
                    raise ValidationError(
                        f"Line #{existing.sl_no} is {state.replace('_', ' ')} and its '{f}' cannot be changed."
                    )

        # Removed locked lines are not allowed
        for pid, existing in existing_by_id.items():
            if pid in incoming_ids:
                continue
            state = self._lock_state(existing)
            if state != 'unlocked':
                raise ValidationError(
                    f"Line #{existing.sl_no} is {state.replace('_', ' ')} and cannot be removed from the order."
                )

        super().perform_update(serializer)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        from rest_framework.exceptions import ValidationError
        from accounting.models import VoucherMain
        order = self.get_object()
        if order.delivery_status in ('delivered', 'cancelled'):
            raise ValidationError(
                f"Customer order '{order.order_no}' is already in '{order.delivery_status}' state."
            )
        pre_data = self.get_serializer(order).data
        had_advance = pre_data.get('has_advance')
        had_production = pre_data.get('has_in_production_items')
        order.delivery_status = 'cancelled'
        order.save(update_fields=['delivery_status'])
        # Detach any advance RCPT vouchers so the receipts survive as plain customer credits
        VoucherMain.objects.filter(customer_order=order).update(customer_order=None)
        order.refresh_from_db()
        data = self.get_serializer(order).data
        warnings = []
        if had_production:
            warnings.append("Some items are still in production. Coordinate with the karigar / supplier to stop or divert work.")
        if had_advance:
            warnings.append("Advance receipts remain on the customer's ledger as a credit. Refund or adjust against a future sale.")
        return Response({**data, 'warnings': warnings})

    @action(detail=True, methods=['get'], url_path='advance-available')
    def advance_available(self, request, pk=None):
        """
        Returns the order's advance state, derived from linked RCPT vouchers:
          - advance_amt:        total advance received (SUM of linked receipts)
          - advance_reconciled: total already applied to sales bills
          - advance_available:  remaining that can be applied to a new bill
        The frontend should use `advance_available` as a read-only display;
        the server auto-applies it when the sale is created.
        """
        order = self.get_object()
        return Response({
            'order_no':           order.order_no,
            'advance_amt':        float(order.advance_amt),
            'advance_reconciled': float(order.advance_reconciled),
            'advance_available':  float(order.advance_available),
        })


class CustomerOrderNumberView(ListCreateAPIView):

    queryset = CustomerOrder.objects.all().distinct()
    serializer_class = CustomerOrderSerializer
    filter_backends = [OrderingFilter]
    ordering = ['-order_no']

class RetrieveCustomerOrderView(RetrieveUpdateDestroyAPIView):
    queryset = CustomerOrder.objects.all()
    serializer_class = CustomerOrderSerializer

from .serializers import CustomerOrderItemsToPurchaseStyleSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_customer_item_as_purchase_style(request, order_no, sl_no):
    try:
        item = CustomerOrderItems.objects.get(order_no=order_no, sl_no=sl_no)
    except CustomerOrderItems.DoesNotExist:
        return Response({"detail": "Item not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = CustomerOrderItemsToPurchaseStyleSerializer(item)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_customer_order_items(request):
    """Customer-order line items not yet released to any Purchase Order
    or Karigar Job Work, scoped to the current retail."""
    retail = getattr(request, 'retail', None)
    if not retail:
        return Response({'error': 'Retail context missing'}, status=400)

    qs = (
        CustomerOrderItems.objects
        .select_related('order_no', 'order_no__ldgr', 'item_id', 'purity')
        .filter(
            order_no__retail=retail,
            purchaseorderitems__isnull=True,
            karigarissueitem__isnull=True,
            purchasevoucheritems__isnull=True,   # exclude direct-PV'd CO items
        )
        .order_by('order_no__date1', 'order_no__order_no', 'sl_no')
    )

    data = [
        {
            'co_item_id': r.id,
            'co_id': r.order_no_id,
            'co_no': r.order_no.order_no if r.order_no else None,
            'co_date': r.order_no.date1.isoformat() if r.order_no and r.order_no.date1 else None,
            'customer_name': r.order_no.ldgr.ac_name if r.order_no and r.order_no.ldgr else None,
            'sl_no': r.sl_no,
            'item': r.item_id.short_code if r.item_id else None,
            'item_name': r.item_id.item_name if r.item_id else None,
            'purity': r.purity.purity if r.purity else None,
            'pcs': r.pcs,
            'approx_wt': float(r.gw) if r.gw is not None else None,
            'size': r.size,
            'due_date': r.order_no.delivery_date.isoformat() if r.order_no and r.order_no.delivery_date else None,
            'remarks': r.remarks,
        }
        for r in qs
    ]
    return Response(data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_order_timeline(request, order_id):
    """
    Per-item event timeline for a single customer order.

    Stitches together already-existing FKs across sales, purchase, manufacturing
    and inventory to produce a precomputed list of events per CO item:
        placed -> released_po / released_mo -> received_karigar -> barcoded -> delivered

    Pure read - no writes, no schema changes.
    """
    from purchase.models import PurchaseOrderItems, PurchaseVoucherItems
    from manufacturing.models import KarigarIssueItem, KarigarReceiveItem
    from sales.models import SalesVouItem
    from sales.serializers import _customer_order_item_lock
    from inventory.models import BarcodeMain

    def _barcodes_for_pv(pv_item_id):
        """A single PV line may split into multiple barcodes (1:N).
        BarcodeMain.pur_voucher is the canonical direction."""
        return list(BarcodeMain.objects.filter(pur_voucher_id=pv_item_id).order_by('created_date', 'id'))

    def _barcodes_for_rec(rec_item_id):
        """Same pattern for the MO path — BarcodeMain.rec_item is canonical."""
        return list(BarcodeMain.objects.filter(rec_item_id=rec_item_id).order_by('created_date', 'id'))

    retail = getattr(request, 'retail', None)
    if not retail:
        return Response({'error': 'Retail context missing'}, status=400)

    try:
        order = (
            CustomerOrder.objects
            .select_related('ldgr', 'retail')
            .prefetch_related('items', 'items__item_id', 'items__purity')
            .get(id=order_id, retail=retail)
        )
    except CustomerOrder.DoesNotExist:
        return Response({'error': 'Customer order not found'}, status=404)

    items_payload = []
    for coi in order.items.all().order_by('sl_no'):
        events = []

        # 1. placed
        if order.date1:
            events.append({
                'kind': 'placed',
                'date': order.date1.isoformat(),
                'label': 'Order placed',
                'ref': order.order_no,
            })

        po_item = (
            PurchaseOrderItems.objects
            .select_related('po_slip', 'po_slip__ldgr')
            .filter(customer_order_item=coi)
            .first()
        )
        ki_item = (
            KarigarIssueItem.objects
            .select_related('issue_slip', 'issue_slip__karigar_ldgr')
            .filter(customer_order_item=coi)
            .first()
        )

        # 2. released_po / received on PV / barcode via PV.
        # A single PV line can split into multiple barcodes (1:N), so collect a list.
        barcodes = []
        if po_item and po_item.po_slip:
            po = po_item.po_slip
            events.append({
                'kind': 'released_po',
                'date': po.date1.isoformat() if po.date1 else None,
                'label': 'Released to Purchase Order',
                'ref': po.po_no,
                'vendor': po.ldgr.ac_name if po.ldgr else None,
            })
            # Any PV line matching this PO's (po_no, po_sl_no) — with or without a barcode yet.
            pv_item_po = (
                PurchaseVoucherItems.objects
                .select_related('billno', 'billno__ldgr')
                .filter(po_no=po.po_no, po_sl_no=po_item.po_sl_no)
                .order_by('id')
                .first()
            )
            if pv_item_po and pv_item_po.billno:
                pv_bill = pv_item_po.billno
                events.append({
                    'kind': 'received_pv',
                    'date': pv_bill.date1.isoformat() if pv_bill.date1 else None,
                    'label': 'Received on Purchase Voucher',
                    'ref': pv_bill.billno,
                    'vendor': pv_bill.ldgr.ac_name if getattr(pv_bill, 'ldgr', None) else None,
                })
                # Barcodes are authoritatively linked via BarcodeMain.pur_voucher (1:N).
                barcodes.extend(_barcodes_for_pv(pv_item_po.id))

        # 2b. direct CO -> PV path (no PO in between). Runs independently of the
        # PO branch — it's possible for data-entry / historical anomalies to link
        # a CO item to both; both should surface on the timeline.
        pv_item_direct = (
            PurchaseVoucherItems.objects
            .select_related('billno', 'billno__ldgr')
            .filter(customer_order_item=coi)
            .order_by('id')
            .first()
        )
        if pv_item_direct and pv_item_direct.billno:
            pv_bill = pv_item_direct.billno
            events.append({
                'kind': 'received_pv',
                'date': pv_bill.date1.isoformat() if pv_bill.date1 else None,
                'label': 'Received directly on Purchase Voucher',
                'ref': pv_bill.billno,
                'vendor': pv_bill.ldgr.ac_name if getattr(pv_bill, 'ldgr', None) else None,
            })
            barcodes.extend(_barcodes_for_pv(pv_item_direct.id))

        # 3. released_mo + 4. received_karigar + barcode via KR
        if ki_item and ki_item.issue_slip:
            ki_slip = ki_item.issue_slip
            karigar_name = ki_slip.karigar_ldgr.ac_name if getattr(ki_slip, 'karigar_ldgr', None) else None
            events.append({
                'kind': 'released_mo',
                'date': ki_slip.date1.isoformat() if ki_slip.date1 else None,
                'label': 'Released to Karigar Job Work',
                # KarigarIssue uses issue_slip_no (CharField) as its human-readable ID.
                'ref': ki_slip.issue_slip_no,
                'karigar': karigar_name,
            })
            # One karigar issue can be split across multiple receive rows
            # (partial receives). Emit a `received_karigar` event per receive
            # and collect barcodes via the canonical BarcodeMain.rec_item FK.
            kr_items = list(
                KarigarReceiveItem.objects
                .select_related('receive_slip_no')
                .filter(ref_job_sl_no=ki_item)
                .order_by('date1', 'id')
            )
            for kr_item in kr_items:
                events.append({
                    'kind': 'received_karigar',
                    'date': kr_item.date1.isoformat() if kr_item.date1 else None,
                    'label': 'Received from Karigar',
                    'ref': kr_item.receive_slip_no.receive_slip_no if kr_item.receive_slip_no else None,
                })
                barcodes.extend(_barcodes_for_rec(kr_item.id))

        # 5. barcoded + 6. delivered — one pair of events per barcode (1:N).
        # De-dupe in case the same barcode got collected via multiple paths.
        seen_bc = set()
        unique_barcodes = []
        for bc in barcodes:
            if bc and bc.id not in seen_bc:
                seen_bc.add(bc.id)
                unique_barcodes.append(bc)
        for bc in unique_barcodes:
            events.append({
                'kind': 'barcoded',
                'date': bc.created_date.isoformat() if bc.created_date else None,
                'label': 'Barcode created - ready for delivery',
                'ref': bc.barcode,
            })
            sv_item = (
                SalesVouItem.objects
                .select_related('billno')
                .filter(barcode=bc)
                .order_by('id')
                .first()
            )
            if sv_item and sv_item.billno:
                sv = sv_item.billno
                events.append({
                    'kind': 'delivered',
                    'date': sv.date1.isoformat() if sv.date1 else None,
                    'label': 'Delivered on Sales Voucher',
                    'ref': sv.billno,
                    'barcode': bc.barcode,
                })

        state, _reason = _customer_order_item_lock(coi)
        items_payload.append({
            'co_item_id': coi.id,
            'sl_no': coi.sl_no,
            'item': coi.item_id.short_code if coi.item_id else None,
            'item_name': coi.item_id.item_name if coi.item_id else None,
            'purity': coi.purity.purity if coi.purity else None,
            'pcs': coi.pcs,
            'approx_wt': float(coi.gw) if coi.gw is not None else None,
            'size': coi.size,
            'remarks': coi.remarks,
            'state': state,
            'events': events,
        })

    return Response({
        'order': {
            'id': order.id,
            'order_no': order.order_no,
            'date1': order.date1.isoformat() if order.date1 else None,
            'delivery_date': order.delivery_date.isoformat() if order.delivery_date else None,
            'customer_name': order.ldgr.ac_name if order.ldgr else None,
            'nature': order.nature,
            'status': order.status,
            'delivery_status': order.delivery_status,
        },
        'items': items_payload,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_order_delivery_overview(request):
    """
    Returns delivery KPI stats for the current retail:
      - overdue_count        orders past delivery_date, not delivered/cancelled/billed
      - due_today_count      orders due exactly today
      - due_this_week_count  orders due in next 7 days (excl. today)
      - pending_count        all open (not delivered/cancelled) orders
      - delivered_count      delivered this month
      - overdue_orders       first 10 overdue orders (for the alert banner)
    """
    from datetime import date, timedelta
    retail = request.retail
    if not retail:
        return Response({'error': 'Retail context missing'}, status=400)

    today     = date.today()
    week_end  = today + timedelta(days=7)
    month_start = today.replace(day=1)

    open_qs = CustomerOrder.objects.filter(
        retail=retail
    ).exclude(
        delivery_status__in=['delivered', 'cancelled']
    ).exclude(status='Billed')

    overdue_qs   = open_qs.filter(delivery_date__lt=today, delivery_date__isnull=False)
    today_qs     = open_qs.filter(delivery_date=today)
    this_week_qs = open_qs.filter(delivery_date__gt=today, delivery_date__lte=week_end)

    delivered_qs = CustomerOrder.objects.filter(
        retail=retail, delivery_status='delivered',
        actual_delivery_date__gte=month_start
    )

    # Lightweight overdue list for the alert banner (max 10 rows)
    overdue_orders = overdue_qs.select_related('ldgr').order_by('delivery_date')[:10]
    overdue_list = [
        {
            'id':            o.id,
            'order_no':      o.order_no,
            'customer':      o.ldgr.ac_name if o.ldgr else '—',
            'delivery_date': str(o.delivery_date),
            'days_overdue':  (today - o.delivery_date).days,
            'delivery_status': o.delivery_status,
            'nature':        o.nature,
        }
        for o in overdue_orders
    ]

    return Response({
        'overdue_count':        overdue_qs.count(),
        'due_today_count':      today_qs.count(),
        'due_this_week_count':  this_week_qs.count(),
        'pending_count':        open_qs.count(),
        'delivered_this_month': delivered_qs.count(),
        'overdue_orders':       overdue_list,
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def customer_order_update_delivery(request, pk):
    """
    Quick update of delivery_status and optionally actual_delivery_date.
    Body: { delivery_status, actual_delivery_date (optional) }
    """
    try:
        order = CustomerOrder.objects.get(pk=pk, retail=request.retail)
    except CustomerOrder.DoesNotExist:
        return Response({'error': 'Order not found'}, status=404)

    new_status = request.data.get('delivery_status')
    if new_status not in dict(CustomerOrder.DELIVERY_STATUS_CHOICES):
        return Response({'error': f'Invalid delivery_status: {new_status}'}, status=400)

    order.delivery_status = new_status

    if new_status == 'delivered':
        from datetime import date as date_cls
        order.actual_delivery_date = request.data.get('actual_delivery_date') or str(date_cls.today())

    order.save(update_fields=['delivery_status', 'actual_delivery_date'])
    return Response(CustomerOrderSerializer(order).data)


# ============= Sales Voucher Views (formerly in sale_voucher app) =============

from datetime import datetime
from rest_framework.viewsets import ModelViewSet
from accounting.serializers import LedgerSerializer, SaleVoucherLedgerSerializer
from sales.utils import generate_next_sale_voucher_no, generate_next_sale_return_no, generate_next_sale_app_no
from sales.serializers import SaleReturnSerializer, SaleVoucherToReturnSerializer, SalesApprovalSerializer, SalesVouSerializer
from django.db.models import F, Value, ExpressionWrapper, DecimalField, Case, When, Exists, OuterRef
from django.db.models import Sum
from django.db.models.functions import Coalesce
from rest_framework.views import APIView
from django.db.models import Q
import decimal


class SalesVoucherViewset(views.RetailBaseViewset):
    queryset = SalesVou.objects.select_related(
        'ldgr', 'sales_person', 'sales_person2', 'ac_voucher', 'retail'
    ).prefetch_related(
        'salesvouitem_set__barcode',
        'salesvouitem_set__main_item_set__item',
        'salesvouitemdetails_set__item',
        'bank_details'
    ).all()
    serializer_class = SalesVouSerializer
    filter_backends = [DjangoFilterBackend,OrderingFilter,SearchFilter]

    search_fields = ['billno','ldgr__ac_name']

    def get_queryset(self):
        from .models import EWayBill
        return super().get_queryset().annotate(
            has_eway_bill=Exists(
                EWayBill.objects.filter(sales_vou=OuterRef('pk'), status='GENERATED')
            )
        )

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    ordering = ['billno']

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
        sales_qs = SalesVou.objects.filter(
            date1__range=[start_date, end_date]
        ).select_related('ldgr', 'ac_voucher')
        if gstin_id:
            sales_qs = sales_qs.filter(gstin_ref_id=gstin_id)

        sales_annotated = sales_qs.annotate(
            vtype=F('ac_voucher__voucher_type'),
            partyname=F("ldgr__ac_name"),
            gstin=F("ldgr__gst"),
            pan=F("ldgr__pan"),
            billvalue=F("mrp"),
            beforetax=F("mrp") - F('discount'),
            taxableamount=F("mrp") - F('discount'),
            placeofsupply=F("place_of_supply"),
            add_less=ExpressionWrapper(
                Coalesce(F("freight_charge"), 0) + Coalesce(F("other_charge"), 0),
                output_field=DecimalField()
            )
        ).values(
            "date1", "vtype", "gst_billno", "partyname", "gstin", "pan",
            "billvalue", "beforetax", "taxableamount", "sgst_per",
            "cgst_per", "igst_per", "placeofsupply", "add_less"
        )

        return_qs = SaleReturn.objects.filter(
            date1__range=[start_date, end_date]
        ).select_related('ldgr', 'ac_voucher')
        if gstin_id:
            return_qs = return_qs.filter(retail__gstin_master_id=gstin_id)

        return_annotated = return_qs.annotate(
            vtype=F('ac_voucher__voucher_type'),
            partyname=F("ldgr__ac_name"),
            gstin=F("ldgr__gst"),
            pan=F("ldgr__pan"),
            billvalue=F("mrp"),
            beforetax=F("mrp") - F('discount'),
            taxableamount=F("mrp") - F('discount'),
        ).values(
            "date1", "vtype", "billno", "partyname", "gstin", "pan",
            "billvalue", "beforetax", "taxableamount", "sgst_per",
            "cgst_per", "igst_per",
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


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


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
                stone_details = SalesVouItemDetails.objects.filter( Q(billno=sales_vou,
                    main_item=sale_main,gw__gt=0) &
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


@api_view()
@permission_classes([IsAuthenticated])
def get_sale_voucher_for_return(request):
    bill_no = request.query_params.get('bill_no')
    if not bill_no:
        return Response({"error": "Bill number is required"}, status=400)
    obj = SalesVou.objects.get(billno=bill_no)
    serializer = SaleVoucherToReturnSerializer(obj)
    return Response(serializer.data)


class SalesApprovalViewset(views.RetailBaseViewset):
    queryset = SalesApproval.objects.all()
    serializer_class = SalesApprovalSerializer
    filter_backends=[DjangoFilterBackend,OrderingFilter,SearchFilter]

    search_fields=['billno','ldgr__ac_name']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields
    ordering=['billno']

    def perform_destroy(self, instance):
        from accounting.utils import release_last_bill_number
        retail = instance.retail
        fiscal_year = instance.fiscal_year
        billno = instance.billno
        super().perform_destroy(instance)
        release_last_bill_number(retail, 'SA', billno, fiscal_year)

class SalesReturnViewset(views.RetailBaseViewset):
    queryset = SaleReturn.objects.select_related('ldgr', 'ac_voucher', 'retail').prefetch_related(
        'salereturnitem_set__salereturndetails_set'
    ).all()
    serializer_class = SaleReturnSerializer
    filter_backends=[DjangoFilterBackend,OrderingFilter,SearchFilter]

    search_fields=['billno','ldgr__ac_name']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    ordering = ['billno']

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
        retail = instance.retail
        fiscal_year = instance.fiscal_year
        billno = instance.billno
        super().perform_destroy(instance)
        release_last_bill_number(retail, 'SR', billno, fiscal_year)

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
def get_next_sv_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response(
            {"error": "Missing or invalid X-RETAIL-ID header"},
            status=status.HTTP_400_BAD_REQUEST
        )
    bill_no = peek_next_bill_number(request.retail, "SV")
    return Response({"billno":bill_no})

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
    return Response({"billno":bill_no})

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
    return Response({"billno":bill_no})

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
                  .only('id', 'ac_name', 'ac_group')
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
                  .only('id', 'ac_name', 'ac_group')
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


def build_invoice_context(voucher, retail):
    """Build the complete data dict for the invoice print view."""
    from mastersconfig.models import State as StateModel

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
def sale_return_print_data(request, pk):
    """Return fully-computed credit-note JSON for a SaleReturn (for React print)."""
    try:
        sr = SaleReturn.objects.select_related(
            'ldgr', 'retail', 'retail__state', 'sales_voucher_ref',
        ).prefetch_related(
            'salereturnitem_set__item',
            'salereturnitem_set__salereturndetails_set__item',
            'salereturnitem_set__salereturndetails_set__metal_purity',
        ).get(pk=pk, retail=request.retail)
    except SaleReturn.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    retail = request.retail
    ldgr   = sr.ldgr

    # ── Company info ─────────────────────────────────────────────────────────
    company = None
    if retail.branch_id and retail.branch and retail.branch.company_id:
        company = retail.branch.company
    company_address = ', '.join(filter(None, [
        retail.address_line1, retail.address_line2, retail.address_line3,
        retail.city, retail.pincode,
    ]))
    _gm = retail.gstin_master
    company_gstin = (_gm.gstin if _gm else '') or ''

    # ── Customer info ─────────────────────────────────────────────────────────
    customer_address = ', '.join(filter(None, [ldgr.add1, ldgr.add2, ldgr.city, ldgr.pincode]))

    # ── Build items list ─────────────────────────────────────────────────────
    items_data = []
    for ri in sr.salereturnitem_set.all():
        sub_rows = []
        for d in ri.salereturndetails_set.all():
            parts = []
            if d.item:
                parts.append(d.item.item_name or d.item.short_code)
            if d.metal_purity:
                parts.append(str(d.metal_purity))
            if d.gw:
                parts.append(f'GW: {float(d.gw):.3f}g')
            if d.tunch:
                parts.append(f'Tunch: {float(d.tunch):.2f}%')
            if d.rate:
                parts.append(f'@ ₹{float(d.rate):.0f}')
            sub_rows.append({
                'text':         ' | '.join(parts),
                'pcs':          d.pcs,
                'gw':           float(d.gw or 0),
                'rate':         float(d.rate or 0),
                'amount':       float(d.amount or 0),
                'item_type':    d.item.item_type if d.item else '',
                'metal_purity': str(d.metal_purity) if d.metal_purity else '',
            })

        items_data.append({
            'sn':        len(items_data) + 1,
            'barcode':   ri.barcode or '',
            'item_name': ri.item.item_name if ri.item else (ri.item.short_code if ri.item else ''),
            'pcs':       ri.pcs or 0,
            'gw':        float(ri.gw or 0),
            'making':    float(ri.making_value or 0),
            'amount':    float(ri.amount or 0),
            'sub_rows':  sub_rows,
        })

    # ── Tax & totals ──────────────────────────────────────────────────────────
    taxable  = float(sr.taxable_value)
    cgst_amt = round(taxable * float(sr.cgst_per or 0) / 100, 2)
    sgst_amt = round(taxable * float(sr.sgst_per or 0) / 100, 2)
    igst_amt = round(taxable * float(sr.igst_per or 0) / 100, 2)
    total    = round(taxable + cgst_amt + sgst_amt + igst_amt, 2)

    # ── Original invoice reference ────────────────────────────────────────────
    ref_billno  = sr.sales_voucher_ref.billno if sr.sales_voucher_ref else ''
    ref_gst_no  = sr.original_sale_gst_billno or (
        sr.sales_voucher_ref.gst_billno if sr.sales_voucher_ref else ''
    )
    ref_date    = str(sr.sales_voucher_ref.date1) if sr.sales_voucher_ref and sr.sales_voucher_ref.date1 else ''

    return Response({
        'note_type':        'CN',
        'company_name':     (company.company_name if company else retail.retail_name) or '',
        'company_address':  company_address,
        'company_gstin':    company_gstin,
        'company_state':    getattr(retail.state, 'name', '') if retail.state else '',
        'note_no':          sr.billno or '',
        'date':             str(sr.date1) if sr.date1 else '',
        'party_name':       ldgr.ac_name or '',
        'party_address':    customer_address,
        'party_gstin':      ldgr.gst or '',
        'party_state':      ldgr.state or '',
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
        data = build_invoice_context(voucher, request.retail)
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
    from .models import EWayBill
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
        from .models import EWayBill
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
        from .models import EWayBill
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

        from .serializers import EWayBillSerializer
        serializer = EWayBillSerializer(qs, many=True)
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def eway_bill_cancel(request, pk):
    """POST /sales/api/eway-bills/<pk>/cancel/ — cancel an E-Way bill."""
    from .models import EWayBill
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
    from .models import EWayBill
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
    from .serializers import EWayBillSerializer
    return Response(EWayBillSerializer(ewb).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def eway_bill_delete(request, pk):
    """DELETE /sales/api/eway-bills/<pk>/ — hard delete (only if no EBN assigned)."""
    from .models import EWayBill
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
        return Response({'detail': 'System ledger "Cheques in Hand" not found. Please re-run seed-accounts from Setup.'}, status=status.HTTP_400_BAD_REQUEST)

    from accounting.serializers import JournalEntrySerializer
    from accounting.utils import get_next_bill_number
    from global_vars import VoucherType

    with transaction.atomic():
        voucher_no = get_next_bill_number(retail, VoucherType.cntr, fiscal_year)
        narration  = f"Cheque deposit — {bd.chq_no} — {bd.bank_name}"

        ser = JournalEntrySerializer(data={
            'date':         deposit_date,
            'voucher_no':   voucher_no,
            'retail':       retail.id,
            'narration':    narration[:150],
            'voucher_type': VoucherType.cntr,
            'voucher_details': [
                {'account': bank_ledger.ac_name,        'debit': str(bd.amount), 'credit': 0},
                {'account': cheques_in_hand.ac_name,    'debit': 0, 'credit': str(bd.amount),
                 'chq_no': bd.chq_no, 'chq_date': str(bd.chq_date) if bd.chq_date else None},
            ],
        }, context={'request': request})

        ser.is_valid(raise_exception=True)
        voucher = ser.save()

        bd.cheque_status   = 'DEPOSITED'
        bd.deposit_date    = deposit_date
        bd.deposit_voucher = voucher
        bd.save(update_fields=['cheque_status', 'deposit_date', 'deposit_voucher'])

    from sales.serializers import BankDetails
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


# ── Quotation ────────────────────────────────────────────────────────────────

from sales.serializers import QuotationSerializer, QuotationListSerializer


class QuotationViewset(views.RetailBaseViewset):
    queryset = Quotation.objects.select_related(
        'ldgr', 'sales_person', 'retail'
    ).prefetch_related('items__details').all()
    serializer_class = QuotationSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['quotation_no', 'ldgr__ac_name', 'party_name']
    filterset_fields = ['status']
    ordering = ['-id']

    def get_serializer_class(self):
        if self.action == 'list':
            return QuotationListSerializer
        return QuotationSerializer

    def perform_create(self, serializer):
        from accounting.utils import peek_next_bill_number
        retail = getattr(self.request, 'retail', None)
        fiscal_year = getattr(retail, 'active_fy', None) if retail else None
        qt_no = peek_next_bill_number(retail, "QT")
        serializer.save(
            retail=retail,
            fiscal_year=fiscal_year,
            created_by=self.request.user,
            quotation_no=qt_no,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_qt_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response({"error": "Missing or invalid X-RETAIL-ID header"}, status=status.HTTP_400_BAD_REQUEST)
    bill_no = peek_next_bill_number(request.retail, "QT")
    return Response({"billno": bill_no})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def quotation_initial_data(request):
    """Combined initial data for the Quotation form."""
    from mastersconfig.models import SalesPersonMaster
    from mastersconfig.serializers import SalesPersonMasterSerializer
    from accounting.utils import peek_next_bill_number
    from accounting.serializers import LedgerLightSerializer
    from goldrates.models import PurityMaster

    if not request.retail:
        return Response({"error": "Missing or invalid X-RETAIL-ID header"}, status=status.HTTP_400_BAD_REQUEST)

    bill_no = peek_next_bill_number(request.retail, "QT")
    ledgers_qs = (Ledger.objects
                  .filter(roles__role='CO')
                  .select_related('ac_group')
                  .prefetch_related('roles')
                  .only('id', 'ac_name', 'ac_group')
                  .distinct())
    salespersons_qs = SalesPersonMaster.objects.filter(retail=request.retail)
    purities = list(PurityMaster.objects.values('purity', 'gw_per'))

    return Response({
        "billno": bill_no,
        "ledgers": LedgerLightSerializer(ledgers_qs, many=True).data,
        "salespersons": SalesPersonMasterSerializer(salespersons_qs, many=True).data,
        "purities": purities,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def quotation_print_data(request, pk):
    """Full quotation data for the print template."""
    qt = get_object_or_404(
        Quotation.objects.select_related('ldgr', 'sales_person')
        .prefetch_related('items__details'),
        pk=pk
    )
    data = QuotationSerializer(qt).data
    # Add party contact info if ledger exists
    if qt.ldgr:
        data['party_mobile'] = qt.ldgr.mobile1 or ''
        data['party_address'] = ', '.join(filter(None, [
            qt.ldgr.address1 or '', qt.ldgr.city or '', qt.ldgr.state or '',
        ]))
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quotation_duplicate(request, pk):
    """Duplicate a quotation with new number and draft status."""
    from accounting.utils import peek_next_bill_number
    from datetime import date, timedelta

    original = get_object_or_404(Quotation, pk=pk)
    retail = getattr(request, 'retail', None)
    new_no = peek_next_bill_number(retail, "QT")

    with transaction.atomic():
        new_qt = Quotation.objects.create(
            date1=date.today(),
            quotation_no=new_no,
            ldgr=original.ldgr,
            party_name=original.party_name,
            gold_rate_date=original.gold_rate_date,
            rate_18kt=original.rate_18kt,
            rate_22kt=original.rate_22kt,
            rate_24kt=original.rate_24kt,
            total_items=original.total_items,
            grand_total=original.grand_total,
            tax_percent=original.tax_percent,
            tax_amount=original.tax_amount,
            net_total=original.net_total,
            status='draft',
            valid_until=date.today() + timedelta(days=7),
            remarks=original.remarks,
            seller_info=original.seller_info,
            sales_person=original.sales_person,
            retail=retail,
            fiscal_year=getattr(retail, 'active_fy', None) if retail else None,
            created_by=request.user,
        )
        for item in original.items.all():
            new_item = QuotationItem.objects.create(
                quotation=new_qt,
                sl_no=item.sl_no,
                barcode=item.barcode,
                barcode_text=item.barcode_text,
                item=item.item,
                item_name=item.item_name,
                design_code=item.design_code,
                purity_text=item.purity_text,
                pcs=item.pcs,
                gw=item.gw,
                nw=item.nw,
                gold_rate=item.gold_rate,
                gold_amount=item.gold_amount,
                making_rate=item.making_rate,
                making_amount=item.making_amount,
                total_diamond_pcs=item.total_diamond_pcs,
                total_diamond_wt=item.total_diamond_wt,
                total_diamond_amt=item.total_diamond_amt,
                total_stone_pcs=item.total_stone_pcs,
                total_stone_wt=item.total_stone_wt,
                total_stone_amt=item.total_stone_amt,
                total_amount=item.total_amount,
                image_url=item.image_url,
            )
            for det in item.details.all():
                QuotationItemDetail.objects.create(
                    quotation_item=new_item,
                    packet=det.packet,
                    packet_name=det.packet_name,
                    item_name=det.item_name,
                    is_diamond=det.is_diamond,
                    pcs=det.pcs,
                    wt=det.wt,
                    rate=det.rate,
                    amount=det.amount,
                )
    return Response({"id": new_qt.id, "quotation_no": new_qt.quotation_no})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quotation_finalize(request, pk):
    """Finalize a quotation (draft → finalized)."""
    qt = get_object_or_404(Quotation, pk=pk)
    if qt.status != 'draft':
        return Response({"error": f"Cannot finalize quotation in '{qt.status}' status."}, status=status.HTTP_400_BAD_REQUEST)
    qt.status = 'finalized'
    qt.save(update_fields=['status'])
    return Response({"status": "finalized"})


@api_view(['GET'])
@permission_classes([])
def portal_customer_orders(request):
    """
    Portal endpoint: Customer sees their orders with status tracking.
    Only includes customer-relevant fields (order_no, delivery_status, item_count, etc.)
    Excludes vendor/karigar names for privacy.
    """
    from goldscheme.portal_auth import PortalTokenAuthentication, IsPortalAuthenticated

    auth = PortalTokenAuthentication()
    try:
        result = auth.authenticate(request)
        if result is None:
            return Response({'error': 'Portal authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)

    customer = getattr(request, 'portal_customer', None)
    if not customer:
        return Response({'error': 'Portal authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    orders = CustomerOrder.objects.filter(ldgr=customer).order_by('-date1')
    serializer = PortalCustomerOrderSerializer(orders, many=True)
    return Response(serializer.data)
