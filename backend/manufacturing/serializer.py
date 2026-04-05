from rest_framework.serializers import ModelSerializer

from accounting.models import Account
from accounting.serializers import JournalEntrySerializer
from accounting.utils import generate_voucher_no
from global_vars import VoucherType
import global_vars
from inventory.models import BarcodeMain, BarcodeTransaction
from inventory.serializer import UnBarcodedMainSerializer
from manufacturing.utils import create_or_update_nested
from purchase.serializer import PurchaseOrderItemsSerializer, PurchaseOrderSerializer
from .models import HallmarkIssue, HallmarkIssueDetails, HallmarkIssueItem, HallmarkReceive, HallmarkReceiveDetails, HallmarkReceiveItem, KarigarGoldIssueHeader, KarigarMaster,KarigarIssueItem,KarigarIssue, KarigarReceive, KarigarReceiveItem, KarigarReceiveItemDetails, KarigarStoneIssueHeader, KarigarStoneReceive, KarigarStoneReceiveHeader, RefinaryIssue, RefinaryIssueDetail, RefinaryReceive, RefinaryReceiveDetail, RepairJobCard, RepairStone, RepairLoss, RepairKarigarLink

from rest_framework import serializers
from django.utils.dateparse import parse_date
from .models import KarigarIssue, KarigarIssueItem ,KarigarGoldIssue
from  sales.models import  CustomerOrderItems
from mastersconfig.models import  Item, Packet, RetailMaster
from contacts.models import Ledger
from goldrates.models import PurityMaster
from .models import KarigarStoneIssue
from django.contrib.contenttypes.models import ContentType
from django.db import transaction



class KarigarStoneIssueDetailSerializer(serializers.ModelSerializer):
    job_sl_content_type = serializers.SlugRelatedField(
        queryset=ContentType.objects.all(), slug_field='model'
    )
    job_sl_object_id = serializers.IntegerField()
    ref_job_content_type = serializers.SlugRelatedField(
        queryset=ContentType.objects.all(), slug_field='model'
    )
    ref_job_object_id = serializers.IntegerField()
    item = serializers.SlugRelatedField(
        queryset=Item.objects.all(), slug_field='item_name'
    )
    packet = serializers.SlugRelatedField(
        queryset=Packet.objects.all(), slug_field='pckt_no'
    )


    class Meta:
        model = KarigarStoneIssue
        fields = [
            'id', "job_sl_content_type", "job_sl_object_id",
            "ref_job_content_type", "ref_job_object_id", "sl_no",
            "item", "pcs", "ct", "gw", "cgst", "sgst", "igst",
            "rate", "taxable_value", "tot_val", "packet",
            "remarks", "place_of_supply"
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

class KarigarStoneIssueSerializer(serializers.ModelSerializer):
    karigar_ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    karigarstoneissue_set = KarigarStoneIssueDetailSerializer(many=True)

    class Meta:
        model = KarigarStoneIssueHeader
        fields = ['id',"billno", "date1", "karigar_ldgr","karigar_ldgr_name", "slip_type", "karigarstoneissue_set"]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            "karigar_ldgr_name" : {'read_only':True}
        }
    def create(self, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('karigarstoneissue_set', [])
            parent_instance = KarigarStoneIssueHeader.objects.create(**validated_data)
            create_or_update_nested(
                KarigarStoneIssueDetailSerializer, parent_instance, 
                'karigarstoneissue_set', 'header',
                KarigarStoneIssueDetailSerializer(detail_data, many=True).data
            )
            return parent_instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('karigarstoneissue_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(
                KarigarStoneIssueDetailSerializer, instance, 
                'karigarstoneissue_set',  'billno',KarigarStoneIssueDetailSerializer(detail_data,many=True).data
            )
            return instance


class KarigarStoneIssueGetSerializer(serializers.ModelSerializer):
    ref_job_no = serializers.SerializerMethodField()
    job_sl_no = serializers.SerializerMethodField()

    class Meta:
        model = KarigarStoneIssue
        fields = [
            'id', 'billno', 'date1', 'karigar_ldgr', 'slip_type', 
            'ref_job_content_type', 'ref_job_object_id', 'ref_job_no', 
            'job_sl_content_type', 'job_sl_object_id', 'job_sl_no', 
            'sl_no', 'item', 'pcs', 'ct', 'gw', 'cgst', 'sgst', 
            'igst', 'rate', 'taxable_value', 'tot_val', 'packet', 
            'remarks', 'place_of_supply',
        ]

    def get_ref_job_no(self, obj):
        return self._get_generic_related_object(obj.ref_job_content_type, obj.ref_job_object_id)

    def get_job_sl_no(self, obj):
        return self._get_generic_related_object(obj.job_sl_content_type, obj.job_sl_object_id)

    def _get_generic_related_object(self, content_type, object_id):
        """
        Dynamically resolve and serialize the related object.
        """
        model_class = content_type.model_class()
        related_object = model_class.objects.filter(id=object_id).first()

        if related_object:
            
            if content_type.model == "karigarissue":
                return KarigarIssueSerializer(related_object).data
            if content_type.model == "karigarissueitem":
                return KarigarIssueItemSerializer(related_object).data
            if content_type.model == "purchaseorder":
                return PurchaseOrderSerializer(related_object).data
            if content_type.model == "purchaseorderitems":
                return PurchaseOrderItemsSerializer(related_object).data
            
              # Example: Define a `to_dict` method in related models
        return None



class KarigarStoneReceiveDetailSerializer(serializers.ModelSerializer):
    job_sl_content_type = serializers.SlugRelatedField(
        queryset=ContentType.objects.all(), slug_field='model'
    )
    job_sl_object_id = serializers.IntegerField()
    ref_job_content_type = serializers.SlugRelatedField(
        queryset=ContentType.objects.all(), slug_field='model'
    )
    ref_job_object_id = serializers.IntegerField()
    item = serializers.SlugRelatedField(
        queryset=Item.objects.all(), slug_field='short_code'
    )
    packet = serializers.SlugRelatedField(
        queryset=Packet.objects.all(), slug_field='pckt_no'
    )
  
    class Meta:
        model = KarigarStoneReceive
        fields = [
            'id',"job_sl_content_type", "job_sl_object_id",
            "ref_job_content_type", "ref_job_object_id", "sl_no",
            "item", "return_pcs", "return_ct", "return_gw",
            "broken_pcs", "broken_ct", "broken_gw",
            "loss_pcs", "loss_ct", "loss_gw",
            "cgst", "sgst", "igst", "rate", "taxable_value", "tot_val",
            "packet", "place_of_supply",'item_name'
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

class KarigarStoneReceiveSerializer(serializers.ModelSerializer):
    karigar_ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    karigarstonereceive_set = KarigarStoneReceiveDetailSerializer(many=True)

    class Meta:
        model = KarigarStoneReceiveHeader
        fields = ['id',"billno", "date1", "karigar_ldgr","karigar_ldgr_name", "karigarstonereceive_set"]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            "karigar_ldgr_name":{'read_only':True}
                    }
    def create(self, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('karigarstonereceive_set', [])
            parent_instance = KarigarStoneReceiveHeader.objects.create(**validated_data)
            create_or_update_nested(
                KarigarStoneReceiveDetailSerializer, parent_instance, 
                'karigarstonereceive_set', 'header',
                KarigarStoneReceiveDetailSerializer(detail_data, many=True).data
            )
            return parent_instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('karigarstonereceive_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(
            KarigarStoneReceiveDetailSerializer, instance, 
                'karigarstonereceive_set',  'billno',KarigarStoneReceiveDetailSerializer(detail_data,many=True).data
            )
            return instance


class KarigarGoldIssueDetailSerializer(serializers.ModelSerializer):
    job_sl_content_type = serializers.SlugRelatedField(
        queryset=ContentType.objects.all(), slug_field="model"
    )
    job_sl_object_id = serializers.IntegerField()
    ref_job_content_type = serializers.SlugRelatedField(
        queryset=ContentType.objects.all(), slug_field="model"
    )
    ref_job_object_id = serializers.IntegerField()

    conv_purity = serializers.SlugRelatedField(
        queryset=PurityMaster.objects.all(), slug_field="purity"
    )
    # metal_purity is now optional — use custom_purity_per for free-form purity percentages
    metal_purity = serializers.SlugRelatedField(
        queryset=PurityMaster.objects.all(), slug_field="purity",
        allow_null=True, required=False
    )
    custom_purity_per = serializers.DecimalField(
        max_digits=6, decimal_places=3, allow_null=True, required=False,
        help_text="Free-form purity % (e.g. 99.2). Used when metal_purity is not in master."
    )

    item = serializers.SlugRelatedField(
        queryset=Item.objects.all(), slug_field="short_code"
    )

    def validate(self, data):
        metal_purity = data.get('metal_purity')
        custom_purity_per = data.get('custom_purity_per')
        if not metal_purity and not custom_purity_per:
            raise serializers.ValidationError(
                "Either metal_purity (predefined) or custom_purity_per (free-form %) must be provided."
            )
        return data

    class Meta:
        model = KarigarGoldIssue
        fields = [
            "id",
            "job_sl_content_type", "job_sl_object_id",
            "ref_job_content_type", "ref_job_object_id", "sl_no",
            "item", "item_gw", "alloy_wt", "conv_wt",
            "metal_purity", "custom_purity_per", "conv_purity", "remarks"
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'karigar_ldgr_name': {'read_only': True},
        }

class KarigarGoldIssueSerializer(serializers.ModelSerializer):
    karigar_ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    karigargoldissue_set = KarigarGoldIssueDetailSerializer(many=True)

    class Meta:
        model = KarigarGoldIssueHeader
        fields = ["id","billno", "date1", "slip_type", "karigar_ldgr","karigar_ldgr_name", "karigargoldissue_set"]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'karigar_ldgr_name':{'read_only': True,}
        }
    def create(self, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop("karigargoldissue_set", [])
            parent_instance = KarigarGoldIssueHeader.objects.create(**validated_data)
            create_or_update_nested(
                KarigarGoldIssueDetailSerializer, parent_instance, 
                "karigargoldissue_set", "header",
                KarigarGoldIssueDetailSerializer(detail_data, many=True).data
            )
            return parent_instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop("karigargoldissue_set", [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(
                    KarigarGoldIssueDetailSerializer, instance, 
                    "karigargoldissue_set", "header",
                    KarigarGoldIssueDetailSerializer(detail_data, many=True).data
            )
            return instance

class KarigarIssueItemForPostSerializer(serializers.ModelSerializer):

    customer_order_item = serializers.PrimaryKeyRelatedField(
        queryset=CustomerOrderItems.objects.all(),
        many=False,
        allow_null=True,
        required=False,
    )
    item = serializers.SlugRelatedField(
        queryset=Item.objects.all(),
        slug_field="short_code"
    )
    
    purity = serializers.SlugRelatedField(
        queryset=PurityMaster.objects.all(),
        slug_field='purity'
    )
    due_date = serializers.DateField(required=False, allow_null=True)
    source_receive_item = serializers.PrimaryKeyRelatedField(
        queryset=KarigarReceiveItem.objects.all(),
        allow_null=True,
        required=False,
        help_text="Set when re-issuing a semi-finished item received from a previous karigar"
    )

    class Meta:
        model = KarigarIssueItem
        fields = [
            'id',
            'issue_sl_no',
            'customer_order_item',
            'source_receive_item',
            'item',
            'purity',
            'pcs',
            'approx_wt',
            'design_code',
            'issued_sample_items',
            'size',
            'due_date',
            'remarks',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

    def create(self, validated_data):
        with transaction.atomic():
            sample_issues = validated_data.pop("issued_sample_items")
            inst = KarigarIssueItem.objects.create(
                **validated_data,
            )
            inst.issued_sample_items.set(sample_issues)

            return inst

    def update(self, instance, validated_data):
        with transaction.atomic():
            sample_issues = validated_data.pop("issued_sample_items")
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            instance.issued_sample_items.set(sample_issues)

            return instance
            

class KarigarIssueItemForUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = KarigarIssueItem
        exclude = ["sketch"]

class KarigarIssueForPostSerializer(serializers.ModelSerializer):
    items = KarigarIssueItemForPostSerializer(many=True,)
    karigar_ldgr = serializers.PrimaryKeyRelatedField(
    queryset=Ledger.objects.all(),
    )
    

    class Meta:
        model = KarigarIssue
        fields = [
            'id',
            'date1',
            'issue_slip_type',
            'issue_slip_no',
            'karigar_ldgr',
            'items',
            'retail',
            'karigar_ldgr_name'
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'karigar_ldgr_name' :{'read_only':True}
        }     
   

    def create(self, validated_data):
        items_data = validated_data.pop('items')
    
        with transaction.atomic():
            karigar_issue_instance = KarigarIssue.objects.create(**validated_data,bill_id=int( validated_data['issue_slip_no'].split('/')[-1]))

            for item_data in items_data:
                sample_issues = item_data.pop("issued_sample_items")
                inst = KarigarIssueItem.objects.create(
                    issue_slip=karigar_issue_instance,
                    **item_data,
                )
                inst.issued_sample_items.set(sample_issues)

        return karigar_issue_instance

    def update(self,instance,validated_data):
        with transaction.atomic():
            
            detail_data = validated_data.pop('items', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(KarigarIssueItemForPostSerializer, instance, 'items','issue_slip',KarigarIssueItemForPostSerializer(detail_data,many=True).data)
            return instance

class KarigarMasterSerializer(ModelSerializer):
    karigar_name = serializers.CharField(source='karigar.ac_name', read_only=True, default='')
    item_name    = serializers.CharField(source='item.item_name',  read_only=True, default='')
    purity_name  = serializers.CharField(source='purity.purity',   read_only=True, default='')
    item_code    = serializers.CharField(source='item.short_code',  read_only=True, default='')

    class Meta:
        model  = KarigarMaster
        fields = [
            'id', 'karigar', 'karigar_name', 'kr_code',
            'item', 'item_name', 'item_code',
            'purity', 'purity_name',
            'making_per_gm', 'making_per_pc', 'loss_rate',
            'retail',
        ]


class KarigarIssueItemSerializer(ModelSerializer): #model a
    class Meta:
        model = KarigarIssueItem
        depth = 3
        fields = [
            "customer_order_item","design_code",]  # Include relevant fields from ModelA



class KarigarIssueSerializer(ModelSerializer): #model b
    items = KarigarIssueItemSerializer(many=True)  # Nest the ModelA serializer
    class Meta:
        model = KarigarIssue
        fields = "__all__"  # Include relevant fields from ModelB
        depth = 2
        
class KarigarIssueforJobsSerializer(ModelSerializer): #model b

    class Meta:
        model = KarigarIssue
        fields = "__all__"  # Include relevant fields from ModelB
    



class KarigarReceiveItemDetailsForPostSerializer(serializers.ModelSerializer):
    # Fields related to KarigarReceiveItemDetails model
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    metal_purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", required=False,allow_null=True)
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(),  slug_field="pckt_no",required=False,allow_null=True)
    main_sl_no = serializers.PrimaryKeyRelatedField(queryset=KarigarReceiveItem.objects.all(),required=False)
    receive_slip_no = serializers.PrimaryKeyRelatedField(queryset=KarigarReceive.objects.all(),required=False)

    class Meta:
        model = KarigarReceiveItemDetails
        fields = [
            'main_sl_no',
            'receive_slip_no',
            'id',
            'sl_no',
            'item',
            'metal_purity',
            'packet',
            'issue_pcs',
            'issue_ct',
            'issue_gw',
            'broken_pcs',
            'broken_ct',
            'broken_gw',
            'return_pcs',
            'return_ct',
            'return_gw',
            'balance_pcs',
            'balance_ct',
            'balance_gw',
            'rate',
            'amt',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

class KarigarReceiveItemSerializer(serializers.ModelSerializer):
    karigarreceiveitemdetails_set = KarigarReceiveItemDetailsForPostSerializer(many=True)
    class Meta:
        model = KarigarReceiveItem
        depth = 3
        fields = "__all__"


class KarigarReceiveSerializer(serializers.ModelSerializer):
    karigarreceiveitem_set = KarigarReceiveItemSerializer(many=True)

    class Meta:
        model = KarigarReceive
        depth = 1
        fields = "__all__"


class KarigarReceiveItemForGetSerializer(serializers.ModelSerializer):
    # Fields related to KarigarReceiveItem model
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field='short_code')
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field='purity')
    ref_job_sl_no = serializers.IntegerField()
    ref_job_no = serializers.IntegerField()
    finish_status = serializers.BooleanField()
    hallmark_status = serializers.BooleanField()
    sample_issued_items = UnBarcodedMainSerializer(many=True)

    # Nested Serializer for KarigarReceiveItemDetails
    details = serializers.JSONField()

    class Meta:
        model = KarigarReceiveItem
        fields = [
            "id",
            "ref_job_no",
            "ref_job_sl_no",
            'sample_issued_items',
            'item',
            'purity',
            'pcs',
            'gw',
            'pending_pcs',
            'pending_gw',
            'finish_status',
            'hallmark_status',
            'details',  # Nested details serializer
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

class KarigarReceiveItemForPostSerializer(serializers.ModelSerializer):
    # Fields related to KarigarReceiveItem model
    ref_job_no = serializers.PrimaryKeyRelatedField(queryset=KarigarIssue.objects.all())
    ref_job_sl_no = serializers.PrimaryKeyRelatedField(queryset=KarigarIssueItem.objects.all())
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field='short_code')
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field='purity')
    receive_slip_no = serializers.PrimaryKeyRelatedField(queryset=KarigarReceive.objects.all(),required=False)
    sample_issued_items = UnBarcodedMainSerializer(many=True, source="ref_job_sl_no.issued_sample_items", read_only=True)
    # Nested Serializer for KarigarReceiveItemDetails
    details = KarigarReceiveItemDetailsForPostSerializer(many=True,source="karigarreceiveitemdetails_set")

    class Meta:
        model = KarigarReceiveItem
        fields = [
            'id',
            'receive_slip_no',
            'date1',
            'sl_no',
            'ref_job_no',
            'ref_job_sl_no',
            'sample_issued_items',
            'item',
            'purity',
            'pcs',
            'gw',
            'nw',
            'add_field_type',
            'add_gw',
            'less_field_type',
            'less_gw',
            'tunch_per',
            'fine_wt',
            'loss',
            'main_total_wt',
            'wastage',
            'barcode',
            'finish_status',
            'hallmark_status',
            'rhodium',
            'making',
            'remarks',
            'pending_pcs',
            'pending_gw',
            'details',  # Nested details serializer
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'sample_issued_items':{'read_only':True,'required':False}
        }

    def create(self, validated_data):
        with transaction.atomic():
            details_data = validated_data.pop('karigarreceiveitemdetails_set')
            karigar_receive_item_instance = KarigarReceiveItem.objects.create(**validated_data)
            
            # Create related KarigarReceiveItemDetails instances
            for detail_data in details_data:
                KarigarReceiveItemDetails.objects.create(main_sl_no=karigar_receive_item_instance, **detail_data)
            
            return karigar_receive_item_instance
    
    def update(self, instance, validated_data):
        with transaction.atomic():
            children_data = KarigarReceiveItemDetailsForPostSerializer(validated_data.pop('karigarreceiveitemdetails_set', []),many=True).data
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            create_or_update_nested(
                serializer_class=KarigarReceiveItemDetailsForPostSerializer,
                parent_instance=instance,
                related_name='karigarreceiveitemdetails_set',
                nested_data=children_data,
                parent_name="main_sl_no"
            )
            return instance


class KarigarReceiveItemForUpdateSerializer(KarigarReceiveItemForPostSerializer):

    def create(self, validated_data):
        with transaction.atomic():
        
            details_data = validated_data.pop('karigarreceiveitemdetails_set')
            karigar_receive_item_instance = KarigarReceiveItem.objects.create(**validated_data)
            return karigar_receive_item_instance
    
    def update(self, instance, validated_data):
        with transaction.atomic():
        
            children_data = KarigarReceiveItemDetailsForPostSerializer(validated_data.pop('karigarreceiveitemdetails_set', []),many=True).data
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            create_or_update_nested(
                serializer_class=KarigarReceiveItemDetailsForPostSerializer,
                parent_instance=instance,
                related_name='karigarreceiveitemdetails_set',
                nested_data=children_data,
                parent_name="main_sl_no"
            )
            return instance



class KarigarReceiveForPostSerializer(serializers.ModelSerializer):
    # Fields related to KarigarReceive model
    karigar_ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    
    # Nested Serializer for KarigarReceiveItem
    items = KarigarReceiveItemForPostSerializer(many=True,source="karigarreceiveitem_set")

    class Meta:
        model = KarigarReceive
        fields = [
            'id',
            'retail',
            'receive_slip_no',
            'date1',
            'karigar_ldgr',
            'karigar_ldgr_name',
            'place_of_supply',
            'items',  # Nested items serializer
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'karigar_ldgr_name':{'read_only':True}
        }

    def create(self, validated_data):
        items_data = validated_data.pop('karigarreceiveitem_set')
        with transaction.atomic():
            karigar_receive_instance = KarigarReceive.objects.create(**validated_data,)
            
            # Create related KarigarReceiveItem instances
            for item_data in items_data:
                details = item_data.pop('karigarreceiveitemdetails_set')
                kr_item = KarigarReceiveItem.objects.create(receive_slip_no=karigar_receive_instance, **item_data)
                for detail in details:
                    KarigarReceiveItemDetails.objects.create( receive_slip_no = karigar_receive_instance,
            main_sl_no = kr_item,**detail)
                        
            total_making_charge = sum(item['making'] for item in items_data)
            ser = JournalEntrySerializer(data={'date':karigar_receive_instance.date1,
                                    "voucher_no":generate_voucher_no(VoucherType.journal, self.context.get('request').retail),
                                    "narration":f"Being making charges for Artisan on date {karigar_receive_instance.date1}",
                                    "voucher_type":global_vars.VoucherType.journal,
                                    # "status":karigar_receive_instance.receive_slip_no,
                                    "retail":self.context.get('request').retail.id,
                                    "voucher_details": [
                                        {   
                                            'account':"Making Charge Receive", 
                                            'debit':total_making_charge,
                                            'credit':0
                                                },
                                        {'account':karigar_receive_instance.karigar_ldgr.ac_name, 
                                            'credit':total_making_charge,
                                            'debit':0
                                            }
                                        
                                    ]
                                        },context=self.context)
            if ser.is_valid(raise_exception=True):
                
                ref = ser.save()
            karigar_receive_instance.making_vid = ref
            karigar_receive_instance.save()
                    
                    
                    # add Voucher main date = date1 KarigarRecive,vou_no = +last_journal_voucher
                    # @add all the making in kr-rec_item and create a vocuher detail with debit ,acc = mkng_Charge 
                    # @add all the making in kr-rec_item , KarigarLedger is in Header of karigar rec and create a vocuher detail with credit ,acc = KarigrLedger 
            
            return karigar_receive_instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            children_data = KarigarReceiveItemForPostSerializer(validated_data.pop('karigarreceiveitem_set', []),many=True).data
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            create_or_update_nested(
                serializer_class=KarigarReceiveItemForUpdateSerializer,
                parent_instance=instance,
                related_name='karigarreceiveitem_set',
                nested_data=children_data,
                parent_name="receive_slip_no"
            )
            instance.making_vid.delete()
            karigar_receive_instance = instance
                        
            total_making_charge = sum(item['making'] for item in children_data)
            ser = JournalEntrySerializer(data={'date':karigar_receive_instance.date1,
                                    "voucher_no":generate_voucher_no(VoucherType.journal, self.context.get('request').retail),
                                    "narration":f"Being making charges for Artisan on date {karigar_receive_instance.date1}",
                                    "voucher_type":global_vars.VoucherType.journal,
                                    # "status":karigar_receive_instance.receive_slip_no,
                                    "retail":self.context.get('request').retail.id,
                                    "voucher_details": [
                                        {   
                                            'account':"Making Charge Receive", 
                                            'debit':total_making_charge,
                                            'credit':0
                                                },
                                        {'account':karigar_receive_instance.karigar_ldgr.ac_name, 
                                            'credit':total_making_charge,
                                            'debit':0
                                            }
                                        
                                    ]
                                            },context=self.context)
            if ser.is_valid(raise_exception=True):
                
                ref = ser.save()
            karigar_receive_instance.making_vid = ref
            karigar_receive_instance.save()

            return instance
        

class  KarigarReceiveItemforRepSerializer(serializers.ModelSerializer):
    karigarreceiveitemdetails_set = KarigarReceiveItemDetailsForPostSerializer(many=True, read_only=True)
    item = serializers.SlugRelatedField(queryset=Item.objects.all(),slug_field='short_code')
    barcode = serializers.SlugRelatedField(queryset=BarcodeMain.objects.all(), slug_field="barcode", required=False,allow_null=True)
    class Meta:
        model = KarigarReceiveItem
        fields = [
            "pcs",
            "gw",
            "nw",
            "add_field_type",
            "add_gw",
            "less_field_type",
            "less_gw",
            "tunch_per",
            "fine_wt",
            "loss",
            "main_total_wt",
            "wastage",
            "barcode",
            "finish_status",
            "hallmark_status",
            "rhodium",
            "making",
            "remarks",
            "pending_pcs",
            "pending_gw",
            "receive_slip_no",
            "ref_job_no",
            "ref_job_sl_no",
            "item",
            "item_name",
            "purity",
            "unbarcoded_item",
            "karigarreceiveitemdetails_set",
        ]
class KarigarIssueItemReportSerializer(ModelSerializer): #model a
    stone_issue = KarigarStoneIssueDetailSerializer(many=True, read_only=True)  # Nested serializer for stone issues
    stone_receive = KarigarStoneReceiveDetailSerializer(many=True, read_only=True)  # Nested serializer for stone issues
    karigarreceiveitem_set = KarigarReceiveItemforRepSerializer(many=True, read_only=True)
    
    class Meta:
        model = KarigarIssueItem
        fields = [
            "stone_issue",
            "item_name",
            'karigarreceiveitem_set',
            "stone_receive",
            "customer_order_item","design_code",]  


class KarigarReceiveItemforNoDetailsSerializer(serializers.ModelSerializer):
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(),slug_field="pckt_no")
    metal_purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(),slug_field="purity")
    item = serializers.SlugRelatedField(queryset=Item.objects.all(),slug_field="short_code")

    class Meta:
        model = KarigarReceiveItemDetails
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Add custom fields from the model
        data = {
            'item':data['item'],
            'metal_purity': data["metal_purity"],
            'packet': data["packet"],
            'pcs': data["balance_pcs"], 
            'ct': data["balance_ct"],
            'gw': data['balance_gw']
        }
        return data


class KarigarReceiveItemforNoSerializer(serializers.ModelSerializer):
    karigarreceiveitemdetails_set = KarigarReceiveItemforNoDetailsSerializer(many=True,)
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(),slug_field="purity")
    item = serializers.SlugRelatedField(queryset=Item.objects.all(),slug_field="short_code")
    class Meta:
        model = KarigarReceiveItem
        fields = ["id",'sl_no','item',"pcs","gw","nw","purity","karigarreceiveitemdetails_set"]

    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["receive_sl"] = data["id"]
        data["hallmarkissuedetails_set"] = data["karigarreceiveitemdetails_set"]
        del data["karigarreceiveitemdetails_set"]
        del data["id"]
        return data


class KarigarReceiveforNoSerializer(serializers.ModelSerializer):
    karigarreceiveitem_set = KarigarReceiveItemforNoSerializer(many=True)

    class Meta:
        model = KarigarReceive
        fields = '__all__'

class HallmarkIssueDetailsForPostSerializer(serializers.ModelSerializer):
    metal_purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", required=False,allow_null=True)
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(),slug_field="pckt_no",allow_null=True)

    class Meta:
        model = HallmarkIssueDetails
        fields = [
            'id',
            'metal_purity',
            'packet',
            'pcs',
            'ct',
            'gw',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

class HallmarkIssueItemForPostSerializer(serializers.ModelSerializer):
    receive_sl = serializers.PrimaryKeyRelatedField(queryset=KarigarReceiveItem.objects.all())
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field='short_code')
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field='purity')

    hallmarkissuedetails_set = HallmarkIssueDetailsForPostSerializer(many=True)

    class Meta:
        model = HallmarkIssueItem
        fields = [
            'id',
            'sl_no',
            'receive_sl',
            'item',
            'pcs',
            'gw',
            'nw',
            'purity',
            'remarks',
            'hallmarkissuedetails_set'
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

    def create(self,validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('hallmarkissuedetails_set', [])
            instance = HallmarkIssueItem.objects.create(**validated_data)
            create_or_update_nested(
                HallmarkIssueDetailsForPostSerializer, instance, 
                'hallmarkissuedetails_set',  'main_item',HallmarkIssueDetailsForPostSerializer(detail_data,many=True).data
            )
            return instance
        

    def update(self, instance, validated_data):
        with transaction.atomic():
        
            detail_data = validated_data.pop('hallmarkissuedetails_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(
                HallmarkIssueDetailsForPostSerializer, instance, 
                'hallmarkissuedetails_set',  'main_item',HallmarkIssueDetailsForPostSerializer(detail_data,many=True).data
            )
            return instance

class HallmarkIssueForPostSerializer(serializers.ModelSerializer):
    hallmarkissueitem_set = HallmarkIssueItemForPostSerializer(many=True)

    class Meta:
        model = HallmarkIssue
        fields = [
            'id',
            'issue_slip_no',
            'date1',
            'hallmark_center',
            'hallmark_center_name',
            'hallmarkissueitem_set',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'hallmark_center_name':{'read_only':True}
        }
    def create(self, validated_data):
        with transaction.atomic():
            items_data = validated_data.pop('hallmarkissueitem_set')
            hallmark_issue_instance = HallmarkIssue.objects.create(**validated_data)
            for item_data in items_data:
                details = item_data.pop('hallmarkissuedetails_set')
                is_item = HallmarkIssueItem.objects.create(issue_slip_no=hallmark_issue_instance, **item_data)
                for detail in details:
                    HallmarkIssueDetails.objects.create(billno=hallmark_issue_instance,main_item=is_item,**detail)
            return hallmark_issue_instance
        
    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('hallmarkissueitem_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(
                HallmarkIssueItemForPostSerializer, instance, 
                'hallmarkissueitem_set',  'issue_slip_no',HallmarkIssueItemForPostSerializer(detail_data,many=True).data
            )
            return instance

class HallmarkReceiveDetailsForPostSerializer(serializers.ModelSerializer):
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(),slug_field='pckt_no',allow_null=True)
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field='short_code',allow_null=True,required=False)
    metal_purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field='purity',allow_null=True)

    class Meta:
        model = HallmarkReceiveDetails
        fields = [
            'id',
            'packet',
            'item',
            'metal_purity',
            'pcs',
            'ct',
            'gw',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }
class HallmarkReceiveItemForPostSerializer(serializers.ModelSerializer):
    issue_slip_no = serializers.PrimaryKeyRelatedField(queryset=HallmarkIssue.objects.all())
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field='purity')
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field='short_code',allow_null=True,required=False)
    hallmarkreceivedetails_set = HallmarkReceiveDetailsForPostSerializer(many=True)

    class Meta:
        model = HallmarkReceiveItem
        fields = [     
            'id',          
            'sl_no',
            'issue_slip_no',
            'huid',
            'remarks',
            'item',
            'pcs',
            'gw',
            'nw',
            'loss_wt',
            'purity',
            'rejection_status',
            'hallmarkreceivedetails_set',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }
    def create(self, validated_data):
        with transaction.atomic():
            details_data = validated_data.pop('details')
            hallmark_receive_item_instance = HallmarkReceiveItem.objects.create(**validated_data)
            for detail_data in details_data:
                HallmarkReceiveDetails.objects.create(main_item=hallmark_receive_item_instance, **detail_data)
            return hallmark_receive_item_instance
    
    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('hallmarkreceivedetails_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(HallmarkReceiveDetailsForPostSerializer, instance, 'hallmarkreceivedetails_set',  'main_item',HallmarkReceiveDetailsForPostSerializer(detail_data,many=True).data)
            return instance

class HallmarkReceiveForPostSerializer(serializers.ModelSerializer):
    hallmark_center = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    hallmarkreceiveitem_set = HallmarkReceiveItemForPostSerializer(many=True)

    class Meta:
        model = HallmarkReceive
        fields = [
            'id',
            'date1',
            'receive_slip_no',
            'hallmark_center',
            'hallmark_center_name',
            'hallmarkreceiveitem_set',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'hallmark_center_name':{'read_only':True}
        }
    
    def create(self, validated_data):
        with transaction.atomic():
            items_data = validated_data.pop('hallmarkreceiveitem_set')
            hallmark_receive_instance = HallmarkReceive.objects.create(**validated_data)
            for item_data in items_data:
                dat = item_data.pop('hallmarkreceivedetails_set')
                rc_item = HallmarkReceiveItem.objects.create(receive_slip_no=hallmark_receive_instance, **item_data)
                for item in dat:
                    
                    HallmarkReceiveDetails.objects.create(main_item= rc_item,receive_slip_no=hallmark_receive_instance,**item)
            return hallmark_receive_instance
    
    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('hallmarkreceiveitem_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(HallmarkReceiveItemForPostSerializer, instance, 'hallmarkreceiveitem_set',  'receive_slip_no',HallmarkReceiveItemForPostSerializer(detail_data,many=True).data)
            return instance

class KarigarGoldIssueforReportSerializer(serializers.ModelSerializer):
    ref_job_no = serializers.SerializerMethodField()
    job_sl_no = serializers.SerializerMethodField()
    
    class Meta:
        model = KarigarGoldIssue
        fields = "__all__"
    def get_ref_job_no(self, obj):
        if obj.ref_job_no:
            return str(obj.ref_job_no)  # Customize as needed
        return None

    def get_job_sl_no(self, obj):
        if obj.job_sl_no:
            return str(obj.job_sl_no)  # Customize as needed
        return None



class KarigarIssueSerializerforReport(serializers.ModelSerializer):
    gold_issue       = KarigarGoldIssueforReportSerializer(many=True, read_only=True)
    karigar_ldgr_name = serializers.CharField(source='karigar_ldgr.ac_name', read_only=True)

    class Meta:
        model = KarigarIssue
        fields = [
            'bill_id', 'date1', 'issue_slip_type', 'issue_slip_no',
            'karigar_ldgr', 'karigar_ldgr_name', 'gold_issue',
        ]

    # def get_gold_issue(self, obj):
    #     # Get the related KarigarGoldIssue objects
    #     gold_issues = obj.gold_issue.all()  # This will return a queryset
    #     # Serialize the queryset using KarigarGoldIssueSerializer
    #     return KarigarGoldIssueSerializer(gold_issues, many=True).data

class KarigarIssueItemforJobStatusSerializer(serializers.ModelSerializer):
    issue_slip = KarigarIssueSerializerforReport()  # Nested serializer for report data
    stage = serializers.SerializerMethodField()
    is_late = serializers.SerializerMethodField()

    def get_stage(self, obj):
        """
        4-stage lifecycle:
          ISSUED              — no KarigarReceiveItem linked yet
          SEMI_FINISHED_RECEIVED — received but finish_status=False
          REISSUED            — semi-finished received item was re-issued to another karigar
          FINISHED            — finish_status=True on at least one linked receive item
        """
        from django.utils import timezone
        receive_items = KarigarReceiveItem.objects.filter(ref_job_sl_no=obj)
        if not receive_items.exists():
            return 'ISSUED'
        if receive_items.filter(finish_status=True).exists():
            return 'FINISHED'
        # Check if any of the receive items have been re-issued to another karigar
        receive_ids = receive_items.values_list('id', flat=True)
        if KarigarIssueItem.objects.filter(source_receive_item_id__in=receive_ids).exists():
            return 'REISSUED'
        return 'SEMI_FINISHED_RECEIVED'

    def get_is_late(self, obj):
        from django.utils import timezone
        if not obj.due_date:
            return False
        stage = self.get_stage(obj)
        return stage != 'FINISHED' and obj.due_date < timezone.now().date()

    class Meta:
        model = KarigarIssueItem
        depth = 1
        fields = [
            'id', 'issue_slip', 'issue_sl_no', 'customer_order_item',
            'source_receive_item', 'item', 'purity', 'pcs', 'approx_wt',
            'design_code', 'size', 'due_date', 'remarks', 'rec_status',
            'retail', 'stage', 'is_late',
        ]


class RefinaryIssueDetailSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(), slug_field="pckt_no")
    metal_purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity")

    class Meta:
        model = RefinaryIssueDetail
        fields = [ 'id','item', 'pcs', 'ct', 'gw', 'packet', 'metal_purity', 'rec_status', 'retail']
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }
class RefinaryIssueSerializer(serializers.ModelSerializer):
    ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    refinaryissuedetail_set = RefinaryIssueDetailSerializer(many=True)

    class Meta:
        model = RefinaryIssue
        fields = ['id','date1', 'billno', 'ldgr','ldgr_name', 'rec_status', 'retail', 'refinaryissuedetail_set']
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'ldgr_name':{'read_only':True}
        }
    def create(self, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('refinaryissuedetail_set', [])
            parent_instance = RefinaryIssue.objects.create(**validated_data)
            create_or_update_nested(RefinaryIssueDetailSerializer, parent_instance, 'refinaryissuedetail_set','billno', RefinaryIssueDetailSerializer(detail_data,many=True).data )
            return parent_instance
    
    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('refinaryissuedetail_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(RefinaryIssueDetailSerializer, instance, 'refinaryissuedetail_set',  'billno',RefinaryIssueDetailSerializer(detail_data,many=True).data)
            return instance


class RefinaryReceiveDetailSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(), slug_field="pckt_no")
    metal_purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity")
    conv_purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity")
    issue_no = serializers.SlugRelatedField(queryset=RefinaryIssue.objects.all(), slug_field="billno")

    class Meta:
        model = RefinaryReceiveDetail
        fields = ['id','issue_no', 'item', 'pcs', 'ct', 'gw', 'loss_per', 'loss_wt', 'remarks', 'packet', 'metal_purity', 'conv_purity', 'conv_nw', 'rec_status', 'retail']
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

class RefinaryReceiveSerializer(serializers.ModelSerializer):
    ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    refinaryreceivedetail_set = RefinaryReceiveDetailSerializer(many=True)

    class Meta:
        model = RefinaryReceive
        fields = ['id','date1', 'billno', 'ldgr',"ldgr_name", 'retail', 'refinaryreceivedetail_set']
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            "ldgr_name":{'read_only':True}
        }
    def create(self, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('refinaryreceivedetail_set', [])
            parent_instance = RefinaryReceive.objects.create(**validated_data)
            create_or_update_nested(RefinaryReceiveDetailSerializer, parent_instance, 'refinaryreceivedetail_set',  'billno',RefinaryReceiveDetailSerializer(detail_data,many=True).data)
            return parent_instance
    
    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('refinaryreceivedetail_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(RefinaryReceiveDetailSerializer, instance, 'refinaryreceivedetail_set',  'billno',RefinaryReceiveDetailSerializer(detail_data,many=True).data)
            return instance
        

from rest_framework import serializers
from .models import HallmarkIssueItem

class HallmarkIssueItemReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = HallmarkIssueItem
        fields = "__all__"

from .models import HallmarkIssue

class HallmarkIssueReportSerializer(serializers.ModelSerializer):
    hallmarkissueitem_set = HallmarkIssueItemReportSerializer(many=True, read_only=True)

    class Meta:
        model = HallmarkIssue
        fields = "__all__"

from contacts.models import Ledger

class LedgerReportSerializer(serializers.ModelSerializer):
    hallmarkreceive_set = HallmarkIssueReportSerializer(many=True, read_only=True)
    hallmarkissue_set = HallmarkIssueReportSerializer(many=True, read_only=True)
    class Meta:
        model = Ledger
        fields = ('ac_name','hallmarkissue_set','hallmarkreceive_set',)

class HallmarkReceiveItemReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = HallmarkReceiveItem
        fields = "__all__"


class HallmarkReceiveReportSerializer(serializers.ModelSerializer):
    hallmarkreceiveitem_set = HallmarkReceiveItemReportSerializer(many=True, read_only=True)

    class Meta:
        model = HallmarkReceive
        fields = "__all__"

class LedgerReceiveReportSerializer(serializers.ModelSerializer):
    hallmarkreceive_set = HallmarkReceiveReportSerializer(many=True, read_only=True)

    class Meta:
        model = Ledger
        fields = "__all__"


class KarigarStoneIssueReportSerializer(serializers.ModelSerializer):
    stone_issue = KarigarStoneIssueGetSerializer(many=True)

    class Meta:
        model = KarigarIssueItem
        fields = "__all__"



class KarigarIssueFullReportSerializer(serializers.ModelSerializer):
    items = KarigarIssueItemReportSerializer(many=True, read_only=True)
    class Meta:
        model = KarigarIssue
        fields = [
            'issue_slip_no', 'date1', 'issue_slip_type',
            'items',
            'karigar_ldgr_name'
        ]


# ── Repair Job Card Serializers ────────────────────────────────────────────────

from manufacturing.models import RepairJobCard, RepairStone, RepairLoss, RepairKarigarLink


class RepairStoneSerializer(serializers.ModelSerializer):
    class Meta:
        model  = RepairStone
        fields = ['id', 'description', 'pcs', 'ct', 'remarks', 'returned']
        extra_kwargs = {'id': {'read_only': False, 'required': False}}


class RepairLossSerializer(serializers.ModelSerializer):
    loss_type_display = serializers.CharField(source='get_loss_type_display', read_only=True)

    class Meta:
        model  = RepairLoss
        fields = ['id', 'loss_type', 'loss_type_display', 'loss_wt', 'remarks']
        extra_kwargs = {'id': {'read_only': False, 'required': False}}


class RepairKarigarLinkSerializer(serializers.ModelSerializer):
    karigar_issue_no  = serializers.SerializerMethodField()
    karigar_receive_no = serializers.SerializerMethodField()
    karigar_name      = serializers.SerializerMethodField()

    def get_karigar_issue_no(self, obj):
        return obj.karigar_issue.issue_slip_no if obj.karigar_issue else None

    def get_karigar_receive_no(self, obj):
        return obj.karigar_receive.receive_slip_no if obj.karigar_receive else None

    def get_karigar_name(self, obj):
        if obj.karigar_issue and obj.karigar_issue.karigar_ldgr:
            return obj.karigar_issue.karigar_ldgr.ac_name
        return None

    class Meta:
        model  = RepairKarigarLink
        fields = [
            'id', 'karigar_issue', 'karigar_issue_no',
            'karigar_receive', 'karigar_receive_no', 'karigar_name',
        ]
        extra_kwargs = {
            'id':              {'read_only': False, 'required': False},
            'karigar_issue':   {'required': False, 'allow_null': True},
            'karigar_receive': {'required': False, 'allow_null': True},
        }


class RepairJobCardSerializer(serializers.ModelSerializer):
    stones        = RepairStoneSerializer(many=True, required=False, default=list)
    losses        = RepairLossSerializer(many=True, required=False, default=list)
    karigar_links = RepairKarigarLinkSerializer(many=True, required=False, default=list)
    customer_name = serializers.CharField(source='customer.ac_name', read_only=True)
    customer_mobile = serializers.CharField(source='customer.mobile1', read_only=True, default='')
    item_name     = serializers.CharField(source='item.item_name', read_only=True, default='')
    purity_name   = serializers.CharField(source='purity.purity_name', read_only=True, default='')
    retail_name   = serializers.CharField(source='retail.retail_name', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    returned_gw   = serializers.SerializerMethodField()
    named_loss_wt = serializers.SerializerMethodField()
    balance_wt    = serializers.SerializerMethodField()

    def get_returned_gw(self, obj):
        from django.db.models import Sum
        from manufacturing.models import KarigarReceiveItem
        issue_ids = obj.karigar_links.filter(
            karigar_receive__isnull=False
        ).values_list('karigar_receive_id', flat=True)
        total = KarigarReceiveItem.objects.filter(
            receive_slip_no__in=issue_ids
        ).aggregate(s=Sum('nw'))['s'] or 0
        return float(total)

    def get_named_loss_wt(self, obj):
        from django.db.models import Sum
        total = obj.losses.aggregate(s=Sum('loss_wt'))['s'] or 0
        return float(total)

    def get_balance_wt(self, obj):
        returned = self.get_returned_gw(obj)
        named    = self.get_named_loss_wt(obj)
        return round(float(obj.received_gw) - returned - named, 3)

    class Meta:
        model  = RepairJobCard
        fields = [
            'id', 'rjc_no', 'date1',
            'customer', 'customer_name', 'customer_mobile',
            'status', 'status_display',
            'item', 'item_name',
            'purity', 'purity_name',
            'description',
            'received_gw', 'received_nw',
            'expected_delivery_date',
            'estimated_making',
            'remarks',
            'fiscal_year', 'retail', 'retail_name',
            'stones', 'losses', 'karigar_links',
            'returned_gw', 'named_loss_wt', 'balance_wt',
        ]
        extra_kwargs = {
            'retail':      {'required': False, 'allow_null': True},
            'fiscal_year': {'required': False, 'allow_null': True},
            'item':        {'required': False, 'allow_null': True},
            'purity':      {'required': False, 'allow_null': True},
        }

    def _sync_children(self, parent, ChildModel, child_serializer_class, data_list, parent_field='job_card'):
        """Create/update/delete child rows based on id presence."""
        existing_ids = set(ChildModel.objects.filter(**{parent_field: parent}).values_list('id', flat=True))
        seen_ids = set()
        for item_data in data_list:
            item_id = item_data.pop('id', None)
            if item_id and item_id in existing_ids:
                ChildModel.objects.filter(pk=item_id).update(**item_data)
                seen_ids.add(item_id)
            else:
                obj = ChildModel.objects.create(**{parent_field: parent}, **item_data)
                seen_ids.add(obj.id)
        # Delete rows that were removed
        to_delete = existing_ids - seen_ids
        if to_delete:
            ChildModel.objects.filter(pk__in=to_delete).delete()

    def create(self, validated_data):
        from django.db import transaction
        stones_data        = validated_data.pop('stones', [])
        losses_data        = validated_data.pop('losses', [])
        karigar_links_data = validated_data.pop('karigar_links', [])
        with transaction.atomic():
            job_card = RepairJobCard.objects.create(**validated_data)
            for d in stones_data:
                d.pop('id', None)
                RepairStone.objects.create(job_card=job_card, **d)
            for d in losses_data:
                d.pop('id', None)
                RepairLoss.objects.create(job_card=job_card, **d)
            for d in karigar_links_data:
                d.pop('id', None)
                RepairKarigarLink.objects.create(job_card=job_card, **d)
        return job_card

    def update(self, instance, validated_data):
        from django.db import transaction
        stones_data        = validated_data.pop('stones', [])
        losses_data        = validated_data.pop('losses', [])
        karigar_links_data = validated_data.pop('karigar_links', [])
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            self._sync_children(instance, RepairStone,       RepairStoneSerializer,       stones_data)
            self._sync_children(instance, RepairLoss,        RepairLossSerializer,        losses_data)
            self._sync_children(instance, RepairKarigarLink, RepairKarigarLinkSerializer, karigar_links_data)
        return instance


class RepairJobCardListSerializer(serializers.ModelSerializer):
    """Flat, lightweight serializer for the list view."""
    customer_name  = serializers.CharField(source='customer.ac_name', read_only=True)
    item_name      = serializers.CharField(source='item.item_name', read_only=True, default='')
    purity_name    = serializers.CharField(source='purity.purity_name', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model  = RepairJobCard
        fields = [
            'id', 'rjc_no', 'date1',
            'customer', 'customer_name',
            'item_name', 'purity_name',
            'status', 'status_display',
            'received_gw', 'expected_delivery_date',
        ]

