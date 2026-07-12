import logging
from decimal import Decimal
from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from goldrates.models import PurityMaster
from manufacturing.utils import create_or_update_nested
from mastersconfig.models import Item, SalesPersonMaster, TCSSectionMaster
from mastersconfig.ledger_utils import get_cheques_in_hand_ledger
from sales.models import CustomerOrder, CustomerOrderItems
from purchase.models import PurchaseVoucher
from django.db import   transaction

logger = logging.getLogger(__name__)

from rest_framework.exceptions import ValidationError as _LedgerConfigError
def _raise_missing_ledger(label):
    raise _LedgerConfigError(
        {'ledger_config': f"Required ledger '{label}' is not configured on master. Please configure it in Company/GSTIN/Retail master before saving vouchers."}
    )


class CustomerOrderSerializer(ModelSerializer):
    class Meta:
        model = CustomerOrder
        fields = "__all__"
        depth = 1

class CustomerOrderItemSerializer(ModelSerializer):
    class Meta:
        model = CustomerOrderItems
        fields = "__all__"





def _customer_order_item_lock(obj):
    """Return (lock_state, lock_reason) for a CustomerOrderItems row.

    Memoized on the instance: lock_state and lock_reason are separate serializer
    fields that both need this, and the list endpoint serializes hundreds of
    rows — computing once per row (and reusing the barcode-id set) avoids a large
    N+1 burst.
    """
    cached = getattr(obj, '_lock_cache', None)
    if cached is not None:
        return cached

    # Barcode chain is reused for both the "sold" and "barcoded" checks.
    barcode_ids = _barcode_ids_for_co_item(obj)

    # Truly delivered: a Sales Voucher exists for a barcode tied to this CO item.
    sv_billno = _sv_billno_from_barcodes(barcode_ids)
    if sv_billno:
        result = ('billed', f"Sold via Sales Voucher {sv_billno}")
    elif obj.sale_status:
        result = ('billed', 'Billed in a sales voucher')
    else:
        # Direct CO -> PV path: billed straight onto a Purchase Voucher.
        # Use the prefetched .all() cache (not .first()) so prefetched list
        # querysets avoid a fresh query per item.
        pv = next(iter(obj.purchasevoucheritems_set.all()), None)
        if pv:
            ref = pv.billno.billno if pv.billno else ''
            result = ('billed', f"Billed directly on Purchase Voucher {ref}".rstrip())
        elif barcode_ids:
            result = ('barcoded', 'Barcode created — ready for delivery')
        else:
            ki = next(iter(obj.karigarissueitem_set.all()), None)
            po = None if ki else next(iter(obj.purchaseorderitems_set.all()), None)
            if ki:
                result = ('in_production', f"Issued to Karigar job {ki.issue_slip.issue_slip_no}")
            elif po:
                result = ('in_production', f"Issued to Purchase Order {po.po_slip.po_no}")
            else:
                result = ('unlocked', '')

    obj._lock_cache = result
    return result


def _barcode_ids_for_co_item(coi):
    """Return a set of BarcodeMain IDs tied to this CustomerOrderItems row.

    Walks three barcode-sourcing chains:
      A) CO â†’ PO line â†’ PV line (po_no/po_sl_no match) â†’ BarcodeMain.pur_voucher
      B) CO â†’ KarigarIssueItem â†’ KarigarReceiveItem (ref_job_sl_no) â†’ BarcodeMain.rec_item
      C) Direct CO â†’ PV line (customer_order_item FK) â†’ BarcodeMain.pur_voucher
    """
    from inventory.models import BarcodeMain
    from purchase.models import PurchaseVoucherItems
    from manufacturing.models import KarigarReceiveItem

    barcode_ids = set()

    # Use the prefetched related managers (.all()) rather than fresh values_list
    # queries, so a CO item with no downstream rows (e.g. freshly-migrated orders)
    # costs zero extra queries — this is what keeps the list endpoint fast.
    po_items = list(coi.purchaseorderitems_set.all())
    ki_items = list(coi.karigarissueitem_set.all())
    pv_items_direct = list(coi.purchasevoucheritems_set.all())

    # Chain A: PO -> PV
    for po_item in po_items:
        if not po_item.po_slip:
            continue
        pv_items = PurchaseVoucherItems.objects.filter(
            po_no=po_item.po_slip.po_no,
            po_sl_no=po_item.po_sl_no,
        ).values_list('id', flat=True)
        for bc_id in BarcodeMain.objects.filter(pur_voucher_id__in=list(pv_items)).values_list('id', flat=True):
            barcode_ids.add(bc_id)

    # Chain B: KI -> KR
    ki_ids = [k.id for k in ki_items]
    if ki_ids:
        kr_ids = list(KarigarReceiveItem.objects.filter(ref_job_sl_no_id__in=ki_ids).values_list('id', flat=True))
        if kr_ids:
            for bc_id in BarcodeMain.objects.filter(rec_item_id__in=kr_ids).values_list('id', flat=True):
                barcode_ids.add(bc_id)

    # Chain C: direct CO -> PV
    pv_ids = [p.id for p in pv_items_direct]
    if pv_ids:
        for bc_id in BarcodeMain.objects.filter(pur_voucher_id__in=pv_ids).values_list('id', flat=True):
            barcode_ids.add(bc_id)

    return barcode_ids


def _sv_billno_for_co_item(coi):
    """Return the SalesVou billno of the first Sales Voucher whose barcode
    traces back to this CustomerOrderItems row, or None if not yet sold."""
    return _sv_billno_from_barcodes(_barcode_ids_for_co_item(coi))


def _sv_billno_from_barcodes(barcode_ids):
    """SalesVou billno for the first sale against any of these barcodes."""
    from sales.models import SalesVouItem

    if not barcode_ids:
        return None

    sv_item = (
        SalesVouItem.objects
        .filter(barcode_id__in=barcode_ids, billno__isnull=False)
        .select_related('billno')
        .order_by('billno__date1', 'id')
        .first()
    )
    return sv_item.billno.billno if sv_item and sv_item.billno else None


def _prime_co_item_locks(items):
    """Batch-compute (lock_state, lock_reason) for many CustomerOrderItems rows
    in a fixed number of queries, then stash each result on the row's
    `_lock_cache`. This collapses the per-row barcode-chain N+1 in
    `_customer_order_item_lock` (chains A/B/C + the sales-voucher lookup) into a
    handful of page-level queries.

    Idempotent: rows that already carry a `_lock_cache` are skipped, and a page
    of relation-free rows (e.g. freshly-migrated orders) costs zero extra
    queries. The per-row `_customer_order_item_lock` reads the seeded cache, so
    output is identical to computing each row individually.
    """
    from inventory.models import BarcodeMain
    from purchase.models import PurchaseVoucherItems
    from manufacturing.models import KarigarReceiveItem
    from sales.models import SalesVouItem

    items = [it for it in items if getattr(it, '_lock_cache', None) is None]
    if not items:
        return

    item_barcodes = {it.id: set() for it in items}
    # PurchaseVoucherItems id -> co_item ids that should receive its barcodes
    # (populated from Chain A's PO->PV pair match and Chain C's direct PV FK).
    pvitem_to_items = {}

    # ---- Chain A: CO -> PO line -> PV line (po_no/po_sl_no match) ----
    pair_to_items = {}                      # (po_no, po_sl_no) -> set(co_item_id)
    po_nos, po_sl_nos = set(), set()
    for it in items:
        for po_item in it.purchaseorderitems_set.all():
            if not po_item.po_slip:
                continue
            key = (po_item.po_slip.po_no, po_item.po_sl_no)
            pair_to_items.setdefault(key, set()).add(it.id)
            po_nos.add(po_item.po_slip.po_no)
            po_sl_nos.add(po_item.po_sl_no)
    if pair_to_items:
        # Over-fetch by the cross product of (po_no, po_sl_no), then attribute
        # only exact-pair matches — equivalent to the per-row exact filter.
        for pv in PurchaseVoucherItems.objects.filter(
            po_no__in=po_nos, po_sl_no__in=po_sl_nos,
        ).values('id', 'po_no', 'po_sl_no'):
            owners = pair_to_items.get((pv['po_no'], pv['po_sl_no']))
            if owners:
                pvitem_to_items.setdefault(pv['id'], set()).update(owners)

    # ---- Chain C: direct CO -> PV line (customer_order_item FK) ----
    for it in items:
        for pv_item in it.purchasevoucheritems_set.all():
            pvitem_to_items.setdefault(pv_item.id, set()).add(it.id)

    # Resolve barcodes for all collected PV-item ids in one query (chains A + C).
    if pvitem_to_items:
        for bc in BarcodeMain.objects.filter(
            pur_voucher_id__in=list(pvitem_to_items.keys()),
        ).values('id', 'pur_voucher_id'):
            for cid in pvitem_to_items.get(bc['pur_voucher_id'], ()):
                item_barcodes[cid].add(bc['id'])

    # ---- Chain B: CO -> KarigarIssueItem -> KarigarReceiveItem -> BarcodeMain ----
    ki_to_item = {}                         # KarigarIssueItem id -> co_item id
    for it in items:
        for ki in it.karigarissueitem_set.all():
            ki_to_item[ki.id] = it.id
    if ki_to_item:
        kr_to_item = {}                     # KarigarReceiveItem id -> co_item id
        for kr in KarigarReceiveItem.objects.filter(
            ref_job_sl_no_id__in=list(ki_to_item.keys()),
        ).values('id', 'ref_job_sl_no_id'):
            owner = ki_to_item.get(kr['ref_job_sl_no_id'])
            if owner is not None:
                kr_to_item[kr['id']] = owner
        if kr_to_item:
            for bc in BarcodeMain.objects.filter(
                rec_item_id__in=list(kr_to_item.keys()),
            ).values('id', 'rec_item_id'):
                owner = kr_to_item.get(bc['rec_item_id'])
                if owner is not None:
                    item_barcodes[owner].add(bc['id'])

    # ---- Earliest Sales Voucher billno per co_item across its barcodes ----
    all_barcode_ids = set()
    for bcs in item_barcodes.values():
        all_barcode_ids.update(bcs)
    sv_billno_for_item = {}
    if all_barcode_ids:
        barcode_owners = {}                 # barcode id -> set(co_item_id)
        for cid, bcs in item_barcodes.items():
            for bc in bcs:
                barcode_owners.setdefault(bc, set()).add(cid)
        # Walk sales items in the SAME order as _sv_billno_from_barcodes
        # (billno__date1, id); the first hit per co_item wins, exactly matching
        # the per-row `.first()`.
        for sv in (SalesVouItem.objects
                   .filter(barcode_id__in=list(all_barcode_ids), billno__isnull=False)
                   .select_related('billno')
                   .order_by('billno__date1', 'id')):
            billno = sv.billno.billno if sv.billno else None
            if not billno:
                continue
            for cid in barcode_owners.get(sv.barcode_id, ()):
                sv_billno_for_item.setdefault(cid, billno)

    # ---- Assemble the same (state, reason) tuple the per-row function returns.
    # The pv/ki/po reads below hit the prefetched .all() cache (no new queries).
    for it in items:
        barcode_ids = item_barcodes[it.id]
        sv_billno = sv_billno_for_item.get(it.id)
        if sv_billno:
            result = ('billed', f"Sold via Sales Voucher {sv_billno}")
        elif it.sale_status:
            result = ('billed', 'Billed in a sales voucher')
        else:
            pv = next(iter(it.purchasevoucheritems_set.all()), None)
            if pv:
                ref = pv.billno.billno if pv.billno else ''
                result = ('billed', f"Billed directly on Purchase Voucher {ref}".rstrip())
            elif barcode_ids:
                result = ('barcoded', 'Barcode created — ready for delivery')
            else:
                ki = next(iter(it.karigarissueitem_set.all()), None)
                po = None if ki else next(iter(it.purchaseorderitems_set.all()), None)
                if ki:
                    result = ('in_production', f"Issued to Karigar job {ki.issue_slip.issue_slip_no}")
                elif po:
                    result = ('in_production', f"Issued to Purchase Order {po.po_slip.po_no}")
                else:
                    result = ('unlocked', '')
        it._lock_cache = result


class CustomerOrderLockListSerializer(serializers.ListSerializer):
    """ListSerializer that batch-primes per-item lock state for the whole page
    before per-row serialization, eliminating the lock-state N+1 on the customer
    order list endpoint."""
    def to_representation(self, data):
        iterable = list(data)
        all_items = []
        for order in iterable:
            all_items.extend(order.items.all())   # prefetched
        _prime_co_item_locks(all_items)
        return super().to_representation(iterable)


class CustomerOrderItemsSerializer(serializers.ModelSerializer):
    item_id = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    item_name = serializers.CharField(source='item_id.item_name', read_only=True)
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", allow_null=True)
    order_no = serializers.PrimaryKeyRelatedField(queryset=CustomerOrder.objects.all(),required=False)
    lock_state = serializers.SerializerMethodField(read_only=True)
    lock_reason = serializers.SerializerMethodField(read_only=True)

    def get_lock_state(self, obj):
        return _customer_order_item_lock(obj)[0]

    def get_lock_reason(self, obj):
        return _customer_order_item_lock(obj)[1]

    class Meta:
        model = CustomerOrderItems
        fields = '__all__'

        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

class CustomerOrderItemsSerializer1(serializers.ModelSerializer):
    item_id = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    item_name = serializers.CharField(source='item_id.item_name', read_only=True)
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", allow_null=True)
    order_no = serializers.SlugRelatedField(queryset=CustomerOrder.objects.all(),slug_field="order_no",required=False)
    lock_state = serializers.SerializerMethodField(read_only=True)
    lock_reason = serializers.SerializerMethodField(read_only=True)

    def get_lock_state(self, obj):
        return _customer_order_item_lock(obj)[0]

    def get_lock_reason(self, obj):
        return _customer_order_item_lock(obj)[1]

    class Meta:
        model = CustomerOrderItems
        fields = '__all__'

        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

class CustomerOrderSerializer(serializers.ModelSerializer):
    items = CustomerOrderItemsSerializer(many=True)
    # advance_amt / advance_reconciled / advance_available are @property on the model
    # (single source of truth = linked RCPT vouchers via VoucherMain.customer_order FK).
    advance_amt        = serializers.SerializerMethodField(read_only=True)
    advance_reconciled = serializers.SerializerMethodField(read_only=True)
    advance_available  = serializers.SerializerMethodField(read_only=True)
    linked_bill_count  = serializers.SerializerMethodField(read_only=True)
    is_overdue         = serializers.SerializerMethodField(read_only=True)
    days_overdue       = serializers.SerializerMethodField(read_only=True)
    salesman_1_name    = serializers.SerializerMethodField(read_only=True)
    salesman_2_name    = serializers.SerializerMethodField(read_only=True)
    ldgr_mobile        = serializers.SerializerMethodField(read_only=True)
    retail_name        = serializers.SerializerMethodField(read_only=True)
    retail_phone       = serializers.SerializerMethodField(read_only=True)
    retail_city        = serializers.SerializerMethodField(read_only=True)

    # advance_* and linked_bill_count read queryset annotations when the view
    # provides them (list endpoint), falling back to the model properties (detail
    # endpoint / un-annotated). The annotations avoid N+1 aggregate queries.
    def get_advance_amt(self, obj):
        v = getattr(obj, 'anno_advance_amt', None)
        return float(v) if v is not None else float(obj.advance_amt)

    def get_advance_reconciled(self, obj):
        v = getattr(obj, 'anno_advance_reconciled', None)
        return float(v) if v is not None else float(obj.advance_reconciled)

    def get_advance_available(self, obj):
        return self.get_advance_amt(obj) - self.get_advance_reconciled(obj)

    def get_linked_bill_count(self, obj):
        v = getattr(obj, 'anno_linked_bill_count', None)
        return int(v) if v is not None else len(obj.linked_vouchers.all())

    def get_is_overdue(self, obj):
        from datetime import date
        if not obj.delivery_date:
            return False
        if obj.delivery_status in ('delivered', 'cancelled', 'returned'):
            return False
        if obj.status == 'Billed':
            return False
        return obj.delivery_date < date.today()

    def get_days_overdue(self, obj):
        from datetime import date
        if not self.get_is_overdue(obj):
            return 0
        return (date.today() - obj.delivery_date).days

    def get_salesman_1_name(self, obj):
        return obj.salesman_1.salesperson_name if obj.salesman_1 else ""

    def get_salesman_2_name(self, obj):
        return obj.salesman_2.salesperson_name if obj.salesman_2 else ""

    def get_ldgr_mobile(self, obj):
        return obj.ldgr.mobile1 if obj.ldgr and obj.ldgr.mobile1 else ""

    def get_retail_name(self, obj):
        return obj.retail.retail_name if obj.retail else ""

    def get_retail_phone(self, obj):
        return obj.retail.phone if obj.retail else ""

    def get_retail_city(self, obj):
        return obj.retail.city if obj.retail else ""

    retail_address_line1 = serializers.SerializerMethodField(read_only=True)
    retail_address_line2 = serializers.SerializerMethodField(read_only=True)
    retail_address_line3 = serializers.SerializerMethodField(read_only=True)
    retail_pincode       = serializers.SerializerMethodField(read_only=True)
    retail_state         = serializers.SerializerMethodField(read_only=True)
    retail_gstin         = serializers.SerializerMethodField(read_only=True)
    retail_email         = serializers.SerializerMethodField(read_only=True)

    def get_retail_address_line1(self, obj):
        return obj.retail.address_line1 if obj.retail else ""

    def get_retail_address_line2(self, obj):
        return obj.retail.address_line2 if obj.retail else ""

    def get_retail_address_line3(self, obj):
        return obj.retail.address_line3 if obj.retail else ""

    def get_retail_pincode(self, obj):
        return obj.retail.pincode if obj.retail else ""

    def get_retail_state(self, obj):
        return obj.retail.state.name if obj.retail and obj.retail.state else ""

    def get_retail_gstin(self, obj):
        if obj.retail and obj.retail.gstin_master:
            return getattr(obj.retail.gstin_master, 'gstin', '') or ''
        return ""

    def get_retail_email(self, obj):
        return obj.retail.email if obj.retail else ""

    is_deletable            = serializers.SerializerMethodField(read_only=True)
    is_cancellable          = serializers.SerializerMethodField(read_only=True)
    has_in_production_items = serializers.SerializerMethodField(read_only=True)
    has_advance             = serializers.SerializerMethodField(read_only=True)
    linked_receipts         = serializers.SerializerMethodField(read_only=True)

    def get_linked_receipts(self, obj):
        from django.db.models import Sum as _Sum
        from accounting.models import ReferenceBills as _RefBills
        # Fast path: the list viewset prefetches posted receipts annotated with
        # `applied_amt` into `posted_receipts`, collapsing the per-receipt
        # aggregate N+1 into two queries for the whole page. Detail/un-prefetched
        # callers fall back to the original per-receipt aggregate.
        prefetched = getattr(obj, 'posted_receipts', None)
        if prefetched is not None:
            receipts = prefetched
        else:
            receipts = obj.receipts.filter(
                voucher_type__in=['RCPT', 'RCPT-SALE'],
                status='posted',
            ).order_by('date', 'id')
        rows = []
        for v in receipts:
            applied = getattr(v, 'applied_amt', None)
            if applied is None:
                applied = (
                    _RefBills.objects.filter(voucher=v)
                    .aggregate(s=_Sum('amount'))['s'] or 0
                )
            rows.append({
                'id': v.id,
                'voucher_no': v.voucher_no,
                'date': v.date.isoformat(),
                'amount': float(v.amount),
                'amount_applied': float(applied),
                'amount_remaining': float(max(0, float(v.amount) - float(applied))),
                'narration': v.narration or '',
            })
        return rows

    def get_is_deletable(self, obj):
        return not obj.linked_vouchers.all()

    def get_is_cancellable(self, obj):
        return obj.delivery_status not in ('delivered', 'cancelled', 'returned')

    def get_has_in_production_items(self, obj):
        for it in obj.items.all():
            state, _ = _customer_order_item_lock(it)
            if state == 'in_production':
                return True
        return False

    def get_has_advance(self, obj):
        try:
            return float(obj.advance_amt) > 0
        except Exception:
            return False

    class Meta:
        model = CustomerOrder
        fields = ['id', 'ldgr', 'ldgr_code_name', 'ldgr_mobile', 'date1', 'order_no',
             'fix_gold_rate', 'gold_rate_date',
             'rate_14kt', 'rate_18kt', 'rate_22kt', 'salesman_1', 'salesman_2',
             'salesman_1_name', 'salesman_2_name',
             'advance_amt', 'est_amount', 'nature', 'status',
             'delivery_date', 'delivery_status', 'actual_delivery_date',
             'remarks', 'items',
             'advance_reconciled', 'advance_available', 'linked_bill_count',
             'is_overdue', 'days_overdue',
             'retail_name', 'retail_phone', 'retail_city',
             'retail_address_line1', 'retail_address_line2', 'retail_address_line3',
             'retail_pincode', 'retail_state', 'retail_gstin', 'retail_email',
             'is_deletable', 'is_cancellable', 'has_in_production_items', 'has_advance',
             'linked_receipts']
        # Batch-prime per-item lock state across the whole page (list endpoint)
        # to avoid the per-row barcode-chain N+1.
        list_serializer_class = CustomerOrderLockListSerializer

        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'ldgr_code_name': {'read_only': True},
            # order_no is generated server-side; frontend may omit or send a stale peek
            'order_no': {'required': False, 'allow_blank': True, 'default': ''},
        }

    def to_representation(self, instance):
        # Detail / write-return path (single order): batch-prime this order's
        # item locks so the nested lock_state fields don't issue per-item
        # barcode-chain queries. Idempotent — the list path primes the whole
        # page first, after which this is a no-op.
        try:
            _prime_co_item_locks(list(instance.items.all()))
        except Exception:
            pass
        return super().to_representation(instance)

    def validate(self, attrs):
        # Delivery date must be strictly after today. A same-day delivery is
        # not a meaningful commitment â€” the order is effectively due "now".
        from datetime import date as _date
        delivery = attrs.get('delivery_date')
        if delivery is not None:
            today = _date.today()
            if delivery <= today:
                raise serializers.ValidationError({
                    'delivery_date': f"Delivery date must be after today ({today.isoformat()})."
                })
        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            items_data = validated_data.pop('items')
            if 'fiscal_year' not in validated_data:
                request = self.context.get('request')
                _retail = validated_data.get('retail') or getattr(request, 'retail', None)
                if _retail:
                    from mastersconfig.fy_validation import assert_date_in_active_fy
                    assert_date_in_active_fy(_retail, validated_data.get("date1"))
                    validated_data['fiscal_year'] = getattr(_retail, 'active_fy', None)
            order_instance = CustomerOrder.objects.create(**validated_data)

            for item in items_data:
                CustomerOrderItems.objects.create(order_no=order_instance, **item)

            return order_instance

    def update(self, instance, validated_data):
        with transaction.atomic():

            items_data = validated_data.pop('items', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(CustomerOrderItemsSerializer, instance, 'items', 'order_no', CustomerOrderItemsSerializer(items_data,many=True).data)
            return instance

        
class CustomerOrderItemsToPurchaseStyleSerializer(CustomerOrderItemsSerializer1):
    def to_representation(self, instance):
        repr = super().to_representation(instance)

        # Rename fields to mimic PurchaseVoucherItems
        repr['item'] = repr.pop('item_id')
        repr['making'] = repr.pop('making_amt')

        # Remove unwanted fields
        repr.pop('remarks', None)
        repr.pop('id', None)
        repr.pop('retail', None)
        repr.pop('sl_no', None)

        return repr


# ============= Sales Voucher Serializers (formerly in sale_voucher app) =============

import json
from accounting import models
from accounting.serializers import JournalEntrySerializer
from accounting.utils import generate_voucher_no
from contacts.models import Ledger
from goldrates.models import PurityMaster
from inventory.models import BarcodeMain, BarcodeTransaction
from mastersconfig.models import Item, Packet, SalesPersonMaster, RetailMaster, State
import global_vars
from sales.models import (
    BankDetail, SalesVou, SalesVouItem, SalesVouItemDetails,
    SaleReturn, SaleReturnItem, SaleReturnDetails,
    SalesApproval, SalesApprovalItem, SalesApprovalItemDetails,
    SalesApprovalReturn, SalesApprovalReturnItem, SalesApprovalReturnItemDetails,
    SaleOldGoldAdjustment,
)


class SalesVouItemDetailsSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(),slug_field="pckt_no",allow_null=True)
    billno = serializers.PrimaryKeyRelatedField(queryset=SalesVou.objects.all(),required=False,allow_null=True)
    # Read-only helpers so the frontend recalc formula (uom === 'Ct' ? ct*rate : gw*rate)
    # works correctly in edit mode as well as add mode.
    uom = serializers.CharField(source='item.uom', read_only=True)
    item_type = serializers.CharField(source='item.item_type', read_only=True)
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    metal_purity = serializers.CharField(max_length=10, allow_null=True, allow_blank=True, required=False)

    class Meta:
        model = SalesVouItemDetails
        fields = [
            'id',
            'billno',
            'item',
            'pcs',
            'ct',
            'gw',
            'metal_purity',
            'tunch',
            'rate',
            'amount',
            'packet',
            'fine_wt',  # Computed property
            'uom',       # Read-only â€” item.uom, needed for frontend amount recalc
            'item_type', # Read-only â€” item.item_type, needed for frontend B2B overrides
            'item_name', # Read-only â€” item.item_name, shown in the sub-item row item column
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'pcs': {'allow_null': True, 'required': False},
            'ct': {'allow_null': True, 'required': False},
            'gw': {'allow_null': True, 'required': False},
        }

    def validate(self, data):
        # BarcodeDetails allows null for pcs/ct/gw; SalesVouItemDetails model does not.
        # Coerce any null weight/count fields to 0 so the DB save never fails.
        if data.get('pcs') is None:
            data['pcs'] = 0
        if data.get('ct') is None:
            data['ct'] = 0
        if data.get('gw') is None:
            data['gw'] = 0
        return data


class SalesVouItemSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    barcode = serializers.SlugRelatedField(queryset=BarcodeMain.objects.all(), slug_field="barcode")
    # purity is IntegerField on model (stores PK of PurityMaster) but frontend
    # sends the slug string (e.g. "14K"). Accept any value and resolve in validate.
    purity = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    main_item_set = SalesVouItemDetailsSerializer(many=True)

    # Read-only: lets the frontend know if this barcode is still in stock.
    # False means it has been sold/transferred â€” the voucher should be locked for editing.
    barcode_stk_status = serializers.SerializerMethodField(read_only=True)

    def get_barcode_stk_status(self, obj):
        try:
            return obj.barcode.stk_status if obj.barcode_id else None
        except Exception:
            return None

    class Meta:
        model = SalesVouItem
        fields = [
            'id',
            'barcode',
            'barcode_stk_status',
            'item',
            'pcs',
            'gw',
            'making',
            'making_type',
            'making_value',
            'purity',
            'amount',
            'main_item_set',  # Nested details serializer
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'pcs': {'required': False, 'allow_null': True},
        }

    def validate_purity(self, value):
        """Convert purity slug string (e.g. '14K') to PurityMaster PK (integer)."""
        if not value:
            return 0
        # Already numeric (PK) â€” return as-is
        try:
            return int(value)
        except (ValueError, TypeError):
            pass
        # Slug string â€” look up the PK
        try:
            return PurityMaster.objects.get(purity=value).pk
        except PurityMaster.DoesNotExist:
            return 0

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Convert purity PK (integer) back to slug string for display / edit reload.
        # IMPORTANT: use rep['purity'] rather than instance.purity here because
        # during the update path, create_or_update_nested re-serializes the
        # validated_data dicts.  Accessing a plain dict via attribute notation
        # (instance.purity) raises AttributeError and aborts the update transaction,
        # reverting all rate changes.  Reading from rep is always safe regardless
        # of whether instance is a model object or a plain dict.
        try:
            purity_pk = int(rep.get('purity') or 0)
        except (ValueError, TypeError):
            purity_pk = 0
        if purity_pk > 0:
            try:
                rep['purity'] = PurityMaster.objects.get(pk=purity_pk).purity
            except PurityMaster.DoesNotExist:
                rep['purity'] = str(purity_pk)
        return rep

    def _get_existing_vou_barcode_ids(self):
        """When this nested item serializer is bound to a SalesVouSerializer
        whose instance is the SalesVou being edited, return the set of
        barcode IDs already attached to that voucher. Used to allow the user
        to re-save the voucher with barcodes whose stk_status was flipped to
        False at original insert time."""
        from sales.models import SalesVou
        p = self.parent
        while p is not None:
            inst = getattr(p, 'instance', None)
            if isinstance(inst, SalesVou) and inst.pk:
                return set(inst.salesvouitem_set.values_list('barcode_id', flat=True))
            p = getattr(p, 'parent', None)
        return set()

    def validate_barcode(self, barcode):
        request = self.context.get('request')
        # When editing an existing sales voucher, the barcodes already attached
        # to it have stk_status=False (they were marked sold at insert time).
        # Skip the in-stock check for those — the user must be able to re-save
        # the voucher with the same barcodes. Newly added barcodes (not in the
        # existing voucher) still need to be in stock.
        existing_vou_barcode_ids = self._get_existing_vou_barcode_ids()
        is_already_on_voucher = barcode.id in existing_vou_barcode_ids
        if request and getattr(request, 'retail', None):
            if barcode.retail_id != request.retail.pk:
                raise serializers.ValidationError(
                    f"Barcode '{barcode.barcode}' does not belong to the current retail location."
                )
            if not is_already_on_voucher and not barcode.stk_status:
                raise serializers.ValidationError(
                    f"Barcode '{barcode.barcode}' is not in active stock "
                    "(it may already be sold, in transit, or transferred)."
                )
        if barcode.customer_order_id:
            bill_ldgr_id = self.context.get('sales_vou_ldgr_id')
            if bill_ldgr_id is None and request is not None and hasattr(request, 'data'):
                bill_ldgr_id = request.data.get('ldgr')
            try:
                bill_ldgr_id = int(bill_ldgr_id) if bill_ldgr_id is not None else None
            except (TypeError, ValueError):
                bill_ldgr_id = None
            reserved_ldgr_id = getattr(barcode.customer_order, 'ldgr_id', None)
            if bill_ldgr_id is not None and reserved_ldgr_id is not None and bill_ldgr_id != reserved_ldgr_id:
                reserved_party = getattr(getattr(barcode.customer_order, 'ldgr', None), 'ldgr_name', 'reserved customer')
                raise serializers.ValidationError(
                    f"Barcode '{barcode.barcode}' is reserved for customer order "
                    f"{barcode.customer_order.order_no} ({reserved_party}). "
                    "Release it from the order before selling to a different party."
                )
        return barcode
    def create(self, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('main_item_set', [])
            instance = SalesVouItem.objects.create(**validated_data)
            create_or_update_nested(SalesVouItemDetailsSerializer, instance, 'main_item_set', 'main_item', SalesVouItemDetailsSerializer(detail_data, many=True).data)
            return instance

    def update(self, instance, validated_data):
        with transaction.atomic():

            detail_data = validated_data.pop('main_item_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(SalesVouItemDetailsSerializer, instance, 'main_item_set', 'main_item',SalesVouItemDetailsSerializer(detail_data,many=True).data)
            return instance

class BankDetails(serializers.ModelSerializer):
    ledger_name = serializers.CharField(source='ledger.ac_name', read_only=True, default='')

    class Meta:
        fields = [
            'id', 'amount', 'payment_mode', 'bank_name',
            'chq_no', 'chq_date', 'ledger', 'ledger_name',
            'cheque_status', 'deposit_date', 'deposit_voucher',
        ]
        extra_kwargs = {
            'id':              {'read_only': False, 'required': False},
            'ledger':          {'required': False, 'allow_null': True},
            'bank_name':       {'required': False, 'allow_null': True, 'allow_blank': True},
            'chq_no':          {'required': False, 'allow_null': True, 'allow_blank': True},
            'chq_date':        {'required': False, 'allow_null': True},
            'payment_mode':    {'default': 'NEFT'},
            'cheque_status':   {'read_only': True},
            'deposit_date':    {'read_only': True},
            'deposit_voucher': {'read_only': True},
        }
        model = BankDetail


class SalesVouSerializer(serializers.ModelSerializer):
    has_eway_bill = serializers.BooleanField(read_only=True, default=False)
    ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    sales_person = serializers.PrimaryKeyRelatedField(queryset=SalesPersonMaster.objects.all())
    sales_person2 = serializers.PrimaryKeyRelatedField(queryset=SalesPersonMaster.objects.all(), allow_null=True, required=False)
    salesvouitem_set = SalesVouItemSerializer(many=True)
    salesvouitemdetails_set = SalesVouItemDetailsSerializer(many=True)
    bank_details =  BankDetails(many=True)
    mobile1 = serializers.CharField(source='ldgr.mobile1', read_only=True, default='')
    ldgr_gst = serializers.SerializerMethodField()

    def get_ldgr_gst(self, obj):
        return (getattr(obj.ldgr, 'gst', '') or '') if obj.ldgr_id else ''
    mobile2 = serializers.CharField(source='ldgr.mobile2', read_only=True, default='')
    mobile3 = serializers.CharField(source='ldgr.mobile3', read_only=True, default='')



    customer_order = serializers.PrimaryKeyRelatedField(
        queryset=CustomerOrder.objects.all(), allow_null=True, required=False
    )
    advance_receipt_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, write_only=True, default=list,
        help_text="PKs of unlinked RCPT vouchers to apply as advance (used when no customer_order is set)"
    )
    applied_advance_receipts = serializers.SerializerMethodField(read_only=True)
    unlinked_receipts = serializers.SerializerMethodField(read_only=True)

    def get_applied_advance_receipts(self, obj):
        if not obj.billno or not obj.ldgr_id:
            return []
        from accounting.models import ReferenceBills as _RefBills
        rows = (
            _RefBills.objects
            .filter(
                ref_bill_txt=obj.billno,
                ldgr=obj.ldgr,
                voucher__voucher_type__in=['RCPT', 'RCPT-SALE'],
            )
            .select_related('voucher')
            .order_by('voucher__date', 'voucher_id')
        )
        # ac_rec_voucher is the bill's own direct payment receipt (created
        # alongside the sale when cash/bank was collected at billing time —
        # see create()/update() below) — it's not a discretionary on-account
        # credit the user opted into, so it shouldn't appear as a selectable
        # "advance". Cash/bank collected this way is reflected via the
        # cash/bank_details fields instead.
        if obj.ac_rec_voucher_id:
            rows = rows.exclude(voucher_id=obj.ac_rec_voucher_id)
        return [
            {
                'id': r.voucher_id,
                'voucher_no': r.voucher.voucher_no,
                'date': r.voucher.date.isoformat() if r.voucher.date else '',
                'amount': float(r.voucher.amount or 0),
                'amount_remaining': float(r.amount or 0),
                'narration': r.voucher.narration or '',
            }
            for r in rows
        ]

    def get_unlinked_receipts(self, obj):
        if not obj.ldgr_id:
            return []
        from accounting.views.vouchers import unlinked_receipts_for_ledger
        return unlinked_receipts_for_ledger(obj.retail, obj.ldgr_id)

    # Multi-voucher old gold (POS path) — [{purchase_id, amount}, ...]
    old_gold_adjustments_data = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False, default=list,
    )

    # Inline old gold (sales-form path) — auto-creates a Customer PurchaseVoucher
    # owned by this sale. Each row: {item: short_code, purity: slug, pcs, ct, gw,
    # loss, tunch, rate, description, color, seives, clarity, uom}.
    inline_old_gold_items = serializers.ListField(
        child=serializers.DictField(), required=False, default=list,
    )
    inline_old_gold_pv = serializers.SerializerMethodField(read_only=True)

    def get_inline_old_gold_pv(self, obj):
        from purchase.models import PurchaseVoucher, PurchaseVoucherDetails
        pv = PurchaseVoucher.objects.filter(
            sale_adjustments__sale=obj, source='sales_inline'
        ).first()
        if not pv:
            return None
        rows = []
        for d in PurchaseVoucherDetails.objects.filter(billno=pv).select_related('sub_item', 'metal_purity'):
            rows.append({
                'id': d.id,
                'item': d.sub_item.short_code if d.sub_item else None,
                'item_name': d.sub_item.item_name if d.sub_item else None,
                'purity': d.metal_purity.purity if d.metal_purity else None,
                'pcs': d.sub_pcs,
                'ct': float(d.sub_ct or 0),
                'gw': float(d.sub_gw or 0),
                'loss': float(d.loss or 0),
                'tunch': float(d.tunch or 0),
                'fine_wt': float(d.fine_wt or 0),
                'rate': float(d.rate or 0),
                'value': float(d.value or 0),
            })
        return {'id': pv.id, 'billno': pv.billno, 'bill_value': float(pv.bill_value or 0), 'rows': rows}

    old_gold_purchase = serializers.PrimaryKeyRelatedField(
        queryset=PurchaseVoucher.objects.filter(voucher_type='Customer'),
        allow_null=True, required=False
    )

    def _upsert_sales_inline_pv(self, sale, rows, request):
        """Create or rebuild the sale-owned Customer PurchaseVoucher from inline rows.

        Returns (pv, total_value). pv is None when rows is empty (and any prior
        sale-inline PV gets deleted).
        """
        from decimal import Decimal
        from purchase.models import PurchaseVoucher, PurchaseVoucherItems, PurchaseVoucherDetails
        from accounting.utils import get_next_bill_number
        from mastersconfig.models import Item as _Item
        from goldrates.models import PurityMaster as _Purity
        from sales.models import SaleOldGoldAdjustment

        rows = rows or []

        def _resolve_item(val):
            if val is None or val == '':
                return None
            if isinstance(val, _Item):
                return val
            try:
                return _Item.objects.get(short_code=val)
            except _Item.DoesNotExist:
                raise ValidationError({'inline_old_gold_items': f"Item '{val}' not found."})

        def _resolve_purity(val):
            if val in (None, '', 'null'):
                return None
            if isinstance(val, _Purity):
                return val
            try:
                return _Purity.objects.get(purity=val)
            except _Purity.DoesNotExist:
                return None

        def _D(v):
            return Decimal(str(v or 0))

        existing_pv = PurchaseVoucher.objects.filter(
            sale_adjustments__sale=sale, source='sales_inline'
        ).first()

        if not rows:
            if existing_pv:
                SaleOldGoldAdjustment.objects.filter(sale=sale, purchase=existing_pv).delete()
                if existing_pv.ac_voucher_id:
                    existing_pv.ac_voucher.delete()
                existing_pv.delete()
            return None, Decimal('0')

        # Resolve and validate every row's item is Raw/Stone, then compute values.
        prepared = []
        for r in rows:
            it = _resolve_item(r.get('item'))
            if not it:
                raise ValidationError({'inline_old_gold_items': "Each row needs an item."})
            if it.item_type not in ('R', 'S'):
                raise ValidationError({'inline_old_gold_items':
                    f"Item '{it.short_code}' is type '{it.item_type}'; only Raw or Stone allowed in old gold exchange."})
            gw, loss, tunch, rate = _D(r.get('gw')), _D(r.get('loss')), _D(r.get('tunch')), _D(r.get('rate'))
            fine_wt = (gw - loss) * tunch / Decimal('100')
            value = (fine_wt * rate).quantize(Decimal('0.01'))
            fine_wt = fine_wt.quantize(Decimal('0.01'))
            prepared.append({
                'item': it,
                'purity': _resolve_purity(r.get('purity')),
                'pcs': int(r.get('pcs') or 0),
                'ct': _D(r.get('ct')),
                'gw': gw,
                'loss': loss,
                'tunch': tunch,
                'rate': rate,
                'fine_wt': fine_wt,
                'value': value,
            })
        total = sum((p['value'] for p in prepared), Decimal('0'))

        retail = request.retail

        # Mirror the branch / GSTIN context from the parent sale so the PV
        # is filterable in the same branch and GSTIN reports.
        sale_branch = getattr(sale, 'branch_ref', None) or getattr(retail, 'branch', None)
        sale_gstin  = getattr(sale, 'gstin_ref',  None) or getattr(retail, 'gstin',  None)

        if existing_pv:
            existing_pv.purchasevoucheritems_set.all().delete()
            existing_pv.purchasevoucherdetails_set.all().delete()
            if existing_pv.ac_voucher_id:
                existing_pv.ac_voucher.delete()
                existing_pv.ac_voucher = None
            pv = existing_pv
            pv.date1 = sale.date1
            pv.ldgr = sale.ldgr
            pv.item_total = total
            pv.bill_value = total
            pv.total_incl_gst = total
            pv.due_amt = Decimal('0')
            pv.fiscal_year = sale.fiscal_year
            pv.branch_ref = sale_branch
            pv.gstin_ref  = sale_gstin
            pv.save()
        else:
            billno = get_next_bill_number(retail, 'PVC', sale.fiscal_year)
            pv = PurchaseVoucher.objects.create(
                date1=sale.date1,
                billno=billno,
                voucher_type='Customer',
                ldgr=sale.ldgr,
                item_total=total,
                bill_value=total,
                total_incl_gst=total,
                due_amt=Decimal('0'),
                source='sales_inline',
                retail=retail,
                fiscal_year=sale.fiscal_year,
                branch_ref=sale_branch,
                gstin_ref=sale_gstin,
            )

        item_details_for_journal = []
        for idx, p in enumerate(prepared, 1):
            main = PurchaseVoucherItems.objects.create(
                billno=pv,
                date1=sale.date1,
                item=p['item'],
                sl_no=idx,
                pcs=p['pcs'],
                gw=p['gw'],
                purity=p['purity'],
                making=Decimal('0'),
                making_value=0,
                item_value=p['value'],
                retail=retail,
            )
            det = PurchaseVoucherDetails.objects.create(
                main_item=main,
                billno=pv,
                date1=sale.date1,
                sub_item=p['item'],
                sub_pcs=p['pcs'],
                sub_gw=p['gw'],
                sub_ct=p['ct'],
                metal_purity=p['purity'],
                loss=p['loss'],
                tunch=p['tunch'],
                fine_wt=p['fine_wt'],
                rate=p['rate'],
                value=p['value'],
                retail=retail,
            )
            item_details_for_journal.append(det)

        # Build the PV's own accounting journal: DR each item.purchase_ledger / CR customer ldgr.
        if total > 0:
            ser = JournalEntrySerializer(data={
                'date': sale.date1.strftime('%Y-%m-%d'),
                'voucher_no': pv.billno,
                'retail': retail.id,
                'narration': f"Old gold purchase inline with Sales {sale.billno}",
                'voucher_type': global_vars.VoucherType.purc_sc,
                'voucher_details': [
                    {
                        'account': (
                            d.sub_item.purchase_ledger_id
                            if d.sub_item and d.sub_item.purchase_ledger
                            else _raise_missing_ledger(f"Purchase Ledger for item '{d.sub_item}'")
                        ),
                        'debit': f"{d.value:.2f}",
                    }
                    for d in item_details_for_journal
                ] + [
                    {
                        'account': pv.ldgr_id,
                        'credit': f"{total:.2f}",
                    }
                ],
            }, context=self.context)
            ser.is_valid(raise_exception=True)
            pv.ac_voucher = ser.save()
            pv.save(update_fields=['ac_voucher'])

        return pv, total


    total_gw = serializers.SerializerMethodField(read_only=True)
    total_net_wt = serializers.SerializerMethodField(read_only=True)
    total_diamond_ct = serializers.SerializerMethodField(read_only=True)

    def get_total_gw(self, obj):
        from decimal import Decimal
        return sum((i.gw or Decimal('0')) for i in obj.salesvouitem_set.all())

    def get_total_net_wt(self, obj):
        from decimal import Decimal
        total = Decimal('0')
        for i in obj.salesvouitem_set.all():
            if i.barcode_id and i.barcode and i.barcode.nw:
                total += i.barcode.nw
        return total

    def get_total_diamond_ct(self, obj):
        from decimal import Decimal
        total = Decimal('0')
        # Sub-items nested under barcode-linked main items
        for it in obj.salesvouitem_set.all():
            for d in it.main_item_set.all():
                if d.item_id and d.item and d.item.item_type == 'S' and d.ct:
                    total += d.ct
        # Manual sub-items (not linked to a main item)
        for d in obj.salesvouitemdetails_set.all():
            if d.main_item_id is None and d.item_id and d.item and d.item.item_type == 'S' and d.ct:
                total += d.ct
        return total

    class Meta:
        model = SalesVou
        fields = [
            'id',
            'bank_details',
            'date1',
            'billno',
            'gst_billno',
            'cash',
            'due_amt',
            'advance_deducted',
            'advance_receipt_ids',
            'applied_advance_receipts',
            'unlinked_receipts',
            'customer_order',
            'old_gold_purchase',
            'old_gold_adjusted',
            'ldgr',
            'ldgr_name',
            'ldgr_gst',
            'mobile1',
            'mobile2',
            'mobile3',
            'sales_person',
            'sales_person2',
            'place_of_supply',
            'ret_status',
            'remarks',
            'freight_charge',
            'other_charge',
            'mrp',
            'discount',
            'taxable_value',  # Computed property
            'sgst_per',
            'cgst_per',
            'igst_per',
            'tcs_per',
            'mode_of_transport',
            'sgst_amt',  # Computed property
            'cgst_amt',  # Computed property
            'igst_amt',  # Computed property
            'total_bill_value',  # Computed property
            'tcs_amt',  # Computed property
            'total_gw',
            'total_net_wt',
            'total_diamond_ct',
            'salesvouitem_set',  # Nested items serializer
            'salesvouitemdetails_set',
            'exhibition_profile',
            'vehicle_no',
            'transporter_name',
            'transporter_id',
            'trans_distance',
            'trans_doc_no',
            'trans_doc_date',
            'has_eway_bill',
            'old_gold_adjustments_data',
            'inline_old_gold_items',
            'inline_old_gold_pv',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'remarks': {'required': False, 'allow_blank': True, 'allow_null': True},
            'cash': {'required': False, 'allow_null': True},
            'gst_billno': {'required': False, 'allow_blank': True},
        }

    def validate_cash(self, value):
        """Treat null/empty cash as 0."""
        if value is None:
            return 0
        return value

    def to_internal_value(self, data):
        # Propagate selected customer (ldgr) into context BEFORE nested item
        # validators run, so SalesVouItemSerializer.validate_barcode() can enforce
        # the customer-order reservation guard reliably (incl. for nested calls
        # where request.data fallback may not see top-level ldgr).
        if hasattr(data, 'get'):
            ldgr_val = data.get('ldgr')
            if ldgr_val not in (None, '', 'null'):
                try:
                    self.context['sales_vou_ldgr_id'] = int(ldgr_val)
                except (TypeError, ValueError):
                    pass
        return super().to_internal_value(data)

    def create(self, validated_data):
        from sales.utils import generate_next_sale_voucher_no
        with transaction.atomic():
            items_data = validated_data.pop('salesvouitem_set')
            item_Details = validated_data.pop('salesvouitemdetails_set')
            bank_details = validated_data.pop('bank_details')
            advance_receipt_ids = validated_data.pop('advance_receipt_ids', [])
            inline_old_gold_items = validated_data.pop('inline_old_gold_items', []) or []

            # Auto-generate bill number server-side to avoid clashes
            request = self.context.get("request")
            validated_data['billno'] = generate_next_sale_voucher_no(request.retail)

            # â”€â”€ Section 269ST cash receipt limit check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            new_cash = Decimal(str(validated_data.get('cash', 0) or 0))
            if new_cash > 0:
                from accounting.utils import get_customer_cash_received, get_company_cash_limits
                limit, _ = get_company_cash_limits(request.retail)
                if limit is not None:   # None means enforcement is disabled
                    customer_ldgr = validated_data.get('ldgr')
                    fy = validated_data.get('fiscal_year') or request.retail.active_fy
                    already = get_customer_cash_received(request.retail, fy, customer_ldgr)
                    if already + new_cash > limit:
                        remaining = max(Decimal('0'), limit - already)
                        raise ValidationError({
                            'cash': (
                                f"Cash receipt limit exceeded for '{customer_ldgr.ac_name}'. "
                                f"Already received â‚¹{already:,.0f} this FY  |  "
                                f"Limit: â‚¹{limit:,.0f}  |  "
                                f"Max receivable now: â‚¹{remaining:,.0f}."
                            )
                        })
            # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

            # â”€â”€ Compute server-side due_amt (patched after instance creation) â”€â”€
            cash_amt         = Decimal(str(validated_data.get('cash', 0) or 0))
            bank_total       = sum(Decimal(str(b.get('amount', 0) or 0)) for b in bank_details)
            # total_bill_value is a model property; read after instance creation below

            # â”€â”€ Auto-apply advance (single source of truth) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # advance_deducted is always computed server-side, never accepted from client.
            # Path A: customer_order FK set â†’ use order's linked RCPT pool.
            # Path B: advance_receipt_ids provided â†’ direct RCPT selection (no order needed).
            customer_order = validated_data.get('customer_order')
            if customer_order and advance_receipt_ids:
                raise ValidationError(
                    'Provide either customer_order or advance_receipt_ids, not both.'
                )
            if customer_order:
                advance_deducted = customer_order.advance_available
            elif advance_receipt_ids:
                from django.db.models import Sum as _Sum
                from accounting.models import VoucherMain as _VM, ReferenceBills as _RefBills
                advance_deducted = Decimal('0')
                for rcpt_pk in advance_receipt_ids:
                    try:
                        rcpt = _VM.objects.get(
                            pk=rcpt_pk,
                            voucher_type__in=['RCPT', 'RCPT-SALE'],
                            status='posted',
                        )
                    except _VM.DoesNotExist:
                        raise ValidationError(f'Receipt id={rcpt_pk} not found or not a valid RCPT.')
                    applied = (
                        _RefBills.objects.filter(voucher=rcpt)
                        .aggregate(s=_Sum('amount'))['s'] or Decimal('0')
                    )
                    advance_deducted += max(Decimal('0'), Decimal(str(rcpt.amount)) - applied)
            else:
                advance_deducted = Decimal('0')
            validated_data['advance_deducted'] = advance_deducted

            # â”€â”€ Validate old_gold_adjusted against purchase's available balance â”€â”€
            # Multi-voucher old gold (POS path)
            from django.db.models import Sum as _Sum
            _og_adjustments_raw = validated_data.pop('old_gold_adjustments_data', []) or []
            _og_adjustments = []  # [{purchase: PurchaseVoucher, amount: Decimal}]
            if _og_adjustments_raw:
                for _entry in _og_adjustments_raw:
                    try:
                        _pv = PurchaseVoucher.objects.get(pk=_entry['purchase_id'], voucher_type='Customer')
                    except PurchaseVoucher.DoesNotExist:
                        raise ValidationError({'old_gold_adjustments_data': f"Purchase {_entry['purchase_id']} not found."})
                    _amt = Decimal(str(_entry.get('amount', 0) or 0))
                    if _amt <= 0:
                        continue
                    _already = (
                        (_pv.linked_sales_vouchers.aggregate(s=_Sum('old_gold_adjusted'))['s'] or Decimal('0')) +
                        (_pv.sale_adjustments.aggregate(s=_Sum('amount'))['s'] or Decimal('0'))
                    )
                    _avail = Decimal(str(_pv.bill_value or 0)) - _already
                    if _amt > _avail:
                        raise ValidationError({'old_gold_adjustments_data':
                            f"Cannot adjust Rs.{_amt:,.0f} from {_pv.billno} - only Rs.{_avail:,.0f} available."})
                    _og_adjustments.append({'purchase': _pv, 'amount': _amt})

            # Single-voucher old gold (legacy Sales Voucher path)
            old_gold_adjusted = Decimal(str(validated_data.get('old_gold_adjusted', 0) or 0))
            old_gold_purchase = validated_data.get('old_gold_purchase')
            if _og_adjustments:
                old_gold_adjusted = sum(e['amount'] for e in _og_adjustments)
                validated_data['old_gold_adjusted'] = old_gold_adjusted
                validated_data['old_gold_purchase'] = None
                old_gold_purchase = None
            elif old_gold_purchase and old_gold_adjusted > 0:
                already_adj = old_gold_purchase.linked_sales_vouchers.aggregate(
                    s=_Sum('old_gold_adjusted'))['s'] or Decimal('0')
                available_og = Decimal(str(old_gold_purchase.bill_value or 0)) - already_adj
                if old_gold_adjusted > available_og:
                    raise ValidationError({
                        'old_gold_adjusted': f'Cannot adjust from {old_gold_purchase.billno} - insufficient balance.'
                    })

            if 'fiscal_year' not in validated_data:
                _retail = validated_data.get('retail') or getattr(request, 'retail', None)
                if _retail:
                    from mastersconfig.fy_validation import assert_date_in_active_fy
                    assert_date_in_active_fy(_retail, validated_data.get("date1"))
                    validated_data['fiscal_year'] = getattr(_retail, 'active_fy', None)
            sales_vou_instance = SalesVou.objects.create(**validated_data)

            # ── Inline old-gold purchase: auto-create a sale-owned Customer PV ──
            # When inline rows are present, fold any legacy single-FK old gold
            # into _og_adjustments so everything flows through the multi-voucher path.
            if inline_old_gold_items:
                if old_gold_purchase and old_gold_adjusted > 0 and not _og_adjustments:
                    _og_adjustments.append({'purchase': old_gold_purchase, 'amount': old_gold_adjusted})
                    sales_vou_instance.old_gold_purchase = None
                    old_gold_purchase = None
                _inline_pv, _inline_total = self._upsert_sales_inline_pv(
                    sales_vou_instance, inline_old_gold_items, request
                )
                if _inline_pv and _inline_total > 0:
                    _og_adjustments.append({'purchase': _inline_pv, 'amount': _inline_total})
                    old_gold_adjusted += _inline_total
                    sales_vou_instance.old_gold_adjusted = old_gold_adjusted
                    sales_vou_instance.save(update_fields=['old_gold_adjusted', 'old_gold_purchase'])

            # Patch due_amt now that the instance exists (total_bill_value is a property)
            total_bill = Decimal(str(sales_vou_instance.total_bill_value))

            # Cap advance_deducted to the portion of the bill not covered by
            # cash / bank / old gold â€” any surplus order advance stays on the
            # order to be consumed by future bills against the same order.
            room_for_advance = max(Decimal('0'), total_bill - cash_amt - bank_total - old_gold_adjusted)
            if advance_deducted > room_for_advance:
                advance_deducted = room_for_advance
                sales_vou_instance.advance_deducted = advance_deducted
                sales_vou_instance.save(update_fields=['advance_deducted'])

            sales_vou_instance.due_amt = max(
                Decimal('0'),
                total_bill - cash_amt - bank_total - advance_deducted - old_gold_adjusted
            )
            # (saved again after ac_voucher is assigned below)

            # â”€â”€ Write ReferenceBills rows (advance audit trail) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # "RCPT-123 was used to pay SV-456 for â‚¹X"
            if advance_deducted > 0:
                from django.db.models import Sum as _Sum
                from accounting.models import ReferenceBills as _RefBills, VoucherMain as _VM
                remaining = advance_deducted

                if customer_order:
                    # Path A: FIFO across all receipts linked to the order
                    receipt_pool = list(
                        customer_order.receipts.filter(
                            voucher_type__in=['RCPT', 'RCPT-SALE'],
                            status='posted',
                        ).order_by('date', 'id')
                    )
                else:
                    # Path B: explicit receipt IDs supplied by the frontend
                    receipt_pool = list(
                        _VM.objects.filter(
                            pk__in=advance_receipt_ids,
                            voucher_type__in=['RCPT', 'RCPT-SALE'],
                            status='posted',
                        ).order_by('date', 'id')
                    )

                for rcpt in receipt_pool:
                    if remaining <= 0:
                        break
                    already = _RefBills.objects.filter(voucher=rcpt).aggregate(
                        s=_Sum('amount')
                    )['s'] or Decimal('0')
                    rcpt_available = Decimal(str(rcpt.amount)) - already
                    if rcpt_available <= 0:
                        continue
                    alloc = min(remaining, rcpt_available)
                    _RefBills.objects.create(
                        ldgr=sales_vou_instance.ldgr,
                        voucher=rcpt,
                        amount=alloc,
                        vendor_bill_no="",
                        ref_bill=None,
                        ref_bill_txt=sales_vou_instance.billno,
                    )
                    remaining -= alloc

            # Create related SalesVouItem instances
            item_instances = []
            item_detail_instances = []

            create_or_update_nested(BankDetails,sales_vou_instance,'bank_details','sales_vou',BankDetails(bank_details,many=True).data)

            for detail_data in item_Details:
                # Drop FE-echoed FK fields so **detail_data doesn't collide
                # with the explicit billno kwarg.
                detail_data = {k: v for k, v in detail_data.items()
                               if k not in {"billno", "main_item", "id"}}
                detail_instance = SalesVouItemDetails.objects.create(billno=sales_vou_instance, **detail_data)
                item_detail_instances.append(detail_instance)

            for item_data in items_data:
                details_data = item_data.pop('main_item_set')
                id = item_data.pop('id')
                sales_vou_item_instance = SalesVouItem.objects.create(billno=sales_vou_instance, **item_data)
                item_instances.append(sales_vou_item_instance)
                sales_vou_item_instance.barcode.stk_status = False
                sales_vou_item_instance.barcode.save()

                # Create related SalesVouItemDetails instances
                for detail_data in details_data:
                    detail_instance = SalesVouItemDetails.objects.create(main_item=sales_vou_item_instance, **detail_data)
                    item_detail_instances.append(detail_instance)

            # â”€â”€ Recompute mrp from actual saved items â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # Journal balance: DEBIT total_bill_value = CREDIT Î£making + Î£item.amount
            # so mrp must equal Î£ making_value + Î£ item_detail.amount.
            # Recomputing from DB guarantees consistency even if the frontend
            # sent a slightly different value due to rounding or stale state.
            _actual_mrp = (
                sum(Decimal(str(item.making_value or 0)) for item in item_instances)
                + sum(Decimal(str(d.amount or 0)) for d in item_detail_instances)
            )
            sales_vou_instance.mrp = _actual_mrp
            sales_vou_instance.save(update_fields=['mrp'])

            _gm = request.retail.gstin_master
            _co = request.retail.branch.company if request.retail.branch_id and request.retail.branch else None
            out_cgst = _gm.output_cgst.id if _gm and _gm.output_cgst else _raise_missing_ledger("OUTPUT CGST")
            out_sgst = _gm.output_sgst.id if _gm and _gm.output_sgst else _raise_missing_ledger("OUTPUT SGST")
            out_igst = _gm.output_igst.id if _gm and _gm.output_igst else _raise_missing_ledger("OUTPUT IGST")
            _making_recv_ldgr = _co.making_receive_ldgr.id if _co and _co.making_receive_ldgr else _raise_missing_ledger("Making Charge Receive")
            _discount_ldgr = _co.discount_ldgr.id if _co and _co.discount_ldgr else _raise_missing_ledger("Sale Discount")
            _cash_ldgr = request.retail.cash_ldgr.id if request.retail.cash_ldgr else _raise_missing_ledger("CASH")
            _round_off_ldgr = _co.round_off_ldgr.id if _co and _co.round_off_ldgr else _raise_missing_ledger("Round Off")

            def _making_recv_ldgr_for_item(item):
                """Return purity-specific making charge received ledger for a barcode item."""
                try:
                    purity_str = (item.barcode.purity.purity or '').upper() if item.barcode_id and item.barcode and item.barcode.purity else ''
                except Exception:
                    purity_str = ''
                if '14' in purity_str and _co and _co.making_receive_14k_ldgr:
                    return _co.making_receive_14k_ldgr.id
                if '18' in purity_str and _co and _co.making_receive_18k_ldgr:
                    return _co.making_receive_18k_ldgr.id
                if '22' in purity_str and _co and _co.making_receive_22k_ldgr:
                    return _co.making_receive_22k_ldgr.id
                return _making_recv_ldgr  # fallback to generic

            # Only build TCS journal line when TCS actually applies
            _tcs_amt = float(sales_vou_instance.tcs_amt or 0)
            _tcs_lines = []
            if _tcs_amt > 0:
                _tcs_ldgr_name = (
                    sales_vou_instance.tcs_section.ledger.id
                    if sales_vou_instance.tcs_section and sales_vou_instance.tcs_section.ledger
                    else _raise_missing_ledger("TCS Payable (configure TCS Section master)")
                )
                _tcs_lines = [{'account': _tcs_ldgr_name, 'debit': 0, 'credit': f"{_tcs_amt:.2f}"}]

            # Compute party debit using Decimal-rounded components so it matches
            # credit-side rounding exactly (avoids 0.01 mismatch with float arithmetic).
            _cgst_d  = Decimal(f"{sales_vou_instance.cgst_amt:.2f}")
            _sgst_d  = Decimal(f"{sales_vou_instance.sgst_amt:.2f}")
            _igst_d  = Decimal(f"{sales_vou_instance.igst_amt:.2f}")
            _taxable_d = Decimal(str(sales_vou_instance.mrp or 0)) - Decimal(str(sales_vou_instance.discount or 0))
            _round_off_d = Decimal(str(sales_vou_instance.round_off or 0))
            _tcs_d   = Decimal(f"{_tcs_amt:.2f}")
            _party_debit = _taxable_d + _cgst_d + _sgst_d + _igst_d + _tcs_d + _round_off_d

            # ── Reject over-receipt ──────────────────────────────────────────
            # Customer cannot pay more than the bill receivable. Check after
            # advance has been server-capped so the comparison is exact.
            _received_total = (
                Decimal(str(sales_vou_instance.cash or 0))
                + sum(Decimal(str(b.get('amount', 0) or 0)) for b in bank_details)
                + Decimal(str(sales_vou_instance.old_gold_adjusted or 0))
                + Decimal(str(sales_vou_instance.advance_deducted or 0))
            )
            if _received_total > _party_debit:
                raise serializers.ValidationError({
                    'bank_details': (
                        f"Receipts (₹{_received_total:.2f}) exceed bill total "
                        f"(₹{_party_debit:.2f}). Reduce cash or bank amounts by "
                        f"₹{(_received_total - _party_debit):.2f}."
                    )
                })

            ser = JournalEntrySerializer(data= {'date':sales_vou_instance.date1.strftime('%Y-%m-%d'),
                                    "voucher_no":sales_vou_instance.billno,
                                    'retail':request.retail.id,
                                    "narration":f"Sale Voucher Narration",
                                    "voucher_type":global_vars.VoucherType.sale,

                                    "voucher_details": [
                                        {
                                            'account': out_cgst,
                                            'credit':f"{sales_vou_instance.cgst_amt:.2f}"

                                        },
                                        {'account': out_sgst,
                                            'debit':0,
                                            'credit':f"{sales_vou_instance.sgst_amt:.2f}"
                                        },
                                        {'account': out_igst,
                                            'debit':0,
                                            'credit':f"{sales_vou_instance.igst_amt:.2f}"
                                        },
                                    ] +
                                    _tcs_lines +
                                    [{'account': _making_recv_ldgr_for_item(item),
                                        'debit':0,
                                        'credit':f"{item.making_value:.2f}"
                                    } for item in item_instances] +
                                    [{'account':(item.item.sale_ledger_id if item.item.sale_ledger else _raise_missing_ledger(f"Sale Ledger for item '{item.item}'")),
                                        'debit':0,
                                        'credit':f"{item.amount:.2f}"
                                    } for item in item_detail_instances] +

                                    [{
                                        'account':_discount_ldgr,
                                        'debit':f"{sales_vou_instance.discount:.2f}",
                                        'credit':0
                                    }] +
                                    ([{
                                        'account': _round_off_ldgr,
                                        'debit':  f"{abs(sales_vou_instance.round_off):.2f}" if sales_vou_instance.round_off and sales_vou_instance.round_off < 0 else 0,
                                        'credit': f"{abs(sales_vou_instance.round_off):.2f}" if sales_vou_instance.round_off and sales_vou_instance.round_off > 0 else 0,
                                    }] if sales_vou_instance.round_off else []) +
                                    [{
                                        'account':sales_vou_instance.ldgr_id,
                                        'debit':f"{_party_debit:.2f}",
                                        'credit':0
                                    }]},
                                    context=self.context)


            if ser.is_valid(raise_exception=True):

                ref = ser.save()


            def _bank_debit_account(bank):
                """Resolve the debit ledger for a bank/cheque receipt line to a
                primary key (never a name). Cheques go to the Cheques-in-Hand
                suspense ledger (company FK); all other modes go to the selected
                bank ledger id. A non-cheque row must carry a ledger id."""
                if bank.get("payment_mode") == "CHEQUE":
                    from mastersconfig.ledger_utils import get_cheques_in_hand_ledger
                    return get_cheques_in_hand_ledger(_co).id
                ldgr = bank.get("ledger")
                if ldgr:
                    return getattr(ldgr, 'id', None) or ldgr
                return _raise_missing_ledger("Bank Ledger")

            _rcpt_customer_credit = (
                sales_vou_instance.cash
                + sum(Decimal(str(bank['amount'])) for bank in bank_details)
                + old_gold_adjusted
            )
            rcpt_ref = None
            if _rcpt_customer_credit > 0:
                _cash_lines = ([{
                    'account': _cash_ldgr,
                    'debit': f"{sales_vou_instance.cash:.2f}",
                    'credit': 0,
                }] if sales_vou_instance.cash > 0 else [])
                ser = JournalEntrySerializer(data= {'date':sales_vou_instance.date1.strftime('%Y-%m-%d'),
                                        "voucher_no":generate_voucher_no(global_vars.VoucherType.rcpt_sale, self.context.get('request').retail),
                                        'retail':request.retail.id,
                                        "narration":f"Sale Voucher Receipt Narration",
                                        "voucher_type":global_vars.VoucherType.rcpt_sale,

                                        "voucher_details": _cash_lines +
                                [{
                                    'account': _bank_debit_account(bank),
                                    'debit':f"{Decimal(str(bank['amount'])):.2f}",
                                    'credit':0,
                                    'party_bank_name':bank["bank_name"],
                                    "chq_no":bank.get("chq_no"),
                                    "chq_date":bank.get("chq_date"),
                                } for bank in bank_details] +
                                # Old gold DR lines: one per purchase (multi-voucher or single)
                                ([{
                                    'account': e['purchase'].ldgr_id,
                                    'debit': f"{e['amount']:.2f}",
                                    'credit': 0,
                                } for e in _og_adjustments] if _og_adjustments else
                                [{
                                    'account': old_gold_purchase.ldgr_id,
                                    'debit': f"{old_gold_adjusted:.2f}",
                                    'credit': 0,
                                }] if old_gold_purchase and old_gold_adjusted > 0 else []) +
                                [{
                                            'account': sales_vou_instance.ldgr_id,
                                            'credit': f"{_rcpt_customer_credit:.2f}",
                                            'debit': 0,
                                            'ref_sales_vou': sales_vou_instance.pk,
                                            'ref_bill_no': sales_vou_instance.billno,
                                        }]},
                                        context=self.context)
                if ser.is_valid(raise_exception=True):
                    rcpt_ref = ser.save()

            sales_vou_instance.ac_voucher = ref
            sales_vou_instance.ac_rec_voucher = rcpt_ref
            sales_vou_instance.gstin_ref  = request.retail.gstin_master
            sales_vou_instance.branch_ref = request.retail.branch
            sales_vou_instance.save()

            # â”€â”€ Update CustomerOrder status to reflect billing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if customer_order:
                total_reconciled = customer_order.advance_reconciled
                advance_total    = customer_order.advance_amt
                if advance_total > 0 and total_reconciled >= advance_total:
                    customer_order.status = 'Billed'
                elif total_reconciled > 0:
                    customer_order.status = 'Partial'
                else:
                    customer_order.status = 'Billed'
                customer_order.save(update_fields=['status'])

            # â”€â”€ Update old gold purchase voucher due_amt â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # Update due_amt on all touched purchase vouchers
            _purchases_to_update = {e['purchase'] for e in _og_adjustments}
            if old_gold_purchase and old_gold_adjusted > 0:
                _purchases_to_update.add(old_gold_purchase)
            # Create SaleOldGoldAdjustment rows for multi-voucher path
            if _og_adjustments:
                SaleOldGoldAdjustment.objects.bulk_create([
                    SaleOldGoldAdjustment(sale=sales_vou_instance, purchase=e['purchase'], amount=e['amount'])
                    for e in _og_adjustments
                ])
            for _pv in _purchases_to_update:
                _total = (
                    (_pv.linked_sales_vouchers.aggregate(s=_Sum('old_gold_adjusted'))['s'] or Decimal('0')) +
                    (_pv.sale_adjustments.aggregate(s=_Sum('amount'))['s'] or Decimal('0'))
                )
                _pv.due_amt = max(Decimal('0'), Decimal(str(_pv.bill_value or 0)) - _total)
                _pv.save(update_fields=['due_amt'])

            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')) if request else None
            for item_br in item_instances:
                BarcodeTransaction.objects.create(
                    barcode=item_br.barcode,
                    billno=sales_vou_instance.billno,
                    trans_type="SALE",
                    user=request.user,
                    ip_address=ip,
                    retail=request.retail
                )
            return sales_vou_instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            # â”€â”€ Release this voucher's barcodes back to stock before update â”€â”€
            # The voucher's own barcodes have stk_status=False (they were marked
            # sold at create time). Temporarily flipping them to True lets the
            # nested update validate/add/remove barcodes freely. We re-mark the
            # FINAL item set as sold after the nested update runs. Everything
            # below is inside transaction.atomic() â€” any failure rolls back.
            for _it in instance.salesvouitem_set.select_related('barcode').all():
                if _it.barcode_id and _it.barcode and not _it.barcode.stk_status:
                    _it.barcode.stk_status = True
                    _it.barcode.save(update_fields=['stk_status'])

            detail_data = validated_data.pop('salesvouitem_set', [])
            item_details_data = validated_data.pop('salesvouitemdetails_set', [])
            bank_details = validated_data.pop('bank_details')
            inline_old_gold_items = validated_data.pop('inline_old_gold_items', []) or []
            # Advance receipts: when the frontend explicitly sends advance_receipt_ids
            # (including an empty list), reconcile ReferenceBills allocations to match.
            _adv_ids_sentinel = object()
            advance_receipt_ids = validated_data.pop('advance_receipt_ids', _adv_ids_sentinel)
            _reconcile_advance = (
                advance_receipt_ids is not _adv_ids_sentinel
                and not validated_data.get('customer_order')
                and not instance.customer_order_id
            )
            if _reconcile_advance:
                from accounting.models import ReferenceBills as _RefBills, VoucherMain as _VM
                # Clear existing RCPT allocations against this bill
                _RefBills.objects.filter(
                    ref_bill_txt=instance.billno,
                    voucher__voucher_type__in=['RCPT', 'RCPT-SALE'],
                ).delete()
                # Recompute advance_deducted from the new selection
                new_advance = Decimal('0')
                _selected_rcpts = list(
                    _VM.objects.filter(
                        pk__in=advance_receipt_ids or [],
                        voucher_type__in=['RCPT', 'RCPT-SALE'],
                        status='posted',
                    ).order_by('date', 'id')
                )
                for rcpt in _selected_rcpts:
                    from django.db.models import Sum as _SumA
                    already = _RefBills.objects.filter(voucher=rcpt).aggregate(
                        s=_SumA('amount')
                    )['s'] or Decimal('0')
                    avail = Decimal(str(rcpt.amount)) - already
                    if avail > 0:
                        new_advance += avail
                validated_data['advance_deducted'] = new_advance
                # Stash for post-save ReferenceBills creation
                self._pending_advance_rcpts = _selected_rcpts
                self._pending_advance_total = new_advance
            else:
                self._pending_advance_rcpts = None
                self._pending_advance_total = None
            validated_data.pop('old_gold_adjustments_data', None)

            # â”€â”€ Snapshot current DB values BEFORE setattr overwrites them â”€â”€â”€â”€â”€â”€
            # Needed to preserve subsequent payment receipts when recalculating due_amt.
            _old_total_bill  = Decimal(str(instance.total_bill_value))
            _old_cash        = Decimal(str(instance.cash or 0))
            _old_bank_total  = sum(Decimal(str(b.amount)) for b in instance.bank_details.all())
            _old_advance     = Decimal(str(instance.advance_deducted or 0))
            _old_old_gold    = Decimal(str(instance.old_gold_adjusted or 0))
            _old_due_amt     = Decimal(str(instance.due_amt or 0))
            # "Due at sale" = what due_amt would have been right after the original sale
            # (before any subsequent payment receipts were recorded against this bill)
            _old_due_at_sale = _old_total_bill - _old_cash - _old_bank_total - _old_advance - _old_old_gold
            # Amount received via payment receipts AFTER the original sale
            _subsequent_payments = max(Decimal('0'), _old_due_at_sale - _old_due_amt)

            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # Re-create RCPT allocations after save (uses instance.billno which won't change)
            if self._pending_advance_rcpts is not None:
                from accounting.models import ReferenceBills as _RefBills
                remaining = self._pending_advance_total or Decimal('0')
                for rcpt in self._pending_advance_rcpts:
                    if remaining <= 0:
                        break
                    from django.db.models import Sum as _SumA
                    already = _RefBills.objects.filter(voucher=rcpt).aggregate(
                        s=_SumA('amount')
                    )['s'] or Decimal('0')
                    avail = Decimal(str(rcpt.amount)) - already
                    if avail <= 0:
                        continue
                    alloc = min(remaining, avail)
                    _RefBills.objects.create(
                        ldgr=instance.ldgr,
                        voucher=rcpt,
                        amount=alloc,
                        vendor_bill_no="",
                        ref_bill=None,
                        ref_bill_txt=instance.billno,
                    )
                    remaining -= alloc

            create_or_update_nested(SalesVouItemSerializer, instance, 'salesvouitem_set', 'billno', SalesVouItemSerializer(detail_data, many=True).data)

            # â”€â”€ Mark the final set of barcodes as sold â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # Kept/added barcodes end up sold; removed barcodes were released
            # above and stay in stock because they're no longer in the set.
            for _it in instance.salesvouitem_set.select_related('barcode').all():
                if _it.barcode_id and _it.barcode and _it.barcode.stk_status:
                    _it.barcode.stk_status = False
                    _it.barcode.save(update_fields=['stk_status'])

            # Rebuild direct manual details (those not linked to a barcode item).
            # These were previously dropped on update â€” now they are properly saved.
            instance.salesvouitemdetails_set.filter(main_item=None).delete()
            for raw in item_details_data:
                raw = {k: v for k, v in raw.items()
                       if k not in {"id", "billno", "main_item", "retail"}}
                SalesVouItemDetails.objects.create(billno=instance, main_item=None, **raw)

            sales_vou_instance = instance
            sales_vou_instance.ac_voucher.delete()
            # Clear the dangling Python reference — after .delete() the FK
            # attribute still points at the (now-deleted) VoucherMain instance
            # whose pk is None, which trips Django's
            # _prepare_related_fields_for_save check on the next instance.save().
            sales_vou_instance.ac_voucher = None
            # The update path rebuilds a SINGLE combined journal that includes
            # both the sale lines and the cash/bank receipt lines. The original
            # ac_rec_voucher created at insert time must therefore be deleted,
            # otherwise its bank-debit lines double-count against the new
            # combined journal in the Bank Book.
            if sales_vou_instance.ac_rec_voucher_id:
                sales_vou_instance.ac_rec_voucher.delete()
                sales_vou_instance.ac_rec_voucher = None
            create_or_update_nested(BankDetails, sales_vou_instance, 'bank_details', 'sales_vou', BankDetails(bank_details, many=True).data)

            # ── Inline old-gold purchase: rebuild sale-owned PV and refresh
            # SaleOldGoldAdjustment row(s); update instance.old_gold_adjusted to
            # the sum of all multi-voucher adjustments tied to this sale.
            _inline_pv, _inline_total = self._upsert_sales_inline_pv(
                sales_vou_instance, inline_old_gold_items, self.context.get('request')
            )
            from sales.models import SaleOldGoldAdjustment as _SOGA
            from django.db.models import Sum as _SumAgg
            if _inline_pv:
                _SOGA.objects.update_or_create(
                    sale=sales_vou_instance, purchase=_inline_pv,
                    defaults={'amount': _inline_total},
                )
            # Recompute the aggregated old gold for downstream due_amt + RCPT logic.
            if _SOGA.objects.filter(sale=sales_vou_instance).exists():
                _sog_total = _SOGA.objects.filter(sale=sales_vou_instance).aggregate(
                    s=_SumAgg('amount'))['s'] or Decimal('0')
                sales_vou_instance.old_gold_adjusted = _sog_total
                sales_vou_instance.save(update_fields=['old_gold_adjusted'])
            # Refresh due_amt on every PV touched by this sale.
            for _pv in {sog.purchase for sog in _SOGA.objects.filter(sale=sales_vou_instance).select_related('purchase')}:
                _adj = (
                    (_pv.linked_sales_vouchers.aggregate(s=_SumAgg('old_gold_adjusted'))['s'] or Decimal('0')) +
                    (_pv.sale_adjustments.aggregate(s=_SumAgg('amount'))['s'] or Decimal('0'))
                )
                _pv.due_amt = max(Decimal('0'), Decimal(str(_pv.bill_value or 0)) - _adj)
                _pv.save(update_fields=['due_amt'])

            # â”€â”€ Fresh DB queries â€” the prefetch_related cache on `instance` is STALE
            #    after create_or_update_nested; using it would put old values in the journal.
            from sales.models import SalesVouItem as _SVItem, SalesVouItemDetails as _SVDetail
            item_instances = list(_SVItem.objects.filter(billno=instance).select_related('item', 'barcode__purity'))
            # Catch BOTH classes of detail rows:
            #   1. Orphan details posted via `salesvouitemdetails_set` (billno=instance, main_item=NULL)
            #   2. Nested details saved per-item via `main_item_set` (billno=NULL, main_item.billno=instance)
            # Filtering only on `billno=instance` silently dropped the nested ones,
            # collapsing `_actual_mrp` to just the making-value sum and breaking
            # the journal balance.
            from django.db.models import Q as _Q
            item_detail_instances = list(
                _SVDetail.objects.filter(
                    _Q(billno=instance) | _Q(main_item__billno=instance)
                ).select_related('item').distinct()
            )

            # â”€â”€ Recompute mrp from actual saved items â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # Journal balance requires:
            #   DEBIT  total_bill_value (= (mrp - discount) Ã— (1 + tax_rate))
            #   CREDIT Î£ making_value  +  Î£ item_detail.amount
            # So mrp must equal Î£ making_value + Î£ item_detail.amount.
            # If the frontend sent a stale mrp (e.g. after editing an item's rate),
            # the journal would be unbalanced.  Recompute it from the DB â€” same fix
            # as the purchase voucher's bill_value recomputation.
            _actual_mrp = (
                sum(Decimal(str(item.making_value or 0)) for item in item_instances)
                + sum(Decimal(str(d.amount or 0)) for d in item_detail_instances)
            )
            instance.mrp = _actual_mrp
            instance.save(update_fields=['mrp'])

            request = self.context.get("request")
            _gm = request.retail.gstin_master
            _co = request.retail.branch.company if request.retail.branch_id and request.retail.branch else None
            out_cgst = _gm.output_cgst.id if _gm and _gm.output_cgst else _raise_missing_ledger("OUTPUT CGST")
            out_sgst = _gm.output_sgst.id if _gm and _gm.output_sgst else _raise_missing_ledger("OUTPUT SGST")
            out_igst = _gm.output_igst.id if _gm and _gm.output_igst else _raise_missing_ledger("OUTPUT IGST")
            _making_recv_ldgr = _co.making_receive_ldgr.id if _co and _co.making_receive_ldgr else _raise_missing_ledger("Making Charge Receive")
            _discount_ldgr = _co.discount_ldgr.id if _co and _co.discount_ldgr else _raise_missing_ledger("Sale Discount")
            _cash_ldgr = request.retail.cash_ldgr.id if request.retail.cash_ldgr else _raise_missing_ledger("CASH")
            _round_off_ldgr = _co.round_off_ldgr.id if _co and _co.round_off_ldgr else _raise_missing_ledger("Round Off")

            def _making_recv_ldgr_for_item(item):
                """Return purity-specific making charge received ledger for a barcode item."""
                try:
                    purity_str = (item.barcode.purity.purity or '').upper() if item.barcode_id and item.barcode and item.barcode.purity else ''
                except Exception:
                    purity_str = ''
                if '14' in purity_str and _co and _co.making_receive_14k_ldgr:
                    return _co.making_receive_14k_ldgr.id
                if '18' in purity_str and _co and _co.making_receive_18k_ldgr:
                    return _co.making_receive_18k_ldgr.id
                if '22' in purity_str and _co and _co.making_receive_22k_ldgr:
                    return _co.making_receive_22k_ldgr.id
                return _making_recv_ldgr  # fallback to generic

            # Only build TCS journal line when TCS actually applies
            _tcs_amt = float(sales_vou_instance.tcs_amt or 0)
            _tcs_lines = []
            if _tcs_amt > 0:
                _tcs_ldgr_name = (
                    sales_vou_instance.tcs_section.ledger.id
                    if sales_vou_instance.tcs_section and sales_vou_instance.tcs_section.ledger
                    else _raise_missing_ledger("TCS Payable (configure TCS Section master)")
                )
                _tcs_lines = [{'account': _tcs_ldgr_name, 'debit': 0, 'credit': f"{_tcs_amt:.2f}"}]

            # Compute party debit using Decimal-rounded components so it matches
            # credit-side rounding exactly (avoids 0.01 mismatch with float arithmetic).
            _cgst_d  = Decimal(f"{sales_vou_instance.cgst_amt:.2f}")
            _sgst_d  = Decimal(f"{sales_vou_instance.sgst_amt:.2f}")
            _igst_d  = Decimal(f"{sales_vou_instance.igst_amt:.2f}")
            _taxable_d = Decimal(str(sales_vou_instance.mrp or 0)) - Decimal(str(sales_vou_instance.discount or 0))
            _round_off_d = Decimal(str(sales_vou_instance.round_off or 0))
            _tcs_d   = Decimal(f"{_tcs_amt:.2f}")
            _party_debit = _taxable_d + _cgst_d + _sgst_d + _igst_d + _tcs_d + _round_off_d

            # ── Reject over-receipt ──────────────────────────────────────────
            # Customer cannot pay more than the bill receivable.
            _rcv_cash      = Decimal(str(sales_vou_instance.cash or 0))
            _rcv_bank      = sum(Decimal(str(b.get('amount', 0) or 0)) for b in bank_details)
            _rcv_old_gold  = Decimal(str(sales_vou_instance.old_gold_adjusted or 0))
            _rcv_advance   = Decimal(str(sales_vou_instance.advance_deducted or 0))
            _received_total = _rcv_cash + _rcv_bank + _rcv_old_gold + _rcv_advance
            if _received_total > _party_debit:
                raise serializers.ValidationError({
                    'bank_details': (
                        f"Receipts (₹{_received_total:.2f}) exceed bill total "
                        f"(₹{_party_debit:.2f}) by ₹{(_received_total - _party_debit):.2f}. "
                        f"Breakdown — Cash: ₹{_rcv_cash:.2f}, "
                        f"Bank: ₹{_rcv_bank:.2f}, "
                        f"Old Gold: ₹{_rcv_old_gold:.2f}, "
                        f"Advance: ₹{_rcv_advance:.2f}."
                    )
                })

            ser = JournalEntrySerializer(data= {'date':sales_vou_instance.date1.strftime('%Y-%m-%d'),
                                    "voucher_no":sales_vou_instance.billno,
                                    'retail':request.retail.id,
                                    "narration":f"Sale Voucher Narration",
                                    "voucher_type":global_vars.VoucherType.sale,

                                    "voucher_details": [
                                        {
                                            'account': out_cgst,

                                            'credit':f"{sales_vou_instance.cgst_amt:.2f}"
                                        },
                                        {'account': out_sgst,
                                            'debit':0,
                                            'credit':f"{sales_vou_instance.sgst_amt:.2f}"
                                        },
                                        {'account': out_igst,
                                            'debit':0,
                                            'credit':f"{sales_vou_instance.igst_amt:.2f}"
                                        },
                                    ] +
                                    _tcs_lines +
                                    [{'account': _making_recv_ldgr_for_item(item),
                                        'debit':0,
                                        'credit':f"{item.making_value:.2f}"
                                    } for item in item_instances] +
                                    [{'account':(item.item.sale_ledger_id if item.item.sale_ledger else _raise_missing_ledger(f"Sale Ledger for item '{item.item}'")),
                                        'debit':0,
                                        'credit':f"{item.amount:.2f}"
                                    } for item in item_detail_instances] +

                                    [{
                                        'account':_discount_ldgr,
                                        'debit':f"{sales_vou_instance.discount:.2f}",
                                        'credit':0
                                    }] +
                                    ([{
                                        'account': _round_off_ldgr,
                                        'debit':  f"{abs(sales_vou_instance.round_off):.2f}" if sales_vou_instance.round_off and sales_vou_instance.round_off < 0 else 0,
                                        'credit': f"{abs(sales_vou_instance.round_off):.2f}" if sales_vou_instance.round_off and sales_vou_instance.round_off > 0 else 0,
                                    }] if sales_vou_instance.round_off else []) +
                                    [{
                                        'account':_cash_ldgr,
                                        'debit':f"{sales_vou_instance.cash:.2f}",
                                        'credit':0
                                    }] +
                                    [{
                                        'account': (
                                            get_cheques_in_hand_ledger(_co).id if bank.get("payment_mode") == "CHEQUE"
                                            else (getattr(bank.get("ledger"), 'id', None) or bank.get("ledger") or _raise_missing_ledger("Bank Ledger"))
                                        ),
                                        'debit':f"{bank['amount']:.2f}",
                                        'credit':0,
                                        'party_bank_name':bank["bank_name"],
                                        "chq_no":bank.get("chq_no"),
                                        "chq_date":bank.get("chq_date"),
                                    } for bank in bank_details] +
                                    [{
                                        'account':sales_vou_instance.ldgr_id,
                                        'debit':f"{(_party_debit - Decimal(str(sales_vou_instance.cash or 0)) - sum(Decimal(str(bank['amount'])) for bank in bank_details)):.2f}",
                                        'credit':0
                                    }]},
                                    context=self.context)
            if ser.is_valid(raise_exception=True):

                ref = ser.save()
            # â”€â”€ Recalculate due_amt preserving subsequent payment receipts â”€â”€â”€â”€â”€â”€
            _new_cash      = Decimal(str(sales_vou_instance.cash or 0))
            _new_bank_total= sum(Decimal(str(b['amount'] or 0)) for b in bank_details)
            _new_advance   = Decimal(str(sales_vou_instance.advance_deducted or 0))
            _new_old_gold  = Decimal(str(sales_vou_instance.old_gold_adjusted or 0))
            _new_total_bill= Decimal(str(sales_vou_instance.total_bill_value))
            sales_vou_instance.due_amt = max(
                Decimal('0'),
                _new_total_bill - _new_cash - _new_bank_total - _new_advance - _new_old_gold - _subsequent_payments,
            )

            sales_vou_instance.ac_voucher = ref
            sales_vou_instance.gstin_ref  = request.retail.gstin_master
            sales_vou_instance.branch_ref = request.retail.branch
            sales_vou_instance.save()

            return sales_vou_instance


class SaleReturnDetailsSerializer(serializers.ModelSerializer):
    metal_purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", allow_null=True, required=False)
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(),slug_field="pckt_no",allow_null=True, required=False)
    item = serializers.SlugRelatedField(queryset=Item.objects.all(),slug_field="short_code",allow_null=True)
    class Meta:
        model = SaleReturnDetails
        fields = [
            'id',
            'metal_purity',
            'pcs',
            'ct',
            'item',
            'gw',
            'tunch',
            'rate',
            'amount',
            'packet',
            'fine_wt',  # Computed property
        ]
        extra_kwargs = {
            'id':    {'read_only': False, 'required': False},
            'tunch': {'required': False, 'allow_null': True},
        }


class SaleReturnItemSerializer(serializers.ModelSerializer):
    sale_billno = serializers.PrimaryKeyRelatedField(queryset=SalesVou.objects.all(), allow_null=True, required=False)
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", allow_null=True, required=False)
    barcode = serializers.SlugRelatedField(queryset=BarcodeMain.objects.all(), slug_field="barcode", allow_null=True, required=False)

    salereturndetails_set = SaleReturnDetailsSerializer(many=True)

    class Meta:
        model = SaleReturnItem
        fields = [
            'id',
            'sale_billno',
            'barcode',
            'item',
            'pcs',
            'gw',
            'purity',
            'making',
            'making_type',
            'making_value',
            'remarks',
            'salereturndetails_set',  # Nested details serializer
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }
    def create(self, validated_data):
        with transaction.atomic():

            details_data = validated_data.pop('salereturndetails_set')
            sale_return_item_instance = SaleReturnItem.objects.create(**validated_data)

            for detail_data in details_data:
                SaleReturnDetails.objects.create(main_item=sale_return_item_instance, **detail_data)

            return sale_return_item_instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('salereturndetails_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(SaleReturnDetailsSerializer, instance, 'salereturndetails_set', 'main_item',SaleReturnDetailsSerializer(detail_data,many=True).data)
            return instance


def _refresh_order_status(customer_order):
    """Recompute CustomerOrder.status from all linked sale vouchers and their returns.

    Status ladder (net = total_billed âˆ’ total_returned):
        ''              â†’ nothing billed yet
        'Partial'       â†’ partially billed, no returns
        'Billed'        â†’ net >= ordered (fully delivered, returns if any cancel out)
        'Partial Return'â†’ returns exist and net > 0 but < ordered
        'Returned'      â†’ net <= 0 (all deliveries reversed)
    """
    from decimal import Decimal
    svous = list(customer_order.linked_vouchers.prefetch_related('sale_returns').all())
    if not svous:
        return

    total_billed   = sum(sv.total_bill_value or Decimal(0) for sv in svous)
    total_returned = sum(
        sr.total_bill_value or Decimal(0)
        for sv in svous
        for sr in sv.sale_returns.all()
    )
    net_delivered = total_billed - total_returned
    ordered_value = customer_order.advance_amt or Decimal(0)

    if total_billed == 0:
        customer_order.status = ''
    elif net_delivered <= 0:
        customer_order.status = 'Returned'
        customer_order.delivery_status = 'returned'
        customer_order.save(update_fields=['status', 'delivery_status'])
        return
    elif total_returned > 0 and net_delivered < ordered_value:
        customer_order.status = 'Partial Return'
        customer_order.delivery_status = 'partial_return'
    elif total_returned > 0 and net_delivered >= ordered_value:
        customer_order.status = 'Billed'
    elif net_delivered < ordered_value:
        customer_order.status = 'Partial'
    else:
        customer_order.status = 'Billed'

    customer_order.save(update_fields=['status', 'delivery_status'])


class SaleReturnSerializer(serializers.ModelSerializer):
    ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())

    salereturnitem_set = SaleReturnItemSerializer(many=True)

    class Meta:
        model = SaleReturn
        fields = [
            'id',
            'date1',
            'billno',
            'sales_voucher_ref',
            'original_sale_gst_billno',
            "igst_per",
           "cgst_per",
           "sgst_per",
           "tcs_per",
            'ldgr',
            'ldgr_name',
            'mrp',
            'taxable_value',
            'discount',
            'cgst_amt',
            'sgst_amt',
            'igst_amt',
            'tcs_amt',
            'total_bill_value',

            'salereturnitem_set',  # Nested items serializer

        ]
        extra_kwargs = {
            'id':                       {'read_only': False, 'required': False},
            'sales_voucher_ref':        {'required': False, 'allow_null': True},
            'original_sale_gst_billno': {'required': False, 'allow_blank': True},
        }

    def create(self, validated_data):
        from sales.utils import generate_next_sale_return_no
        with transaction.atomic():
            items_data = validated_data.pop('salereturnitem_set')
            request = self.context.get("request")
            validated_data['billno'] = generate_next_sale_return_no(request.retail)
            if 'fiscal_year' not in validated_data:
                _retail = validated_data.get('retail') or getattr(request, 'retail', None)
                if _retail:
                    from mastersconfig.fy_validation import assert_date_in_active_fy
                    assert_date_in_active_fy(_retail, validated_data.get("date1"))
                    validated_data['fiscal_year'] = getattr(_retail, 'active_fy', None)
            sale_return_instance = SaleReturn.objects.create(**validated_data)

            item_instances = []
            item_detail_instances = []
            items_with_details = []  # list of (main_item, [detail_instances]) for journal building
            for item in items_data:
                details_data = item.pop('salereturndetails_set')
                id = item.pop('id')
                sale_return_item_instance = SaleReturnItem.objects.create(billno=sale_return_instance, **item)
                item_instances.append(sale_return_item_instance)
                # Only update barcode stock status for barcode-linked items
                if sale_return_item_instance.barcode:
                    sale_return_item_instance.barcode.stk_status = True
                    sale_return_item_instance.barcode.customer_order = None
                    sale_return_item_instance.barcode.save()

                detail_instances = []
                for detail in details_data:
                    det = SaleReturnDetails.objects.create(main_item=sale_return_item_instance, **detail)
                    detail_instances.append(det)
                    item_detail_instances.append(det)
                items_with_details.append((sale_return_item_instance, detail_instances))

            _gm = request.retail.gstin_master
            _co = request.retail.branch.company if request.retail.branch_id and request.retail.branch else None
            out_cgst = _gm.output_cgst.id if _gm and _gm.output_cgst else _raise_missing_ledger("OUTPUT CGST")
            out_sgst = _gm.output_sgst.id if _gm and _gm.output_sgst else _raise_missing_ledger("OUTPUT SGST")
            out_igst = _gm.output_igst.id if _gm and _gm.output_igst else _raise_missing_ledger("OUTPUT IGST")
            _making_recv_ldgr = _co.making_receive_ldgr.id if _co and _co.making_receive_ldgr else _raise_missing_ledger("Making Charge Receive")
            _discount_ldgr = _co.discount_ldgr.id if _co and _co.discount_ldgr else _raise_missing_ledger("Sale Discount")
            _tcs_section = TCSSectionMaster.objects.filter(is_active=True, ledger__isnull=False).select_related('ledger').first()
            _tcs_ldgr = _tcs_section.ledger.id if _tcs_section and _tcs_section.ledger else _raise_missing_ledger("TCS")

            def _making_recv_ldgr_for_item(item):
                try:
                    purity_str = (item.barcode.purity.purity or '').upper() if item.barcode_id and item.barcode and item.barcode.purity else ''
                except Exception:
                    purity_str = ''
                if '14' in purity_str and _co and _co.making_receive_14k_ldgr:
                    return _co.making_receive_14k_ldgr.id
                if '18' in purity_str and _co and _co.making_receive_18k_ldgr:
                    return _co.making_receive_18k_ldgr.id
                if '22' in purity_str and _co and _co.making_receive_22k_ldgr:
                    return _co.making_receive_22k_ldgr.id
                return _making_recv_ldgr

            _sr_making_lines = [
                {'account': _making_recv_ldgr_for_item(_main), 'debit': f"{Decimal(str(_main.making_value or 0)):.2f}"}
                for _main, _ in items_with_details
                if Decimal(str(_main.making_value or 0)) > 0
            ]
            _sr_item_lines = []
            for _main, _sub_details in items_with_details:
                for _d in _sub_details:
                    _sr_item_lines.append({
                        'account': (_d.item.sale_ledger_id if _d.item.sale_ledger else _raise_missing_ledger(f"Sale Ledger for item '{_d.item}'")),
                        'debit': f"{Decimal(str(_d.amount or 0)):.2f}",
                    })

            # Build party credit using Decimal-rounded components so it matches
            # the individually-rounded debit lines exactly (avoids 0.01 mismatch).
            _sr_cgst_d     = Decimal(f"{sale_return_instance.cgst_amt:.2f}")
            _sr_sgst_d     = Decimal(f"{sale_return_instance.sgst_amt:.2f}")
            _sr_igst_d     = Decimal(f"{sale_return_instance.igst_amt:.2f}")
            _sr_tcs_d      = Decimal(f"{sale_return_instance.tcs_amt:.2f}")
            _sr_making_total = sum(Decimal(line['debit']) for line in _sr_making_lines)
            _sr_item_total = sum(Decimal(line['debit']) for line in _sr_item_lines)
            _sr_discount_d = Decimal(f"{sale_return_instance.discount:.2f}")
            _sr_party_credit = _sr_cgst_d + _sr_sgst_d + _sr_igst_d + _sr_tcs_d + _sr_making_total + _sr_item_total - _sr_discount_d

            ser = JournalEntrySerializer(data= {'date':sale_return_instance.date1.strftime('%Y-%m-%d'),
                        "voucher_no":sale_return_instance.billno,
                        "narration":f"Sale Return Narration",
                        "voucher_type":global_vars.VoucherType.sale_ret,
                        "retail":request.retail.id,
                        "voucher_details": [
                            {'account': out_cgst, 'debit':f"{_sr_cgst_d:.2f}"},
                            {'account': out_sgst, 'debit':f"{_sr_sgst_d:.2f}"},
                            {'account': out_igst, 'debit':f"{_sr_igst_d:.2f}"},
                            {'account':_tcs_ldgr,  'debit':f"{_sr_tcs_d:.2f}"},
                        ] +
                        _sr_making_lines +
                        _sr_item_lines +
                        [{
                            'account':_discount_ldgr,
                            'credit':f"{_sr_discount_d:.2f}",
                        }] +
                        [{
                            'account':sale_return_instance.ldgr_id,
                            'credit':f"{_sr_party_credit:.2f}",
                        }]},
                        context=self.context)
            if ser.is_valid(raise_exception=True):

                ref = ser.save()
            sale_return_instance.ac_voucher= ref
            sale_return_instance.gstin_ref  = request.retail.gstin_master
            sale_return_instance.branch_ref = request.retail.branch
            sale_return_instance.save()
            request = self.context.get("request")
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')) if request else None

            for item_br in item_instances:
                BarcodeTransaction.objects.create(
                    barcode=item_br.barcode,
                    billno=sale_return_instance.billno,
                    trans_type="SALE-RET",
                    user=request.user,
                    ip_address=ip,
                    retail=request.retail
                )

            # Reverse any salesperson commission earned on the original sale bills
            try:
                from mastersconfig.commission_views import reverse_commissions_for_return
                reverse_commissions_for_return(sale_return_instance, item_instances)
            except (ImportError, AttributeError, TypeError) as e:
                # Non-critical: log but never block the return save
                logger.warning(
                    "Commission reversal skipped for return %s: %s",
                    sale_return_instance.billno, e,
                )

            # â”€â”€ Update linked Customer Order status â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            _sv = sale_return_instance.sales_voucher_ref
            _co = getattr(_sv, 'customer_order', None) if _sv else None
            if _co:
                _refresh_order_status(_co)

            if sale_return_instance.sales_voucher_ref_id:
                sv = sale_return_instance.sales_voucher_ref
                return_total = Decimal(str(sale_return_instance.total_bill_value))
                sv.due_amt = max(Decimal('0'), sv.due_amt - return_total)
                sv.save(update_fields=['due_amt'])

            return sale_return_instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('salereturnitem_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(SaleReturnItemSerializer, instance, 'salereturnitem_set', 'billno',SaleReturnItemSerializer(detail_data,many=True).data)
            sale_return_instance = instance
            instance.ac_voucher.delete()
            # Fresh DB queries â€” avoid stale prefetch cache left by create_or_update_nested
            from sales.models import SaleReturnItem as _SRItem, SaleReturnDetails as _SRDetails
            item_instances = list(_SRItem.objects.filter(billno=instance).select_related('item__sale_ledger', 'purity'))
            item_detail_instances = list(_SRDetails.objects.filter(main_item__billno=instance).select_related('item__sale_ledger', 'main_item'))
            # Recompute mrp from actual saved items so the journal entry balances
            _actual_mrp = (
                sum(Decimal(str(it.making_value or 0)) for it in item_instances)
                + sum(Decimal(str(d.amount or 0)) for d in item_detail_instances)
            )
            sale_return_instance.mrp = _actual_mrp
            sale_return_instance.save(update_fields=['mrp'])

            request = self.context.get('request')
            _gm = request.retail.gstin_master
            _co = request.retail.branch.company if request.retail.branch_id and request.retail.branch else None
            out_cgst = _gm.output_cgst.id if _gm and _gm.output_cgst else _raise_missing_ledger("OUTPUT CGST")
            out_sgst = _gm.output_sgst.id if _gm and _gm.output_sgst else _raise_missing_ledger("OUTPUT SGST")
            out_igst = _gm.output_igst.id if _gm and _gm.output_igst else _raise_missing_ledger("OUTPUT IGST")
            _making_recv_ldgr = _co.making_receive_ldgr.id if _co and _co.making_receive_ldgr else _raise_missing_ledger("Making Charge Receive")
            _discount_ldgr = _co.discount_ldgr.id if _co and _co.discount_ldgr else _raise_missing_ledger("Sale Discount")
            _cash_ldgr = request.retail.cash_ldgr.id if request.retail.cash_ldgr else _raise_missing_ledger("CASH")
            _tcs_section = TCSSectionMaster.objects.filter(is_active=True, ledger__isnull=False).select_related('ledger').first()
            _tcs_ldgr = _tcs_section.ledger.id if _tcs_section and _tcs_section.ledger else _raise_missing_ledger("TCS")

            def _making_recv_ldgr_for_item(item):
                try:
                    purity_str = (item.barcode.purity.purity or '').upper() if item.barcode_id and item.barcode and item.barcode.purity else ''
                except Exception:
                    purity_str = ''
                if '14' in purity_str and _co and _co.making_receive_14k_ldgr:
                    return _co.making_receive_14k_ldgr.id
                if '18' in purity_str and _co and _co.making_receive_18k_ldgr:
                    return _co.making_receive_18k_ldgr.id
                if '22' in purity_str and _co and _co.making_receive_22k_ldgr:
                    return _co.making_receive_22k_ldgr.id
                return _making_recv_ldgr

            from collections import defaultdict as _defaultdict
            _sr_details_by_main = _defaultdict(list)
            for _d in item_detail_instances:
                _sr_details_by_main[_d.main_item_id].append(_d)
            _sr_making_lines = [
                {'account': _making_recv_ldgr_for_item(_main), 'debit': f"{Decimal(str(_main.making_value or 0)):.2f}"}
                for _main in item_instances
                if Decimal(str(_main.making_value or 0)) > 0
            ]
            _sr_item_lines = []
            for _main in item_instances:
                for _d in _sr_details_by_main.get(_main.id, []):
                    _sr_item_lines.append({'account': (_d.item.sale_ledger_id if _d.item.sale_ledger else _raise_missing_ledger(f"Sale Ledger for item '{_d.item}'")), 'debit': f"{Decimal(str(_d.amount or 0)):.2f}"})

            # Build party credit using Decimal-rounded components so it matches
            # the individually-rounded debit lines exactly (avoids 0.01 mismatch).
            _sr_cgst_d     = Decimal(f"{sale_return_instance.cgst_amt:.2f}")
            _sr_sgst_d     = Decimal(f"{sale_return_instance.sgst_amt:.2f}")
            _sr_igst_d     = Decimal(f"{sale_return_instance.igst_amt:.2f}")
            _sr_tcs_d      = Decimal(f"{sale_return_instance.tcs_amt:.2f}")
            _sr_making_total = sum(Decimal(line['debit']) for line in _sr_making_lines)
            _sr_item_total = sum(Decimal(line['debit']) for line in _sr_item_lines)
            _sr_discount_d = Decimal(f"{sale_return_instance.discount:.2f}")
            _sr_party_credit = _sr_cgst_d + _sr_sgst_d + _sr_igst_d + _sr_tcs_d + _sr_making_total + _sr_item_total - _sr_discount_d

            ser = JournalEntrySerializer(data= {'date':sale_return_instance.date1.strftime('%Y-%m-%d'),
                        "voucher_no":sale_return_instance.billno,
                        "narration":f"Sale Return Narration",
                        "voucher_type":global_vars.VoucherType.sale_ret,
                        "retail":request.retail.id,
                        "voucher_details": [
                            {'account': out_cgst, 'debit':f"{_sr_cgst_d:.2f}"},
                            {'account': out_sgst, 'debit':f"{_sr_sgst_d:.2f}"},
                            {'account': out_igst, 'debit':f"{_sr_igst_d:.2f}"},
                            {'account':_tcs_ldgr, 'debit':f"{_sr_tcs_d:.2f}"},
                        ] +
                        _sr_making_lines +
                        _sr_item_lines +
                        [{
                            'account':_discount_ldgr,
                            'credit':f"{_sr_discount_d:.2f}",
                        }] +
                        [{
                            'account':sale_return_instance.ldgr_id,
                            'credit':f"{_sr_party_credit:.2f}",
                        }]},
                        context=self.context)
            if ser.is_valid(raise_exception=True):

                ref = ser.save()
            instance.ac_voucher = ref
            instance.gstin_ref  = request.retail.gstin_master
            instance.branch_ref = request.retail.branch
            instance.save()

            # â”€â”€ Update linked Customer Order status â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            _sv = instance.sales_voucher_ref
            _co = getattr(_sv, 'customer_order', None) if _sv else None
            if _co:
                _refresh_order_status(_co)

            return sale_return_instance


class SaleVoucherDetailsToReturnDetailsSerializer(SalesVouItemDetailsSerializer):
    def to_representation(self, instance):
        repr = super().to_representation(instance)
        return repr

class SaleVoucherItemToReturnItemSerializer(SalesVouItemSerializer):
    main_item_set = SaleVoucherDetailsToReturnDetailsSerializer(many=True)
    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr["salereturndetails_set"] = repr['main_item_set']
        del repr['main_item_set']
        repr['sale_billno'] = self.context.get('sale_billno')
        return repr

class SaleVoucherToReturnSerializer(SalesVouSerializer):
    salesvouitem_set = SaleVoucherItemToReturnItemSerializer(many=True)
    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        instance = self.instance

        if instance:
            sale_id = instance.id
            self.fields['salesvouitem_set'].context.update({**self.context, 'sale_billno': sale_id})

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        data = {
           "id":             instance.id,          # needed for sales_voucher_ref FK
           "salereturnitem_set": repr["salesvouitem_set"],
           "sgst_amt":repr["sgst_amt"],
           "cgst_amt":repr["cgst_amt"],
           "igst_amt":repr["igst_amt"],
           "igst_per":repr["igst_per"],
           "cgst_per":repr["cgst_per"],
           "sgst_per":repr["sgst_per"],
           "tcs_per":repr["tcs_per"],
           "mrp":repr["mrp"],
           "taxable_value":repr["taxable_value"],
           "discount":repr["discount"],
           "billno":repr["billno"],
           "gst_billno": repr.get("gst_billno", ""),  # for credit note printing
           "ldgr":repr["ldgr"],
           "ldgr_name":repr["ldgr_name"],
        }

        return data


class SalesApprovalItemDetailsSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(),slug_field="pckt_no",allow_null=True)
    ct = serializers.DecimalField(max_digits=10, decimal_places=3, required=False, allow_null=True, default=0)
    gw = serializers.DecimalField(max_digits=10, decimal_places=3, required=False, allow_null=True, default=0)

    class Meta:
        model = SalesApprovalItemDetails
        fields = [
            'id',
            'item',
            'item_name',
            'pcs',
            'ct',
            'gw',
            'metal_purity',
            'rate',
            'amount',
            'packet',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # If metal_purity was never stored (legacy records created before the
        # BarcodeDetToSaleVouDetSerializer fix), derive it from the BarcodeDetails
        # row that corresponds to this sub-item:
        #   SalesApprovalItemDetails → SalesApprovalItem → BarcodeMain → BarcodeDetails
        # Match on barcode + item so we get the purity for this specific component.
        if not rep.get('metal_purity') and instance.main_item_id and instance.item_id:
            try:
                from inventory.models import BarcodeDetails
                barcode_id = SalesApprovalItem.objects.values_list(
                    'barcode_id', flat=True
                ).get(pk=instance.main_item_id)
                if barcode_id:
                    bd = BarcodeDetails.objects.select_related('purity').filter(
                        barcode_id=barcode_id,
                        item_id=instance.item_id,
                    ).first()
                    if bd and bd.purity:
                        rep['metal_purity'] = bd.purity.purity
            except Exception:
                pass
        return rep

class SalesApprovalItemSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    barcode = serializers.SlugRelatedField(queryset=BarcodeMain.objects.all(), slug_field="barcode")
    # purity is IntegerField on model (stores PK of PurityMaster) but frontend
    # sends the slug string (e.g. "14K"). Accept any value and resolve in validate.
    purity = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    main_item_set = SalesApprovalItemDetailsSerializer(many=True)

    class Meta:
        model = SalesApprovalItem
        fields = [
            'id',
            'barcode',
            'item',
            'item_name',
            'pcs',
            'gw',
            'making',
            'making_type',
            'making_value',
            'purity',
            'amount',
            'ret_status',
            'main_item_set',  # Nested details
        ]

    def validate_purity(self, value):
        """Convert purity slug string (e.g. '14K') to PurityMaster PK (integer)."""
        if not value:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            pass
        try:
            return PurityMaster.objects.get(purity=value).pk
        except PurityMaster.DoesNotExist:
            return 0

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        try:
            purity_pk = int(rep.get('purity') or 0)
        except (ValueError, TypeError):
            purity_pk = 0
        if purity_pk > 0:
            try:
                rep['purity'] = PurityMaster.objects.get(pk=purity_pk).purity
            except PurityMaster.DoesNotExist:
                rep['purity'] = str(purity_pk)
        return rep

    def validate(self, attrs):
        barcode = attrs.get('barcode')
        request = self.context.get("request") if hasattr(self, 'context') else None
        if barcode is not None and self.instance is None and not attrs.get('ret_status'):
            # New item being added on approval: barcode must currently be in stock
            if request is not None and getattr(request, 'retail', None) is not None:
                if barcode.retail_id != request.retail.id:
                    raise serializers.ValidationError(
                        f"Barcode '{barcode.barcode}' does not belong to the current retail location."
                    )
            if not barcode.stk_status:
                raise serializers.ValidationError(
                    f"Barcode '{barcode.barcode}' is not in active stock "
                    "(it may already be sold, on another approval, or transferred)."
                )
        return attrs
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

    def validate_barcode(self, barcode):
        request = self.context.get('request')
        if request and getattr(request, 'retail', None):
            if barcode.retail_id != request.retail.pk:
                raise serializers.ValidationError(
                    f"Barcode '{barcode.barcode}' does not belong to the current retail location."
                )
            if not barcode.stk_status:
                raise serializers.ValidationError(
                    f"Barcode '{barcode.barcode}' is not in active stock "
                    "(it may already be sold, in transit, or transferred)."
                )
        if barcode.customer_order_id:
            bill_ldgr_id = self.context.get('sales_vou_ldgr_id')
            if bill_ldgr_id is None and request is not None and hasattr(request, 'data'):
                bill_ldgr_id = request.data.get('ldgr')
            try:
                bill_ldgr_id = int(bill_ldgr_id) if bill_ldgr_id is not None else None
            except (TypeError, ValueError):
                bill_ldgr_id = None
            reserved_ldgr_id = getattr(barcode.customer_order, 'ldgr_id', None)
            if bill_ldgr_id is not None and reserved_ldgr_id is not None and bill_ldgr_id != reserved_ldgr_id:
                reserved_party = getattr(getattr(barcode.customer_order, 'ldgr', None), 'ldgr_name', 'reserved customer')
                raise serializers.ValidationError(
                    f"Barcode '{barcode.barcode}' is reserved for customer order "
                    f"{barcode.customer_order.order_no} ({reserved_party}). "
                    "Release it from the order before selling to a different party."
                )
        return barcode

    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('main_item_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(SalesApprovalItemDetailsSerializer, instance, 'main_item_set', 'main_item',SalesApprovalItemDetailsSerializer(detail_data,many=True).data)
            return instance

class _StatePlaceOfSupplyField(serializers.Field):
    """Accept a state by:
       - State.code  (the GST numeric code, e.g. '19')
       - State.name  (case-insensitive, e.g. 'West Bengal')
       - 2-letter alias from STATES_OF_INDIA (e.g. 'WB' → 'West Bengal')
    Returns a State instance. Serializes back to State.code."""

    def to_internal_value(self, value):
        if value in (None, '', 'null', 'undefined'):
            return None
        value = str(value).strip()
        qs = State.objects.all()

        # 1. Exact-code match (e.g. "19")
        state = qs.filter(code__iexact=value).first()
        if state:
            return state

        # 2. Exact-name match (e.g. "West Bengal")
        state = qs.filter(name__iexact=value).first()
        if state:
            return state

        # 3. Alias lookup via the STATES_OF_INDIA constant (e.g. "WB").
        #    The constant lives in backend/global_vars.py as a list of
        #    (alias, full_name) tuples used by the frontend dropdown.
        try:
            from global_vars import STATES_OF_INDIA
            alias_to_name = {alias.upper(): name for alias, name in STATES_OF_INDIA}
            mapped_name = alias_to_name.get(value.upper())
            if mapped_name:
                state = qs.filter(name__iexact=mapped_name).first()
                if state:
                    return state
        except Exception:
            pass

        raise serializers.ValidationError(f"Unknown state '{value}'.")

    def to_representation(self, value):
        # `value` is a State instance (when source maps to the FK).
        # We return the 2-letter STATES_OF_INDIA alias (e.g. "WB") so it
        # matches the SelectItem values that the frontend dropdown uses.
        # The numeric State.code (e.g. "19") is only used internally in the
        # State model, not in the STATES_OF_INDIA constant.
        if value is None:
            return None
        state_name = getattr(value, 'name', None)
        if state_name:
            try:
                from global_vars import STATES_OF_INDIA
                for alias, name in STATES_OF_INDIA:
                    if name.lower() == state_name.lower():
                        return alias
            except Exception:
                pass
        # Fallback: return the numeric code if no alias match found
        return getattr(value, 'code', None)


class SalesApprovalSerializer(serializers.ModelSerializer):
    ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    sales_person = serializers.PrimaryKeyRelatedField(queryset=SalesPersonMaster.objects.all())
    sales_person2 = serializers.PrimaryKeyRelatedField(queryset=SalesPersonMaster.objects.all(), allow_null=True, required=False)
    place_of_supply = _StatePlaceOfSupplyField(required=False, allow_null=True)
    narration = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    items = SalesApprovalItemSerializer(many=True)
    total_bill_value = serializers.ReadOnlyField()
    total_incl_taxes = serializers.ReadOnlyField()

    class Meta:
        model = SalesApproval
        fields = [
            'id',
            'date1',
            'billno',
            'ldgr',
            'ldgr_name',
            'narration',
            'sales_person',
            'sales_person2',
            'place_of_supply',
            'taxable_value',
            'discount',
            'sgst_per',
            'cgst_per',
            'igst_per',
            'total_bill_value',
            'total_incl_taxes',
            'items',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }
    def to_internal_value(self, data):
        # Propagate selected customer (ldgr) into context BEFORE nested item
        # validators run â€” same reservation guard as SalesVouSerializer.
        if hasattr(data, 'get'):
            ldgr_val = data.get('ldgr')
            if ldgr_val not in (None, '', 'null'):
                try:
                    self.context['sales_vou_ldgr_id'] = int(ldgr_val)
                except (TypeError, ValueError):
                    pass
        return super().to_internal_value(data)

    def create(self, validated_data):
        from sales.utils import generate_next_sale_app_no
        with transaction.atomic():
            items_data = validated_data.pop('items')
            request = self.context.get("request")
            validated_data['billno'] = generate_next_sale_app_no(request.retail)
            if 'fiscal_year' not in validated_data:
                _retail = validated_data.get('retail') or getattr(request, 'retail', None)
                if _retail:
                    from mastersconfig.fy_validation import assert_date_in_active_fy
                    assert_date_in_active_fy(_retail, validated_data.get("date1"))
                    validated_data['fiscal_year'] = getattr(_retail, 'active_fy', None)
            sale_return_instance = SalesApproval.objects.create(**validated_data)

            item_instances = []
            item_detail_instances = []
            for item in items_data:
                details_data = item.pop('main_item_set')
                sale_return_item_instance = SalesApprovalItem.objects.create(billno=sale_return_instance, **item)
                item_instances.append(sale_return_item_instance)

                for detail in details_data:
                    det = SalesApprovalItemDetails.objects.create(
                        billno=sale_return_instance,
                        main_item=sale_return_item_instance,
                        **detail,
                    )
                    item_detail_instances.append(det)
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')) if request else None

            barcode_ids_out = []
            for item_br in item_instances:
                BarcodeTransaction.objects.create(
                    barcode=item_br.barcode,
                    billno=sale_return_instance.billno,
                    trans_type="SALE-APP",
                    user=request.user,
                    ip_address=ip,
                    retail=request.retail
                )
                if item_br.barcode_id and not item_br.ret_status:
                    barcode_ids_out.append(item_br.barcode_id)

            if barcode_ids_out:
                BarcodeMain.objects.filter(id__in=barcode_ids_out).update(stk_status=False)

            return sale_return_instance


    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('items', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            request = self.context.get("request")
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')) if request else None

            # Snapshot pre-update item state for ret_status flip detection.
            before = {it.id: it.ret_status for it in instance.items.all()}

            create_or_update_nested(SalesApprovalItemSerializer, instance, 'items', 'billno',SalesApprovalItemSerializer(detail_data,many=True).data)

            # Reconcile barcode stock against the canonical post-update item set.
            # Items removed by create_or_update_nested are restored via the
            # SalesApprovalItem pre_delete signal in sales/signals.py.
            after_items = list(instance.items.all().select_related('barcode'))
            out_of_stock_ids = [it.barcode_id for it in after_items if not it.ret_status and it.barcode_id]
            restored_ids    = [it.barcode_id for it in after_items if it.ret_status     and it.barcode_id]
            if out_of_stock_ids:
                BarcodeMain.objects.filter(id__in=out_of_stock_ids).update(stk_status=False)
            if restored_ids:
                BarcodeMain.objects.filter(id__in=restored_ids).update(stk_status=True)

            # Audit-log returns for items whose ret_status flipped False -> True this update.
            for it in after_items:
                if it.ret_status and not before.get(it.id, False) and it.barcode_id:
                    BarcodeTransaction.objects.create(
                        barcode=it.barcode,
                        billno=instance.billno,
                        trans_type="SALE-APP-RET",
                        user=request.user,
                        ip_address=ip,
                        retail=request.retail
                    )
            return instance


# ── Sales Approval Return serializers ─────────────────────────────────────────

class SalesApprovalReturnItemDetailsSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    packet = serializers.SlugRelatedField(
        queryset=Packet.objects.all(), slug_field="pckt_no", allow_null=True,
    )
    ct = serializers.DecimalField(
        max_digits=10, decimal_places=3, required=False, allow_null=True, default=0,
    )
    gw = serializers.DecimalField(
        max_digits=10, decimal_places=3, required=False, allow_null=True, default=0,
    )

    class Meta:
        model = SalesApprovalReturnItemDetails
        fields = ['id', 'item', 'pcs', 'ct', 'gw', 'metal_purity', 'rate', 'amount', 'packet']
        extra_kwargs = {'id': {'read_only': False, 'required': False}}
        validators = []


class SalesApprovalReturnItemSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    barcode = serializers.SlugRelatedField(
        queryset=BarcodeMain.objects.all(), slug_field="barcode",
        allow_null=True, required=False,
    )
    approval_item = serializers.PrimaryKeyRelatedField(
        queryset=SalesApprovalItem.objects.all(), allow_null=True, required=False,
    )
    purity = serializers.CharField(allow_blank=True, allow_null=True, required=False, default='')
    main_item_set = SalesApprovalReturnItemDetailsSerializer(many=True)

    def update(self, instance, validated_data):
        details_data = validated_data.pop('main_item_set', [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        create_or_update_nested(
            SalesApprovalReturnItemDetailsSerializer, instance,
            'main_item_set', 'main_item',
            details_data,
        )
        return instance

    class Meta:
        model = SalesApprovalReturnItem
        fields = [
            'id', 'barcode', 'approval_item', 'item', 'pcs', 'gw', 'purity', 'amount',
            'main_item_set',
        ]
        extra_kwargs = {'id': {'read_only': False, 'required': False}}
        validators = []


class SalesApprovalReturnSerializer(serializers.ModelSerializer):
    ref_approval = serializers.PrimaryKeyRelatedField(
        queryset=SalesApproval.objects.all(), allow_null=True, required=False,
    )
    ref_approval_billno = serializers.SerializerMethodField(read_only=True)
    items = SalesApprovalReturnItemSerializer(many=True)

    def get_ref_approval_billno(self, obj):
        return obj.ref_approval.billno if obj.ref_approval_id else None

    class Meta:
        model = SalesApprovalReturn
        fields = [
            'id', 'billno', 'date1', 'ref_approval', 'ref_approval_billno', 'narration',
            'retail', 'fiscal_year', 'items',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'billno': {'read_only': True},
        }

    def create(self, validated_data):
        from accounting.utils import get_next_bill_number
        with transaction.atomic():
            items_data = validated_data.pop('items')
            request = self.context.get('request')
            validated_data['billno'] = get_next_bill_number(
                request.retail, 'SAR', request.retail.active_fy,
            )
            from mastersconfig.fy_validation import assert_date_in_active_fy
            assert_date_in_active_fy(getattr(request, 'retail', None), validated_data.get("date1"))
            validated_data.setdefault('fiscal_year', getattr(getattr(request, 'retail', None), 'active_fy', None))
            sar = SalesApprovalReturn.objects.create(**validated_data)

            barcode_ids = []
            approval_item_ids = []
            for item in items_data:
                details_data = item.pop('main_item_set')
                sar_item = SalesApprovalReturnItem.objects.create(billno=sar, **item)
                for detail in details_data:
                    SalesApprovalReturnItemDetails.objects.create(
                        billno=sar, main_item=sar_item, **detail,
                    )
                if sar_item.barcode_id:
                    barcode_ids.append(sar_item.barcode_id)
                if sar_item.approval_item_id:
                    approval_item_ids.append(sar_item.approval_item_id)

            if barcode_ids:
                BarcodeMain.objects.filter(id__in=barcode_ids).update(stk_status=True)
            if approval_item_ids:
                SalesApprovalItem.objects.filter(id__in=approval_item_ids).update(ret_status=True)

            # Audit-log each returned barcode in the barcode-wise transaction table.
            if barcode_ids:
                ip = (
                    request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
                    if request else None
                )
                for barcode_id in barcode_ids:
                    try:
                        barcode_obj = BarcodeMain.objects.get(id=barcode_id)
                        BarcodeTransaction.objects.create(
                            barcode=barcode_obj,
                            billno=sar.billno,
                            trans_type="SALE-APP-RET",
                            user=request.user if request else None,
                            ip_address=ip,
                            retail=sar.retail,
                        )
                    except BarcodeMain.DoesNotExist:
                        pass

            return sar

    def update(self, instance, validated_data):
        with transaction.atomic():
            items_data = validated_data.pop('items', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(
                SalesApprovalReturnItemSerializer, instance, 'items', 'billno',
                SalesApprovalReturnItemSerializer(items_data, many=True).data,
            )
            # Reconcile stock and ret_status for all post-update items
            current_items = list(instance.items.all())
            barcode_ids = [it.barcode_id for it in current_items if it.barcode_id]
            approval_item_ids = [it.approval_item_id for it in current_items if it.approval_item_id]
            if barcode_ids:
                BarcodeMain.objects.filter(id__in=barcode_ids).update(stk_status=True)
            if approval_item_ids:
                SalesApprovalItem.objects.filter(id__in=approval_item_ids).update(ret_status=True)
            return instance


class EWayBillSerializer(serializers.ModelSerializer):
    source_billno = serializers.SerializerMethodField(read_only=True)
    source_type   = serializers.SerializerMethodField(read_only=True)
    party_name    = serializers.SerializerMethodField(read_only=True)

    class Meta:
        from .models import EWayBill
        model = EWayBill
        fields = [
            'id', 'sales_vou', 'sales_approval',
            'source_billno', 'source_type', 'party_name',
            'eway_bill_no', 'generated_date', 'valid_from', 'valid_until',
            'status', 'cancelled_date', 'cancel_reason',
            'vehicle_no', 'transporter_name', 'transporter_id',
            'trans_distance', 'mode_of_transport',
            'json_payload', 'retail', 'fiscal_year',
        ]
        read_only_fields = ['id', 'generated_date', 'json_payload', 'retail', 'fiscal_year']

    def get_source_billno(self, obj):
        # Prefer stored snapshot; fall back to FK lookup for pre-migration records
        if obj.source_billno:
            return obj.source_billno
        if obj.sales_vou_id:
            return obj.sales_vou.billno
        if obj.sales_approval_id:
            return obj.sales_approval.billno
        return None

    def get_source_type(self, obj):
        if obj.sales_vou_id:
            return 'Invoice'
        if obj.sales_approval_id:
            return 'Approval'
        return None

    def get_party_name(self, obj):
        # Prefer stored snapshot; fall back to FK lookup for pre-migration records
        if obj.party_name:
            return obj.party_name
        if obj.sales_vou_id and obj.sales_vou.ldgr_id:
            return obj.sales_vou.ldgr.ac_name
        if obj.sales_approval_id and obj.sales_approval.ldgr_id:
            return obj.sales_approval.ldgr.ac_name
        return None


# â”€â”€ Quotation Serializers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

from sales.models import Quotation, QuotationItem, QuotationItemDetail


class QuotationItemDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationItemDetail
        fields = [
            'id', 'packet', 'packet_name', 'item_name', 'is_diamond',
            'pcs', 'wt', 'rate', 'amount',
        ]
        extra_kwargs = {'id': {'read_only': False, 'required': False}}


class QuotationItemSerializer(serializers.ModelSerializer):
    details = QuotationItemDetailSerializer(many=True, required=False, default=[])

    class Meta:
        model = QuotationItem
        fields = [
            'id', 'sl_no', 'barcode', 'barcode_text', 'item', 'item_name',
            'design_code', 'purity_text', 'pcs', 'gw', 'nw',
            'gold_rate', 'gold_amount', 'fine_wt', 'making_rate', 'making_amount',
            'total_diamond_pcs', 'total_diamond_wt', 'total_diamond_amt',
            'total_stone_pcs', 'total_stone_wt', 'total_stone_amt',
            'total_amount', 'image_url', 'details',
        ]
        extra_kwargs = {'id': {'read_only': False, 'required': False}}


class QuotationSerializer(serializers.ModelSerializer):
    items = QuotationItemSerializer(many=True, required=False, default=[])
    ldgr_name = serializers.CharField(read_only=True)

    class Meta:
        model = Quotation
        fields = [
            'id', 'date1', 'quotation_no', 'ldgr', 'ldgr_name', 'party_name',
            'gold_rate_date', 'rate_18kt', 'rate_22kt', 'rate_24kt',
            'total_items', 'grand_total', 'tax_percent', 'tax_amount', 'net_total',
            'status', 'valid_until', 'remarks', 'seller_info',
            'sales_person', 'converted_to',
            'retail', 'fiscal_year', 'created_at', 'items',
        ]
        extra_kwargs = {
            'id':           {'read_only': False, 'required': False},
            'retail':       {'required': False},
            'fiscal_year':  {'required': False},
            'quotation_no': {'required': False},
        }

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        with transaction.atomic():
            request = self.context.get('request')
            _retail = validated_data.get('retail') or getattr(request, 'retail', None)
            from mastersconfig.fy_validation import assert_date_in_active_fy
            assert_date_in_active_fy(_retail, validated_data.get("date1"))
            validated_data.setdefault('fiscal_year', getattr(_retail, 'active_fy', None))
            validated_data.pop('quotation_no', None)
            quotation = Quotation(**validated_data)
            from accounting.utils import save_with_bill_number
            save_with_bill_number(quotation, _retail, 'QT', field='quotation_no', fy=validated_data.get('fiscal_year'))
            for item_data in items_data:
                details_data = item_data.pop('details', [])
                qi = QuotationItem.objects.create(quotation=quotation, **item_data)
                for detail_data in details_data:
                    QuotationItemDetail.objects.create(quotation_item=qi, **detail_data)
        return quotation

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            if items_data is not None:
                # Delete old items and re-create
                instance.items.all().delete()
                for item_data in items_data:
                    details_data = item_data.pop('details', [])
                    qi = QuotationItem.objects.create(quotation=instance, **item_data)
                    for detail_data in details_data:
                        QuotationItemDetail.objects.create(quotation_item=qi, **detail_data)
        return instance


class QuotationListSerializer(serializers.ModelSerializer):
    ldgr_name = serializers.CharField(read_only=True)

    class Meta:
        model = Quotation
        fields = [
            'id', 'date1', 'quotation_no', 'ldgr', 'ldgr_name', 'party_name',
            'total_items', 'grand_total', 'net_total',
            'status', 'valid_until', 'created_at',
        ]


class PortalCustomerOrderSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField(read_only=True)
    is_overdue = serializers.SerializerMethodField(read_only=True)
    days_overdue = serializers.SerializerMethodField(read_only=True)

    def get_item_count(self, obj):
        return obj.items.count()

    def get_is_overdue(self, obj):
        from datetime import date
        if not obj.delivery_date:
            return False
        if obj.delivery_status in ('delivered', 'cancelled', 'returned'):
            return False
        if obj.status == 'Billed':
            return False
        return obj.delivery_date < date.today()

    def get_days_overdue(self, obj):
        from datetime import date
        if not self.get_is_overdue(obj):
            return 0
        return (date.today() - obj.delivery_date).days

    class Meta:
        model = CustomerOrder
        fields = [
            'id', 'order_no', 'delivery_status', 'delivery_date',
            'est_amount', 'item_count', 'is_overdue', 'days_overdue'
        ]
        read_only_fields = fields


