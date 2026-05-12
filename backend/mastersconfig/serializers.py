from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import (
    Hsn, Item, ItemGroupMaster, Packet, PacketGroup, RetailMaster,
    SalesPersonMaster, Shapes, Colors, FiscalYearMaster, State,
    TDSSectionMaster, TCSSectionMaster, ExhibitionProfile, BranchMaster,
    CompanyMaster, SystemSettings, CRMSettings, CRMSendLog, GSTINMaster,
    B2BPricelist, B2BPricelistTunch, B2BPricelistMaking, B2BPricelistStoneOverride,
    RetailDiscountPricelist, RetailDiscountPricelistRule,
    SalesOffer, SalesOfferRule,
)


class StateSerializer(ModelSerializer):
    class Meta:
        model = State
        fields = '__all__'


class ItemSerializer(ModelSerializer):
    """Read serializer for Item — resolves FK names without depth=1 to avoid N+1."""
    grp_name = serializers.CharField(source='grp.name', read_only=True, default=None)
    hsn_code = serializers.CharField(source='hsn_no.hsn_no', read_only=True, default=None)
    purchase_ledger_name = serializers.CharField(source='purchase_ledger.ac_name', read_only=True, default=None)
    sale_ledger_name = serializers.CharField(source='sale_ledger.ac_name', read_only=True, default=None)

    class Meta:
        model = Item
        fields = "__all__"

class ItemWriteSerializer(ModelSerializer):
    """Flat serializer for create/update — enforces purchase_ledger & sale_ledger."""
    class Meta:
        model = Item
        fields = "__all__"

    def validate(self, attrs):
        if not attrs.get('purchase_ledger'):
            raise serializers.ValidationError({'purchase_ledger': 'Purchase ledger is required.'})
        if not attrs.get('sale_ledger'):
            raise serializers.ValidationError({'sale_ledger': 'Sale ledger is required.'})
        return attrs

class HSNSerializer(ModelSerializer):
    item_set = ItemSerializer(many=True, read_only=True)
    class Meta:
        model = Hsn
        fields = "__all__"

class HSNListSerializer(ModelSerializer):
    """Lightweight HSN serializer for list endpoints — no nested item_set."""
    class Meta:
        model = Hsn
        fields = "__all__"


class ItemGroupMasterSerializer(ModelSerializer):
    class Meta:
        model= ItemGroupMaster
        fields = "__all__"

class ShapeSerializer(ModelSerializer):
    class Meta:
        model= Shapes
        fields = "__all__"

class ColorSerializer(ModelSerializer):
    class Meta:
        model= Colors
        fields = "__all__"

class PacketGroupSerializer(ModelSerializer):
    class Meta:
        model= PacketGroup
        fields = "__all__"


class PacketWithTotalSerializer(ModelSerializer):
    total_issued_pcs = serializers.IntegerField(read_only=True)
    total_issued_ct = serializers.FloatField(read_only=True)
    total_issued_gw = serializers.FloatField(read_only=True)
    
    total_returned_pcs = serializers.IntegerField(read_only=True)
    total_returned_ct = serializers.FloatField(read_only=True)
    total_returned_gw = serializers.FloatField(read_only=True)
    
    total_broken_pcs = serializers.IntegerField(read_only=True)
    total_broken_ct = serializers.FloatField(read_only=True)
    total_broken_gw = serializers.FloatField(read_only=True)
    
    total_loss_pcs = serializers.IntegerField(read_only=True)
    total_loss_ct = serializers.FloatField(read_only=True)
    total_loss_gw = serializers.FloatField(read_only=True)

    total_receivable_pcs = serializers.IntegerField(read_only=True)
    total_receivable_ct = serializers.FloatField(read_only=True)
    total_receivable_gw = serializers.FloatField(read_only=True)

    class Meta:
        model = Packet
        fields = [
            "id", "pckt_no", "stone_item_id",
            "total_issued_pcs", "total_issued_ct", "total_issued_gw",
            "total_returned_pcs", "total_returned_ct", "total_returned_gw",
            "total_broken_pcs", "total_broken_ct", "total_broken_gw",
            "total_loss_pcs", "total_loss_ct", "total_loss_gw",
            "total_receivable_pcs", "total_receivable_ct", "total_receivable_gw"
        ]
        depth = 2

class PacketSerializer(ModelSerializer):
    # Resolve FK names for read convenience without expensive depth=2 nesting
    packet_group_name    = serializers.SerializerMethodField(read_only=True)
    stone_item_name      = serializers.SerializerMethodField(read_only=True)
    stone_item_short_code = serializers.SerializerMethodField(read_only=True)
    stone_item_uom       = serializers.SerializerMethodField(read_only=True)
    color_name           = serializers.SerializerMethodField(read_only=True)
    shape_name           = serializers.SerializerMethodField(read_only=True)

    def get_packet_group_name(self, obj):
        return obj.packet_group.packet_group_name if obj.packet_group else None

    def get_stone_item_name(self, obj):
        return obj.stone_item_id.item_name if obj.stone_item_id else None

    def get_stone_item_short_code(self, obj):
        return obj.stone_item_id.short_code if obj.stone_item_id else None

    def get_stone_item_uom(self, obj):
        return obj.stone_item_id.uom if obj.stone_item_id else None

    def get_color_name(self, obj):
        return obj.color.color_name if obj.color else None

    stone_item_hsn_cgst  = serializers.SerializerMethodField(read_only=True)
    stone_item_hsn_sgst  = serializers.SerializerMethodField(read_only=True)
    stone_item_hsn_igst  = serializers.SerializerMethodField(read_only=True)

    def get_shape_name(self, obj):
        return obj.shape.shape_name if obj.shape else None

    def get_stone_item_hsn_cgst(self, obj):
        return float(obj.stone_item_id.hsn_no.cgst) if obj.stone_item_id and obj.stone_item_id.hsn_no else 0

    def get_stone_item_hsn_sgst(self, obj):
        return float(obj.stone_item_id.hsn_no.sgst) if obj.stone_item_id and obj.stone_item_id.hsn_no else 0

    def get_stone_item_hsn_igst(self, obj):
        return float(obj.stone_item_id.hsn_no.igst) if obj.stone_item_id and obj.stone_item_id.hsn_no else 0

    class Meta:
        model  = Packet
        fields = "__all__"

class SalesPersonMasterSerializer(ModelSerializer):
    ledger_name = serializers.SerializerMethodField(read_only=True)

    def get_ledger_name(self, obj):
        return obj.ledger.ac_name if obj.ledger else None

    class Meta:
        model  = SalesPersonMaster
        fields = [
            'id', 'salesperson_name', 'retail',
            'ledger', 'ledger_name',
            'commission_rate', 'commission_on', 'deduct_discount', 'apply_on_b2b',
        ]

class CompanyMasterSerializer(ModelSerializer):
    state_name    = serializers.CharField(source='state.name', read_only=True, default='')
    branch_count  = serializers.SerializerMethodField(read_only=True)
    retail_count  = serializers.SerializerMethodField(read_only=True)

    # Operational ledger names (read-only convenience fields)
    discount_ldgr_name              = serializers.CharField(source='discount_ldgr.ac_name',              read_only=True, default='')
    round_off_ldgr_name             = serializers.CharField(source='round_off_ldgr.ac_name',             read_only=True, default='')
    hallmark_charge_ldgr_name       = serializers.CharField(source='hallmark_charge_ldgr.ac_name',       read_only=True, default='')
    making_receive_ldgr_name        = serializers.CharField(source='making_receive_ldgr.ac_name',        read_only=True, default='')
    gold_conversion_ldgr_name       = serializers.CharField(source='gold_conversion_ldgr.ac_name',       read_only=True, default='')
    carriage_inward_ldgr_name        = serializers.CharField(source='carriage_inward_ldgr.ac_name',        read_only=True, default='')
    making_charge_paid_14k_ldgr_name = serializers.CharField(source='making_charge_paid_14k_ldgr.ac_name', read_only=True, default='')
    making_charge_paid_18k_ldgr_name = serializers.CharField(source='making_charge_paid_18k_ldgr.ac_name', read_only=True, default='')
    making_charge_paid_22k_ldgr_name = serializers.CharField(source='making_charge_paid_22k_ldgr.ac_name', read_only=True, default='')

    def get_branch_count(self, obj):
        return obj.branches.count()

    def get_retail_count(self, obj):
        return sum(b.retails.count() for b in obj.branches.all())

    class Meta:
        model  = CompanyMaster
        fields = [
            'id', 'company_name', 'legal_name', 'pan', 'tan', 'cin',
            'phone', 'email', 'address', 'city', 'state', 'state_name',
            'pincode', 'website', 'bis_logo', 'company_logo',
            'created_at', 'branch_count', 'retail_count',
            'enforce_cash_limits', 'max_cash_receipt_limit', 'max_cash_payment_limit',
            'discount_ldgr', 'round_off_ldgr', 'hallmark_charge_ldgr',
            'making_receive_ldgr', 'gold_conversion_ldgr',
            'carriage_inward_ldgr',
            'making_charge_paid_14k_ldgr', 'making_charge_paid_18k_ldgr', 'making_charge_paid_22k_ldgr',
            'discount_ldgr_name', 'round_off_ldgr_name', 'hallmark_charge_ldgr_name',
            'making_receive_ldgr_name', 'gold_conversion_ldgr_name',
            'carriage_inward_ldgr_name',
            'making_charge_paid_14k_ldgr_name', 'making_charge_paid_18k_ldgr_name', 'making_charge_paid_22k_ldgr_name',
        ]
        read_only_fields = [
            'created_at', 'branch_count', 'retail_count', 'state_name',
            'discount_ldgr', 'round_off_ldgr', 'hallmark_charge_ldgr',
            'making_receive_ldgr', 'gold_conversion_ldgr',
            'carriage_inward_ldgr',
            'making_charge_paid_14k_ldgr', 'making_charge_paid_18k_ldgr', 'making_charge_paid_22k_ldgr',
            'discount_ldgr_name', 'round_off_ldgr_name', 'hallmark_charge_ldgr_name',
            'making_receive_ldgr_name', 'gold_conversion_ldgr_name',
            'carriage_inward_ldgr_name',
            'making_charge_paid_14k_ldgr_name', 'making_charge_paid_18k_ldgr_name', 'making_charge_paid_22k_ldgr_name',
        ]


class BranchMasterSerializer(ModelSerializer):
    retail_count = serializers.SerializerMethodField(read_only=True)
    company_name = serializers.CharField(source='company.company_name', read_only=True, default='')
    state_name   = serializers.CharField(source='state.name', read_only=True, default='')

    def get_retail_count(self, obj):
        return obj.retails.count()

    class Meta:
        model  = BranchMaster
        fields = [
            'id', 'company', 'company_name', 'branch_name', 'branch_code',
            'state', 'state_name', 'description', 'created_at', 'retail_count',
        ]
        read_only_fields = ['created_at', 'retail_count', 'company_name', 'state_name']


class GSTINMasterSerializer(ModelSerializer):
    branch_name  = serializers.CharField(source='branch.branch_name', read_only=True, default='')
    state_name   = serializers.CharField(source='state.name',         read_only=True, default='')

    # GST register ledger names (read-only)
    input_cgst_name  = serializers.CharField(source='input_cgst.ac_name',  read_only=True, default='')
    input_sgst_name  = serializers.CharField(source='input_sgst.ac_name',  read_only=True, default='')
    input_igst_name  = serializers.CharField(source='input_igst.ac_name',  read_only=True, default='')
    output_cgst_name = serializers.CharField(source='output_cgst.ac_name', read_only=True, default='')
    output_sgst_name = serializers.CharField(source='output_sgst.ac_name', read_only=True, default='')
    output_igst_name = serializers.CharField(source='output_igst.ac_name', read_only=True, default='')

    class Meta:
        model  = GSTINMaster
        fields = [
            'id', 'gstin', 'legal_name', 'branch', 'branch_name', 'state', 'state_name',
            'input_cgst', 'input_sgst', 'input_igst',
            'output_cgst', 'output_sgst', 'output_igst',
            'input_cgst_name', 'input_sgst_name', 'input_igst_name',
            'output_cgst_name', 'output_sgst_name', 'output_igst_name',
        ]
        read_only_fields = [
            'branch_name', 'state_name',
            'input_cgst', 'input_sgst', 'input_igst',
            'output_cgst', 'output_sgst', 'output_igst',
            'input_cgst_name', 'input_sgst_name', 'input_igst_name',
            'output_cgst_name', 'output_sgst_name', 'output_igst_name',
        ]


class RetailSerializer(ModelSerializer):
    active_fy_code       = serializers.CharField(source='active_fy.fy_code', read_only=True, default='')
    state_name           = serializers.CharField(source='state.name', read_only=True, default='')
    commission_ldgr_name = serializers.SerializerMethodField(read_only=True)
    branch_name          = serializers.CharField(source='branch.branch_name', read_only=True, default='')
    gstin_master_str     = serializers.CharField(source='gstin_master.gstin', read_only=True, default='')
    gstin_legal_name     = serializers.CharField(source='gstin_master.legal_name', read_only=True, default='')

    def get_commission_ldgr_name(self, obj):
        return obj.commission_ldgr.ac_name if obj.commission_ldgr else None

    class Meta:
        model = RetailMaster
        fields = "__all__"


class FiscalYearSerializer(ModelSerializer):
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = FiscalYearMaster
        fields = [
            'id', 'retail', 'fy_code', 'fy_start', 'fy_end',
            'is_closed', 'closed_at',
            'is_hard_closed', 'hard_closed_at',
            'last_synced_at',
            'created_at', 'is_active',
        ]
        read_only_fields = ['retail', 'closed_at', 'hard_closed_at', 'last_synced_at', 'created_at', 'is_active']

    def get_is_active(self, obj):
        retail = obj.retail
        return retail.active_fy_id == obj.id if retail and retail.active_fy_id else False

    def validate(self, data):
        fy_start = data.get('fy_start')
        fy_end = data.get('fy_end')
        if fy_start and fy_end and fy_start >= fy_end:
            raise serializers.ValidationError("Fiscal year start date must be before end date.")
        return data


class TDSSectionMasterSerializer(ModelSerializer):
    ledger_name = serializers.CharField(source='ledger.ac_name', read_only=True, default='')

    class Meta:
        model = TDSSectionMaster
        fields = '__all__'


class TCSSectionMasterSerializer(ModelSerializer):
    ledger_name = serializers.CharField(source='ledger.ac_name', read_only=True, default='')

    class Meta:
        model = TCSSectionMaster
        fields = '__all__'


class SystemSettingsSerializer(ModelSerializer):
    class Meta:
        model  = SystemSettings
        fields = ['attachment_storage_path', 'barcode_image_storage_path', 'bill_total_auto_calc', 'spell_check_enabled', 'enable_gst_bill', 'updated_at']
        read_only_fields = ['updated_at']


class ExhibitionProfileSerializer(ModelSerializer):
    state_name = serializers.CharField(source='state.name', read_only=True, default='')

    class Meta:
        model = ExhibitionProfile
        fields = '__all__'
        read_only_fields = ('retail', 'created_at')


class CRMSettingsSerializer(ModelSerializer):
    class Meta:
        model  = CRMSettings
        fields = [
            'id', 'retail', 'is_enabled', 'send_time', 'provider',
            'api_key', 'phone_number_id',
            'birthday_template_name', 'anniversary_template_name',
            'webhook_url', 'webhook_headers',
            'last_send_date', 'last_run_status',
        ]
        read_only_fields = ('retail', 'last_send_date', 'last_run_status')


class CRMSendLogSerializer(ModelSerializer):
    class Meta:
        model  = CRMSendLog
        fields = ['id', 'customer_name', 'mobile', 'occasion', 'sent_at', 'status', 'error_message']


# ── B2B Pricelist serializers ────────────────────────────────────────────────

class B2BPricelistTunchSerializer(ModelSerializer):
    purity = serializers.SlugRelatedField(
        queryset=__import__('goldrates.models', fromlist=['PurityMaster']).PurityMaster.objects.all(),
        slug_field='purity',
    )
    pricelist = serializers.PrimaryKeyRelatedField(
        queryset=B2BPricelist.objects.all(), required=False,
    )

    class Meta:
        model  = B2BPricelistTunch
        fields = ['id', 'pricelist', 'purity', 'tunch_percent']
        extra_kwargs = {'id': {'read_only': False, 'required': False}}


class B2BPricelistMakingSerializer(ModelSerializer):
    purity = serializers.SlugRelatedField(
        queryset=__import__('goldrates.models', fromlist=['PurityMaster']).PurityMaster.objects.all(),
        slug_field='purity', allow_null=True, required=False,
    )
    item = serializers.SlugRelatedField(
        queryset=Item.objects.all(),
        slug_field='short_code', allow_null=True, required=False,
    )
    pricelist = serializers.PrimaryKeyRelatedField(
        queryset=B2BPricelist.objects.all(), required=False,
    )

    class Meta:
        model  = B2BPricelistMaking
        fields = ['id', 'pricelist', 'purity', 'item', 'making_type', 'making_value']
        extra_kwargs = {'id': {'read_only': False, 'required': False}}


class B2BPricelistStoneOverrideSerializer(ModelSerializer):
    packet = serializers.SlugRelatedField(
        queryset=Packet.objects.all(), slug_field='pckt_no',
    )
    pricelist = serializers.PrimaryKeyRelatedField(
        queryset=B2BPricelist.objects.all(), required=False,
    )

    class Meta:
        model  = B2BPricelistStoneOverride
        fields = ['id', 'pricelist', 'packet', 'rate']
        extra_kwargs = {'id': {'read_only': False, 'required': False}}


class B2BPricelistSerializer(ModelSerializer):
    tunch_entries   = B2BPricelistTunchSerializer(many=True, required=False)
    making_entries  = B2BPricelistMakingSerializer(many=True, required=False)
    stone_overrides = B2BPricelistStoneOverrideSerializer(many=True, required=False)

    class Meta:
        model  = B2BPricelist
        fields = [
            'id', 'name', 'description', 'is_active',
            'tunch_entries', 'making_entries', 'stone_overrides',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        has_tunch  = bool(attrs.get('tunch_entries'))
        has_making = bool(attrs.get('making_entries'))
        if has_tunch and has_making:
            raise serializers.ValidationError(
                "A pricelist cannot have both Tunch rules and Making Charge rules. Use one or the other."
            )
        return attrs

    def create(self, validated_data):
        from manufacturing.utils import create_or_update_nested
        from django.db import transaction

        tunch   = validated_data.pop('tunch_entries', [])
        making  = validated_data.pop('making_entries', [])
        stones  = validated_data.pop('stone_overrides', [])

        with transaction.atomic():
            pricelist = B2BPricelist.objects.create(**validated_data)
            if tunch:
                create_or_update_nested(
                    B2BPricelistTunchSerializer, pricelist,
                    'tunch_entries', 'pricelist',
                    B2BPricelistTunchSerializer(tunch, many=True).data,
                )
            if making:
                create_or_update_nested(
                    B2BPricelistMakingSerializer, pricelist,
                    'making_entries', 'pricelist',
                    B2BPricelistMakingSerializer(making, many=True).data,
                )
            if stones:
                create_or_update_nested(
                    B2BPricelistStoneOverrideSerializer, pricelist,
                    'stone_overrides', 'pricelist',
                    B2BPricelistStoneOverrideSerializer(stones, many=True).data,
                )
        return pricelist

    def update(self, instance, validated_data):
        from manufacturing.utils import create_or_update_nested
        from django.db import transaction

        tunch   = validated_data.pop('tunch_entries', [])
        making  = validated_data.pop('making_entries', [])
        stones  = validated_data.pop('stone_overrides', [])

        with transaction.atomic():
            for attr, val in validated_data.items():
                setattr(instance, attr, val)
            instance.save()

            create_or_update_nested(
                B2BPricelistTunchSerializer, instance,
                'tunch_entries', 'pricelist',
                B2BPricelistTunchSerializer(tunch, many=True).data,
            )
            create_or_update_nested(
                B2BPricelistMakingSerializer, instance,
                'making_entries', 'pricelist',
                B2BPricelistMakingSerializer(making, many=True).data,
            )
            create_or_update_nested(
                B2BPricelistStoneOverrideSerializer, instance,
                'stone_overrides', 'pricelist',
                B2BPricelistStoneOverrideSerializer(stones, many=True).data,
            )
        return instance


# ── Retail Discount Pricelist serializers ─────────────────────────────────────

class RetailDiscountPricelistRuleSerializer(ModelSerializer):
    purity = serializers.SlugRelatedField(
        queryset=__import__('goldrates.models', fromlist=['PurityMaster']).PurityMaster.objects.all(),
        slug_field='purity',
    )
    pricelist = serializers.PrimaryKeyRelatedField(
        queryset=RetailDiscountPricelist.objects.all(), required=False,
    )

    class Meta:
        model  = RetailDiscountPricelistRule
        fields = ['id', 'pricelist', 'purity', 'making_discount_pct', 'diamond_discount_pct']
        extra_kwargs = {'id': {'read_only': False, 'required': False}}


class RetailDiscountPricelistSerializer(ModelSerializer):
    rules = RetailDiscountPricelistRuleSerializer(many=True, required=False)

    class Meta:
        model  = RetailDiscountPricelist
        fields = ['id', 'name', 'description', 'is_active', 'rules', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        from manufacturing.utils import create_or_update_nested
        from django.db import transaction
        rules = validated_data.pop('rules', [])
        with transaction.atomic():
            pricelist = RetailDiscountPricelist.objects.create(**validated_data)
            if rules:
                create_or_update_nested(
                    RetailDiscountPricelistRuleSerializer, pricelist,
                    'rules', 'pricelist',
                    RetailDiscountPricelistRuleSerializer(rules, many=True).data,
                )
        return pricelist

    def update(self, instance, validated_data):
        from manufacturing.utils import create_or_update_nested
        from django.db import transaction
        rules = validated_data.pop('rules', [])
        with transaction.atomic():
            for attr, val in validated_data.items():
                setattr(instance, attr, val)
            instance.save()
            create_or_update_nested(
                RetailDiscountPricelistRuleSerializer, instance,
                'rules', 'pricelist',
                RetailDiscountPricelistRuleSerializer(rules, many=True).data,
            )
        return instance


# ── Sales Offer ───────────────────────────────────────────────────────────────

class SalesOfferRuleSerializer(ModelSerializer):
    offer = serializers.PrimaryKeyRelatedField(
        queryset=SalesOffer.objects.all(), required=False,
    )

    class Meta:
        model  = SalesOfferRule
        fields = ['id', 'offer', 'purity', 'making_type', 'making_value']
        extra_kwargs = {'id': {'read_only': False, 'required': False}}


class SalesOfferSerializer(ModelSerializer):
    rules = SalesOfferRuleSerializer(many=True, required=False)

    class Meta:
        model  = SalesOffer
        fields = [
            'id', 'name', 'start_date', 'end_date',
            'diamond_discount_pct', 'is_active', 'rules',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        from django.db.models import Q
        is_active  = data.get('is_active',  getattr(self.instance, 'is_active',  False))
        start_date = data.get('start_date', getattr(self.instance, 'start_date', None))
        end_date   = data.get('end_date',   getattr(self.instance, 'end_date',   None))

        if not is_active:
            return data

        qs = SalesOffer.objects.filter(is_active=True)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        overlap_q = Q()
        if end_date is not None:
            overlap_q &= Q(start_date__lte=end_date) | Q(start_date__isnull=True)
        if start_date is not None:
            overlap_q &= Q(end_date__gte=start_date) | Q(end_date__isnull=True)

        conflict = qs.filter(overlap_q).first()
        if conflict:
            raise serializers.ValidationError(
                f"Active offer '{conflict.name}' already covers overlapping dates "
                f"({conflict.start_date} – {conflict.end_date}). "
                "Deactivate it first or adjust the date range."
            )
        return data

    def create(self, validated_data):
        from manufacturing.utils import create_or_update_nested
        from django.db import transaction
        rules = validated_data.pop('rules', [])
        with transaction.atomic():
            offer = SalesOffer.objects.create(**validated_data)
            if rules:
                create_or_update_nested(
                    SalesOfferRuleSerializer, offer,
                    'rules', 'offer',
                    SalesOfferRuleSerializer(rules, many=True).data,
                )
        return offer

    def update(self, instance, validated_data):
        from manufacturing.utils import create_or_update_nested
        from django.db import transaction
        rules = validated_data.pop('rules', [])
        with transaction.atomic():
            for attr, val in validated_data.items():
                setattr(instance, attr, val)
            instance.save()
            create_or_update_nested(
                SalesOfferRuleSerializer, instance,
                'rules', 'offer',
                SalesOfferRuleSerializer(rules, many=True).data,
            )
        return instance