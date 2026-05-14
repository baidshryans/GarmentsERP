from purchase.models import PurchaseVoucher, PurchaseVoucherItems
from rest_framework import serializers

from mastersconfig.models import Packet
from goldrates.models import GoldRates, PurityMaster
from sales.models import CustomerOrder
from .models import BarcodeDetails, BarcodeImage, BarcodeMain, BarcodeSplitMerge, BarcodeTransaction, InterRetailTransferItem, InterRetailTransferVoucher, OpeningInventory, RawMaterialInventory, RawMaterialTransaction, RfidCountResult, RfidCountSession, StockJournal, StockJournalDetail, StockTransfer, StockTransferMain, UnBarcodedDetails, UnBarcodedMain
from django.db import transaction
from .models import DesignMain, DesignDetails, Item, Ledger, AssetType


def create_or_update_nested(serializer_class, parent_instance, related_name,parent_name, nested_data):
    """
    Generic function to create or update nested objects.

    Args:
        serializer_class (Serializer): The serializer class for the nested object.
        parent_instance (Model): The parent instance to link the nested objects to.
        related_name (str): The related name of the nested field (e.g., 'children', 'grandchildren').
        nested_data (list): List of dictionaries with nested data.
        parent_name (str) : name referenced in child for parent (field with relation name)

    Returns:
        None
    """
    related_manager = getattr(parent_instance, related_name)
    existing_objects = {obj.id: obj for obj in related_manager.all()}
    for item_data in nested_data:
        obj_id = item_data.get("id")
        if obj_id and (obj_id in existing_objects):
            # Update the existing object
            serializer_instance = serializer_class(instance=existing_objects.pop(obj_id), data=item_data, partial=True)
            serializer_instance.is_valid(raise_exception=True)
            serializer_instance.save()
        else:
            # Create a new object and link it

            serializer_instance = serializer_class(data=item_data)
            serializer_instance.is_valid(raise_exception=True)
            # serializer_instance.validated_data[parent_name] = parent_instance
            serializer_instance.save(**{parent_name:parent_instance})

    # Delete any remaining objects not in the new data
    for obj in existing_objects.values():
        obj.delete()


class OpeningInventorySerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    item_short_code = serializers.CharField(source='item.short_code', read_only=True)
    ldgr_name = serializers.CharField(source='ldgr.ac_name', read_only=True, allow_null=True, default=None)
    purity_label = serializers.CharField(source='purity.purity', read_only=True, allow_null=True, default=None)
    packet_label = serializers.CharField(source='packet.pckt_no', read_only=True, allow_null=True, default=None)

    class Meta:
        model = OpeningInventory
        fields = [
            'id', 'item', 'item_name', 'item_short_code',
            'ldgr', 'ldgr_name',
            'pcs', 'ct', 'gw',
            'type',
            'packet', 'packet_label',
            'purity', 'purity_label',
            'retail',
        ]
        read_only_fields = ['retail']

    def validate(self, attrs):
        entry_type = attrs.get('type', getattr(self.instance, 'type', None))
        ldgr = attrs.get('ldgr', getattr(self.instance, 'ldgr', None))
        if entry_type in ('KR', 'CO') and not ldgr:
            raise serializers.ValidationError(
                {'ldgr': 'A party (karigar/customer) is required for KR and CO type entries.'}
            )
        return attrs


class ItemStockReportSerializer(serializers.ModelSerializer):
    opening = serializers.IntegerField()
    # Inflows
    create_pur = serializers.IntegerField()
    create_rec = serializers.IntegerField()
    sale_ret = serializers.IntegerField()
    sale_app_ret = serializers.IntegerField()
    trf_rr_in = serializers.IntegerField()
    bar_mer_crt = serializers.IntegerField()
    bar_split_crt = serializers.IntegerField()
    inflow = serializers.IntegerField()
    # Outflows
    sale = serializers.IntegerField()
    sale_app = serializers.IntegerField()
    trf_rr_out = serializers.IntegerField()
    bar_mer = serializers.IntegerField()
    bar_split = serializers.IntegerField()
    bar_trf_unb = serializers.IntegerField()
    pur_ret = serializers.IntegerField()
    outflow = serializers.IntegerField()
    # Net
    stock = serializers.IntegerField()

    class Meta:
        model = Item
        fields = [
            'id', 'short_code', 'item_name', 'opening',
            'create_pur', 'create_rec', 'sale_ret', 'sale_app_ret',
            'trf_rr_in', 'bar_mer_crt', 'bar_split_crt', 'inflow',
            'sale', 'sale_app', 'trf_rr_out',
            'bar_mer', 'bar_split', 'bar_trf_unb', 'pur_ret', 'outflow',
            'stock',
        ]

class BarCodeDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = BarcodeDetails
        fields = "__all__"
        depth = 1


class BarcodeSplitMergeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BarcodeSplitMerge
        fields = "__all__"
        depth = 1


from .models import DesignMain, DesignDetails, Item, Ledger, AssetType


class DesignDetailsSerializer(serializers.ModelSerializer):
    sub_item = serializers.SlugRelatedField(
        queryset=Item.objects.all(),
        slug_field='name',  # Replace 'name' with the field you want to use as the slug field
    )
    sub_item_txt = serializers.CharField(required=False)

    class Meta:
        model = DesignDetails
        fields = [
            'design_no',
            'design_no_txt',
            'sub_item',
            'sub_item_txt',
            'metal_purity',
            'pcs',
            'ct',
            'rate',
            'amt',
        ]


class DesignMainSerializer(serializers.ModelSerializer):
    design_details = DesignDetailsSerializer(many=True)

    asset_type = serializers.SlugRelatedField(
        queryset=AssetType.objects.all(),
        slug_field='asset_type',  # Replace 'type_name' with the field you want to use
    )
    item = serializers.SlugRelatedField(
        queryset=Item.objects.all(),
        slug_field='short_code',  # Replace 'short_code' with the field you want to use
    )
    kr_code = serializers.PrimaryKeyRelatedField(
        queryset=Ledger.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = DesignMain
        fields = [
            'design_no',
            'variation_suffix',
            'asset_type',
            'file',
            'item',
            'item_desc',
            'pcs',
            'gw',
            'nw',
            'making',
            'making_type',
            'kr_code',
            'loss_rate',
            'making_rate',
            'design_photo',
            'created_date',
            'design_details',
        ]

    def create(self, validated_data):
        with transaction.atomic():
            details_data = validated_data.pop('design_details')
            design_main_instance = DesignMain.objects.create(**validated_data)

            for detail_data in details_data:
                DesignDetails.objects.create(
                    design_no=design_main_instance,
                    **detail_data,
                )

            return design_main_instance

class BarcodeDetailsSerializer(serializers.ModelSerializer):

    packet = serializers.SlugRelatedField(
        queryset=Packet.objects.all(),
        required=False,
        slug_field="pckt_no",
        allow_null=True,
    )
    item = serializers.SlugRelatedField(
        queryset=Item.objects.all(),
        slug_field="short_code",
    )
    purity = serializers.SlugRelatedField(
        queryset=PurityMaster.objects.all(),
        required=False,
        slug_field="purity",
        allow_null=True,
    )

    class Meta:
        model = BarcodeDetails
        fields = [
            'barcode',
            'barcode_text',
            'packet',
            'pcs',
            'ct',
            'uom',
            'gw',
            'item',
            'purity',
            'rate',
            'amt',
        ]
        extra_kwargs = {
            'barcode': {'required': False},
            'uom': {'read_only': True},
            'barcode_text': {'required': False},
        }

    def validate(self, attrs):
        item = attrs.get('item')
        if item and item.item_type != 'M':
            attrs['purity'] = None
        return attrs

from manufacturing.models import KarigarReceiveItem
class BarCodeMainSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(
        queryset=Item.objects.all(),
        slug_field="short_code"
    )
    purity = serializers.SlugRelatedField(
        queryset=PurityMaster.objects.all(),
        slug_field="purity"
    )
    pur_voucher = serializers.PrimaryKeyRelatedField(
        queryset=PurchaseVoucherItems.objects.all(),
        required=False,
        allow_null=True
    )

    rec_item = serializers.PrimaryKeyRelatedField(
        queryset=KarigarReceiveItem.objects.all(),
        required=False,
        allow_null=True
    )

    kr_code = serializers.PrimaryKeyRelatedField(
        queryset=Ledger.objects.all(),
        required=False,
        allow_null=True,
    )
    barcodedetails_set = BarcodeDetailsSerializer(many=True)
    item_desc = serializers.SerializerMethodField()
    item_name = serializers.SerializerMethodField()
    purity_name = serializers.SerializerMethodField()
    created_from = serializers.SerializerMethodField()

    def get_item_desc(self, obj):
        return obj.item.item_name if obj.item else None

    def get_item_name(self, obj):
        return obj.item.item_name if obj.item else None

    def get_purity_name(self, obj):
        return obj.purity.purity if obj.purity else None

    def get_created_from(self, obj):
        if obj.rec_item_id:
            return 'KAR_REC'
        if obj.pur_voucher_id:
            return 'PUR_VOU'
        return 'MANUAL'

    class Meta:
        model = BarcodeMain
        fields = [
            'id',
            'rec_item',
            'barcodedetails_set',
            'item',
            'item_desc',
            'item_name',
            'purity_name',
            'barcode',
            'qr_code',
            'pcs',
            'gw',
            'nw',
            'huid',
            'purity',
            'value',
            'making_val',
            'making_type',
            'pur_voucher',
            'other_chg',
            'design_code',
            'kr_code',
            'total_amount',
            'size',
            'metal_color',
            'created_from',
            'created_by',
            'created_date',
            'stk_status',
            'voucher_no',
            'customer_order',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'qr_code': {'read_only': True},
            'item_name': {'read_only': True},
            'purity_name': {'read_only': True},
            'customer_order': {'required': False, 'allow_null': True},
        }


    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['customer_order_no'] = instance.customer_order.order_no if instance.customer_order_id and instance.customer_order else None
        return rep

    #TODO : add logic to karigar receive too
    def create(self, validated_data):
        with transaction.atomic():
            pur = validated_data.get('pur_voucher')
            rec_item = validated_data.get('rec_item')
            grandchildren_data = BarcodeDetailsSerializer(validated_data.pop('barcodedetails_set', []),many=True).data

            # Auto-tag the barcode with its Customer Order, if traceable.
            # Priority: explicit value from the client > direct CO-item FK on the
            # PV line > PO→CO-item traversal > PV header order_no.
            if not validated_data.get('customer_order') and pur is not None:
                co = None
                # (1) direct CO → PV path (new line-level FK)
                if getattr(pur, 'customer_order_item_id', None):
                    coi = pur.customer_order_item
                    co = coi.order_no if coi else None
                # (2) CO → PO → PV path (traverse po_no + po_sl_no back to the PO item)
                if not co and pur.po_no and pur.po_sl_no is not None:
                    from purchase.models import PurchaseOrderItems
                    poi = (
                        PurchaseOrderItems.objects
                        .select_related('customer_order_item', 'customer_order_item__order_no')
                        .filter(po_slip__po_no=pur.po_no, po_sl_no=pur.po_sl_no)
                        .first()
                    )
                    if poi and poi.customer_order_item:
                        co = poi.customer_order_item.order_no
                # (3) header-level fallback
                if not co and getattr(pur, 'order_no_id', None):
                    co = pur.order_no
                if co is not None:
                    validated_data['customer_order'] = co

            child = BarcodeMain.objects.create(**validated_data)
            create_or_update_nested(
                serializer_class=BarcodeDetailsSerializer,
                parent_instance=child,
                related_name='barcodedetails_set',
                parent_name="barcode",
                nested_data=grandchildren_data
            )
            request = self.context.get("request")
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')) if request else None

            created_from = 'KAR_REC' if rec_item else ('PUR_VOU' if pur else 'MANUAL')
            trans_type = "CREATE-REC" if created_from == "KAR_REC" else "CREATE-PUR"
       
            BarcodeTransaction.objects.create(
                barcode=child,
                billno=validated_data.get('voucher_no', ''),
                trans_type=trans_type,
                user=request.user,
                ip_address=ip,
                retail=request.retail
            )
            if pur:
                new_pending_pcs = (pur.pending_pcs or 0) - (child.pcs or 0)
                new_pending_gw = (pur.pending_gw or 0) - (child.gw or 0)

                # NOTE: pending-pcs guard intentionally skipped for PV-based
                # barcode creation — pieces may be uninitialised (None) on
                # older PV rows, and over-allocation by piece count is allowed.
                # Weight, however, is still validated.
                if new_pending_gw < 0:
                    raise serializers.ValidationError(
                        f"Cannot create barcode: Purchase voucher item has only {pur.pending_gw} pending weight, "
                        f"but barcode requires {child.gw} weight."
                    )

                pur.pending_pcs = new_pending_pcs
                pur.pending_gw = new_pending_gw
                # NOTE: Do NOT mirror child onto pur.barcode — a single PV line
                # can split into multiple BarcodeMain rows (1→N). The authoritative
                # direction is BarcodeMain.pur_voucher. pur.barcode is a legacy FK
                # and should be treated as unreliable for traversal.
                pur.save()

            if rec_item:
                new_pending_pcs = (rec_item.pending_pcs or 0) - (child.pcs or 0)
                new_pending_gw = (rec_item.pending_gw or 0) - (child.gw or 0)

                if new_pending_pcs < 0:
                    raise serializers.ValidationError(
                        f"Cannot create barcode: Receive item has only {rec_item.pending_pcs} pending pieces, "
                        f"but barcode requires {child.pcs} pieces."
                    )
                if new_pending_gw < 0:
                    raise serializers.ValidationError(
                        f"Cannot create barcode: Receive item has only {rec_item.pending_gw} pending weight, "
                        f"but barcode requires {child.gw} weight."
                    )

                rec_item.pending_pcs = new_pending_pcs
                rec_item.pending_gw = new_pending_gw
                rec_item.save()
        return child

    def update(self, instance, validated_data):
        with transaction.atomic():
            grandchildren_data = BarcodeDetailsSerializer(validated_data.pop('barcodedetails_set', []),many=True).data
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            create_or_update_nested(
                serializer_class=BarcodeDetailsSerializer,
                parent_instance=instance,
                related_name='barcodedetails_set',
                nested_data=grandchildren_data,
                parent_name="barcode"
            )
            return instance

class BarCodeMainListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views — includes barcodedetails_set for modal display."""
    item = serializers.SlugRelatedField(read_only=True, slug_field="short_code")
    purity = serializers.SlugRelatedField(read_only=True, slug_field="purity")
    item_name = serializers.SerializerMethodField()
    purity_name = serializers.SerializerMethodField()
    barcodedetails_set = BarcodeDetailsSerializer(many=True, read_only=True)
    # dia_ct is annotated on the queryset via Sum('barcodedetails_set__ct')
    dia_ct = serializers.FloatField(read_only=True, default=None)
    customer_order_no = serializers.CharField(source='customer_order.order_no', read_only=True, default=None)
    customer_order_status = serializers.CharField(source='customer_order.delivery_status', read_only=True, default=None)
    customer_order_party_name = serializers.SerializerMethodField()

    def get_item_name(self, obj):
        return obj.item.item_name if obj.item else None

    def get_purity_name(self, obj):
        return obj.purity.purity if obj.purity else None

    def get_customer_order_party_name(self, obj):
        if obj.customer_order_id and obj.customer_order and obj.customer_order.ldgr_id:
            return getattr(obj.customer_order.ldgr, 'ldgr_name', None)
        return None

    class Meta:
        model = BarcodeMain
        fields = [
            'id', 'item', 'item_name', 'purity', 'purity_name',
            'barcode', 'pcs', 'gw', 'nw', 'huid',
            'making_val', 'making_type', 'other_chg', 'design_code',
            'total_amount', 'stk_status', 'created_date', 'voucher_no',
            'dia_ct', 'barcodedetails_set',
            'customer_order', 'customer_order_no',
            'customer_order_status', 'customer_order_party_name',
        ]


class UnBarcodedDetailsSerializer(serializers.ModelSerializer):
    packet = serializers.SlugRelatedField(
        queryset=Packet.objects.all(),
        required=False,
        slug_field="pckt_no",
        allow_null=True
    )
    item = serializers.SlugRelatedField(
        queryset=Item.objects.all(),
        slug_field="short_code"
    )

    class Meta:
        model = UnBarcodedDetails
        fields = [
            'packet',
            'pcs',
            'ct',
            'gw',
            'item',
            'rate',
            'amt',
        ]


class UnBarcodedMainSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(
        queryset=Item.objects.all(),
        slug_field="short_code"
    )
    purity = serializers.SlugRelatedField(
        queryset=PurityMaster.objects.all(),
        slug_field="purity"
    )
    kr_code = serializers.PrimaryKeyRelatedField(
        queryset=Ledger.objects.all(),
        required=False
    )
    customer_order = serializers.SlugRelatedField(
        queryset=CustomerOrder.objects.all(),
        slug_field="order_no",
        required=False,
        allow_null=True
    )
    unbarcodeddetails_set = UnBarcodedDetailsSerializer(many=True)

    class Meta:
        model = UnBarcodedMain
        fields = [
            'id',

            'unbarcodeddetails_set',
            'item',
            'label',
            'item_desc',
            'pcs',
            'gw',
            'nw',
            'huid',
            'purity',
            'value',
            'making_val',
            'making_type',
            'other_chg',
            'design_code',
            'kr_code',
            'total_amount',
            'size',
            'metal_color',
            'created_from',
            'customer_order',
            'created_by',
            'created_date',
            'next',
            'stk_status',
            'op_stk',
            'voucher_no',
        ]

    def create(self, validated_data):
        with transaction.atomic():
            grandchildren_data = UnBarcodedDetailsSerializer(
                validated_data.pop('unbarcodeddetails_set', []), many=True
            ).data
            child = UnBarcodedMain.objects.create(**validated_data)
            create_or_update_nested(
                serializer_class=UnBarcodedDetailsSerializer,
                parent_instance=child,
                related_name='unbarcodeddetails_set',
                parent_name="main_item",
                nested_data=grandchildren_data
            )
            return child

    def update(self, instance, validated_data):
        with transaction.atomic():
            grandchildren_data = UnBarcodedDetailsSerializer(
                validated_data.pop('unbarcodeddetails_set', []), many=True
            ).data
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            create_or_update_nested(
                serializer_class=UnBarcodedDetailsSerializer,
                parent_instance=instance,
                related_name='unbarcodeddetails_set',
                nested_data=grandchildren_data,
                parent_name="main_item"
            )
            return instance

def get_recent_gold_rate(purity_value):
    """
    Get the most recent gold rate for a specific purity.
    
    Args:
        purity_value (str): The purity value (e.g., "22K", "24K", etc.)
        
    Returns:
        int: The most recent gold rate for the specified purity
        None: If no rate is found for the specified purity
    """
    try:
        # First, get the PurityMaster object that matches the purity value
        purity_obj = PurityMaster.objects.get(purity=purity_value)
        
        # Get the most recent gold rate for this purity
        # We order by date1 in descending order and take the first one
        latest_rate = GoldRates.objects.filter(purity=purity_obj).order_by('-date1').first()
        
        if latest_rate:
            return latest_rate.selling_rate or latest_rate.rate
        else:
            return None
            
    except PurityMaster.DoesNotExist:
        # Handle the case where the specified purity doesn't exist
        return None
    except Exception as e:
        # Handle any other exceptions
        print(f"Error retrieving gold rate: {e}")
        return None
class BarcodeDetToSaleVouDetSerializer(BarcodeDetailsSerializer):
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Use the sub-item's own purity FK (null for stones/diamonds, set for gold).
        # Do NOT inherit the parent barcode's purity — that would stamp purity on every sub-item.
        representation["metal_purity"] = instance.purity.purity if instance.purity else None
        representation["item_name"] = instance.item.item_name if instance.item else None
        if instance.item.short_code == "Gold":
            rate = get_recent_gold_rate(self.context.get('purity'))
            representation["rate"] = rate
            uom = instance.item.uom
            if uom == "Ct":
                qty = float(instance.ct or 0)
            elif uom == "Pcs":
                qty = float(instance.pcs or 0)
            else:  # "Gm"
                qty = float(instance.gw or 0)
            representation["amt"] = round(rate * qty, 2) if rate else 0
        return representation


class BarcodeMainToSaleVouSerializer(BarCodeMainSerializer):
    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)
        
        # Dynamically pass context to the nested serializer
        instance = self.instance

        if instance:
            purity_value = instance.purity.purity 
            self.fields['barcodedetails_set'].context.update({**self.context, 'purity': purity_value})
    
    barcodedetails_set = BarcodeDetToSaleVouDetSerializer(many=True,)
    
    def to_representation(self, instance):
        
        representation = super().to_representation(instance)


        representation['main_item_set'] =  representation['barcodedetails_set']
        representation['making'] = representation['making_val']
        del representation['making_val']
        del representation['barcodedetails_set']
        return representation
    
class StockJournalDetailSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(), slug_field="pckt_no", allow_null=True)
    metal_purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", allow_null=True)

    class Meta:
        model = StockJournalDetail
        fields = [ 'doc_type', 'item', 'pcs', 'ct', 'gw', 'loss', 'packet', 'metal_purity', 'retail']

class StockJournalSerializer(serializers.ModelSerializer):
    stockjournaldetail_set = StockJournalDetailSerializer(many=True)

    class Meta:
        model = StockJournal
        fields = ['id','date1', 'billno', 'remarks', 'retail', 'stockjournaldetail_set']

        extra_kwargs={
            'id': {'read_only': False, 'required': False},
        }
    
    def create(self, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('stockjournaldetail_set', [])
            parent_instance = StockJournal.objects.create(**validated_data)
            create_or_update_nested(StockJournalDetailSerializer, parent_instance, 'stockjournaldetail_set', 'billno', StockJournalDetailSerializer(detail_data,many=True).data)
            return parent_instance
    
    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('stockjournaldetail_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(StockJournalDetailSerializer, instance, 'stockjournaldetail_set','billno',StockJournalDetailSerializer(detail_data,many=True).data)
            return instance
    
class BarcodeTransactionSerializer(serializers.ModelSerializer):
    barcode = serializers.SlugRelatedField(queryset=BarcodeMain.objects.all(), slug_field="barcode")
    item_name = serializers.CharField(source='barcode.item.item_name', read_only=True, default=None)
    item_short_code = serializers.CharField(source='barcode.item.short_code', read_only=True, default=None)
    gw = serializers.DecimalField(source='barcode.gw', max_digits=10, decimal_places=3, read_only=True, default=None)
    pcs = serializers.IntegerField(source='barcode.pcs', read_only=True, default=None)

    class Meta:
        model = BarcodeTransaction
        fields = ['id', 'barcode', 'date', 'billno', 'trans_type', 'item_name', 'item_short_code', 'gw', 'pcs']

class BarcodeCreationReportSerializer(serializers.ModelSerializer):
    stone_details = BarcodeDetailsSerializer(many=True)
    other_details = BarcodeDetailsSerializer(many=True)
    created_from = serializers.SerializerMethodField()

    def get_created_from(self, obj):
        if obj.rec_item_id:
            return 'KAR_REC'
        if obj.pur_voucher_id:
            return 'PUR_VOU'
        return 'MANUAL'

    class Meta:
        model = BarcodeMain
        fields = [
            'id',
            'barcode',
            'item',
            'pcs',
            'gw',
            'nw',
            'huid',
            'purity',
            'value',
            'making_val',
            'making_type',
            'other_chg',
            'design_code',
            'kr_code',
            'total_amount',
            'size',
            'metal_color',
            'created_from',
            'created_by',
            'created_date',
            'stone_details',
            'other_details',
        ]


# ── Stock Transfer ─────────────────────────────────────────────────────────────

from mastersconfig.models import RetailMaster


class StockTransferMainSerializer(serializers.ModelSerializer):
    barcode = serializers.SlugRelatedField(queryset=BarcodeMain.objects.all(), slug_field="barcode")
    gw        = serializers.SerializerMethodField(read_only=True)
    nw        = serializers.SerializerMethodField(read_only=True)
    item_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = StockTransferMain
        fields = ['id', 'sl_no', 'barcode', 'rec_status', 'gw', 'nw', 'item_name']
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'rec_status': {'read_only': True},
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

    def get_gw(self, obj):
        try:
            return float(obj.barcode.gw)
        except Exception:
            return None

    def get_nw(self, obj):
        try:
            return float(obj.barcode.nw)
        except Exception:
            return None

    def get_item_name(self, obj):
        try:
            return obj.barcode.item.item_name if obj.barcode.item else None
        except Exception:
            return None


class StockTransferSerializer(serializers.ModelSerializer):
    stocktransfermain_set = StockTransferMainSerializer(many=True)
    to_rt_code       = serializers.SlugRelatedField(queryset=RetailMaster.objects.all(), allow_null=True, slug_field="retail_code")
    from_retail_name = serializers.SerializerMethodField(read_only=True)
    to_retail_name   = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = StockTransfer
        fields = ['id', 'date1', 'billno', 'to_rt_code', 'sent_status', 'rec_status',
                  'from_retail_name', 'to_retail_name', 'stocktransfermain_set']
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'sent_status': {'read_only': True},
            'rec_status': {'read_only': True},
        }

    def get_from_retail_name(self, obj):
        try:
            return obj.retail.retail_name if obj.retail else None
        except Exception:
            return None

    def get_to_retail_name(self, obj):
        try:
            return obj.to_rt_code.retail_name if obj.to_rt_code else None
        except Exception:
            return None

    def create(self, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('stocktransfermain_set', [])
            request = self.context.get("request")
            from accounting.utils import get_next_bill_number
            validated_data['billno'] = get_next_bill_number(request.retail, 'RST')
            parent_instance = StockTransfer.objects.create(**validated_data)
            create_or_update_nested(
                StockTransferMainSerializer, parent_instance,
                'stocktransfermain_set', 'billno',
                StockTransferMainSerializer(detail_data, many=True).data,
            )
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')) if request else None
            for stm in parent_instance.stocktransfermain_set.select_related('barcode').all():
                BarcodeTransaction.objects.create(
                    barcode=stm.barcode, billno=parent_instance.billno,
                    trans_type="TRF-RR-OUT", user=request.user, ip_address=ip, retail=request.retail,
                )
                BarcodeTransaction.objects.create(
                    barcode=stm.barcode, billno=parent_instance.billno,
                    trans_type="TRF-RR-IN", user=request.user, ip_address=ip, retail=parent_instance.to_rt_code,
                )
            return parent_instance

    def update(self, instance, validated_data):
        if instance.sent_status:
            raise serializers.ValidationError("Cannot edit a transfer that has been sent.")
        with transaction.atomic():
            detail_data = validated_data.pop('stocktransfermain_set', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(
                StockTransferMainSerializer, instance,
                'stocktransfermain_set', 'billno',
                StockTransferMainSerializer(detail_data, many=True).data,
            )
            return instance


class RawMaterialInventorySerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    item_short_code = serializers.CharField(source='item.short_code', read_only=True)
    item_type = serializers.CharField(source='item.item_type', read_only=True)
    packet_no = serializers.CharField(source='packet.pckt_no', read_only=True, default=None)
    purity_name = serializers.SerializerMethodField()

    def get_purity_name(self, obj):
        return str(obj.purity) if obj.purity else None

    class Meta:
        model = RawMaterialInventory
        fields = ['id', 'item', 'item_name', 'item_short_code', 'item_type',
                  'pcs', 'ct', 'gw', 'packet', 'packet_no', 'purity', 'purity_name', 'retail']


class RawMaterialTransactionSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    item_short_code = serializers.CharField(source='item.short_code', read_only=True)
    packet_no = serializers.CharField(source='packet.pckt_no', read_only=True, default=None)
    purity_name = serializers.CharField(source='purity.purity', read_only=True, default=None)

    class Meta:
        model = RawMaterialTransaction
        fields = ['id', 'date', 'item', 'item_name', 'item_short_code',
                  'packet', 'packet_no', 'purity', 'purity_name',
                  'trans_type', 'pcs', 'ct', 'gw', 'rate', 'amt',
                  'billno', 'retail']


class RfidTagAssignSerializer(serializers.Serializer):
    """Assigns (or clears) an RFID tag EPC on a BarcodeMain record."""
    barcode = serializers.CharField(max_length=13)
    rfid_tag = serializers.CharField(max_length=100, allow_blank=True)

    def validate(self, data):
        try:
            self._barcode_obj = BarcodeMain.objects.get(
                barcode=data['barcode'],
                retail=self.context['retail'],
            )
        except BarcodeMain.DoesNotExist:
            raise serializers.ValidationError({'barcode': 'Barcode not found in this retail.'})

        rfid = data.get('rfid_tag', '').strip()
        if rfid:
            qs = BarcodeMain.objects.filter(rfid_tag=rfid)
            if self._barcode_obj.pk:
                qs = qs.exclude(pk=self._barcode_obj.pk)
            if qs.exists():
                raise serializers.ValidationError({'rfid_tag': 'This RFID tag is already assigned to another item.'})
        return data

    def save(self):
        rfid = self.validated_data.get('rfid_tag', '').strip() or None
        self._barcode_obj.rfid_tag = rfid
        self._barcode_obj.save(update_fields=['rfid_tag'])
        return self._barcode_obj


class RfidCountSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RfidCountSession
        fields = ['id', 'session_no', 'date', 'status', 'note', 'retail', 'created_by']
        read_only_fields = ['date', 'created_by']


class RfidCountResultSerializer(serializers.ModelSerializer):
    barcode_value = serializers.CharField(source='barcode.barcode', read_only=True)
    item_name = serializers.CharField(source='barcode.item.item_name', read_only=True)

    class Meta:
        model = RfidCountResult
        fields = ['id', 'rfid_tag', 'barcode', 'barcode_value', 'item_name', 'match_status']


class BarcodeImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BarcodeImage
        fields = ['id', 'barcode', 'image', 'original_name', 'uploaded_at']
        read_only_fields = ['original_name', 'uploaded_at']

    def create(self, validated_data):
        file = validated_data['image']
        validated_data['original_name'] = file.name
        return super().create(validated_data)


# ---------------------------------------------------------------------------
# Inter-Retail Transfer Voucher
# ---------------------------------------------------------------------------

class InterRetailTransferItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    item_type = serializers.CharField(source='item.item_type', read_only=True)

    class Meta:
        model = InterRetailTransferItem
        fields = [
            'id', 'item', 'item_name', 'item_type', 'purity',
            'qty_pcs', 'qty_gw', 'qty_ct',
            'primary_qty', 'source_avg_rate', 'transfer_value',
            'barcode', 'unbarcoded_ref', 'packet',
        ]
        read_only_fields = ['primary_qty', 'source_avg_rate', 'transfer_value']
        extra_kwargs = {'id': {'read_only': False, 'required': False}}


class InterRetailTransferVoucherSerializer(serializers.ModelSerializer):
    items = InterRetailTransferItemSerializer(many=True)
    from_retail_name = serializers.CharField(source='from_retail.retail_name', read_only=True)
    to_retail_name = serializers.CharField(source='to_retail.retail_name', read_only=True)

    class Meta:
        model = InterRetailTransferVoucher
        fields = [
            'id', 'voucher_no', 'transfer_date',
            'from_retail', 'from_retail_name', 'to_retail', 'to_retail_name',
            'status', 'narration', 'fiscal_year',
            'created_by', 'created_at', 'updated_at', 'received_at',
            'items',
        ]
        read_only_fields = [
            'voucher_no', 'status', 'created_by', 'created_at',
            'updated_at', 'received_at', 'fiscal_year',
        ]

    def validate(self, attrs):
        from_retail = attrs.get('from_retail') or getattr(self.instance, 'from_retail', None)
        to_retail = attrs.get('to_retail') or getattr(self.instance, 'to_retail', None)
        if from_retail and to_retail and from_retail == to_retail:
            raise serializers.ValidationError({'to_retail': 'from_retail and to_retail must differ.'})

        items = attrs.get('items')
        if items is not None:
            if not items:
                raise serializers.ValidationError({'items': 'At least one line item is required.'})
            for it in items:
                item_obj = it.get('item')
                if item_obj and item_obj.item_type not in ('R', 'S', 'M'):
                    raise serializers.ValidationError(
                        {'items': f"Item '{item_obj.item_name}' has type {item_obj.item_type}; only R/S/M allowed."}
                    )
        return attrs

    def _snapshot_item(self, voucher, item_data):
        """Compute primary_qty, source_avg_rate, transfer_value and build a model kwargs dict."""
        from decimal import Decimal
        from inventory.views import ClosingStockCal

        item_obj = item_data['item']
        qty_gw = Decimal(str(item_data.get('qty_gw') or 0))
        qty_ct = Decimal(str(item_data.get('qty_ct') or 0))

        if item_obj.item_type == 'S':
            primary_qty = qty_ct
        else:
            primary_qty = qty_gw

        try:
            rate = ClosingStockCal().get_weighted_avg_rate(
                item_obj, voucher.from_retail_id, voucher.transfer_date
            )
        except ValueError as e:
            raise serializers.ValidationError({'items': str(e)})

        rate = Decimal(str(rate))
        data = dict(item_data)
        data['primary_qty'] = primary_qty
        data['source_avg_rate'] = rate
        data['transfer_value'] = (primary_qty * rate)
        return data

    def create(self, validated_data):
        from accounting.utils import get_next_bill_number
        items_data = validated_data.pop('items', [])
        request = self.context.get('request')
        with transaction.atomic():
            retail = validated_data['from_retail']
            validated_data['voucher_no'] = get_next_bill_number(retail, 'IRT')
            req_user = getattr(request, 'user', None)
            if req_user is not None and getattr(req_user, 'is_authenticated', False):
                validated_data['created_by'] = req_user
            validated_data['fiscal_year'] = getattr(retail, 'active_fy', None)
            validated_data['status'] = InterRetailTransferVoucher.STATUS_DRAFT
            voucher = InterRetailTransferVoucher.objects.create(**validated_data)
            for item_data in items_data:
                snap = self._snapshot_item(voucher, item_data)
                InterRetailTransferItem.objects.create(voucher=voucher, **snap)
            return voucher

    def update(self, instance, validated_data):
        if instance.status != InterRetailTransferVoucher.STATUS_DRAFT:
            raise serializers.ValidationError(
                f"Cannot edit voucher in status '{instance.status}'. Only draft vouchers are editable."
            )
        items_data = validated_data.pop('items', None)
        with transaction.atomic():
            for attr in ('transfer_date', 'from_retail', 'to_retail', 'narration'):
                if attr in validated_data:
                    setattr(instance, attr, validated_data[attr])
            instance.save()
            if items_data is not None:
                instance.items.all().delete()
                for item_data in items_data:
                    snap = self._snapshot_item(instance, item_data)
                    InterRetailTransferItem.objects.create(voucher=instance, **snap)
            return instance
