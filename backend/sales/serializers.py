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





class CustomerOrderItemsSerializer(serializers.ModelSerializer):
    item_id = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", allow_null=True)
    order_no = serializers.PrimaryKeyRelatedField(queryset=CustomerOrder.objects.all(),required=False)
    class Meta:
        model = CustomerOrderItems
        fields = '__all__' 

        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

class CustomerOrderItemsSerializer1(serializers.ModelSerializer):
    item_id = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", allow_null=True)
    order_no = serializers.SlugRelatedField(queryset=CustomerOrder.objects.all,slug_field="order_no",required=False)
    class Meta:
        model = CustomerOrderItems
        fields = '__all__' 

        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

class CustomerOrderSerializer(serializers.ModelSerializer):
    items = CustomerOrderItemsSerializer(many=True)
    advance_reconciled = serializers.SerializerMethodField(read_only=True)
    advance_available  = serializers.SerializerMethodField(read_only=True)
    linked_bill_count  = serializers.SerializerMethodField(read_only=True)
    is_overdue         = serializers.SerializerMethodField(read_only=True)
    days_overdue       = serializers.SerializerMethodField(read_only=True)

    def get_advance_reconciled(self, obj):
        from django.db.models import Sum
        total = obj.linked_vouchers.aggregate(s=Sum('advance_deducted'))['s']
        return float(total) if total else 0.0

    def get_advance_available(self, obj):
        return float(obj.advance_amt or 0) - self.get_advance_reconciled(obj)

    def get_linked_bill_count(self, obj):
        return obj.linked_vouchers.count()

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
        fields = ['id', 'ldgr', 'ldgr_code_name', 'date1', 'order_no', 'fix_gold_rate', 'gold_rate_date',
             'rate_18kt', 'rate_22kt', 'rate_24kt', 'salesman_1', 'salesman_2',
             'advance_amt', 'est_amount', 'nature', 'status',
             'delivery_date', 'delivery_status', 'actual_delivery_date',
             'remarks', 'items',
             'advance_reconciled', 'advance_available', 'linked_bill_count',
             'is_overdue', 'days_overdue']

        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'ldgr_code_name': {'read_only': True},
        }

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
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }


class SalesVouItemSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    barcode = serializers.SlugRelatedField(queryset=BarcodeMain.objects.all(), slug_field="barcode")

    main_item_set = SalesVouItemDetailsSerializer(many=True)

    class Meta:
        model = SalesVouItem
        fields = [
            'id',
            'barcode',
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
        return barcode
    def create(self, instance, validated_data):
        with transaction.atomic():

            detail_data = validated_data.pop('main_item_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(SalesVouItemDetailsSerializer, instance, 'main_item_set', 'main_item',SalesVouItemDetailsSerializer(detail_data,many=True).data)
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
        fields = ['id', 'amount', 'bank_name', 'chq_no', 'chq_date', 'ledger', 'ledger_name']
        extra_kwargs = {
            'id':     {'read_only': False, 'required': False},
            'ledger': {'required': False, 'allow_null': True},
        }
        model = BankDetail


class SalesVouSerializer(serializers.ModelSerializer):
    ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    sales_person = serializers.PrimaryKeyRelatedField(queryset=SalesPersonMaster.objects.all())
    sales_person2 = serializers.PrimaryKeyRelatedField(queryset=SalesPersonMaster.objects.all())
    salesvouitem_set = SalesVouItemSerializer(many=True)
    salesvouitemdetails_set = SalesVouItemDetailsSerializer(many=True)
    bank_details =  BankDetails(many=True)
    mobile1 = serializers.CharField(source='ldgr.mobile1', read_only=True, default='')
    mobile2 = serializers.CharField(source='ldgr.mobile2', read_only=True, default='')
    mobile3 = serializers.CharField(source='ldgr.mobile3', read_only=True, default='')



    customer_order = serializers.PrimaryKeyRelatedField(
        queryset=CustomerOrder.objects.all(), allow_null=True, required=False
    )
    old_gold_purchase = serializers.PrimaryKeyRelatedField(
        queryset=PurchaseVoucher.objects.filter(voucher_type='Customer'),
        allow_null=True, required=False
    )

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
            'salesvouitem_set',  # Nested items serializer
            'salesvouitemdetails_set',
            'exhibition_profile',
            'vehicle_no',
            'transporter_name',
            'transporter_id',
            'trans_distance',
            'trans_doc_no',
            'trans_doc_date',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

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
                from accounting.utils import get_customer_cash_received
                customer_ldgr = validated_data.get('ldgr')
                fy = validated_data.get('fiscal_year') or request.retail.active_fy
                from accounting.utils import get_company_cash_limits
                limit, _ = get_company_cash_limits(request.retail)
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
            advance_deducted = Decimal(str(validated_data.get('advance_deducted', 0) or 0))
            cash_amt         = Decimal(str(validated_data.get('cash', 0) or 0))
            bank_total       = sum(Decimal(str(b.get('amount', 0) or 0)) for b in bank_details)
            # total_bill_value is a model property; read after instance creation below

            # ── Validate advance_deducted against order's available advance ───
            customer_order = validated_data.get('customer_order')
            if customer_order and advance_deducted > 0:
                from django.db.models import Sum as _Sum
                already = customer_order.linked_vouchers.aggregate(s=_Sum('advance_deducted'))['s'] or Decimal('0')
                available = Decimal(str(customer_order.advance_amt or 0)) - already
                if advance_deducted > available:
                    raise ValidationError({
                        'advance_deducted': (
                            f"Cannot deduct ₹{advance_deducted:,.0f} — only ₹{available:,.0f} "
                            f"is available from order {customer_order.order_no}."
                        )
                    })

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
            sales_vou_instance.due_amt = max(Decimal('0'), total_bill - cash_amt - bank_total - advance_deducted - old_gold_adjusted)
            # (saved again after ac_voucher is assigned below)

            # Create related SalesVouItem instances
            item_instances = []
            item_detail_instances = []

            create_or_update_nested(BankDetails,sales_vou_instance,'bank_details','sales_vou',BankDetails(bank_details,many=True).data)

            for detail_data in item_Details:
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

            _gm = request.retail.gstin_master
            _co = request.retail.branch.company if request.retail.branch_id and request.retail.branch else None
            out_cgst = _gm.output_cgst.ac_name if _gm and _gm.output_cgst else _raise_missing_ledger("OUTPUT CGST")
            out_sgst = _gm.output_sgst.ac_name if _gm and _gm.output_sgst else _raise_missing_ledger("OUTPUT SGST")
            out_igst = _gm.output_igst.ac_name if _gm and _gm.output_igst else _raise_missing_ledger("OUTPUT IGST")
            _making_recv_ldgr = _co.making_receive_ldgr.ac_name if _co and _co.making_receive_ldgr else _raise_missing_ledger("Making Charge Receive")
            _discount_ldgr = _co.discount_ldgr.ac_name if _co and _co.discount_ldgr else _raise_missing_ledger("Sale Discount")
            _cash_ldgr = request.retail.cash_ldgr.ac_name if request.retail.cash_ldgr else _raise_missing_ledger("CASH")
            _tcs_section = TCSSectionMaster.objects.filter(is_active=True, ledger__isnull=False).select_related('ledger').first()
            _tcs_ldgr = _tcs_section.ledger.ac_name if _tcs_section and _tcs_section.ledger else _raise_missing_ledger("TCS")

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
                                        {'account': sales_vou_instance.tcs_section.ledger.ac_name if sales_vou_instance.tcs_section and sales_vou_instance.tcs_section.ledger else _raise_missing_ledger("TCS Payable (configure TCS Section master)"),
                                            'debit':0,
                                            'credit':f"{sales_vou_instance.tcs_amt:.2f}"
                                        },
                                    ] +
                                    [{'account':_making_recv_ldgr,
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
                                    },

                                    {
                                        'account':sales_vou_instance.ldgr.ac_name,
                                        'debit':f"{(sales_vou_instance.total_bill_value):.2f}",
                                        'credit':0
                                    }]},
                                    context=self.context)


            if ser.is_valid(raise_exception=True):

                ref = ser.save()


            ser = JournalEntrySerializer(data= {'date':sales_vou_instance.date1.strftime('%Y-%m-%d'),
                                    "voucher_no":generate_voucher_no(global_vars.VoucherType.rcpt_sale, self.context.get('request').retail),
                                    'retail':request.retail.id,
                                    "narration":f"Sale Voucher Receipt Narration",
                                    "voucher_type":global_vars.VoucherType.rcpt_sale,

                                    "voucher_details": [
                                        {
                                'account':_cash_ldgr,
                                'debit':f"{sales_vou_instance.cash:.2f}",
                                'credit':0
                            }] +
                            [{
                                'account':bank["bank_name"],
                                'debit':f"{bank['amount']:.2f}",
                                'credit':0,
                                'party_bank_name':bank["bank_name"],
                                "chq_no":bank["chq_no"],
                                "chq_date":bank["chq_date"],
                            } for bank in bank_details] +[{
                                        'account':sales_vou_instance.ldgr.ac_name,
                                        'credit':f"{(sales_vou_instance.cash + sum((int(bank['amount']) for bank in bank_details))):.2f}",
                                        'debit':0
                                    }]})
            if ser.is_valid(raise_exception=True):

                rcpt_ref = ser.save()


            sales_vou_instance.ac_voucher = ref
            sales_vou_instance.ac_rec_voucher = rcpt_ref
            sales_vou_instance.gstin_ref  = request.retail.gstin_master
            sales_vou_instance.branch_ref = request.retail.branch
            sales_vou_instance.save()

            # ── Update CustomerOrder status to reflect billing ────────────────
            if customer_order:
                from django.db.models import Sum as _Sum
                total_reconciled = customer_order.linked_vouchers.aggregate(
                    s=_Sum('advance_deducted')
                )['s'] or Decimal('0')
                advance_total = Decimal(str(customer_order.advance_amt or 0))
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
            detail_data = validated_data.pop('salesvouitem_set', [])
            validated_data.pop('salesvouitemdetails_set', [])
            bank_details = validated_data.pop('bank_details')
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            create_or_update_nested(SalesVouItemSerializer, instance, 'salesvouitem_set', 'billno',SalesVouItemSerializer(detail_data,many=True).data)
            sales_vou_instance = instance
            sales_vou_instance.ac_voucher.delete()
            item_instances = []
            item_detail_instances = []
            create_or_update_nested(BankDetails,sales_vou_instance,'bank_details','sales_vou',BankDetails(bank_details,many=True).data)

            for detail_instance in sales_vou_instance.salesvouitemdetails_set.all():
                item_detail_instances.append(detail_instance)

            for sales_vou_item_instance in instance.salesvouitem_set.all():
                item_instances.append(sales_vou_item_instance)
                for detail_instance in sales_vou_item_instance.main_item_set.all():
                    item_detail_instances.append(detail_instance)

            request = self.context.get("request")
            _gm = request.retail.gstin_master
            _co = request.retail.branch.company if request.retail.branch_id and request.retail.branch else None
            out_cgst = _gm.output_cgst.ac_name if _gm and _gm.output_cgst else _raise_missing_ledger("OUTPUT CGST")
            out_sgst = _gm.output_sgst.ac_name if _gm and _gm.output_sgst else _raise_missing_ledger("OUTPUT SGST")
            out_igst = _gm.output_igst.ac_name if _gm and _gm.output_igst else _raise_missing_ledger("OUTPUT IGST")
            _making_recv_ldgr = _co.making_receive_ldgr.ac_name if _co and _co.making_receive_ldgr else _raise_missing_ledger("Making Charge Receive")
            _discount_ldgr = _co.discount_ldgr.ac_name if _co and _co.discount_ldgr else _raise_missing_ledger("Sale Discount")
            _cash_ldgr = request.retail.cash_ldgr.ac_name if request.retail.cash_ldgr else _raise_missing_ledger("CASH")
            _tcs_section = TCSSectionMaster.objects.filter(is_active=True, ledger__isnull=False).select_related('ledger').first()
            _tcs_ldgr = _tcs_section.ledger.ac_name if _tcs_section and _tcs_section.ledger else _raise_missing_ledger("TCS")

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
                                        {'account': sales_vou_instance.tcs_section.ledger.ac_name if sales_vou_instance.tcs_section and sales_vou_instance.tcs_section.ledger else _raise_missing_ledger("TCS Payable (configure TCS Section master)"),
                                            'debit':0,
                                            'credit':f"{sales_vou_instance.tcs_amt:.2f}"
                                        },
                                    ] +
                                    [{'account':_making_recv_ldgr,
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
                                    },
                                    {
                                        'account':_cash_ldgr,
                                        'debit':f"{sales_vou_instance.cash:.2f}",
                                        'credit':0
                                    }] +
                                    [{
                                        'account':bank["bank_name"],
                                        'debit':f"{bank['amount']:.2f}",
                                        'credit':0,
                                        'party_bank_name':bank["bank_name"],
                                        "chq_no":bank["chq_no"],
                                        "chq_date":bank["chq_date"],
                                    } for bank in bank_details] +
                                    [{
                                        'account':sales_vou_instance.ldgr.ac_name,
                                        'debit':f"{(sales_vou_instance.total_bill_value - sales_vou_instance.cash - sum((int(bank['amount']) for bank in bank_details))):.2f}",
                                        'credit':0
                                    }]},
                                    context=self.context)
            if ser.is_valid(raise_exception=True):

                ref = ser.save()
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
            'id': {'read_only': False, 'required': False},
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
            "igst_per",
           "cgst_per",
           "sgst_per",
           "tcs_per",
            'ldgr',
            'ldgr_name',
            'mrp',
            'taxable_value',
            'discount',

            'salereturnitem_set',  # Nested items serializer

        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
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
            for item in items_data:
                details_data = item.pop('salereturndetails_set')
                id = item.pop('id')
                sale_return_item_instance = SaleReturnItem.objects.create(billno=sale_return_instance, **item)
                item_instances.append(sale_return_item_instance)
                # Only update barcode stock status for barcode-linked items
                if sale_return_item_instance.barcode:
                    sale_return_item_instance.barcode.stk_status = True
                    sale_return_item_instance.barcode.save()

                for detail in details_data:
                    det = SaleReturnDetails.objects.create(main_item=sale_return_item_instance, **detail)
                    item_detail_instances.append(det)

            _gm = request.retail.gstin_master
            _co = request.retail.branch.company if request.retail.branch_id and request.retail.branch else None
            out_cgst = _gm.output_cgst.ac_name if _gm and _gm.output_cgst else _raise_missing_ledger("OUTPUT CGST")
            out_sgst = _gm.output_sgst.ac_name if _gm and _gm.output_sgst else _raise_missing_ledger("OUTPUT SGST")
            out_igst = _gm.output_igst.ac_name if _gm and _gm.output_igst else _raise_missing_ledger("OUTPUT IGST")
            _making_recv_ldgr = _co.making_receive_ldgr.ac_name if _co and _co.making_receive_ldgr else _raise_missing_ledger("Making Charge Receive")
            _discount_ldgr = _co.discount_ldgr.ac_name if _co and _co.discount_ldgr else _raise_missing_ledger("Sale Discount")
            _cash_ldgr = request.retail.cash_ldgr.ac_name if request.retail.cash_ldgr else _raise_missing_ledger("CASH")
            _tcs_section = TCSSectionMaster.objects.filter(is_active=True, ledger__isnull=False).select_related('ledger').first()
            _tcs_ldgr = _tcs_section.ledger.ac_name if _tcs_section and _tcs_section.ledger else _raise_missing_ledger("TCS")
            ser = JournalEntrySerializer(data= {'date':sale_return_instance.date1.strftime('%Y-%m-%d'),
                        "voucher_no":generate_voucher_no(global_vars.VoucherType.sale_ret, request.retail),
                        "narration":f"Sale Return Narration",
                        "voucher_type":global_vars.VoucherType.sale_ret,
                        "retail":request.retail.id,
                        "voucher_details": [
                            {
                                'account': out_cgst,

                                'debit':f"{sale_return_instance.cgst_amt:.2f}"
                            },
                            {'account': out_sgst,

                                'debit':f"{sale_return_instance.sgst_amt:.2f}"
                            },
                            {'account': out_igst,

                                'debit':f"{sale_return_instance.igst_amt:.2f}"
                            },
                            {'account':_tcs_ldgr,

                                'debit':f"{sale_return_instance.tcs_amt:.2f}"
                            },
                        ] +
                        [{'account':_making_recv_ldgr,

                            'debit':f"{item.making_value:.2f}"
                        } for item in item_instances] +
                        [{
                            'account':item.item.sale_ledger.ac_name,

                            'debit':f"{item.amount:.2f}"
                        } for item in item_detail_instances] +

                        [{
                            'account':_discount_ldgr,
                            'credit':f"{sale_return_instance.discount:.2f}",

                        },
                       ] +
                        [{
                            'account':sale_return_instance.ldgr.ac_name,
                            'credit':f"{(sale_return_instance.total_bill_value ):.2f}",

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
            except Exception:
                pass  # Commission reversal is non-critical; never block the return save

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
            item_instances = []
            item_detail_instances = []
            for sale_return_item_instance in instance.salereturnitem_set.all():
                item_instances.append(sale_return_item_instance)

                for detail in sale_return_item_instance.salereturndetails_set.all():
                    item_detail_instances.append(detail)

            request = self.context.get('request')
            _gm = request.retail.gstin_master
            _co = request.retail.branch.company if request.retail.branch_id and request.retail.branch else None
            out_cgst = _gm.output_cgst.ac_name if _gm and _gm.output_cgst else _raise_missing_ledger("OUTPUT CGST")
            out_sgst = _gm.output_sgst.ac_name if _gm and _gm.output_sgst else _raise_missing_ledger("OUTPUT SGST")
            out_igst = _gm.output_igst.ac_name if _gm and _gm.output_igst else _raise_missing_ledger("OUTPUT IGST")
            _making_recv_ldgr = _co.making_receive_ldgr.ac_name if _co and _co.making_receive_ldgr else _raise_missing_ledger("Making Charge Receive")
            _discount_ldgr = _co.discount_ldgr.ac_name if _co and _co.discount_ldgr else _raise_missing_ledger("Sale Discount")
            _cash_ldgr = request.retail.cash_ldgr.ac_name if request.retail.cash_ldgr else _raise_missing_ledger("CASH")
            _tcs_section = TCSSectionMaster.objects.filter(is_active=True, ledger__isnull=False).select_related('ledger').first()
            _tcs_ldgr = _tcs_section.ledger.ac_name if _tcs_section and _tcs_section.ledger else _raise_missing_ledger("TCS")
            ser = JournalEntrySerializer(data= {'date':sale_return_instance.date1.strftime('%Y-%m-%d'),
                        "voucher_no":generate_voucher_no(global_vars.VoucherType.sale_ret, request.retail),
                        "narration":f"Sale Return Narration",
                        "voucher_type":global_vars.VoucherType.sale_ret,
                        "retail":request.retail.id,
                        "voucher_details": [
                            {
                                'account': out_cgst,

                                'debit':f"{sale_return_instance.cgst_amt:.2f}"
                            },
                            {'account': out_sgst,

                                'debit':f"{sale_return_instance.sgst_amt:.2f}"
                            },
                            {'account': out_igst,

                                'debit':f"{sale_return_instance.igst_amt:.2f}"
                            },
                            {'account':_tcs_ldgr,

                                'debit':f"{sale_return_instance.tcs_amt:.2f}"
                            },
                        ] +
                        [{'account':_making_recv_ldgr,

                            'debit':f"{item.making_value:.2f}"
                        } for item in item_instances] +
                        [{'account':item.item.sale_ledger.ac_name,

                            'debit':f"{item.amount:.2f}"
                        } for item in item_detail_instances] +

                        [{
                            'account':_discount_ldgr,
                            'credit':f"{sale_return_instance.discount:.2f}",

                        },
                        ] +
                        [{
                            'account':sale_return_instance.ldgr.ac_name,
                            'credit':f"{(sale_return_instance.total_bill_value ):.2f}",

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
            'main_item_set',  # Nested details
        ]
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

            for item_br in item_instances:
                BarcodeTransaction.objects.create(
                    barcode=item_br.barcode,
                    billno=sale_return_instance.billno,
                    trans_type="SALE-APP",
                    user=request.user,
                    ip_address=ip,
                    retail=request.retail
                )



            return sale_return_instance


    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('items', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            request = self.context.get("request")
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')) if request else None

            create_or_update_nested(SalesApprovalItemSerializer, instance, 'items', 'billno',SalesApprovalItemSerializer(detail_data,many=True).data)
            for item_br in detail_data:
                if item_br["ret_status"]:
                    BarcodeTransaction.objects.create(
                        barcode=item_br["barcode"],
                        billno=instance.billno,
                        trans_type="SALE-APP-RET",
                        user=request.user,
                        ip_address=ip,
                        retail=request.retail
                    )
            return instance