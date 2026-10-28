from decimal import Decimal

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from contacts.models import Ledger
from goldrates.models import PurityMaster
from mastersconfig.models import Packet
from mastersconfig.serializer_fields import ItemRefField

from ..approval_stock import apply_stock, reverse_stock
from ..models import PurchaseApproval, PurchaseApprovalItem, PurchaseApprovalItemDetails


class PurchaseApprovalItemDetailsSerializer(serializers.ModelSerializer):
    sub_item = ItemRefField(required=True)
    sub_item_name = serializers.SerializerMethodField()
    metal_purity = serializers.SlugRelatedField(
        queryset=PurityMaster.objects.all(), slug_field="purity", allow_null=True, required=False)
    packet = serializers.SlugRelatedField(
        queryset=Packet.objects.all(), slug_field="pckt_no", allow_null=True, required=False)

    def get_sub_item_name(self, obj):
        item = obj.get('sub_item') if isinstance(obj, dict) else obj.sub_item
        return item.item_name if item else None

    class Meta:
        model = PurchaseApprovalItemDetails
        fields = ['id', 'sub_item', 'sub_item_name', 'sub_pcs', 'sub_gw', 'sub_ct',
                  'metal_purity', 'packet', 'rate', 'value']
        extra_kwargs = {'id': {'read_only': False, 'required': False, 'allow_null': True}}


class PurchaseApprovalItemSerializer(serializers.ModelSerializer):
    item = ItemRefField(required=True)
    item_name = serializers.SerializerMethodField()
    purity = serializers.SlugRelatedField(
        queryset=PurityMaster.objects.all(), slug_field="purity", allow_null=True, required=False)
    status = serializers.CharField(read_only=True)
    details = PurchaseApprovalItemDetailsSerializer(many=True, required=False)

    def get_item_name(self, obj):
        item = obj.get('item') if isinstance(obj, dict) else obj.item
        return item.item_name if item else None

    class Meta:
        model = PurchaseApprovalItem
        fields = ['id', 'sl_no', 'item', 'item_name', 'pcs', 'gw', 'purity', 'making_type',
                  'making', 'making_value', 'amount', 'remarks', 'returned_on', 'status', 'details']
        extra_kwargs = {
            'id': {'read_only': False, 'required': False, 'allow_null': True},
            'returned_on': {'read_only': True},
        }

    def validate(self, data):
        details = data.get('details') or []
        if details:
            gw = Decimal(str(data.get('gw') or 0))
            sub_gw = sum(Decimal(str(d.get('sub_gw') or 0)) for d in details)
            if abs(sub_gw - gw) > Decimal('0.01'):
                raise ValidationError(
                    f"Sub-item GW total ({sub_gw:.3f}g) does not match item GW ({gw:.3f}g). Please reconcile.")
        return data


class PurchaseApprovalSerializer(serializers.ModelSerializer):
    ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    narration = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    items = PurchaseApprovalItemSerializer(many=True)
    ldgr_name = serializers.ReadOnlyField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseApproval
        fields = ['id', 'date1', 'billno', 'ldgr', 'ldgr_name', 'narration', 'status', 'items']
        read_only_fields = ['billno']

    def get_status(self, obj):
        """Open while any line is undecided, otherwise Closed."""
        return 'Open' if any(i.status == PurchaseApprovalItem.PENDING for i in obj.items.all()) else 'Closed'

    def validate_items(self, items):
        if not items:
            raise ValidationError("Add at least one item.")
        return items

    @staticmethod
    def _save_items(approval, items_data):
        for n, item_data in enumerate(items_data, start=1):
            details = item_data.pop('details', [])
            item_data.pop('id', None)
            item_data['sl_no'] = n
            row = PurchaseApprovalItem.objects.create(billno=approval, retail=approval.retail, **item_data)
            detail_total = Decimal('0')
            for d in details:
                d.pop('id', None)
                if not d.get('value') and d.get('sub_gw') and d.get('rate'):
                    d['value'] = Decimal(str(d['sub_gw'])) * Decimal(str(d['rate']))
                detail_total += Decimal(str(d.get('value') or 0))
                PurchaseApprovalItemDetails.objects.create(
                    billno=approval, main_item=row, retail=approval.retail, **d)
            if details:
                # Same rule as a purchase voucher line: item_value = sub-item values + making.
                making = Decimal(str(row.making_value or 0)) if row.making_type == 'val' else Decimal('0')
                row.amount = detail_total + making
                row.save(update_fields=['amount'])
            apply_stock(row)

    def create(self, validated_data):
        from accounting.utils import save_with_bill_number
        from mastersconfig.fy_validation import assert_date_in_active_fy
        items_data = validated_data.pop('items')
        request = self.context.get('request')
        # The viewset passes retail via save(); fall back to the request's branch.
        retail = validated_data.pop('retail', None) or getattr(request, 'retail', None)
        if retail is None:
            raise ValidationError({"retail": "Missing or invalid X-RETAIL-ID header."})
        assert_date_in_active_fy(retail, validated_data.get('date1'))
        fy = getattr(retail, 'active_fy', None)
        with transaction.atomic():
            approval = PurchaseApproval(retail=retail, fiscal_year=fy, **validated_data)
            save_with_bill_number(approval, retail, 'PAP', field='billno', fy=fy)
            self._save_items(approval, items_data)
        return approval

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        settled = [i.sl_no for i in instance.items.all() if i.status != PurchaseApprovalItem.PENDING]
        if settled:
            raise ValidationError(
                f"Lines {settled} are already purchased or returned, so this approval can no longer be edited.")
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            for line in instance.items.all():
                reverse_stock(line, 'PURCHASE_APPR_EDIT')
            instance.items.all().delete()
            self._save_items(instance, items_data)
        return instance
