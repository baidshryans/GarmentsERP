import logging
from decimal import Decimal

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from mastersconfig.models import Item
from userauth import views

from ..models import *
from ..serializers import CustomerOrderSerializer

logger = logging.getLogger(__name__)


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
    filter_backends = [OrderingFilter, DjangoFilterBackend]
    ordering = ['-order_no']

    def get_queryset(self):
        from django.db.models import OuterRef, Subquery, Sum, Count, DecimalField, Value
        from django.db.models.functions import Coalesce
        from accounting.models import VoucherMain

        _money = DecimalField(max_digits=15, decimal_places=2)
        adv = (VoucherMain.objects
               .filter(customer_order=OuterRef('pk'), voucher_type__in=['RCPT', 'RCPT-SALE'], status='posted')
               .values('customer_order').annotate(s=Sum('amount')).values('s'))
        rec = (SalesVou.objects
               .filter(customer_order=OuterRef('pk'))
               .values('customer_order').annotate(s=Sum('advance_deducted')).values('s'))
        retail = self.request.retail
        qs = (
            CustomerOrder.objects
            .filter(retail=retail)
            .select_related('ldgr', 'salesman_1', 'salesman_2', 'retail')
            .prefetch_related('items', 'items__item_id', 'items__purity')
            .annotate(
                anno_advance_amt=Coalesce(Subquery(adv, output_field=_money), Value(0), output_field=_money),
                anno_advance_reconciled=Coalesce(Subquery(rec, output_field=_money), Value(0), output_field=_money),
                anno_linked_bill_count=Count('linked_vouchers', distinct=True),
            )
        )
        # Mirror RetailBaseViewset list scoping for this plain endpoint.
        if (
            getattr(retail, 'active_fy_id', None)
            and self.request.query_params.get('all_fy', '').lower() not in ('1', 'true')
        ):
            qs = qs.filter(fiscal_year_id=retail.active_fy_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(retail=self.request.retail)


def _posted_receipts_prefetch():
    """Prefetch posted advance receipts for customer orders, annotated with the
    amount already applied to bills. Mirrors the filter/order used by
    CustomerOrderSerializer.get_linked_receipts so that method can read the
    prefetched cache instead of issuing one aggregate query per receipt
    (an N+1 burst on the order list endpoint)."""
    from django.db.models import Prefetch, Sum, OuterRef, Subquery
    from django.db.models.functions import Coalesce
    from accounting.models import VoucherMain, ReferenceBills

    applied_sq = Subquery(
        ReferenceBills.objects
        .filter(voucher_id=OuterRef('pk'))
        .values('voucher_id')
        .annotate(s=Sum('amount'))
        .values('s')[:1]
    )
    receipts_qs = (
        VoucherMain.objects
        .filter(voucher_type__in=['RCPT', 'RCPT-SALE'], status='posted')
        .annotate(applied_amt=Coalesce(applied_sq, Decimal('0')))
        .order_by('date', 'id')
    )
    return Prefetch('receipts', queryset=receipts_qs, to_attr='posted_receipts')


class CustomerOrderViewset(views.RetailBaseViewset):
    queryset = CustomerOrder.objects.select_related(
        'ldgr', 'retail', 'retail__state', 'retail__gstin_master',
        'salesman_1', 'salesman_2',
    ).prefetch_related('items', 'linked_vouchers', _posted_receipts_prefetch()).all()
    serializer_class = CustomerOrderSerializer
    filter_backends = [OrderingFilter, DjangoFilterBackend, SearchFilter]
    filterset_fields = ['ldgr', 'status']
    search_fields = ['order_no', 'ldgr__ac_name', 'ldgr__mobile1', 'ldgr__mobile2', 'ldgr__mobile3']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['-date1', '-order_no']

    def get_queryset(self):
        """Annotate advance/bill-count and prefetch the lock-state relations so
        the list serializer (advance_* + per-item lock_state) avoids N+1."""
        from django.db.models import OuterRef, Subquery, Sum, Count, DecimalField, Value
        from django.db.models.functions import Coalesce
        from accounting.models import VoucherMain

        _money = DecimalField(max_digits=15, decimal_places=2)
        adv = (VoucherMain.objects
               .filter(customer_order=OuterRef('pk'), voucher_type__in=['RCPT', 'RCPT-SALE'], status='posted')
               .values('customer_order').annotate(s=Sum('amount')).values('s'))
        rec = (SalesVou.objects
               .filter(customer_order=OuterRef('pk'))
               .values('customer_order').annotate(s=Sum('advance_deducted')).values('s'))
        return (
            super().get_queryset()
            .prefetch_related(
                'items__item_id', 'items__purity',
                'items__purchaseorderitems_set__po_slip',
                'items__karigarissueitem_set__issue_slip',
                'items__purchasevoucheritems_set__billno',
            )
            .annotate(
                anno_advance_amt=Coalesce(Subquery(adv, output_field=_money), Value(0), output_field=_money),
                anno_advance_reconciled=Coalesce(Subquery(rec, output_field=_money), Value(0), output_field=_money),
                anno_linked_bill_count=Count('linked_vouchers', distinct=True),
            )
        )

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
        from ..serializers import _customer_order_item_lock
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
        if instance.delivery_status in ('delivered', 'cancelled', 'returned'):
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
        if order.delivery_status in ('delivered', 'cancelled', 'returned'):
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


from ..serializers import CustomerOrderItemsToPurchaseStyleSerializer


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
    from ..models import SalesVouItem, SaleReturnItem
    from ..serializers import _customer_order_item_lock
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
                # Check if this barcode was subsequently returned
                sr_item = (
                    SaleReturnItem.objects
                    .select_related('billno')
                    .filter(barcode=bc)
                    .order_by('id')
                    .first()
                )
                if sr_item and sr_item.billno:
                    sr = sr_item.billno
                    events.append({
                        'kind': 'returned',
                        'date': sr.date1.isoformat() if sr.date1 else None,
                        'label': 'Returned via Sale Return',
                        'ref': sr.billno,
                        'barcode': bc.barcode,
                    })

        state, _reason = _customer_order_item_lock(coi)
        # Override state with return-awareness when the item was billed (delivered).
        # Count sold vs returned barcodes so we can distinguish full vs partial return.
        if state == 'billed' and unique_barcodes:
            sold_ids = set(
                SalesVouItem.objects
                .filter(barcode__in=unique_barcodes, billno__isnull=False)
                .values_list('barcode_id', flat=True)
            )
            returned_ids = set(
                SaleReturnItem.objects
                .filter(barcode__in=unique_barcodes)
                .values_list('barcode_id', flat=True)
            )
            if sold_ids and returned_ids >= sold_ids:
                state = 'Returned'
            elif returned_ids:
                state = 'Partial Return'

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
        delivery_status__in=['delivered', 'cancelled', 'returned']
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
