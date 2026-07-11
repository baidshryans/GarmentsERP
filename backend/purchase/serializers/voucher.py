from decimal import Decimal

from django.db import transaction

from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.serializers import ModelSerializer

import global_vars
from accounting.serializers import JournalEntrySerializer
from accounting.utils import generate_voucher_no
from goldrates.models import PurityMaster
from inventory.models import BarcodeMain
from manufacturing.utils import create_or_update_nested
from mastersconfig.models import Item, Packet, State, Hsn
from sales.models import CustomerOrder, CustomerOrderItems
from ..models import (
    PurchaseVoucher,
    PurchaseVoucherDetails,
    PurchaseVoucherItems,
    PurchaseAttachment,
)


class PurchaseVoucherSerializer(ModelSerializer):
    # GST rates resolved from the linked HSN master row so the print/UI
    # render them without having to walk the FK themselves.
    hsn_cgst_per = serializers.SerializerMethodField()
    hsn_sgst_per = serializers.SerializerMethodField()
    hsn_igst_per = serializers.SerializerMethodField()

    def _hsn_rate(self, obj, field):
        hsn = getattr(obj, 'hsn', None)
        if not hsn:
            return None
        val = getattr(hsn, field, None)
        return float(val) if val is not None else None

    def get_hsn_cgst_per(self, obj): return self._hsn_rate(obj, 'cgst')
    def get_hsn_sgst_per(self, obj): return self._hsn_rate(obj, 'sgst')
    def get_hsn_igst_per(self, obj): return self._hsn_rate(obj, 'igst')

    class Meta:
        model = PurchaseVoucher
        fields = "__all__"


def _raise_missing_ledger(label):
    raise ValidationError(
        {'ledger_config': f"Required ledger '{label}' is not configured on master. Please configure it in Company/GSTIN/Retail master before saving vouchers."}
    )


def _making_ldgr_name_for_purity(co, purity_obj):
    """Return the id (primary key) of the Making Charge Paid ledger matching the item's purity.

    Matches karat ('22', '18', '14') within PurityMaster.purity name.
    Falls back to 22K ledger for unrecognised purities.
    """
    purity_name = purity_obj.purity if purity_obj else ''
    if '22' in purity_name:
        ldgr = co.making_charge_paid_22k_ldgr
    elif '18' in purity_name:
        ldgr = co.making_charge_paid_18k_ldgr
    elif '14' in purity_name:
        ldgr = co.making_charge_paid_14k_ldgr
    else:
        ldgr = co.making_charge_paid_22k_ldgr  # fallback to 22K
    if not ldgr:
        _raise_missing_ledger(f"Making Charge Paid ledger for purity '{purity_name}' (configure on Company master)")
    return ldgr.id


class PurchaseVoucherDetailsSerializer(serializers.ModelSerializer):
    sub_item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code", required=True)
    sub_item_name = serializers.SerializerMethodField()
    metal_purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity",allow_null=True, required=False)
    packet = serializers.SlugRelatedField(queryset=Packet.objects.all(), slug_field="pckt_no", required=False, allow_null=True,)

    def get_sub_item_name(self, obj):
        item = obj.get('sub_item') if isinstance(obj, dict) else obj.sub_item
        return item.item_name if item else None

    class Meta:
        model = PurchaseVoucherDetails
        fields = [
            'id',
            'date1',
            'sub_item',
            'sub_item_name',
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
            'main_item',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False, 'allow_null': True},
            'sub_pcs': {'required': False, 'allow_null': True},
            'main_item': {'required': False, 'allow_null': True},
        }

    @staticmethod
    def _derive_value(validated_data, instance=None):
        """If `value` is missing/zero but sub_gw and rate are present, set
        value = sub_gw * rate. Customer-purchase flow doesn't compute this
        client-side, but we still need it for closing-stock / journals."""
        v = validated_data.get('value')
        if v in (None, 0, Decimal('0'), Decimal('0.00')):
            sub_gw = validated_data.get('sub_gw')
            rate = validated_data.get('rate')
            if sub_gw is None and instance is not None:
                sub_gw = instance.sub_gw
            if rate is None and instance is not None:
                rate = instance.rate
            if sub_gw and rate:
                validated_data['value'] = Decimal(str(sub_gw)) * Decimal(str(rate))

    def create(self, validated_data):
        # Derive billno from main_item so the FK is always populated
        main_item = validated_data.get('main_item')
        if main_item and 'billno' not in validated_data:
            validated_data['billno'] = main_item.billno
        self._derive_value(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Guard: never let an incoming null clear a main_item FK that is already
        # set. The frontend may omit or send null for main_item, but when the
        # record is already attached to a parent item that relationship must be
        # preserved — otherwise filter(main_item=None).delete() will erase it.
        # Records that legitimately have main_item=None (direct details) are
        # unaffected: their existing None stays None.
        if (
            'main_item' in validated_data
            and validated_data['main_item'] is None
            and instance.main_item_id is not None
        ):
            validated_data.pop('main_item')
        self._derive_value(validated_data, instance=instance)
        return super().update(instance, validated_data)


class PurchaseVoucherItemsSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code", required=True)
    item_name = serializers.SerializerMethodField()
    barcode = serializers.SlugRelatedField(queryset=BarcodeMain.objects.all(), slug_field="barcode", required=False,allow_null=True)
    purity = serializers.SlugRelatedField(queryset=PurityMaster.objects.all(), slug_field="purity", required=False)
    order_no = serializers.SlugRelatedField(queryset=CustomerOrder.objects.all(), slug_field="order_no", required=False,allow_null=True)
    customer_order_item = serializers.PrimaryKeyRelatedField(
        queryset=CustomerOrderItems.objects.all(), required=False, allow_null=True
    )

    # Nested serializer for details
    purchasevoucherdetails_set = PurchaseVoucherDetailsSerializer(many=True,)

    def get_item_name(self, obj):
        item = obj.get('item') if isinstance(obj, dict) else obj.item
        return item.item_name if item else None

    class Meta:
        model = PurchaseVoucherItems
        fields = [
            'id',
            'date',
            'po_no',
            'po_sl_no',
            'item',
            'item_name',
            'barcode',
            'barcode_txt',
            'order_no',
            'customer_order_item',
            'sl_no',
            'pcs',
            'gw',
            'size',
            'purity',
            'pending_pcs',
            'pending_gw',
            'making',
            'making_type',
            'making_value',
            'item_value',
            'remarks',
            'purchasevoucherdetails_set',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False, 'allow_null': True},
            'pcs': {'required': False, 'allow_null': True},
            'pending_pcs': {'required': False, 'allow_null': True},
            'making_type': {'required': False, 'allow_blank': True},
            'making_value': {'required': False, 'allow_null': True},
        }

    def validate(self, data):
        details = data.get('purchasevoucherdetails_set', [])
        if details:
            gw = Decimal(str(data.get('gw', 0) or 0))
            total_sub_gw = sum(Decimal(str(d.get('sub_gw', 0) or 0)) for d in details)
            if abs(total_sub_gw - gw) > Decimal('0.01'):
                raise ValidationError(
                    f"Sub-item GW total ({total_sub_gw:.3f}g) does not match item GW ({gw:.3f}g). Please reconcile."
                )

        # Mutual exclusivity: a line is either from a PO (carries po_no/po_sl_no)
        # or directly from a CO item — never both.
        coi = data.get('customer_order_item')
        po_no = data.get('po_no')
        po_sl_no = data.get('po_sl_no')
        if coi and (po_no or po_sl_no):
            raise ValidationError(
                "A Purchase Voucher line cannot reference both a Purchase Order and a Customer Order item."
            )

        # Already-billed guard for the direct CO → PV path.
        if coi:
            from sales.serializers import _customer_order_item_lock
            state, reason = _customer_order_item_lock(coi)
            if state == 'billed' and (self.instance is None or self.instance.customer_order_item_id != coi.id):
                raise ValidationError(
                    f"Customer order item is already locked: {reason or state}."
                )

        return data

    def create(self, validated_data):
        details_data = validated_data.pop('purchasevoucherdetails_set')
        coi = validated_data.get('customer_order_item')
        # Mirror voucher date onto the item row when FE omits date1.
        billno = validated_data.get('billno')
        if billno and not validated_data.get('date1'):
            validated_data['date1'] = billno.date1
        voucher_item_instance = PurchaseVoucherItems.objects.create(**validated_data)

        # Create related PurchaseVoucherDetails instances
        for detail_data in details_data:
            PurchaseVoucherDetailsSerializer._derive_value(detail_data)
            if not detail_data.get('date1') and voucher_item_instance.billno_id:
                detail_data['date1'] = voucher_item_instance.billno.date1
            PurchaseVoucherDetails.objects.create(main_item=voucher_item_instance, **detail_data)

        # Belt-and-braces: flip sale_status True so the CO item is locked
        # even if the FK is later nulled by on_delete=SET_NULL.
        if coi:
            from sales.models import CustomerOrderItems
            CustomerOrderItems.objects.filter(pk=coi.pk).update(sale_status=True)

        return voucher_item_instance

    def update(self, instance, validated_data):
        detail_data = validated_data.pop('purchasevoucherdetails_set', [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        reserialized = PurchaseVoucherDetailsSerializer(detail_data, many=True).data
        create_or_update_nested(PurchaseVoucherDetailsSerializer, instance, 'purchasevoucherdetails_set',  'main_item', reserialized)

        # ── Always recompute item_value from the actual saved sub-item values.
        #    item_value = Σ(sub-item.value) + making_value.
        #    This prevents a debit/credit mismatch when a sub-item rate is edited:
        #    the frontend may send a stale item_value, but the journal debits use
        #    the real sub-item values, so item_value must match the real total.
        from django.db.models import Sum
        actual_sub_value = (
            instance.purchasevoucherdetails_set
            .aggregate(total=Sum('value'))['total']
            or Decimal('0')
        )
        actual_making = Decimal(str(instance.making_value or 0))
        instance.item_value = actual_sub_value + actual_making
        instance.save(update_fields=['item_value'])

        return instance


class PurchaseVoucherPostSerializer(serializers.ModelSerializer):

    # Nested serializers
    purchasevoucheritems_set = PurchaseVoucherItemsSerializer(many=True)
    # Direct raw/material details not linked to a main item
    purchasevoucherdetails_set = PurchaseVoucherDetailsSerializer(many=True, required=False)
    # Accept/return HSN by hsn_no instead of pk
    hsn = serializers.SlugRelatedField(slug_field='hsn_no', queryset=Hsn.objects.all(), required=False, allow_null=True)
    # First 2 digits of the vendor's GSTIN = state code (read-only, used by frontend for IGST vs CGST+SGST logic).
    # ldgr is already select_related in the viewset queryset, so no extra DB hit.
    vendor_state_code = serializers.SerializerMethodField()
    total_gw = serializers.SerializerMethodField()
    total_stone_wt = serializers.SerializerMethodField()
    total_nw = serializers.SerializerMethodField()
    party_address = serializers.SerializerMethodField()
    party_pan     = serializers.SerializerMethodField()
    party_gstin   = serializers.SerializerMethodField()
    party_phone   = serializers.SerializerMethodField()
    party_aadhar  = serializers.SerializerMethodField()
    party_state   = serializers.SerializerMethodField()
    hsn_cgst_per  = serializers.SerializerMethodField()
    hsn_sgst_per  = serializers.SerializerMethodField()
    hsn_igst_per  = serializers.SerializerMethodField()

    def _hsn_rate(self, obj, field):
        hsn = getattr(obj, 'hsn', None)
        if not hsn:
            return None
        val = getattr(hsn, field, None)
        return float(val) if val is not None else None

    def get_hsn_cgst_per(self, obj): return self._hsn_rate(obj, 'cgst')
    def get_hsn_sgst_per(self, obj): return self._hsn_rate(obj, 'sgst')
    def get_hsn_igst_per(self, obj): return self._hsn_rate(obj, 'igst')

    def get_party_address(self, obj):
        ldgr = obj.ldgr
        if not ldgr:
            return ''
        parts = [ldgr.add1, ldgr.add2, ldgr.city]
        addr = ', '.join(p for p in parts if p)
        if ldgr.pincode:
            addr += ' - ' + ldgr.pincode
        return addr

    def get_party_pan(self, obj):
        return obj.ldgr.pan if obj.ldgr else ''

    def get_party_gstin(self, obj):
        return obj.ldgr.gst if obj.ldgr else ''

    def get_party_phone(self, obj):
        ldgr = obj.ldgr
        if not ldgr:
            return ''
        return ldgr.mobile1 or ldgr.phone1 or ''

    def get_party_aadhar(self, obj):
        return obj.ldgr.aadhar if obj.ldgr else ''

    def get_party_state(self, obj):
        return obj.ldgr.state if obj.ldgr else ''

    def get_vendor_state_code(self, obj):
        try:
            gst = obj.ldgr.gst
            return gst[:2] if gst else None
        except Exception:
            return None

    def get_total_gw(self, obj):
        return float(sum(
            (item.gw or Decimal('0')) for item in obj.purchasevoucheritems_set.all()
        ))

    def get_total_stone_wt(self, obj):
        stone_wt = Decimal('0')
        for item in obj.purchasevoucheritems_set.all():
            for detail in item.purchasevoucherdetails_set.all():
                if detail.sub_item and detail.sub_item.item_type == 'S':
                    stone_wt += detail.sub_ct or Decimal('0')
        return float(stone_wt)

    def get_total_nw(self, obj):
        gold_nw = Decimal('0')
        for item in obj.purchasevoucheritems_set.all():
            for detail in item.purchasevoucherdetails_set.all():
                if detail.sub_item_id == 31:
                    gold_nw += detail.sub_gw or Decimal('0')
        return float(gold_nw)

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
            'ldgr',
            'ldgr_name',
            'vendor_state_code',
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
            'due_amt',
            'is_return',
            'hsn',
            'purchasevoucheritems_set',
            'purchasevoucherdetails_set',
            'total_gw',
            'total_stone_wt',
            'total_nw',
            'party_address',
            'party_pan',
            'party_gstin',
            'party_phone',
            'party_aadhar',
            'party_state',
            'hsn_cgst_per',
            'hsn_sgst_per',
            'hsn_igst_per',
            'source',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
        }

    def create(self, validated_data):
        with transaction.atomic():
            items_data = validated_data.pop('purchasevoucheritems_set')
            direct_details_data = validated_data.pop('purchasevoucherdetails_set', [])
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
            _vtype = validated_data.get('voucher_type')
            _prefix = 'PVC' if _vtype == 'Customer' else 'PVV'
            purchase_voucher_instance = PurchaseVoucher(**validated_data)
            from accounting.utils import save_with_bill_number
            save_with_bill_number(purchase_voucher_instance, _retail, _prefix, field='billno',
                                  fy=validated_data.get('fiscal_year'))

            # Create related PurchaseVoucherItems and their sub-details
            item_detail_instances = []
            item_instances = []
            _retail = purchase_voucher_instance.retail
            for item_data in items_data:
                details_data = item_data.pop('purchasevoucherdetails_set')
                # Mirror the voucher date onto the item/detail rows when the
                # frontend omits date1 — the column is nullable but downstream
                # reports (closing stock, day book) rely on it.
                item_data.setdefault('date1', purchase_voucher_instance.date1)
                voucher_item_instance = PurchaseVoucherItems.objects.create(
                    billno=purchase_voucher_instance,
                    retail=_retail,
                    **item_data,
                )
                item_instances.append(voucher_item_instance)
                _detail_value_sum = Decimal('0')
                for detail_data in details_data:
                    PurchaseVoucherDetailsSerializer._derive_value(detail_data)
                    detail_data.setdefault('date1', purchase_voucher_instance.date1)
                    det = PurchaseVoucherDetails.objects.create(
                        main_item=voucher_item_instance,
                        billno=purchase_voucher_instance,
                        retail=_retail,
                        **detail_data,
                    )
                    item_detail_instances.append(det)
                    _detail_value_sum += Decimal(str(det.value or 0))
                # Recompute item_value so customer-purchase rows (where the
                # client sends 0) end up with the correct total. item_value
                # = Σ(detail.value) + making_value.
                _making = Decimal(str(voucher_item_instance.making_value or 0))
                voucher_item_instance.item_value = _detail_value_sum + _making
                voucher_item_instance.save(update_fields=['item_value'])

            # Create direct raw/material details (no parent main item)
            for detail_data in direct_details_data:
                detail_data.pop('main_item', None)
                PurchaseVoucherDetailsSerializer._derive_value(detail_data)
                detail_data.setdefault('date1', purchase_voucher_instance.date1)
                det = PurchaseVoucherDetails.objects.create(
                    billno=purchase_voucher_instance,
                    main_item=None,
                    retail=_retail,
                    **detail_data,
                )
                item_detail_instances.append(det)

            # ── Recompute bill_value from actual created data so the journal
            #    entry is always internally consistent.
            _item_value_sum = sum(
                Decimal(str(item.item_value or 0)) for item in item_instances
            )
            _direct_value_sum = sum(
                Decimal(str(d.value or 0))
                for d in item_detail_instances if d.main_item is None
            )
            _taxable = (
                _item_value_sum + _direct_value_sum
                + Decimal(str(purchase_voucher_instance.freight_amt or 0))
                + Decimal(str(purchase_voucher_instance.hallmark_charge or 0))
                + Decimal(str(purchase_voucher_instance.add_chrg_amt1 or 0))
                + Decimal(str(purchase_voucher_instance.add_chrg_amt2 or 0))
            )
            purchase_voucher_instance.bill_value = (
                _taxable
                + Decimal(str(purchase_voucher_instance.cgst or 0))
                + Decimal(str(purchase_voucher_instance.sgst or 0))
                + Decimal(str(purchase_voucher_instance.igst or 0))
                + Decimal(str(purchase_voucher_instance.tcs_amt or 0))
                + Decimal(str(purchase_voucher_instance.round_off or 0))
            )
            # On creation the full bill is outstanding — nothing has been paid yet.
            purchase_voucher_instance.due_amt = purchase_voucher_instance.bill_value
            purchase_voucher_instance.save(update_fields=['bill_value', 'due_amt'])

            retail = self.context.get('request').retail
            _gm = retail.gstin_master
            _co = retail.branch.company if retail.branch_id and retail.branch else None
            in_cgst = _gm.input_cgst.id if _gm and _gm.input_cgst else _raise_missing_ledger("INPUT CGST")
            in_sgst = _gm.input_sgst.id if _gm and _gm.input_sgst else _raise_missing_ledger("INPUT SGST")
            in_igst = _gm.input_igst.id if _gm and _gm.input_igst else _raise_missing_ledger("INPUT IGST")
            _hallmark_ldgr = _co.hallmark_charge_ldgr.id if _co and _co.hallmark_charge_ldgr else _raise_missing_ledger("Hallmarking/Testing Charges")
            _discount_ldgr = _co.discount_ldgr.id if _co and _co.discount_ldgr else _raise_missing_ledger("Discount")
            _round_off_ldgr = _co.round_off_ldgr.id if _co and _co.round_off_ldgr else _raise_missing_ledger("Round Off")
            _carriage_ldgr = _co.carriage_inward_ldgr.id if _co and _co.carriage_inward_ldgr else _raise_missing_ledger("Carriage Inward")
            _round_off = Decimal(str(purchase_voucher_instance.round_off or 0))

            # making charge ledger is resolved per-item by purity (see _making_ldgr_name_for_purity)
            ser = JournalEntrySerializer(data= {'date':purchase_voucher_instance.date1.strftime('%Y-%m-%d'),
                            "voucher_no":purchase_voucher_instance.billno,
                            "narration":f"Purchase Voucher {purchase_voucher_instance.billno}",
                            "voucher_type":global_vars.VoucherType.purc_sc,
                            "retail":retail.id,
                            "voucher_details": (
                                ([{'account': in_cgst, 'debit': f"{purchase_voucher_instance.cgst:.2f}"}] if (purchase_voucher_instance.cgst or 0) != 0 else []) +
                                ([{'account': in_sgst, 'debit': f"{purchase_voucher_instance.sgst:.2f}"}] if (purchase_voucher_instance.sgst or 0) != 0 else []) +
                                ([{'account': in_igst, 'debit': f"{purchase_voucher_instance.igst:.2f}"}] if (purchase_voucher_instance.igst or 0) != 0 else [])
                            ) + [
                                {'account':_hallmark_ldgr,
                                    'debit':f"{purchase_voucher_instance.hallmark_charge:.2f}" if purchase_voucher_instance.hallmark_charge else'0.0'
                                },
                                {'account':_carriage_ldgr,
                                    'debit':f"{purchase_voucher_instance.freight_amt:.2f}" if purchase_voucher_instance.freight_amt else '0.0'
                                },
                                {'account':_discount_ldgr,
                                  'credit': f"{(purchase_voucher_instance.discount_amt or 0):.2f}" },
                            ] +
                            ([{'account': _round_off_ldgr, 'debit': f"{_round_off:.2f}"}] if _round_off > 0 else []) +
                            ([{'account': _round_off_ldgr, 'credit': f"{abs(_round_off):.2f}"}] if _round_off < 0 else []) +
                            [{'account': _making_ldgr_name_for_purity(_co, item.purity),
                                'debit': f"{item.making_value:.2f}"
                            } for item in item_instances if item.making_value] +
                            [{'account': (
                                    item.sub_item.purchase_ledger.id
                                    if item.sub_item and item.sub_item.purchase_ledger
                                    else (_ for _ in ()).throw(ValidationError(
                                        f"Item '{item.sub_item}' has no purchase ledger configured. "
                                        f"Please set the purchase ledger in the Item Master."
                                    ))
                                ),
                                'debit':f"{item.value:.2f}"
                            } for item in item_detail_instances]  +
                            [{
                                'account': purchase_voucher_instance.ldgr_id,
                                'credit': f"{purchase_voucher_instance.bill_value:.2f}" if purchase_voucher_instance.bill_value else '0.0',
                            }]},
                            context=self.context)

            if ser.is_valid(raise_exception=True):
                ref = ser.save()
                purchase_voucher_instance.ac_voucher = ref

            # Separate TDS journal: Dr Vendor / Cr TDS Payable
            _tds_amt = purchase_voucher_instance.tds_amt or 0
            _existing_tds_voucher_no = None  # new voucher — no prior TDS journal to preserve
            if _tds_amt > 0 and purchase_voucher_instance.tds_section:
                _tds_ldgr = purchase_voucher_instance.tds_section.ledger
                if not _tds_ldgr:
                    _raise_missing_ledger(f"TDS Payable u/s {purchase_voucher_instance.tds_section.section_code}")
                tds_ser = JournalEntrySerializer(data={
                    'date': purchase_voucher_instance.date1.strftime('%Y-%m-%d'),
                    'voucher_no': _existing_tds_voucher_no or f"{purchase_voucher_instance.billno}/TDS",
                    'narration': f"TDS u/s {purchase_voucher_instance.tds_section.section_code} on {purchase_voucher_instance.billno}",
                    'voucher_type': global_vars.VoucherType.purc_sc,
                    'retail': retail.id,
                    'voucher_details': [
                        {'account': purchase_voucher_instance.ldgr_id, 'debit': f"{_tds_amt:.2f}"},
                        {'account': _tds_ldgr.id, 'credit': f"{_tds_amt:.2f}"},
                    ],
                }, context=self.context)
                if tds_ser.is_valid(raise_exception=True):
                    purchase_voucher_instance.tds_ac_voucher = tds_ser.save()

            purchase_voucher_instance.gstin_ref  = retail.gstin_master
            purchase_voucher_instance.branch_ref = retail.branch
            purchase_voucher_instance.save()
            return purchase_voucher_instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            items_data = validated_data.pop('purchasevoucheritems_set', [])
            direct_details_data = validated_data.pop('purchasevoucherdetails_set', [])
            validated_data.pop("ac_voucher", None)

            # Snapshot current DB values BEFORE setattr overwrites them.
            # Used later to preserve partial payments when bill_value changes.
            _db_bill_value = Decimal(str(instance.bill_value or 0))
            _db_due_amt    = Decimal(str(instance.due_amt    or 0))

            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(PurchaseVoucherItemsSerializer, instance, 'purchasevoucheritems_set', 'billno', PurchaseVoucherItemsSerializer(items_data, many=True).data)

            # Rebuild direct details (those without a main item)
            instance.purchasevoucherdetails_set.filter(main_item=None).delete()
            for detail_data in direct_details_data:
                # FE may echo back fields we set explicitly below — drop them so
                # **detail_data doesn't double-pass billno/main_item/retail.
                detail_data = {k: v for k, v in detail_data.items()
                               if k not in {"billno", "main_item", "retail", "id"}}
                PurchaseVoucherDetailsSerializer._derive_value(detail_data)
                detail_data.setdefault('date1', instance.date1)
                PurchaseVoucherDetails.objects.create(
                    billno=instance,
                    main_item=None,
                    retail=instance.retail,
                    **detail_data,
                )

            # ── Use fresh DB queries here — the prefetch_related cache on `instance`
            #    is STALE after create_or_update_nested modifies sub-items.
            #    Using stale cache gives old detail values in the journal, causing
            #    the debit/credit mismatch equal to the rate-change amount.
            from ..models import PurchaseVoucherItems as _PVItems
            from ..models import PurchaseVoucherDetails as _PVDetails
            item_instances = list(
                _PVItems.objects.filter(billno=instance).select_related('item', 'purity')
            )
            # Catch BOTH classes of detail rows:
            #   1. Nested under a main item — newly created ones during edit
            #      come through PurchaseVoucherItemsSerializer.update() and only
            #      have main_item set (billno=NULL); pre-existing ones still
            #      carry billno from create time.
            #   2. Direct (orphan) details — always have billno=instance and
            #      main_item=NULL.
            # A `billno=instance`-only filter silently dropped newly-added
            # nested details, collapsing item_value/bill_value to a stale subset
            # and breaking journal balance after an edit that added rows.
            from django.db.models import Q as _Q
            item_detail_instances = list(
                _PVDetails.objects
                .filter(
                    (_Q(billno=instance) | _Q(main_item__billno=instance))
                    & _Q(main_item__isnull=False)
                )
                .select_related('sub_item__purchase_ledger')
                .order_by('main_item_id', 'id')
                .distinct()
            ) + list(
                _PVDetails.objects.filter(billno=instance, main_item__isnull=True)
                .select_related('sub_item__purchase_ledger')
            )

            # ── Recompute bill_value from the actual saved data so the journal
            #    entry is always internally consistent, regardless of what the
            #    frontend sent.  This prevents a debit/credit mismatch when
            #    sub-item rates are changed during an edit.
            _item_value_sum = sum(
                Decimal(str(item.item_value or 0)) for item in item_instances
            )
            # Separate direct details (no main_item) for bill_value — already fresh from DB
            _direct_details = [d for d in item_detail_instances if d.main_item_id is None]
            _direct_value_sum = sum(Decimal(str(d.value or 0)) for d in _direct_details)
            _taxable = (
                _item_value_sum + _direct_value_sum
                + Decimal(str(instance.freight_amt or 0))
                + Decimal(str(instance.hallmark_charge or 0))
                + Decimal(str(instance.add_chrg_amt1 or 0))
                + Decimal(str(instance.add_chrg_amt2 or 0))
            )
            instance.bill_value = (
                _taxable
                + Decimal(str(instance.cgst or 0))
                + Decimal(str(instance.sgst or 0))
                + Decimal(str(instance.igst or 0))
                + Decimal(str(instance.tcs_amt or 0))
                + Decimal(str(instance.round_off or 0))
            )
            # Recalculate due_amt preserving any partial payments already recorded.
            # amount_paid = old bill_value − old due_amt  (both captured before any edits above)
            # new due_amt  = new bill_value − amount_paid (clamped to ≥ 0)
            _amount_paid = max(_db_bill_value - _db_due_amt, Decimal('0'))
            instance.due_amt = max(instance.bill_value - _amount_paid, Decimal('0'))
            instance.save(update_fields=['bill_value', 'due_amt'])

            _existing_voucher_no     = instance.ac_voucher.voucher_no     if instance.ac_voucher     else None
            _existing_tds_voucher_no = instance.tds_ac_voucher.voucher_no if instance.tds_ac_voucher else None
            if instance.ac_voucher:
                instance.ac_voucher.delete()
            if instance.tds_ac_voucher:
                instance.tds_ac_voucher.delete()

            purchase_voucher_instance = instance
            retail = self.context.get('request').retail
            _gm = retail.gstin_master
            _co = retail.branch.company if retail.branch_id and retail.branch else None
            in_cgst = _gm.input_cgst.id if _gm and _gm.input_cgst else _raise_missing_ledger("INPUT CGST")
            in_sgst = _gm.input_sgst.id if _gm and _gm.input_sgst else _raise_missing_ledger("INPUT SGST")
            in_igst = _gm.input_igst.id if _gm and _gm.input_igst else _raise_missing_ledger("INPUT IGST")
            _hallmark_ldgr = _co.hallmark_charge_ldgr.id if _co and _co.hallmark_charge_ldgr else _raise_missing_ledger("Hallmarking/Testing Charges")
            _discount_ldgr = _co.discount_ldgr.id if _co and _co.discount_ldgr else _raise_missing_ledger("Discount")
            _round_off_ldgr = _co.round_off_ldgr.id if _co and _co.round_off_ldgr else _raise_missing_ledger("Round Off")
            _carriage_ldgr = _co.carriage_inward_ldgr.id if _co and _co.carriage_inward_ldgr else _raise_missing_ledger("Carriage Inward")
            _round_off = Decimal(str(purchase_voucher_instance.round_off or 0))
            # making charge ledger is resolved per-item by purity (see _making_ldgr_name_for_purity)
            ser = JournalEntrySerializer(data= {'date':purchase_voucher_instance.date1.strftime('%Y-%m-%d'),
                            "voucher_no":purchase_voucher_instance.billno,
                            "narration":f"Purchase Voucher {purchase_voucher_instance.billno}",
                            "voucher_type":global_vars.VoucherType.purc_sc,
                            "retail":retail.id,
                            "voucher_details": (
                                ([{'account': in_cgst, 'debit': f"{purchase_voucher_instance.cgst:.2f}"}] if (purchase_voucher_instance.cgst or 0) != 0 else []) +
                                ([{'account': in_sgst, 'debit': f"{purchase_voucher_instance.sgst:.2f}"}] if (purchase_voucher_instance.sgst or 0) != 0 else []) +
                                ([{'account': in_igst, 'debit': f"{purchase_voucher_instance.igst:.2f}"}] if (purchase_voucher_instance.igst or 0) != 0 else [])
                            ) + [
                                {'account':_hallmark_ldgr,
                                    'debit':f"{purchase_voucher_instance.hallmark_charge:.2f}" if purchase_voucher_instance.hallmark_charge else'0.0'
                                },
                                {'account':_carriage_ldgr,
                                    'debit':f"{purchase_voucher_instance.freight_amt:.2f}" if purchase_voucher_instance.freight_amt else '0.0'
                                },
                                {'account':_discount_ldgr,
                                    'credit': f"{(purchase_voucher_instance.discount_amt or 0):.2f}"
                                },
                            ] +
                            ([{'account': _round_off_ldgr, 'debit': f"{_round_off:.2f}"}] if _round_off > 0 else []) +
                            ([{'account': _round_off_ldgr, 'credit': f"{abs(_round_off):.2f}"}] if _round_off < 0 else []) +
                            [{'account': _making_ldgr_name_for_purity(_co, item.purity),
                                'debit': f"{item.making_value:.2f}"
                            } for item in item_instances if item.making_value] +
                            [{'account': (
                                    item.sub_item.purchase_ledger.id
                                    if item.sub_item and item.sub_item.purchase_ledger
                                    else (_ for _ in ()).throw(ValidationError(
                                        f"Item '{item.sub_item}' has no purchase ledger configured. "
                                        f"Please set the purchase ledger in the Item Master."
                                    ))
                                ),
                                'debit':f"{item.value:.2f}"
                            } for item in item_detail_instances]  +
                            [{
                                'account': purchase_voucher_instance.ldgr_id,
                                'credit': f"{purchase_voucher_instance.bill_value:.2f}" if purchase_voucher_instance.bill_value else '0.0',
                            }]},
                            context=self.context)

            if ser.is_valid(raise_exception=True):
                ref = ser.save()
                purchase_voucher_instance.ac_voucher = ref

            # Separate TDS journal: Dr Vendor / Cr TDS Payable
            _tds_amt = purchase_voucher_instance.tds_amt or 0
            if _tds_amt > 0 and purchase_voucher_instance.tds_section:
                _tds_ldgr = purchase_voucher_instance.tds_section.ledger
                if not _tds_ldgr:
                    _raise_missing_ledger(f"TDS Payable u/s {purchase_voucher_instance.tds_section.section_code}")
                tds_ser = JournalEntrySerializer(data={
                    'date': purchase_voucher_instance.date1.strftime('%Y-%m-%d'),
                    'voucher_no': _existing_tds_voucher_no or f"{purchase_voucher_instance.billno}/TDS",
                    'narration': f"TDS u/s {purchase_voucher_instance.tds_section.section_code} on {purchase_voucher_instance.billno}",
                    'voucher_type': global_vars.VoucherType.purc_sc,
                    'retail': retail.id,
                    'voucher_details': [
                        {'account': purchase_voucher_instance.ldgr_id, 'debit': f"{_tds_amt:.2f}"},
                        {'account': _tds_ldgr.id, 'credit': f"{_tds_amt:.2f}"},
                    ],
                }, context=self.context)
                if tds_ser.is_valid(raise_exception=True):
                    purchase_voucher_instance.tds_ac_voucher = tds_ser.save()

            purchase_voucher_instance.gstin_ref  = retail.gstin_master
            purchase_voucher_instance.branch_ref = retail.branch
            purchase_voucher_instance.save()
            return purchase_voucher_instance


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
    purchasevoucheritems_set = PurchaseVoucherItemToReturnSerializer(many=True)

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
