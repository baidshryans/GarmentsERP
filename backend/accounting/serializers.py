from decimal import Decimal
from rest_framework import serializers

from accounting.utils import generate_voucher_no
import global_vars
from manufacturing.utils import create_or_update_nested
from mastersconfig.models import RetailMaster
from sales.models import SalesVou
from .models import Account, CashGoldConversion, LedgerOpenBalance
from django.db import transaction
from rest_framework.exceptions import ValidationError


from rest_framework import serializers
from .models import VoucherMain, VoucherDetail, Ledger, ReferenceBills, VoucherAttachment, BankStatementEntry
from contacts.models import LedgerRole
from purchase.models import PurchaseVoucher


class BankStatementSerializer(serializers.ModelSerializer):
    bank_ledger_name = serializers.CharField(source='bank_ledger.ac_name', read_only=True)
    is_matched       = serializers.SerializerMethodField()

    class Meta:
        model  = BankStatementEntry
        fields = [
            'id', 'bank_ledger', 'bank_ledger_name', 'date', 'description',
            'reference', 'debit', 'credit', 'matched_entry', 'is_matched', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'is_matched']

    def get_is_matched(self, obj):
        return obj.matched_entry_id is not None


class _LedgerRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerRole
        fields = ['role', 'is_primary']


def _has_role(account, role):
    """Check if a Ledger instance has a given role. Replaces account.type == role checks."""
    if account is None:
        return False
    return account.roles.filter(role=role).exists()


class LedgerSerializer(serializers.ModelSerializer):
    roles = _LedgerRoleSerializer(many=True, read_only=True)
    primary_role = serializers.SerializerMethodField()
    ac_group_name = serializers.CharField(source='ac_group.name', read_only=True, allow_null=True)

    class Meta:
        model = Ledger
        fields = "__all__"

    def get_primary_role(self, obj):
        r = obj.roles.filter(is_primary=True).first()
        if r:
            return r.role
        first = obj.roles.first()
        return first.role if first else None

class VoucherDetailSerializer(serializers.ModelSerializer):
    account = serializers.SlugRelatedField(queryset=Ledger.objects.all(),slug_field="ac_name")
    credit = serializers.FloatField(default=0)
    debit = serializers.FloatField(default=0)
    class Meta:
        model = VoucherDetail
        fields=[
        "voucher_no",
        "ref_bill_no",
        "voucher_type",
        "account",
        "status",
        "debit",
        "credit",
        "party_bank_name",
        "chq_no", 
        "chq_date"
        ]
        extra_kwargs = {
            'retail_code': {'required': False},
            'voucher_no': {'required': False},
            'voucher_type': {'required': False}
        }


class GoldCashSerializder(serializers.ModelSerializer):
    class Meta:
        model = CashGoldConversion
        fields = "__all__"
        
    def create(self, validated_data):
        with transaction.atomic():
            instance = CashGoldConversion.objects.create(**validated_data)
            # Create journal entry for gold/cash conversion
            _retail = self.context['request'].retail
            _co = _retail.branch.company if _retail.branch_id and _retail.branch else None
            _gold_conv_ldgr = _co.gold_conversion_ldgr.ac_name if _co and _co.gold_conversion_ldgr else "Gold Conversion"
            journal_data = {
                'date': instance.date,
                'voucher_no': generate_voucher_no(type=global_vars.VoucherType.journal,retail=_retail),
                'narration': f"{'Cash to Gold' if instance.conv_type == 'CG' else 'Gold to Cash'} Conversion",
                'voucher_type': global_vars.VoucherType.journal,
                'voucher_details': []
            }

            if instance.conv_type == 'CG':
                # Cash to Gold entry
                journal_data['voucher_details'] = [
                    {
                        'account': instance.ldgr.ac_name,
                        'debit': instance.amount,
                        'credit': 0
                    },
                    {
                        'account': _gold_conv_ldgr,
                        'debit': 0,
                        'credit': instance.amount
                    }
                ]
            else:
                # Gold to Cash entry
                journal_data['voucher_details'] = [
                    {
                        'account': _gold_conv_ldgr,
                        'debit': instance.amount,
                        'credit': 0
                    },
                    {
                        'account': instance.ldgr.ac_name,
                        'debit': 0,
                        'credit': instance.amount
                    }
                ]

            serializer = JournalEntrySerializer(data=journal_data, context={'request': self.context['request']})
            serializer.is_valid(raise_exception=True)
            
            serializer.save()
            instance.v_type = serializer.instance
            instance.save()
            return instance
        

class CashbookTransactionSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.ac_name", read_only=True)
    class Meta:
        model = VoucherDetail
        fields = [
            "voucher_no",
            "voucher_type",
            "account_name",
            "debit",
            "credit",
            "party_bank_name",
            "chq_no",
            "chq_date",
        ]


class JournalEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False,read_only=False)
    date = serializers.DateField()
    voucher_no = serializers.CharField(max_length=50)
    narration = serializers.CharField(max_length=200)
    voucher_type = serializers.CharField(max_length=10)
    retail = serializers.PrimaryKeyRelatedField(queryset=RetailMaster.objects.all())
    status = serializers.CharField(max_length=200,required=False)
    voucher_details = VoucherDetailSerializer(many=True,source='transactions')
    """
    {
      date:
    }
    """
    
    @transaction.atomic
    def create(self, validated_data):
        voucher_details = validated_data.pop('transactions')

        # ── Section 269ST cash receipt limit check (standalone RCPT only) ────
        retail_obj = validated_data.get('retail')
        if (
            validated_data.get('voucher_type', '').strip().upper() == 'RCPT'
            and retail_obj
            and retail_obj.cash_ldgr
        ):
            from accounting.utils import get_customer_cash_received
            cash_ldgr = retail_obj.cash_ldgr
            limit = Decimal(str(retail_obj.max_cash_receipt_limit))
            fy = retail_obj.active_fy

            new_cash = sum(
                Decimal(str(d.get('debit', 0) or 0))
                for d in voucher_details
                if d.get('account') == cash_ldgr
                or _has_role(d.get('account'), 'CA')
            )
            customer_ldgr = next(
                (
                    d['account'] for d in voucher_details
                    if (d.get('credit', 0) or 0) > 0
                    and not _has_role(d.get('account'), 'CA')
                    and not _has_role(d.get('account'), 'BA')
                ),
                None,
            )
            if new_cash > 0 and customer_ldgr and fy:
                already = get_customer_cash_received(retail_obj, fy, customer_ldgr)
                if already + new_cash > limit:
                    remaining = max(Decimal('0'), limit - already)
                    raise ValidationError(
                        f"Cash receipt limit exceeded for '{customer_ldgr.ac_name}'. "
                        f"Already received ₹{already:,.0f} this FY  |  "
                        f"Limit: ₹{limit:,.0f}  |  "
                        f"Max receivable now: ₹{remaining:,.0f}."
                    )
        # ── Section 40A(3) daily cash payment limit check (PMNT only) ────────
        if (
            validated_data.get('voucher_type', '').strip().upper() == 'PMNT'
            and retail_obj
        ):
            from accounting.utils import get_vendor_cash_paid_on_date
            cash_ldgr_pm = retail_obj.cash_ldgr
            limit_pm = Decimal(str(retail_obj.max_cash_payment_limit))
            payment_date = validated_data.get('date')

            # Cash = the CREDIT side of a payment (money leaving via cash ledger)
            new_cash_pm = sum(
                Decimal(str(d.get('credit', 0) or 0))
                for d in voucher_details
                if (
                    (cash_ldgr_pm and d.get('account') == cash_ldgr_pm)
                    or _has_role(d.get('account'), 'CA')
                )
            )
            # Vendor = the DEBIT side (non-cash, non-bank ledger)
            vendor_ldgr = next(
                (
                    d['account'] for d in voucher_details
                    if (d.get('debit', 0) or 0) > 0
                    and not _has_role(d.get('account'), 'CA')
                    and not _has_role(d.get('account'), 'BA')
                ),
                None,
            )
            if new_cash_pm > 0 and vendor_ldgr and payment_date:
                already_pm = get_vendor_cash_paid_on_date(retail_obj, payment_date, vendor_ldgr)
                if already_pm + new_cash_pm > limit_pm:
                    remaining_pm = max(Decimal('0'), limit_pm - already_pm)
                    raise ValidationError(
                        f"Cash payment limit exceeded for '{vendor_ldgr.ac_name}' on {payment_date}. "
                        f"Already paid ₹{already_pm:,.0f} today  |  "
                        f"Limit: ₹{limit_pm:,.0f}/day  |  "
                        f"Max payable in cash now: ₹{remaining_pm:,.0f}."
                    )
        # ─────────────────────────────────────────────────────────────────────

        voucher_main = VoucherMain.objects.create(
            **validated_data,
            amount=sum(float(detail['debit'] or 0) for detail in voucher_details)
        )

        debit_total = sum(d.get("debit", 0) for d in voucher_details)
        credit_total = sum(d.get("credit", 0) for d in voucher_details)

        if round(Decimal(str(debit_total)), 2) != round(Decimal(str(credit_total)), 2):
            raise ValidationError(f"Total debit and credit amounts must be equal credit:{credit_total} debit:{debit_total} \n det :{voucher_details}")
        for detail in voucher_details:

            if detail['debit'] == 0 and detail['credit'] == 0:
                continue
            if detail['debit'] > 0 and detail['credit'] > 0:
                raise ValidationError("Both debit and credit amount should not be greater than zero")
            if detail['debit'] < 0 or detail['credit'] < 0:
                raise ValidationError("Either debit or credit amount should not be less than zero")
            try:
                account_instance = detail['account']
                
                detail.pop('account')
            except Ledger.DoesNotExist:
                raise ValidationError(f"Ledger with {detail['account']} not found")
           
            voucher_detail = VoucherDetail.objects.create(
                voucher_main=voucher_main,
                voucher_no=validated_data['voucher_no'],
                voucher_type=validated_data['voucher_type'],
                
                account=account_instance,
                **detail
            )
            
            # Reference Bills creation logic
            if detail.get('ref_bill_no',False):
                ReferenceBills.objects.create(
                    ldgr=account_instance,
                    voucher=voucher_main,
                    amount=detail['debit'] if detail['debit'] else detail['credit'],
                    vendor_bill_no="",
                    ref_bill=voucher_detail,
                    ref_bill_txt=detail['ref_bill_no']
                )
            elif voucher_main.vendor_bill:
                ReferenceBills.objects.create(
                    ldgr=account_instance,
                    voucher=voucher_main,
                    amount=detail['debit'] if detail['debit'] else detail['credit'],
                    vendor_bill_no=detail['ref_bill_no'],
                    ref_bill=None,
                    ref_bill_txt=""
                )

            # Update due amount if PMNT voucher type
            if (validated_data['voucher_type'].strip().upper() == "PMNT" and detail.get('ref_bill_no',False) and detail.get('ref_bill_no',False) != ''):
                purchase_voucher = PurchaseVoucher.objects.select_for_update().get(bill_no=detail['ref_bill_no'])
                purchase_voucher.due_amt -= Decimal(str(detail['debit'] or detail['credit'] or 0))
                purchase_voucher.save()

            if (validated_data['voucher_type'].strip().upper() == "RCPT" and detail.get('ref_bill_no',False) and detail.get('ref_bill_no',False) != ''):
                sale_voucher = SalesVou.objects.select_for_update().get(billno=detail['ref_bill_no'])
                sale_voucher.due_amt -= Decimal(str(detail['debit'] or detail['credit'] or 0))
                sale_voucher.save()


        return voucher_main
    
    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('transactions', [])
            old_details = instance.transactions.all()

            voucher_type = validated_data.get('voucher_type', instance.voucher_type).strip().upper()

            for old_detail in old_details:
                ref_bill_no = old_detail.ref_bill_no
                amt = old_detail.debit or old_detail.credit or Decimal(0)
                if voucher_type == "PMNT" and ref_bill_no:
                    try:
                        purchase_voucher = PurchaseVoucher.objects.select_for_update().get(bill_no=ref_bill_no)
                        purchase_voucher.due_amt += amt
                        purchase_voucher.save()
                    except PurchaseVoucher.DoesNotExist:
                        pass
                elif voucher_type == "RCPT" and ref_bill_no:
                    try:
                        sale_voucher = SalesVou.objects.select_for_update().get(billno=ref_bill_no)
                        sale_voucher.due_amt += amt
                        sale_voucher.save()
                    except SalesVou.DoesNotExist:
                        pass
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            vou_det = VoucherDetailSerializer(detail_data,many=True).data
            create_or_update_nested(VoucherDetailSerializer, instance, 'transactions',  'voucher_main',vou_det)
            for detail in vou_det:
                ref_bill_no = detail.get('ref_bill_no')
                amt = Decimal(detail.get('debit') or detail.get('credit') or 0)
                if voucher_type == "PMNT" and ref_bill_no:
                    try:
                        purchase_voucher = PurchaseVoucher.objects.select_for_update().get(bill_no=ref_bill_no)
                        purchase_voucher.due_amt -= amt
                        purchase_voucher.save()
                    except PurchaseVoucher.DoesNotExist:
                        pass
                elif voucher_type == "RCPT" and ref_bill_no:
                    try:
                        sale_voucher = SalesVou.objects.select_for_update().get(billno=ref_bill_no)
                        sale_voucher.due_amt -= amt
                        sale_voucher.save()
                    except SalesVou.DoesNotExist:
                        pass
            return instance



class AccountSerializer(serializers.ModelSerializer):
    parent_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Account
        fields = ['id', 'name', 'code', 'parent', 'parent_name', 'can_be_deleted']

    def get_parent_name(self, obj):
        if obj.parent:
            return f"{obj.parent.code} — {obj.parent.name}"
        return None

    def save_with_parent_account(self, parent_id):
        with transaction.atomic():
            try:
                parent_account = Account.objects.get(id=parent_id)
                self.save(parent=parent_account)
            except Account.DoesNotExist:
                raise ValidationError("Parent account matching id not found")
        
class LedgerOpenBalanceSerializer(serializers.ModelSerializer):
    ledger_name = serializers.CharField(source='ldgr.ac_name', read_only=True)

    class Meta:
        model = LedgerOpenBalance
        fields = ['id', 'ldgr', 'ledger_name', 'debit', 'credit', 'acc_year']
        read_only_fields = []


class VoucherAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoucherAttachment
        fields = ['id', 'voucher', 'file', 'original_name', 'uploaded_at']
        read_only_fields = ['original_name', 'uploaded_at']

    def validate(self, data):
        voucher = data.get('voucher') or self.instance and self.instance.voucher
        if voucher and voucher.attachments.count() >= 3:
            raise ValidationError("Maximum 3 attachments allowed per voucher.")
        return data

    def create(self, validated_data):
        file = validated_data['file']
        validated_data['original_name'] = file.name
        return super().create(validated_data)


class PurchaseVoucherSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseVoucher
        fields = "__all__"
