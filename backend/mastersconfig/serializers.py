from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import Hsn, Item, ItemGroupMaster, Packet, PacketGroup, RetailMaster, SalesPersonMaster, Shapes, Colors, FiscalYearMaster, State, TDSSectionMaster, TCSSectionMaster, ExhibitionProfile, BranchMaster, CompanyMaster, SystemSettings, CRMSettings, CRMSendLog, GSTINMaster


class StateSerializer(ModelSerializer):
    class Meta:
        model = State
        fields = '__all__'


class ItemSerializer(ModelSerializer):
    class Meta:
        model= Item
        fields = "__all__"
        depth = 1
class HSNSerializer(ModelSerializer):
    item_set = ItemSerializer(many=True)
    class Meta:
        model= Hsn
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
    class Meta:
        model= Packet
        fields = "__all__"
        depth = 2

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
    carriage_inward_ldgr_name       = serializers.CharField(source='carriage_inward_ldgr.ac_name',       read_only=True, default='')
    making_charge_purchase_ldgr_name = serializers.CharField(source='making_charge_purchase_ldgr.ac_name', read_only=True, default='')

    def get_branch_count(self, obj):
        return obj.branches.count()

    def get_retail_count(self, obj):
        return sum(b.retails.count() for b in obj.branches.all())

    class Meta:
        model  = CompanyMaster
        fields = [
            'id', 'company_name', 'pan', 'tan', 'gstin', 'cin',
            'phone', 'email', 'address', 'city', 'state', 'state_name',
            'pincode', 'website', 'created_at', 'branch_count', 'retail_count',
            'discount_ldgr', 'round_off_ldgr', 'hallmark_charge_ldgr',
            'making_receive_ldgr', 'gold_conversion_ldgr',
            'carriage_inward_ldgr', 'making_charge_purchase_ldgr',
            'discount_ldgr_name', 'round_off_ldgr_name', 'hallmark_charge_ldgr_name',
            'making_receive_ldgr_name', 'gold_conversion_ldgr_name',
            'carriage_inward_ldgr_name', 'making_charge_purchase_ldgr_name',
        ]
        read_only_fields = [
            'created_at', 'branch_count', 'retail_count', 'state_name',
            'discount_ldgr', 'round_off_ldgr', 'hallmark_charge_ldgr',
            'making_receive_ldgr', 'gold_conversion_ldgr',
            'carriage_inward_ldgr', 'making_charge_purchase_ldgr',
            'discount_ldgr_name', 'round_off_ldgr_name', 'hallmark_charge_ldgr_name',
            'making_receive_ldgr_name', 'gold_conversion_ldgr_name',
            'carriage_inward_ldgr_name', 'making_charge_purchase_ldgr_name',
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
        fields = ['attachment_storage_path', 'barcode_image_storage_path', 'bill_total_auto_calc', 'updated_at']
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