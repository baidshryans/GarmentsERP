import logging
from decimal import Decimal
from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from goldrates.models import PurityMaster
from manufacturing.utils import create_or_update_nested
from mastersconfig.models import Item, SalesPersonMaster, TCSSectionMaster
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
    """Return (lock_state, lock_reason) for a CustomerOrderItems row."""
    # Truly delivered: a Sales Voucher exists for a barcode tied to this CO item.
    sv_billno = _sv_billno_for_co_item(obj)
    if sv_billno:
        return 'billed', f"Sold via Sales Voucher {sv_billno}"

    if obj.sale_status:
        return 'billed', 'Billed in a sales voucher'

    # Direct CO → PV path: the CO item was billed straight onto a Purchase
    # Voucher without going through a Purchase Order. This is terminal.
    pv = obj.purchasevoucheritems_set.select_related('billno').first()
    if pv:
        ref = pv.billno.billno if pv.billno else ''
        return 'billed', f"Billed directly on Purchase Voucher {ref}".rstrip()

    # Barcoded but not yet sold: a barcode exists for this CO item.
    barcode_ids = _barcode_ids_for_co_item(obj)
    if barcode_ids:
        return 'barcoded', 'Barcode created — ready for delivery'

    ki = obj.karigarissueitem_set.select_related('issue_slip').first()
    if ki:
        return 'in_production', f"Issued to Karigar job {ki.issue_slip.issue_slip_no}"
    po = obj.purchaseorderitems_set.select_related('po_slip').first()
    if po:
        return 'in_production', f"Issued to Purchase Order {po.po_slip.po_no}"
    return 'unlocked', ''


def _barcode_ids_for_co_item(coi):
    """Return a set of BarcodeMain IDs tied to this CustomerOrderItems row.

    Walks three barcode-sourcing chains:
      A) CO → PO line → PV line (po_no/po_sl_no match) → BarcodeMain.pur_voucher
      B) CO → KarigarIssueItem → KarigarReceiveItem (ref_job_sl_no) → BarcodeMain.rec_item
      C) Direct CO → PV line (customer_order_item FK) → BarcodeMain.pur_voucher
    """
    from inventory.models import BarcodeMain
    from purchase.models import PurchaseVoucherItems
    from manufacturing.models import KarigarReceiveItem

    barcode_ids = set()

    # Chain A: PO → PV
    po_items = coi.purchaseorderitems_set.select_related('po_slip').all()
    for po_item in po_items:
        if not po_item.po_slip:
            continue
        pv_items = PurchaseVoucherItems.objects.filter(
            po_no=po_item.po_slip.po_no,
            po_sl_no=po_item.po_sl_no,
        ).values_list('id', flat=True)
        for bc_id in BarcodeMain.objects.filter(pur_voucher_id__in=list(pv_items)).values_list('id', flat=True):
            barcode_ids.add(bc_id)

    # Chain B: KI → KR
    ki_ids = list(coi.karigarissueitem_set.values_list('id', flat=True))
    if ki_ids:
        kr_ids = list(KarigarReceiveItem.objects.filter(ref_job_sl_no_id__in=ki_ids).values_list('id', flat=True))
        if kr_ids:
            for bc_id in BarcodeMain.objects.filter(rec_item_id__in=kr_ids).values_list('id', flat=True):
                barcode_ids.add(bc_id)

    # Chain C: direct CO → PV
    pv_ids = list(coi.purchasevoucheritems_set.values_list('id', flat=True))
    if pv_ids:
        for bc_id in BarcodeMain.objects.filter(pur_voucher_id__in=pv_ids).values_list('id', flat=True):
            barcode_ids.add(bc_id)

    return barcode_ids


def _sv_billno_for_co_item(coi):
    """Return the SalesVou billno of the first Sales Voucher whose barcode
    traces back to this CustomerOrderItems row, or None if not yet sold."""
    from sales.models import SalesVouItem

    barcode_ids = _barcode_ids_for_co_item(coi)
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
    order_no = serializers.SlugRelatedField(queryset=CustomerOrder.objects.all,slug_field="order_no",required=False)
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

    def get_advance_amt(self, obj):
        return float(obj.advance_amt)

    def get_advance_reconciled(self, obj):
        return float(obj.advance_reconciled)

    def get_advance_available(self, obj):
        return float(obj.advance_available)

    def get_linked_bill_count(self, obj):
        return len(obj.linked_vouchers.all())

    def get_is_overdue(self, obj):
        from datetime import date
        if not obj.delivery_date:
            return False
        if obj.delivery_status in ('delivered', 'cancelled'):
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

    def get_is_deletable(self, obj):
        return not obj.linked_vouchers.all()

    def get_is_cancellable(self, obj):
        return obj.delivery_status not in ('delivered', 'cancelled')

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
             'is_deletable', 'is_cancellable', 'has_in_production_items', 'has_advance']

        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'ldgr_code_name': {'read_only': True},
            # order_no is generated server-side; frontend may omit or send a stale peek
            'order_no': {'required': False, 'allow_blank': True, 'default': ''},
        }

    def validate(self, attrs):
        # Delivery date must be strictly after today. A same-day delivery is
        # not a meaningful commitment — the order is effectively due "now".
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
from sales.models import BankDetail, SalesVou, SalesVouItem, SalesVouItemDetails, SaleReturn, SaleReturnItem, SaleReturnDetails, SalesApproval, SalesApprovalItem, SalesApprovalItemDetails


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
            'uom',       # Read-only — item.uom, needed for frontend amount recalc
            'item_type', # Read-only — item.item_type, needed for frontend B2B overrides
            'item_name', # Read-only — item.item_name, shown in the sub-item row item column
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
    # False means it has been sold/transferred — the voucher should be locked for editing.
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
        # Already numeric (PK) — return as-is
        try:
            return int(value)
        except (ValueError, TypeError):
            pass
        # Slug string — look up the PK
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
    old_gold_purchase = serializers.PrimaryKeyRelatedField(
        queryset=PurchaseVoucher.objects.filter(voucher_type='Customer'),
        allow_null=True, required=False
    )

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

            # Auto-generate bill number server-side to avoid clashes
            request = self.context.get("request")
            validated_data['billno'] = generate_next_sale_voucher_no(request.retail)

            # ── Section 269ST cash receipt limit check ────────────────────────
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
                                f"Already received ₹{already:,.0f} this FY  |  "
                                f"Limit: ₹{limit:,.0f}  |  "
                                f"Max receivable now: ₹{remaining:,.0f}."
                            )
                        })
            # ─────────────────────────────────────────────────────────────────

            # ── Compute server-side due_amt (patched after instance creation) ──
            cash_amt         = Decimal(str(validated_data.get('cash', 0) or 0))
            bank_total       = sum(Decimal(str(b.get('amount', 0) or 0)) for b in bank_details)
            # total_bill_value is a model property; read after instance creation below

            # ── Auto-apply CustomerOrder advance (single source of truth) ─────
            # The client MUST NOT send advance_deducted. It is computed on the
            # server from the order's linked receipts so the ledger and the
            # advance adjustment can never drift apart.
            customer_order = validated_data.get('customer_order')
            if customer_order:
                advance_deducted = customer_order.advance_available
            else:
                advance_deducted = Decimal('0')
            validated_data['advance_deducted'] = advance_deducted

            # ── Validate old_gold_adjusted against purchase's available balance ──
            old_gold_adjusted = Decimal(str(validated_data.get('old_gold_adjusted', 0) or 0))
            old_gold_purchase = validated_data.get('old_gold_purchase')
            if old_gold_purchase and old_gold_adjusted > 0:
                from django.db.models import Sum as _Sum
                already_adj = old_gold_purchase.linked_sales_vouchers.aggregate(
                    s=_Sum('old_gold_adjusted'))['s'] or Decimal('0')
                available_og = Decimal(str(old_gold_purchase.bill_value or 0)) - already_adj
                if old_gold_adjusted > available_og:
                    raise ValidationError({
                        'old_gold_adjusted': (
                            f"Cannot adjust ₹{old_gold_adjusted:,.0f} — only ₹{available_og:,.0f} "
                            f"is available from purchase {old_gold_purchase.billno}."
                        )
                    })

            sales_vou_instance = SalesVou.objects.create(**validated_data)

            # Patch due_amt now that the instance exists (total_bill_value is a property)
            total_bill = Decimal(str(sales_vou_instance.total_bill_value))

            # Cap advance_deducted to the portion of the bill not covered by
            # cash / bank / old gold — any surplus order advance stays on the
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

            # ── Write ReferenceBills rows linking order receipts → this sale ──
            # Splits the advance across receipts in FIFO order. This is the
            # audit trail that says "RCPT-123 was used to pay SV-456 for ₹X".
            if customer_order and advance_deducted > 0:
                from django.db.models import Sum as _Sum
                from accounting.models import ReferenceBills as _RefBills
                remaining = advance_deducted
                order_receipts = customer_order.receipts.filter(
                    voucher_type__in=['RCPT', 'RCPT-SALE'],
                    status='posted',
                ).order_by('date', 'id')
                for rcpt in order_receipts:
                    if remaining <= 0:
                        break
                    # How much of this receipt is still unallocated against any bill?
                    already = _RefBills.objects.filter(voucher=rcpt).aggregate(
                        s=_Sum('amount')
                    )['s'] or Decimal('0')
                    rcpt_available = Decimal(rcpt.amount) - already
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

            # ── Recompute mrp from actual saved items ─────────────────────────
            # Journal balance: DEBIT total_bill_value = CREDIT Σmaking + Σitem.amount
            # so mrp must equal Σ making_value + Σ item_detail.amount.
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
            out_cgst = _gm.output_cgst.ac_name if _gm and _gm.output_cgst else _raise_missing_ledger("OUTPUT CGST")
            out_sgst = _gm.output_sgst.ac_name if _gm and _gm.output_sgst else _raise_missing_ledger("OUTPUT SGST")
            out_igst = _gm.output_igst.ac_name if _gm and _gm.output_igst else _raise_missing_ledger("OUTPUT IGST")
            _making_recv_ldgr = _co.making_receive_ldgr.ac_name if _co and _co.making_receive_ldgr else _raise_missing_ledger("Making Charge Receive")
            _discount_ldgr = _co.discount_ldgr.ac_name if _co and _co.discount_ldgr else _raise_missing_ledger("Sale Discount")
            _cash_ldgr = request.retail.cash_ldgr.ac_name if request.retail.cash_ldgr else _raise_missing_ledger("CASH")
            _round_off_ldgr = _co.round_off_ldgr.ac_name if _co and _co.round_off_ldgr else _raise_missing_ledger("Round Off")

            def _making_recv_ldgr_for_item(item):
                """Return purity-specific making charge received ledger for a barcode item."""
                try:
                    purity_str = (item.barcode.purity.purity or '').upper() if item.barcode_id and item.barcode and item.barcode.purity else ''
                except Exception:
                    purity_str = ''
                if '14' in purity_str and _co and _co.making_receive_14k_ldgr:
                    return _co.making_receive_14k_ldgr.ac_name
                if '18' in purity_str and _co and _co.making_receive_18k_ldgr:
                    return _co.making_receive_18k_ldgr.ac_name
                if '22' in purity_str and _co and _co.making_receive_22k_ldgr:
                    return _co.making_receive_22k_ldgr.ac_name
                return _making_recv_ldgr  # fallback to generic

            # Only build TCS journal line when TCS actually applies
            _tcs_amt = float(sales_vou_instance.tcs_amt or 0)
            _tcs_lines = []
            if _tcs_amt > 0:
                _tcs_ldgr_name = (
                    sales_vou_instance.tcs_section.ledger.ac_name
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

            ser = JournalEntrySerializer(data= {'date':sales_vou_instance.date1.strftime('%Y-%m-%d'),
                                    "voucher_no":generate_voucher_no(global_vars.VoucherType.sale, request.retail),
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
                                    [{'account':item.item.sale_ledger.ac_name,
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
                                        'account':sales_vou_instance.ldgr.ac_name,
                                        'debit':f"{_party_debit:.2f}",
                                        'credit':0
                                    }]},
                                    context=self.context)


            if ser.is_valid(raise_exception=True):

                ref = ser.save()


            def _bank_debit_account(bank):
                """Cheques go to 'Cheques in Hand' suspense; all other modes go direct to bank."""
                if bank.get("payment_mode") == "CHEQUE":
                    return "Cheques in Hand"
                return bank["bank_name"]

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
                                # Old gold: DR old-gold vendor ledger, reducing their payable to us
                                ([{
                                    'account': old_gold_purchase.ldgr.ac_name,
                                    'debit': f"{old_gold_adjusted:.2f}",
                                    'credit': 0,
                                }] if old_gold_purchase and old_gold_adjusted > 0 else []) +
                                [{
                                            'account':sales_vou_instance.ldgr.ac_name,
                                            'credit':f"{_rcpt_customer_credit:.2f}",
                                            'debit':0
                                        }]},
                                        context=self.context)
                if ser.is_valid(raise_exception=True):
                    rcpt_ref = ser.save()

            sales_vou_instance.ac_voucher = ref
            sales_vou_instance.ac_rec_voucher = rcpt_ref
            sales_vou_instance.gstin_ref  = request.retail.gstin_master
            sales_vou_instance.branch_ref = request.retail.branch
            sales_vou_instance.save()

            # ── Update CustomerOrder status to reflect billing ────────────────
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

            # ── Update old gold purchase voucher due_amt ─────────────────────
            if old_gold_purchase and old_gold_adjusted > 0:
                from django.db.models import Sum as _Sum
                total_adj = old_gold_purchase.linked_sales_vouchers.aggregate(
                    s=_Sum('old_gold_adjusted'))['s'] or Decimal('0')
                purchase_bill = Decimal(str(old_gold_purchase.bill_value or 0))
                old_gold_purchase.due_amt = max(Decimal('0'), purchase_bill - total_adj)
                old_gold_purchase.save(update_fields=['due_amt'])

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
            # ── Release this voucher's barcodes back to stock before update ──
            # The voucher's own barcodes have stk_status=False (they were marked
            # sold at create time). Temporarily flipping them to True lets the
            # nested update validate/add/remove barcodes freely. We re-mark the
            # FINAL item set as sold after the nested update runs. Everything
            # below is inside transaction.atomic() — any failure rolls back.
            for _it in instance.salesvouitem_set.select_related('barcode').all():
                if _it.barcode_id and _it.barcode and not _it.barcode.stk_status:
                    _it.barcode.stk_status = True
                    _it.barcode.save(update_fields=['stk_status'])

            detail_data = validated_data.pop('salesvouitem_set', [])
            item_details_data = validated_data.pop('salesvouitemdetails_set', [])
            bank_details = validated_data.pop('bank_details')

            # ── Snapshot current DB values BEFORE setattr overwrites them ──────
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

            create_or_update_nested(SalesVouItemSerializer, instance, 'salesvouitem_set', 'billno', SalesVouItemSerializer(detail_data, many=True).data)

            # ── Mark the final set of barcodes as sold ────────────────────────
            # Kept/added barcodes end up sold; removed barcodes were released
            # above and stay in stock because they're no longer in the set.
            for _it in instance.salesvouitem_set.select_related('barcode').all():
                if _it.barcode_id and _it.barcode and _it.barcode.stk_status:
                    _it.barcode.stk_status = False
                    _it.barcode.save(update_fields=['stk_status'])

            # Rebuild direct manual details (those not linked to a barcode item).
            # These were previously dropped on update — now they are properly saved.
            instance.salesvouitemdetails_set.filter(main_item=None).delete()
            for raw in item_details_data:
                raw = {k: v for k, v in raw.items()
                       if k not in {"id", "billno", "main_item", "retail"}}
                SalesVouItemDetails.objects.create(billno=instance, main_item=None, **raw)

            sales_vou_instance = instance
            sales_vou_instance.ac_voucher.delete()
            create_or_update_nested(BankDetails, sales_vou_instance, 'bank_details', 'sales_vou', BankDetails(bank_details, many=True).data)

            # ── Fresh DB queries — the prefetch_related cache on `instance` is STALE
            #    after create_or_update_nested; using it would put old values in the journal.
            from sales.models import SalesVouItem as _SVItem, SalesVouItemDetails as _SVDetail
            item_instances = list(_SVItem.objects.filter(billno=instance).select_related('item', 'barcode__purity'))
            item_detail_instances = list(
                _SVDetail.objects.filter(billno=instance).select_related('item')
            )

            # ── Recompute mrp from actual saved items ─────────────────────────
            # Journal balance requires:
            #   DEBIT  total_bill_value (= (mrp - discount) × (1 + tax_rate))
            #   CREDIT Σ making_value  +  Σ item_detail.amount
            # So mrp must equal Σ making_value + Σ item_detail.amount.
            # If the frontend sent a stale mrp (e.g. after editing an item's rate),
            # the journal would be unbalanced.  Recompute it from the DB — same fix
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
            out_cgst = _gm.output_cgst.ac_name if _gm and _gm.output_cgst else _raise_missing_ledger("OUTPUT CGST")
            out_sgst = _gm.output_sgst.ac_name if _gm and _gm.output_sgst else _raise_missing_ledger("OUTPUT SGST")
            out_igst = _gm.output_igst.ac_name if _gm and _gm.output_igst else _raise_missing_ledger("OUTPUT IGST")
            _making_recv_ldgr = _co.making_receive_ldgr.ac_name if _co and _co.making_receive_ldgr else _raise_missing_ledger("Making Charge Receive")
            _discount_ldgr = _co.discount_ldgr.ac_name if _co and _co.discount_ldgr else _raise_missing_ledger("Sale Discount")
            _cash_ldgr = request.retail.cash_ldgr.ac_name if request.retail.cash_ldgr else _raise_missing_ledger("CASH")
            _round_off_ldgr = _co.round_off_ldgr.ac_name if _co and _co.round_off_ldgr else _raise_missing_ledger("Round Off")

            def _making_recv_ldgr_for_item(item):
                """Return purity-specific making charge received ledger for a barcode item."""
                try:
                    purity_str = (item.barcode.purity.purity or '').upper() if item.barcode_id and item.barcode and item.barcode.purity else ''
                except Exception:
                    purity_str = ''
                if '14' in purity_str and _co and _co.making_receive_14k_ldgr:
                    return _co.making_receive_14k_ldgr.ac_name
                if '18' in purity_str and _co and _co.making_receive_18k_ldgr:
                    return _co.making_receive_18k_ldgr.ac_name
                if '22' in purity_str and _co and _co.making_receive_22k_ldgr:
                    return _co.making_receive_22k_ldgr.ac_name
                return _making_recv_ldgr  # fallback to generic

            # Only build TCS journal line when TCS actually applies
            _tcs_amt = float(sales_vou_instance.tcs_amt or 0)
            _tcs_lines = []
            if _tcs_amt > 0:
                _tcs_ldgr_name = (
                    sales_vou_instance.tcs_section.ledger.ac_name
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

            ser = JournalEntrySerializer(data= {'date':sales_vou_instance.date1.strftime('%Y-%m-%d'),
                                    "voucher_no":generate_voucher_no(global_vars.VoucherType.sale, request.retail),
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
                                    [{'account':item.item.sale_ledger.ac_name,
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
                                        'account': "Cheques in Hand" if bank.get("payment_mode") == "CHEQUE" else bank["bank_name"],
                                        'debit':f"{bank['amount']:.2f}",
                                        'credit':0,
                                        'party_bank_name':bank["bank_name"],
                                        "chq_no":bank.get("chq_no"),
                                        "chq_date":bank.get("chq_date"),
                                    } for bank in bank_details] +
                                    [{
                                        'account':sales_vou_instance.ldgr.ac_name,
                                        'debit':f"{(_party_debit - Decimal(str(sales_vou_instance.cash or 0)) - sum(Decimal(str(bank['amount'])) for bank in bank_details)):.2f}",
                                        'credit':0
                                    }]},
                                    context=self.context)
            if ser.is_valid(raise_exception=True):

                ref = ser.save()
            # ── Recalculate due_amt preserving subsequent payment receipts ──────
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
                    sale_return_item_instance.barcode.save()

                detail_instances = []
                for detail in details_data:
                    det = SaleReturnDetails.objects.create(main_item=sale_return_item_instance, **detail)
                    detail_instances.append(det)
                    item_detail_instances.append(det)
                items_with_details.append((sale_return_item_instance, detail_instances))

            _gm = request.retail.gstin_master
            _co = request.retail.branch.company if request.retail.branch_id and request.retail.branch else None
            out_cgst = _gm.output_cgst.ac_name if _gm and _gm.output_cgst else _raise_missing_ledger("OUTPUT CGST")
            out_sgst = _gm.output_sgst.ac_name if _gm and _gm.output_sgst else _raise_missing_ledger("OUTPUT SGST")
            out_igst = _gm.output_igst.ac_name if _gm and _gm.output_igst else _raise_missing_ledger("OUTPUT IGST")
            _discount_ldgr = _co.discount_ldgr.ac_name if _co and _co.discount_ldgr else _raise_missing_ledger("Sale Discount")
            _tcs_section = TCSSectionMaster.objects.filter(is_active=True, ledger__isnull=False).select_related('ledger').first()
            _tcs_ldgr = _tcs_section.ledger.ac_name if _tcs_section and _tcs_section.ledger else _raise_missing_ledger("TCS")

            # Build item journal lines:
            # Making is rolled into the FIRST sub-item's sale_ledger debit so that the
            # return passes through the same sale ledgers as the original sale entry,
            # rather than splitting into a separate "Making Charge Received" account.
            _sr_item_lines = []
            for _main, _sub_details in items_with_details:
                _making = Decimal(str(_main.making_value or 0))
                for _idx, _d in enumerate(_sub_details):
                    _amt = Decimal(str(_d.amount or 0)) + (_making if _idx == 0 else Decimal('0'))
                    _sr_item_lines.append({
                        'account': _d.item.sale_ledger.ac_name,
                        'debit': f"{_amt:.2f}",
                    })

            # Build party credit using Decimal-rounded components so it matches
            # the individually-rounded debit lines exactly (avoids 0.01 mismatch).
            _sr_cgst_d    = Decimal(f"{sale_return_instance.cgst_amt:.2f}")
            _sr_sgst_d    = Decimal(f"{sale_return_instance.sgst_amt:.2f}")
            _sr_igst_d    = Decimal(f"{sale_return_instance.igst_amt:.2f}")
            _sr_tcs_d     = Decimal(f"{sale_return_instance.tcs_amt:.2f}")
            _sr_item_total = sum(Decimal(line['debit']) for line in _sr_item_lines)
            _sr_discount_d = Decimal(f"{sale_return_instance.discount:.2f}")
            _sr_party_credit = _sr_cgst_d + _sr_sgst_d + _sr_igst_d + _sr_tcs_d + _sr_item_total - _sr_discount_d

            ser = JournalEntrySerializer(data= {'date':sale_return_instance.date1.strftime('%Y-%m-%d'),
                        "voucher_no":generate_voucher_no(global_vars.VoucherType.sale_ret, request.retail),
                        "narration":f"Sale Return Narration",
                        "voucher_type":global_vars.VoucherType.sale_ret,
                        "retail":request.retail.id,
                        "voucher_details": [
                            {'account': out_cgst, 'debit':f"{_sr_cgst_d:.2f}"},
                            {'account': out_sgst, 'debit':f"{_sr_sgst_d:.2f}"},
                            {'account': out_igst, 'debit':f"{_sr_igst_d:.2f}"},
                            {'account':_tcs_ldgr,  'debit':f"{_sr_tcs_d:.2f}"},
                        ] +
                        _sr_item_lines +
                        [{
                            'account':_discount_ldgr,
                            'credit':f"{_sr_discount_d:.2f}",
                        }] +
                        [{
                            'account':sale_return_instance.ldgr.ac_name,
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
            # Fresh DB queries — avoid stale prefetch cache left by create_or_update_nested
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
            out_cgst = _gm.output_cgst.ac_name if _gm and _gm.output_cgst else _raise_missing_ledger("OUTPUT CGST")
            out_sgst = _gm.output_sgst.ac_name if _gm and _gm.output_sgst else _raise_missing_ledger("OUTPUT SGST")
            out_igst = _gm.output_igst.ac_name if _gm and _gm.output_igst else _raise_missing_ledger("OUTPUT IGST")
            _discount_ldgr = _co.discount_ldgr.ac_name if _co and _co.discount_ldgr else _raise_missing_ledger("Sale Discount")
            _cash_ldgr = request.retail.cash_ldgr.ac_name if request.retail.cash_ldgr else _raise_missing_ledger("CASH")
            _tcs_section = TCSSectionMaster.objects.filter(is_active=True, ledger__isnull=False).select_related('ledger').first()
            _tcs_ldgr = _tcs_section.ledger.ac_name if _tcs_section and _tcs_section.ledger else _raise_missing_ledger("TCS")

            # Build item journal lines: making rolled into first sub-item's sale_ledger
            from collections import defaultdict as _defaultdict
            _sr_details_by_main = _defaultdict(list)
            for _d in item_detail_instances:
                _sr_details_by_main[_d.main_item_id].append(_d)
            _sr_item_lines = []
            for _main in item_instances:
                _making = Decimal(str(_main.making_value or 0))
                for _idx, _d in enumerate(_sr_details_by_main.get(_main.id, [])):
                    _amt = Decimal(str(_d.amount or 0)) + (_making if _idx == 0 else Decimal('0'))
                    _sr_item_lines.append({'account': _d.item.sale_ledger.ac_name, 'debit': f"{_amt:.2f}"})

            # Build party credit using Decimal-rounded components so it matches
            # the individually-rounded debit lines exactly (avoids 0.01 mismatch).
            _sr_cgst_d    = Decimal(f"{sale_return_instance.cgst_amt:.2f}")
            _sr_sgst_d    = Decimal(f"{sale_return_instance.sgst_amt:.2f}")
            _sr_igst_d    = Decimal(f"{sale_return_instance.igst_amt:.2f}")
            _sr_tcs_d     = Decimal(f"{sale_return_instance.tcs_amt:.2f}")
            _sr_item_total = sum(Decimal(line['debit']) for line in _sr_item_lines)
            _sr_discount_d = Decimal(f"{sale_return_instance.discount:.2f}")
            _sr_party_credit = _sr_cgst_d + _sr_sgst_d + _sr_igst_d + _sr_tcs_d + _sr_item_total - _sr_discount_d

            ser = JournalEntrySerializer(data= {'date':sale_return_instance.date1.strftime('%Y-%m-%d'),
                        "voucher_no":generate_voucher_no(global_vars.VoucherType.sale_ret, request.retail),
                        "narration":f"Sale Return Narration",
                        "voucher_type":global_vars.VoucherType.sale_ret,
                        "retail":request.retail.id,
                        "voucher_details": [
                            {'account': out_cgst, 'debit':f"{_sr_cgst_d:.2f}"},
                            {'account': out_sgst, 'debit':f"{_sr_sgst_d:.2f}"},
                            {'account': out_igst, 'debit':f"{_sr_igst_d:.2f}"},
                            {'account':_tcs_ldgr, 'debit':f"{_sr_tcs_d:.2f}"},
                        ] +
                        _sr_item_lines +
                        [{
                            'account':_discount_ldgr,
                            'credit':f"{_sr_discount_d:.2f}",
                        }] +
                        [{
                            'account':sale_return_instance.ldgr.ac_name,
                            'credit':f"{_sr_party_credit:.2f}",
                        }]},
                        context=self.context)
            if ser.is_valid(raise_exception=True):

                ref = ser.save()
            instance.ac_voucher = ref
            instance.gstin_ref  = request.retail.gstin_master
            instance.branch_ref = request.retail.branch
            instance.save()
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
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(),slug_field="pckt_no",allow_null=True)
    fine_wt = serializers.ReadOnlyField()

    class Meta:
        model = SalesApprovalItemDetails
        fields = [
            'id',
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
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

class SalesApprovalItemSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    barcode = serializers.SlugRelatedField(queryset=BarcodeMain.objects.all(), slug_field="barcode")
    main_item_set = SalesApprovalItemDetailsSerializer(many=True)

    class Meta:
        model = SalesApprovalItem
        fields = [
            'id',
            'barcode',
            'item',
            'pcs',
            'gw',
            'purity',
            'amount',
            'ret_status',
            'main_item_set',  # Nested details
        ]

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

class SalesApprovalSerializer(serializers.ModelSerializer):
    ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    sales_person = serializers.PrimaryKeyRelatedField(queryset=SalesPersonMaster.objects.all())
    sales_person2 = serializers.PrimaryKeyRelatedField(queryset=SalesPersonMaster.objects.all(), allow_null=True)
    place_of_supply = serializers.SlugRelatedField(queryset=State.objects.all(), slug_field='code', required=False, allow_null=True)
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
        # validators run — same reservation guard as SalesVouSerializer.
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
            sale_return_instance = SalesApproval.objects.create(**validated_data)

            item_instances = []
            item_detail_instances = []
            for item in items_data:
                details_data = item.pop('main_item_set')
                sale_return_item_instance = SalesApprovalItem.objects.create(billno=sale_return_instance, **item)
                item_instances.append(sale_return_item_instance)

                for detail in details_data:
                    det = SalesApprovalItemDetails.objects.create(main_item=sale_return_item_instance, **detail)
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


# ── Quotation Serializers ────────────────────────────────────────────────────

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
            quotation = Quotation.objects.create(**validated_data)
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
        if obj.delivery_status in ('delivered', 'cancelled'):
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