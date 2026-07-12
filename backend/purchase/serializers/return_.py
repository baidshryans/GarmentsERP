from decimal import Decimal
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from accounting.serializers import JournalEntrySerializer
from accounting.utils import generate_voucher_no
from contacts.models import Ledger
import global_vars
from goldrates.models import PurityMaster
from manufacturing.utils import create_or_update_nested
from inventory.models import BarcodeMain, BarcodeTransaction
from mastersconfig.models import Item, Packet
from mastersconfig.serializer_fields import ItemRefField
from ..models import PurchaseReturn, PurchaseReturnItems, PurchaseReturnDetails

from .voucher import _raise_missing_ledger


class PurchaseReturnDetailsSerializer(serializers.ModelSerializer):
    # Fields related to PurchaseReturnDetails model
    sub_item = ItemRefField(required=True)
    metal_purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", required=False, allow_null=True)
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(), slug_field="pckt_no", required=False, allow_null=True)

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
    item = ItemRefField(required=True)
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", required=False)
    barcode = serializers.PrimaryKeyRelatedField(queryset=BarcodeMain.objects.all(), allow_null=True, required=False)

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
            'barcode',
            'barcode_txt',
            'purchasereturndetails_set',  # Nested details serializer
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'barcode_txt': {'required': False, 'allow_null': True, 'allow_blank': True},
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
        create_or_update_nested(PurchaseReturnDetailsSerializer, instance, 'purchasereturndetails_set', 'main_item', PurchaseReturnDetailsSerializer(detail_data, many=True).data)
        return instance


class PurchaseReturnSerializer(serializers.ModelSerializer):
    # Fields related to PurchaseReturn model
    ldgr = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    pv_billno = serializers.CharField(write_only=True, allow_blank=True, required=False)
    # Nested Serializer for PurchaseReturnItems
    purchasereturnitems_set = PurchaseReturnItemsSerializer(many=True)

    class Meta:
        model = PurchaseReturn
        fields = [
            'id',
            'billno',
            'pv_billno',
            'purchase_voucher_ref',
            'date1',
            'ldgr',
            'ldgr_name',
            'discount',
            'cgst_amt',
            'sgst_amt',
            'igst_amt',
            'tcs_amt',
            'hallmark_charge',
            'freight_amt',
            'bill_value',
            'round_off',
            'narration',
            'mode_of_transport',
            'total_incl_tax',  # Computed property
            'purchasereturnitems_set',  # Nested items serializer
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'narration': {'allow_blank': True, 'required': False},
            'mode_of_transport': {'allow_blank': True, 'required': False},
            'ldgr_name': {'read_only': True},
        }

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('purchasereturnitems_set')
        if 'fiscal_year' not in validated_data:
            request = self.context.get('request')
            _retail = validated_data.get('retail') or getattr(request, 'retail', None)
            if _retail:
                from mastersconfig.fy_validation import assert_date_in_active_fy
                assert_date_in_active_fy(_retail, validated_data.get("date1"))
                validated_data['fiscal_year'] = getattr(_retail, 'active_fy', None)
        request = self.context.get('request')
        _retail = validated_data.get('retail') or getattr(request, 'retail', None)
        validated_data.pop('billno', None)
        purchase_return_instance = PurchaseReturn(**validated_data)
        from accounting.utils import save_with_bill_number
        save_with_bill_number(purchase_return_instance, _retail, 'PR', field='billno',
                              fy=validated_data.get('fiscal_year'))

        # Create related PurchaseReturnItems instances
        item_instances = []
        item_detail_instances = []
        items_with_details = []  # list of (main_item_instance, [detail_instances]) for journal building
        for item_data in items_data:
            details_data = item_data.pop('purchasereturndetails_set')
            purchase_return_item_instance = PurchaseReturnItems.objects.create(billno=purchase_return_instance, **item_data)
            item_instances.append(purchase_return_item_instance)
            # Create related PurchaseReturnDetails instances
            detail_instances = []
            for detail_data in details_data:
                ret_item = PurchaseReturnDetails.objects.create(main_item=purchase_return_item_instance, **detail_data)
                item_detail_instances.append(ret_item)
                detail_instances.append(ret_item)
            items_with_details.append((purchase_return_item_instance, detail_instances))
        retail = self.context.get('request').retail
        _gm = retail.gstin_master
        _co = retail.branch.company if retail.branch_id and retail.branch else None
        in_cgst = _gm.input_cgst.id if _gm and _gm.input_cgst else _raise_missing_ledger("INPUT CGST")
        in_sgst = _gm.input_sgst.id if _gm and _gm.input_sgst else _raise_missing_ledger("INPUT SGST")
        in_igst = _gm.input_igst.id if _gm and _gm.input_igst else _raise_missing_ledger("INPUT IGST")
        _hallmark_ldgr = _co.hallmark_charge_ldgr.id if _co and _co.hallmark_charge_ldgr else _raise_missing_ledger("Hallmarking/Testing Charges")
        _discount_ldgr = _co.discount_ldgr.id if _co and _co.discount_ldgr else _raise_missing_ledger("Discount/Round Off")
        _round_off_ldgr = _co.round_off_ldgr.id if _co and _co.round_off_ldgr else _raise_missing_ledger("Round Off")
        _carriage_ldgr = _co.carriage_inward_ldgr.id if _co and _co.carriage_inward_ldgr else _raise_missing_ledger("Carriage Inward")
        _pr_round_off = Decimal(str(purchase_return_instance.round_off or 0))

        # Build item journal lines: making rolled into first sub-item's purchase_ledger (credit)
        _pr_item_lines = []
        for _main, _sub_details in items_with_details:
            _making = Decimal(str(_main.making_value or 0))
            for _idx, _d in enumerate(_sub_details):
                if not (_d.sub_item and _d.sub_item.purchase_ledger):
                    raise ValidationError(
                        f"Item '{_d.sub_item}' has no purchase ledger configured. "
                        f"Please set the purchase ledger in the Item Master."
                    )
                _amt = Decimal(str(_d.value or 0)) + (_making if _idx == 0 else Decimal('0'))
                _pr_item_lines.append({'account': _d.sub_item.purchase_ledger_id, 'credit': f"{_amt:.2f}"})

        ser = JournalEntrySerializer(data= {'date':purchase_return_instance.date1.strftime('%Y-%m-%d'),
                "voucher_no":purchase_return_instance.billno,
                "narration":f"Purchase Return Narration",
                "voucher_type":global_vars.VoucherType.purc_ret,
                "retail":retail.id,
                "voucher_details": [
                    {
                        'account': in_cgst,
                        'credit':f"{purchase_return_instance.cgst_amt:.2f}"
                    },
                    {'account': in_sgst,
                        'credit':f"{purchase_return_instance.sgst_amt:.2f}"
                    },
                    {'account': in_igst,
                        'credit':f"{purchase_return_instance.igst_amt:.2f}"
                    },
                    {'account':_hallmark_ldgr,
                        'credit':f"{purchase_return_instance.hallmark_charge:.2f}" if purchase_return_instance.hallmark_charge else '0.0'
                    },
                    {'account':_carriage_ldgr,
                        'credit':f"{purchase_return_instance.freight_amt:.2f}" if purchase_return_instance.freight_amt else '0.0'
                    },
                ] +
                # Round off: reverse the sign vs purchase voucher
                # PV: positive round_off → DEBIT round_off_ldgr  → Return: CREDIT round_off_ldgr
                # PV: negative round_off → CREDIT round_off_ldgr → Return: DEBIT round_off_ldgr
                ([{'account': _round_off_ldgr, 'credit': f"{_pr_round_off:.2f}"}] if _pr_round_off > 0 else []) +
                ([{'account': _round_off_ldgr, 'debit': f"{abs(_pr_round_off):.2f}"}] if _pr_round_off < 0 else []) +
                # Discount: PV credits discount_ldgr → Return debits discount_ldgr (reversal)
                ([{'account': _discount_ldgr, 'debit': f"{purchase_return_instance.discount:.2f}"}]
                    if (purchase_return_instance.discount or 0) > 0 else []) +
                _pr_item_lines +
                [{
                    'account':purchase_return_instance.ldgr_id,
                    'debit':f"{(purchase_return_instance.bill_value ):.2f}" if purchase_return_instance.bill_value else '0.0',
                }]},
                context=self.context)

        if ser.is_valid(raise_exception=True):

            ref = ser.save()
        purchase_return_instance.ac_voucher = ref
        purchase_return_instance.gstin_ref  = retail.gstin_master
        purchase_return_instance.branch_ref = retail.branch
        purchase_return_instance.save()

        # Record outflow transactions for barcode-scanned items
        request = self.context.get('request')
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')) if request else None
        for item_inst in item_instances:
            if item_inst.barcode_id:
                BarcodeTransaction.objects.create(
                    barcode=item_inst.barcode,
                    billno=purchase_return_instance.billno,
                    trans_type='PURCHASE-RET',
                    user=request.user if request else None,
                    ip_address=ip,
                    retail=retail,
                )

        return purchase_return_instance

    @transaction.atomic
    def update(self, instance, validated_data):
        detail_data = validated_data.pop('purchasereturnitems_set', [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        create_or_update_nested(PurchaseReturnItemsSerializer, instance, 'purchasereturnitems_set', 'billno', PurchaseReturnItemsSerializer(detail_data, many=True).data)
        purchase_return_instance = instance
        instance.ac_voucher.delete()
        # Fresh DB queries — avoid stale prefetch cache left by create_or_update_nested
        item_instances = list(PurchaseReturnItems.objects.filter(billno=instance).select_related('purity', 'item'))
        item_detail_instances = list(PurchaseReturnDetails.objects.filter(billno=instance).select_related('sub_item__purchase_ledger', 'main_item'))
        retail = self.context.get('request').retail
        _gm = retail.gstin_master
        _co = retail.branch.company if retail.branch_id and retail.branch else None
        in_cgst = _gm.input_cgst.id if _gm and _gm.input_cgst else _raise_missing_ledger("INPUT CGST")
        in_sgst = _gm.input_sgst.id if _gm and _gm.input_sgst else _raise_missing_ledger("INPUT SGST")
        in_igst = _gm.input_igst.id if _gm and _gm.input_igst else _raise_missing_ledger("INPUT IGST")
        _hallmark_ldgr = _co.hallmark_charge_ldgr.id if _co and _co.hallmark_charge_ldgr else _raise_missing_ledger("Hallmarking/Testing Charges")
        _discount_ldgr = _co.discount_ldgr.id if _co and _co.discount_ldgr else _raise_missing_ledger("Discount/Round Off")
        _round_off_ldgr = _co.round_off_ldgr.id if _co and _co.round_off_ldgr else _raise_missing_ledger("Round Off")
        _carriage_ldgr = _co.carriage_inward_ldgr.id if _co and _co.carriage_inward_ldgr else _raise_missing_ledger("Carriage Inward")
        _pr_round_off = Decimal(str(purchase_return_instance.round_off or 0))

        # Build item journal lines: making rolled into first sub-item's purchase_ledger (credit)
        from collections import defaultdict as _defaultdict
        _pr_details_by_main = _defaultdict(list)
        for _d in item_detail_instances:
            _pr_details_by_main[_d.main_item_id].append(_d)
        _pr_item_lines = []
        for _main in item_instances:
            _making = Decimal(str(_main.making_value or 0))
            for _idx, _d in enumerate(_pr_details_by_main.get(_main.id, [])):
                if not (_d.sub_item and _d.sub_item.purchase_ledger):
                    raise ValidationError(
                        f"Item '{_d.sub_item}' has no purchase ledger configured. "
                        f"Please set the purchase ledger in the Item Master."
                    )
                _amt = Decimal(str(_d.value or 0)) + (_making if _idx == 0 else Decimal('0'))
                _pr_item_lines.append({'account': _d.sub_item.purchase_ledger_id, 'credit': f"{_amt:.2f}"})

        ser = JournalEntrySerializer(data= {'date':purchase_return_instance.date1.strftime('%Y-%m-%d'),
                "voucher_no":purchase_return_instance.billno,
                "narration":f"Purchase Return Narration",
                "voucher_type":global_vars.VoucherType.purc_ret,
                "retail":retail.id,
                "voucher_details": [
                    {
                        'account': in_cgst,
                        'credit':f"{purchase_return_instance.cgst_amt:.2f}"
                    },
                    {'account': in_sgst,
                        'credit':f"{purchase_return_instance.sgst_amt:.2f}"
                    },
                    {'account': in_igst,
                        'credit':f"{purchase_return_instance.igst_amt:.2f}"
                    },
                    {'account':_hallmark_ldgr,
                        'credit':f"{purchase_return_instance.hallmark_charge:.2f}" if purchase_return_instance.hallmark_charge else '0.0'
                    },
                    {'account':_carriage_ldgr,
                        'credit':f"{purchase_return_instance.freight_amt:.2f}" if purchase_return_instance.freight_amt else '0.0'
                    },
                ] +
                ([{'account': _round_off_ldgr, 'credit': f"{_pr_round_off:.2f}"}] if _pr_round_off > 0 else []) +
                ([{'account': _round_off_ldgr, 'debit': f"{abs(_pr_round_off):.2f}"}] if _pr_round_off < 0 else []) +
                ([{'account': _discount_ldgr, 'debit': f"{purchase_return_instance.discount:.2f}"}]
                    if (purchase_return_instance.discount or 0) > 0 else []) +
                _pr_item_lines +
                [{
                    'account':purchase_return_instance.ldgr_id,
                    'debit':f"{(purchase_return_instance.bill_value ):.2f}" if purchase_return_instance.bill_value else '0.0',
                }]},
                context=self.context)

        if ser.is_valid(raise_exception=True):

            ref = ser.save()
        purchase_return_instance.ac_voucher = ref
        purchase_return_instance.gstin_ref  = retail.gstin_master
        purchase_return_instance.branch_ref = retail.branch
        purchase_return_instance.save()

        # Refresh barcode outflow transactions: delete old, recreate from current items
        request = self.context.get('request')
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')) if request else None
        BarcodeTransaction.objects.filter(
            billno=purchase_return_instance.billno, trans_type='PURCHASE-RET'
        ).delete()
        for item_inst in item_instances:
            if item_inst.barcode_id:
                BarcodeTransaction.objects.create(
                    barcode=item_inst.barcode,
                    billno=purchase_return_instance.billno,
                    trans_type='PURCHASE-RET',
                    user=request.user if request else None,
                    ip_address=ip,
                    retail=retail,
                )

        return purchase_return_instance
