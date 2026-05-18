from rest_framework.serializers import ModelSerializer
from rest_framework import serializers

from contacts.models import Ledger
from goldrates.models import PurityMaster
from manufacturing.utils import create_or_update_nested
from mastersconfig.models import Item
from ..models import PurchaseOrder, PurchaseOrderItems
from sales.models import CustomerOrderItems
from django.db import transaction


class PurchaseOrderSerializer(ModelSerializer):
    class Meta:
        model = PurchaseOrder
        fields = "__all__"


class PurchaseOrderItemsSerializer(ModelSerializer):
    class Meta:
        model = PurchaseOrderItems
        fields = "__all__"


class PurchaseOrderItemsForPostSerializer(serializers.ModelSerializer):
    customer_order_item = serializers.PrimaryKeyRelatedField(queryset=CustomerOrderItems.objects.all(), required=False, allow_null=True)
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity")
    due_date = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = PurchaseOrderItems
        fields = [
            'id',
            'po_sl_no',
            'customer_order_item',
            'item',
            'item_name',
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
            'purchaseorderitems_set'
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

    def validate(self, attrs):
        """
        Reject duplicate customer_order_item references:
          1) within the same submitted payload (user added the same CO item twice)
          2) against already-saved PurchaseOrderItems elsewhere in the system
             (each CO item may live on at most ONE PO line across the system).
        """
        items = attrs.get('purchaseorderitems_set') or []
        po_type = attrs.get('po_type') or (self.instance.po_type if self.instance else None)

        # Required-field guard — each line must have item, purity, pcs, approx_wt.
        # Mirrors the frontend Tab-add guard so raw API / admin writes can't bypass it.
        from datetime import date as _date
        today = _date.today()
        field_errors = []
        for idx, it in enumerate(items, start=1):
            missing = []
            if not it.get('item'):
                missing.append('item')
            if not it.get('purity'):
                missing.append('purity')
            pcs = it.get('pcs')
            if pcs in (None, '') or (isinstance(pcs, (int, float)) and pcs <= 0):
                missing.append('pcs')
            wt = it.get('approx_wt')
            try:
                wt_val = float(wt) if wt not in (None, '') else 0
            except (TypeError, ValueError):
                wt_val = 0
            if wt_val <= 0:
                missing.append('approx_wt')
            if missing:
                field_errors.append(f"Line {idx}: missing {', '.join(missing)}")
            # Due-date guard — if supplied, must be strictly after today.
            due = it.get('due_date')
            if due is not None and due <= today:
                field_errors.append(f"Line {idx}: due_date must be after today ({today.isoformat()})")
        if field_errors:
            raise serializers.ValidationError({'purchaseorderitems_set': field_errors})

        # For Customer-Order POs, every line must carry a customer_order_item FK.
        # Stock / manual items are not allowed on a CO-type PO.
        if po_type == 'Customer Order':
            unlinked = [idx for idx, it in enumerate(items, start=1) if not it.get('customer_order_item')]
            if unlinked:
                raise serializers.ValidationError({
                    'purchaseorderitems_set': (
                        f"Customer Order POs must only contain items linked to a customer order. "
                        f"Line(s) {unlinked} are unlinked — use the 'Pick from Customer Orders' dialog."
                    )
                })

        seen = set()
        dupes_in_payload = set()
        for it in items:
            coi = it.get('customer_order_item')
            if coi is None:
                continue
            coi_id = coi.pk if hasattr(coi, 'pk') else coi
            if coi_id in seen:
                dupes_in_payload.add(coi_id)
            seen.add(coi_id)
        if dupes_in_payload:
            raise serializers.ValidationError({
                'purchaseorderitems_set': (
                    f"The same customer-order item cannot appear twice in one PO. "
                    f"Duplicate item id(s): {sorted(dupes_in_payload)}"
                )
            })
        # Collision against OTHER saved POs — excludes the current PO on update.
        if seen:
            qs = PurchaseOrderItems.objects.filter(customer_order_item_id__in=seen)
            if self.instance is not None:
                qs = qs.exclude(po_slip=self.instance)
            already = list(qs.values_list('customer_order_item_id', flat=True))
            if already:
                raise serializers.ValidationError({
                    'purchaseorderitems_set': (
                        f"Customer-order item(s) {sorted(set(already))} are already "
                        f"allocated to another Purchase Order."
                    )
                })
        return attrs

    def create(self, validated_data):
        with transaction.atomic():

            items_data = validated_data.pop('purchaseorderitems_set')
            if 'fiscal_year' not in validated_data:
                request = self.context.get('request')
                _retail = validated_data.get('retail') or getattr(request, 'retail', None)
                if _retail:
                    validated_data['fiscal_year'] = getattr(_retail, 'active_fy', None)
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
            create_or_update_nested(PurchaseOrderItemsForPostSerializer, instance, 'purchaseorderitems_set', 'po_slip', PurchaseOrderItemsForPostSerializer(detail_data, many=True).data)
            return instance
