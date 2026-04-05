from rest_framework.serializers import ModelSerializer

from accounting.serializers import JournalEntrySerializer
from accounting.utils import generate_voucher_no
from contacts.models import Ledger
from global_vars import STATES_OF_INDIA
import global_vars
from goldrates.models import PurityMaster
from inventory.models import BarcodeMain
from manufacturing.utils import create_or_update_nested
from mastersconfig.models import Item, Packet, State
from purchase.models import PurchaseOrderItems, PurchaseVoucher,PurchaseOrder
from sales.models import CustomerOrder, CustomerOrderItems
from django.db import transaction
from accounting.models import VoucherMain
class PurchaseVoucherSerializer(ModelSerializer):
    class Meta:
        model = PurchaseVoucher
        fields = "__all__"

class PurchaseOrderSerializer(ModelSerializer):
    class Meta:
        model = PurchaseOrder
        fields = "__all__"

class PurchaseOrderItemsSerializer(ModelSerializer):
    class Meta:
        model = PurchaseOrderItems
        fields = "__all__"

from rest_framework import serializers
from .models import PurchaseReturn, PurchaseReturnItems, PurchaseReturnDetails, PurchaseVoucherDetails, PurchaseVoucherItems


class PurchaseReturnDetailsSerializer(serializers.ModelSerializer):
    # Fields related to PurchaseReturnDetails model
    sub_item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code", required=True)
    metal_purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", required=False)
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(),slug_field ="pckt_no", required=False)

    class Meta:
        model = PurchaseReturnDetails
        fields = [
            'id',
            
            'sub_item',
            'sub_pcs',
            'sub_gw',
            'sub_ct',
            'metal_purity',
            'loss',
            'tunch',
            'packet',
            'rate',
            'value',
            'fine_wt',  # Computed property
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

class PurchaseReturnItemsSerializer(serializers.ModelSerializer):
    # Fields related to PurchaseReturnItems model
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code", required=True)
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", required=False)

    # Nested Serializer for PurchaseReturnDetails
    purchasereturndetails_set = PurchaseReturnDetailsSerializer(many=True)

    class Meta:
        model = PurchaseReturnItems
        fields = [
            'id',
            'sl_no',
            'item',
            'pcs',
            'gw',
            'purity',
            'making_type',
            'making_value',
            'making',
            'remarks',
            'purchasereturndetails_set',  # Nested details serializer
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

    def create(self, validated_data):
        details_data = validated_data.pop('purchasereturndetails_set')
        purchase_return_item_instance = PurchaseReturnItems.objects.create(**validated_data)
        
        # Create related PurchaseReturnDetails instances
        for detail_data in details_data:
            PurchaseReturnDetails.objects.create(main_item=purchase_return_item_instance, **detail_data)
        
        return purchase_return_item_instance
    
    def update(self, instance, validated_data):
        detail_data = validated_data.pop('purchasereturndetails_set', [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        create_or_update_nested(PurchaseReturnDetailsSerializer, instance, 'purchasereturndetails_set',  'main_item',PurchaseReturnDetailsSerializer(detail_data,many=True).data)
        return instance


class PurchaseReturnSerializer(serializers.ModelSerializer):
    # Fields related to PurchaseReturn model
    ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    pv_billno = serializers.CharField(write_only=True)
    # Nested Serializer for PurchaseReturnItems
    purchasereturnitems_set = PurchaseReturnItemsSerializer(many=True)

    class Meta:
        model = PurchaseReturn
        fields = [
            'id',
            'billno',
            'pv_billno',
            'date1',
            'ldgr',
            'ldgr_name',
            'discount',
            'cgst_amt',
            'sgst_amt',
            'igst_amt',
            'tcs_amt',
            'narration',
            'mode_of_transport',
            'total_incl_tax',  # Computed property
            'purchasereturnitems_set',  # Nested items serializer
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }
    def create(self, validated_data):
        items_data = validated_data.pop('purchasereturnitems_set')
        purchase_return_instance = PurchaseReturn.objects.create(**validated_data)
        
        # Create related PurchaseReturnItems instances
        item_instances = []
        item_detail_instances = []
        for item_data in items_data:
            details_data = item_data.pop('purchasereturndetails_set')
            purchase_return_item_instance = PurchaseReturnItems.objects.create(billno=purchase_return_instance, **item_data)
            item_instances.append(purchase_return_item_instance)
            # Create related PurchaseReturnDetails instances
            for detail_data in details_data:
                ret_item = PurchaseReturnDetails.objects.create(main_item=purchase_return_item_instance, **detail_data)
                item_detail_instances.append(ret_item)
        print(item_instances)
        ser = JournalEntrySerializer(data= {'date':purchase_return_instance.date1.strftime('%Y-%m-%d'),
                "voucher_no":generate_voucher_no(global_vars.VoucherType.purc_ret, self.context.get('request').retail),
                "narration":f"Purchase Return Narration",
                "voucher_type":global_vars.VoucherType.purc_ret,
                "retail":self.context.get('request').retail.id,
                "voucher_details": [
                    {   
                        'account':"INPUT CGST", 
                        
                        'credit':f"{purchase_return_instance.cgst_amt:.2f}"
                    },
                    {'account':"INPUT SGST", 
                        
                        'credit':f"{purchase_return_instance.sgst_amt:.2f}"
                    },
                    {'account':"INPUT IGST", 
                        
                        'credit':f"{purchase_return_instance.igst_amt:.2f}"
                    },
                    {'account':"Hallmarking/Testing Charges", 
                        
                        'credit':f"{purchase_return_instance.hallmark_charge:.2f}" if purchase_return_instance.hallmark_charge else '0.0'
                    },
                    {'account':"Carriage Inward", 
                        
                        'credit':f"{purchase_return_instance.freight_amt:.2f}"if purchase_return_instance.freight_amt else '0.0'
                    },
                        {'account':"Discount/Round Off", 
                        
                        'credit':f"{purchase_return_instance.round_off:.2f}"if purchase_return_instance.round_off else '0.0'
                    },
                ] + 
                [{'account':"Making Charge Purchase", 
                    
                    'credit':f"{item.making_value:.2f}" if item.making_value else '0.0'
                } for item in item_instances] +
                [{'account':item.sub_item.sale_ledger.ac_name, 
                    
                    'credit':f"{item.value:.2f}"
                } for item in item_detail_instances]  +
                [{   
                    'account':purchase_return_instance.ldgr.ac_name, 
                    'debit':f"{(purchase_return_instance.bill_value ):.2f}" if purchase_return_instance.bill_value else '0.0',
                    
                }]},
                context=self.context)

        if ser.is_valid(raise_exception=True):
            
            ref = ser.save()
        purchase_return_instance.ac_voucher = ref
        purchase_return_instance.save()
        return purchase_return_instance

    def update(self, instance, validated_data):
        detail_data = validated_data.pop('purchasereturnitems_set', [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        create_or_update_nested(PurchaseReturnItemsSerializer, instance, 'purchasereturnitems_set',  'billno',PurchaseReturnItemsSerializer(detail_data,many=True).data)
        purchase_return_instance = instance
        instance.ac_voucher.delete()
        item_instances = []
        item_detail_instances = []
        for item_data in instance.purchasereturnitems_set.all():
            item_instances.append(item_data)
            for detail in item_data.purchasereturndetails_set.all():
                item_detail_instances.append(detail)
        print(item_instances)
        ser = JournalEntrySerializer(data= {'date':purchase_return_instance.date1.strftime('%Y-%m-%d'),
                "voucher_no":generate_voucher_no(global_vars.VoucherType.purc_ret, self.context.get('request').retail),
                "narration":f"Purchase Return Narration",
                "voucher_type":global_vars.VoucherType.purc_ret,
                "retail":self.context.get('request').retail.id,
                "voucher_details": [
                    {   
                        'account':"INPUT CGST", 
                        
                        'credit':f"{purchase_return_instance.cgst_amt:.2f}"
                    },
                    {'account':"INPUT SGST", 
                        
                        'credit':f"{purchase_return_instance.sgst_amt:.2f}"
                    },
                    {'account':"INPUT IGST", 
                        
                        'credit':f"{purchase_return_instance.igst_amt:.2f}"
                    },
                    {'account':"Hallmarking/Testing Charges",
                        
                        'credit':f"{purchase_return_instance.hallmark_charge:.2f}" if purchase_return_instance.hallmark_charge else '0.0'
                    },
                    {'account':"Carriage Inward", 
                        
                        'credit':f"{purchase_return_instance.freight_amt:.2f}"if purchase_return_instance.freight_amt else '0.0'
                    },
                        {'account':"Discount/Round Off", 
                        
                        'credit':f"{purchase_return_instance.round_off:.2f}"if purchase_return_instance.round_off else '0.0'
                    },
                ] + 
                [{'account':"Making Charge Purchase",  
                    
                    'credit':f"{item.making_value:.2f}" if item.making_value else '0.0'
                } for item in item_instances] +
                [{'account':item.sub_item.sale_ledger.ac_name, 
                    
                    'credit':f"{item.value:.2f}"
                } for item in item_detail_instances]  +
                [{   
                    'account':purchase_return_instance.ldgr.ac_name, 
                    'debit':f"{(purchase_return_instance.bill_value ):.2f}" if purchase_return_instance.bill_value else '0.0',
                    
                }]},
                context=self.context)

        if ser.is_valid(raise_exception=True):
            
            ref = ser.save()
        purchase_return_instance.ac_voucher = ref
        purchase_return_instance.save()
        return purchase_return_instance

class PurchaseVoucherDetailsSerializer(serializers.ModelSerializer):
    sub_item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code", required=True)
    metal_purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity",allow_null=True, required=False)
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(), slug_field="pckt_no", required=False, allow_null=True,)

    class Meta:
        model = PurchaseVoucherDetails
        fields = [
            'id',
            'date1',
            'sub_item',
            'sub_pcs',
            'sub_gw',
            'sub_ct',
            'metal_purity',
            'loss',
            'tunch',
            'fine_wt',
            'packet',
            'rate',
            'value',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'sub_pcs': {'required': False, 'allow_null': True},
        }

class PurchaseVoucherItemsSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code", required=True)
    barcode = serializers.SlugRelatedField(queryset=BarcodeMain.objects.all(), slug_field="barcode", required=False,allow_null=True)
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", required=False)
    order_no = serializers.SlugRelatedField(queryset=CustomerOrder.objects.all(), slug_field="order_no", required=False,allow_null=True)

    # Nested serializer for details
    purchasevoucherdetails_set = PurchaseVoucherDetailsSerializer(many=True,)

    class Meta:
        model = PurchaseVoucherItems
        fields = [
            'id',
            'date',
            'po_no',
            'po_sl_no',
            'item',
            'barcode',
            'barcode_txt',
            'order_no',
            'sl_no',
            'pcs',
            'gw',
            'size',
            'purity',
            'pending_pcs',
            'pending_gw',
            'making_type',
            'making_value',
            'item_value',
            'remarks',
            'purchasevoucherdetails_set',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

    def validate(self, data):
        details = data.get('purchasevoucherdetails_set', [])
        if details:
            from decimal import Decimal
            gw = Decimal(str(data.get('gw', 0) or 0))
            total_sub_gw = sum(Decimal(str(d.get('sub_gw', 0) or 0)) for d in details)
            if abs(total_sub_gw - gw) > Decimal('0.01'):
                raise ValidationError(
                    f"Sub-item GW total ({total_sub_gw:.3f}g) does not match item GW ({gw:.3f}g). Please reconcile."
                )
        return data

    def create(self, validated_data):
        details_data = validated_data.pop('purchasevoucherdetails_set')
        voucher_item_instance = PurchaseVoucherItems.objects.create(**validated_data)

        # Create related PurchaseVoucherDetails instances
        for detail_data in details_data:
            PurchaseVoucherDetails.objects.create(main_item=voucher_item_instance, **detail_data)

        return voucher_item_instance

    def update(self, instance, validated_data):
        detail_data = validated_data.pop('purchasevoucherdetails_set', [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        create_or_update_nested(PurchaseVoucherDetailsSerializer, instance, 'purchasevoucherdetails_set',  'main_item',PurchaseVoucherDetailsSerializer(detail_data,many=True).data)
        return instance
from rest_framework.exceptions import ValidationError
class PurchaseVoucherPostSerializer(serializers.ModelSerializer):

    # Nested serializer for items
    purchasevoucheritems_set = PurchaseVoucherItemsSerializer(many=True)
    place_of_supply = serializers.SlugRelatedField(queryset=State.objects.all(), slug_field="code", required=False,allow_null=True)
    class Meta:
        model = PurchaseVoucher
        fields = [
            'id',
            'date1',
            'billno',
            'voucher_type',
            'ref_no',
            'hallmark_charge',
            'ref_date',
            'place_of_supply',
            'ldgr',
            'ldgr_name',
            'item_total',
            'discount_amt',
            'round_off',
            'add_chrg_cap1',
            'add_chrg_cap2',
            'add_chrg_amt1',
            'add_chrg_amt2',
            'freight_amt',
            'cgst',
            'sgst',
            'igst',
            'tcs_amt',
            'tds_section',
            'tds_rate',
            'tds_taxable_value',
            'tds_amt',
            'narration',
            'total_incl_gst',
            'bill_value',
            'pos_name',
            'due_amt',
            'is_return',
            'purchasevoucheritems_set',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }
    def create(self, validated_data):
        with transaction.atomic():
            items_data = validated_data.pop('purchasevoucheritems_set')
            purchase_voucher_instance = PurchaseVoucher.objects.create(**validated_data)

            # Create related PurchaseVoucherItems instances
            item_detail_instances = []
            item_instances = []
            for item_data in items_data:
                details_data = item_data.pop('purchasevoucherdetails_set')
                voucher_item_instance = PurchaseVoucherItems.objects.create(billno=purchase_voucher_instance, **item_data)
                item_instances.append(voucher_item_instance)
                # Create related PurchaseVoucherDetails instances
                for detail_data in details_data:
                    det = PurchaseVoucherDetails.objects.create(main_item=voucher_item_instance, **detail_data)
                    item_detail_instances.append(det)
            
            ser = JournalEntrySerializer(data= {'date':purchase_voucher_instance.date1.strftime('%Y-%m-%d'),
                            "voucher_no":generate_voucher_no(global_vars.VoucherType.purc_sc, self.context.get('request').retail),
                            "narration":f"Purchase Voucher Narration",
                            "voucher_type":global_vars.VoucherType.purc_sc,
                            "retail":self.context.get('request').retail.id,
                            "voucher_details": [
                                {   
                                    'account':"INPUT CGST", 
                                    
                                    'debit':f"{purchase_voucher_instance.cgst:.2f}"
                                },
                                {'account':"INPUT SGST", 
                                    
                                    'debit':f"{purchase_voucher_instance.sgst:.2f}"
                                },
                                {'account':"INPUT IGST", 
                                    
                                    'debit':f"{purchase_voucher_instance.igst:.2f}"
                                },
                                {'account':"Hallmarking/Testing Charges", 
                                    
                                    'debit':f"{purchase_voucher_instance.hallmark_charge:.2f}" if purchase_voucher_instance.hallmark_charge else'0.0'
                                },
                                {'account':"Carriage Inward", 
                                    
                                    'debit':f"{purchase_voucher_instance.freight_amt:.2f}"
                                },
                                {'account':"Discount/Round Off", 
                                    
                                  'credit': f"{(purchase_voucher_instance.round_off + purchase_voucher_instance.discount_amt):.2f}" },
                            ] + 
                            [{'account':"Making Charge Purchase", 
                                
                                'debit':f"{item.making_value:.2f}"if item.making_value else'0.0'
                            } for item in item_instances] +
                            [{'account':item.sub_item.sale_ledger.ac_name if item.sub_item.sale_ledger != None else  (_ for _ in ()).throw(ValidationError(f"{item.sub_item} has no sale ledger")),

                                'debit':f"{item.value:.2f}"
                            } for item in item_detail_instances]  +
                            (
                                [{
                                    'account':purchase_voucher_instance.ldgr.ac_name,
                                    'credit':f"{(purchase_voucher_instance.bill_value - (purchase_voucher_instance.tds_amt or 0)):.2f}" if purchase_voucher_instance.bill_value else '0.0',
                                }] +
                                ([{
                                    'account': purchase_voucher_instance.tds_section.ledger.ac_name if purchase_voucher_instance.tds_section.ledger else f"TDS Payable u/s {purchase_voucher_instance.tds_section.section_code}",
                                    'credit': f"{purchase_voucher_instance.tds_amt:.2f}",
                                }] if purchase_voucher_instance.tds_amt and purchase_voucher_instance.tds_amt > 0 and purchase_voucher_instance.tds_section else [])
                            )},
                            context=self.context)

            if ser.is_valid(raise_exception=True):

                ref = ser.save()

            purchase_voucher_instance.ac_voucher = ref

            purchase_voucher_instance.save()
            return purchase_voucher_instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('purchasevoucheritems_set', [])
            ac_voucher_data = validated_data.pop("ac_voucher", None)
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(PurchaseVoucherItemsSerializer, instance, 'purchasevoucheritems_set',  'billno',PurchaseVoucherItemsSerializer(detail_data,many=True).data)
            item_instances = []
            item_detail_instances = []
            for item_data in instance.purchasevoucheritems_set.all():
                item_instances.append(item_data)
                for detail in item_data.purchasevoucherdetails_set.all():
                    item_detail_instances.append(detail)
            if instance.ac_voucher:
                instance.ac_voucher.delete()

            purchase_voucher_instance = instance
            ser = JournalEntrySerializer(data= {'date':purchase_voucher_instance.date1.strftime('%Y-%m-%d'),
                            "voucher_no":generate_voucher_no(global_vars.VoucherType.purc_sc, self.context.get('request').retail),
                            "narration":f"Purchase Voucher Narration",
                            "voucher_type":global_vars.VoucherType.purc_sc,
                            "retail":self.context.get('request').retail.id,
                            "voucher_details": [
                                {   
                                    'account':"INPUT CGST", 
                                    
                                    'debit':f"{purchase_voucher_instance.cgst:.2f}"
                                },
                                {'account':"INPUT SGST", 
                                    
                                    'debit':f"{purchase_voucher_instance.sgst:.2f}"
                                },
                                {'account':"INPUT IGST", 
                                    
                                    'debit':f"{purchase_voucher_instance.igst:.2f}"
                                },
                                {'account':"Hallmarking/Testing Charges", 
                                    
                                    'debit':f"{purchase_voucher_instance.hallmark_charge:.2f}" if purchase_voucher_instance.hallmark_charge else'0.0'
                                },
                                {'account':"Carriage Inward", 
                                    
                                    'debit':f"{purchase_voucher_instance.freight_amt:.2f}"
                                },
                                {'account':"Discount/Round Off",

                                    'credit': f"{(purchase_voucher_instance.round_off + purchase_voucher_instance.discount_amt):.2f}"
                                },
                            ] + 
                            [{'account':"Making Charge Purchase", 
                                
                                'debit':f"{item.making_value:.2f}"if item.making_value else'0.0'
                            } for item in item_instances] +
                            [{'account':item.sub_item.sale_ledger.ac_name,

                                'debit':f"{item.value:.2f}"
                            } for item in item_detail_instances]  +
                            (
                                [{
                                    'account':purchase_voucher_instance.ldgr.ac_name,
                                    'credit':f"{(purchase_voucher_instance.bill_value - (purchase_voucher_instance.tds_amt or 0)):.2f}" if purchase_voucher_instance.bill_value else '0.0',
                                }] +
                                ([{
                                    'account': purchase_voucher_instance.tds_section.ledger.ac_name if purchase_voucher_instance.tds_section.ledger else f"TDS Payable u/s {purchase_voucher_instance.tds_section.section_code}",
                                    'credit': f"{purchase_voucher_instance.tds_amt:.2f}",
                                }] if purchase_voucher_instance.tds_amt and purchase_voucher_instance.tds_amt > 0 and purchase_voucher_instance.tds_section else [])
                            )},
                            context=self.context)

            if ser.is_valid(raise_exception=True):

                ref = ser.save()

            purchase_voucher_instance.ac_voucher = ref
            purchase_voucher_instance.save()
            return purchase_voucher_instance
                
class PurchaseOrderItemsForPostSerializer(serializers.ModelSerializer):
    customer_order_item = serializers.PrimaryKeyRelatedField(queryset=CustomerOrderItems.objects.all(), required=False, allow_null=True)
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity")
    due_date = serializers.DateField(required=False, allow_null=True)
    
    class Meta:
        model = PurchaseOrderItems
        fields = [
            'id',
            'po_sl_no',
            'customer_order_item',
            'item',
            'purity',
            'pcs',
            'approx_wt',
            'design_code',
            'size',
            'due_date',
            'remarks',
            'rec_status',
        ]

class PurchaseOrderForPostSerializer(serializers.ModelSerializer):
    ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    place_of_supply = serializers.ChoiceField(choices=STATES_OF_INDIA, required=False)
    purchaseorderitems_set = PurchaseOrderItemsForPostSerializer(many=True,)
    class Meta:
        model = PurchaseOrder
        fields = [
            'id',
            'date1',
            'po_type',
            'po_no',
            'ldgr',
            'ldgr_name',
            'retail',
            'place_of_supply',
            'purchaseorderitems_set'
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

    def create(self, validated_data):
        with transaction.atomic():
            
            items_data = validated_data.pop('purchaseorderitems_set')
            purchase_order_instance = PurchaseOrder.objects.create(**validated_data)

            # Create related PurchaseVoucherItems instances
            for item_data in items_data:
                PurchaseOrderItems.objects.create(po_slip=purchase_order_instance, **item_data)

            return purchase_order_instance
        
    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('purchaseorderitems_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(PurchaseOrderItemsForPostSerializer, instance, 'purchaseorderitems_set',  'po_slip',PurchaseOrderItemsForPostSerializer(detail_data,many=True).data)
            return instance

class PurchaseVoucherDetailsToReturnDetailsSerializer(PurchaseVoucherDetailsSerializer):
    def to_representation(self, instance):
        repr = super().to_representation(instance)
        return repr
    
class PurchaseVoucherItemToReturnSerializer(PurchaseVoucherItemsSerializer):
    purchasevoucherdetails_set = PurchaseVoucherDetailsToReturnDetailsSerializer(many=True)
    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr['purchasereturndetails_set'] = repr["purchasevoucherdetails_set"]
        del repr["purchasevoucherdetails_set"]
        return repr

class PurchaseAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import PurchaseAttachment
        model = PurchaseAttachment
        fields = ['id', 'purchase', 'file', 'original_name', 'uploaded_at']
        read_only_fields = ['original_name', 'uploaded_at']

    def validate(self, data):
        purchase = data.get('purchase') or (self.instance and self.instance.purchase)
        if purchase and purchase.attachments.count() >= 3:
            raise ValidationError("Maximum 3 attachments allowed per purchase voucher.")
        return data

    def create(self, validated_data):
        file = validated_data['file']
        validated_data['original_name'] = file.name
        return super().create(validated_data)


class PurchaseVoucherToReturnSerializer(PurchaseVoucherPostSerializer):
    purchasevoucheritems_set =  PurchaseVoucherItemToReturnSerializer(many=True)
    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr['ldgr'] = repr['ldgr']
        repr['discount'] =  repr['discount_amt']
        repr['cgst_amt'] =  repr['cgst']
        repr['sgst_amt'] =  repr['sgst']
        repr['igst_amt'] =  repr['igst']
        repr['purchasereturnitems_set'] = repr['purchasevoucheritems_set']
        del repr['purchasevoucheritems_set']
        del repr['narration']
        del repr['date1']
        return repr
