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

from rest_framework.exceptions import ValidationError as _LedgerConfigError
def _raise_missing_ledger(label):
    raise _LedgerConfigError(
        {'ledger_config': f"Required ledger '{label}' is not configured on master. Please configure it in Company/GSTIN/Retail master before saving vouchers."}
    )



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


class LedgerLightSerializer(serializers.ModelSerializer):
    """Lightweight ledger serializer for dropdowns and initial-data endpoints.
    Returns only the fields needed for select options — no nested roles or masking."""
    ac_group_name = serializers.CharField(source='ac_group.name', read_only=True, default=None)
    primary_role = serializers.SerializerMethodField()

    class Meta:
        model = Ledger
        fields = ['id', 'ac_name', 'ac_group', 'ac_group_name', 'primary_role', 'state', 'ship_state']

    def get_primary_role(self, obj):
        # Uses prefetched roles if available
        roles = obj.roles.all()
        for r in roles:
            if r.is_primary:
                return r.role
        return roles[0].role if roles else None


class LedgerSerializer(serializers.ModelSerializer):
    roles = _LedgerRoleSerializer(many=True, read_only=True)
    primary_role = serializers.SerializerMethodField()
    ac_group_name = serializers.CharField(source='ac_group.name', read_only=True, allow_null=True)
    ac_group_code = serializers.CharField(source='ac_group.code', read_only=True, allow_null=True)
    parent_group_name = serializers.CharField(source='ac_group.parent.name', read_only=True, allow_null=True, default=None)

    class Meta:
        model = Ledger
        fields = "__all__"
        # Every ledger must belong to an account group. The model field still
        # allows NULL to avoid breaking historical rows, but all writes go
        # through this serializer so we enforce it at the API boundary.
        extra_kwargs = {
            'ac_group': {'required': True, 'allow_null': False},
        }

    def get_primary_role(self, obj):
        # Iterate obj.roles.all() to reuse the prefetch_related('roles') cache
        # set by the viewset. Using .filter() here would bypass the cache and
        # issue one extra query per ledger row in list endpoints.
        roles = list(obj.roles.all())
        for r in roles:
            if r.is_primary:
                return r.role
        return roles[0].role if roles else None

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get('request')
        if request:
            from userauth.utils import can_user_view_customer_data
            if not can_user_view_customer_data(request.user):
                from contacts.masking import mask_ledger_representation
                ret = mask_ledger_representation(ret, instance)
        return ret

class SaleVoucherLedgerSerializer(serializers.ModelSerializer):
    """Minimal ledger serializer for sale/return voucher forms.
    Uses Python-side iteration over prefetched roles to avoid N+1 queries."""
    primary_role = serializers.SerializerMethodField()

    class Meta:
        model = Ledger
        fields = ['id', 'ac_name', 'ac_group', 'primary_role', 'mobile1', 'phone1']

    def get_primary_role(self, obj):
        # obj.roles.all() hits the prefetch cache — no extra query per ledger
        roles = list(obj.roles.all())
        primary = next((r for r in roles if r.is_primary), None)
        if primary:
            return primary.role
        return roles[0].role if roles else None

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get('request')
        if request:
            from userauth.utils import can_user_view_customer_data
            if not can_user_view_customer_data(request.user):
                from contacts.masking import is_customer_ledger, MASK_VALUE
                if is_customer_ledger(instance):
                    ret['ac_name'] = MASK_VALUE
        return ret


class VoucherDetailSerializer(serializers.ModelSerializer):
    account = serializers.SlugRelatedField(queryset=Ledger.objects.all(),slug_field="ac_name")
    credit = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    debit = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    class Meta:
        model = VoucherDetail
        fields=[
        "voucher_no",
        "ref_bill_no",
        "ref_sales_vou",
        "ref_purchase_vou",
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
            _gold_conv_ldgr = _co.gold_conversion_ldgr.ac_name if _co and _co.gold_conversion_ldgr else _raise_missing_ledger("Gold Conversion")
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
    narration = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    voucher_type = serializers.CharField(max_length=10)
    retail = serializers.PrimaryKeyRelatedField(queryset=RetailMaster.objects.all(), required=False)
    status = serializers.CharField(max_length=200,required=False)
    vendor_bill = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    # customer_order: accepted as a plain integer ID on input and resolved in
    # create(). Using PrimaryKeyRelatedField here would force a module-load-time
    # import of sales.CustomerOrder, which pulls in sales.serializers, which
    # already imports from accounting.serializers → circular import.
    customer_order = serializers.IntegerField(
        required=False, allow_null=True,
        help_text="For RCPT vouchers: link this receipt to an advance on a Customer Order (PK)"
    )
    voucher_details = VoucherDetailSerializer(many=True,source='transactions')
    """
    {
      date:
    }
    """
    
    @transaction.atomic
    def create(self, validated_data):
        voucher_details = validated_data.pop('transactions')

        # ── Resolve customer_order ID → instance (lazy import breaks cycle) ──
        co_id = validated_data.pop('customer_order', None)
        vtype_upper = validated_data.get('voucher_type', '').strip().upper()
        if co_id:
            if vtype_upper not in ('RCPT', 'RCPT-SALE'):
                raise ValidationError(
                    "customer_order can only be linked to a RCPT/RCPT-SALE voucher."
                )
            from sales.models import CustomerOrder
            try:
                validated_data['customer_order'] = CustomerOrder.objects.get(pk=co_id)
            except CustomerOrder.DoesNotExist:
                raise ValidationError(f"CustomerOrder id={co_id} not found.")

        # ── Fiscal year boundary check ──────────────────────────────────────
        retail_obj = validated_data.get('retail')
        if retail_obj:
            fy = getattr(retail_obj, 'active_fy', None)
            voucher_date = validated_data.get('date')
            if fy and voucher_date:
                if voucher_date < fy.fy_start or voucher_date > fy.fy_end:
                    raise ValidationError(
                        f"Voucher date {voucher_date} falls outside the active fiscal year "
                        f"({fy.fy_start} to {fy.fy_end}). Please select the correct fiscal year."
                    )
                if fy.is_hard_closed:
                    raise ValidationError(
                        f"Fiscal year {fy.fy_code} is hard-closed. No entries can be posted. "
                        f"Contact your administrator to reopen the fiscal year."
                    )

        # ── Section 269ST cash receipt limit check (standalone RCPT only) ────
        retail_obj = validated_data.get('retail')
        if (
            validated_data.get('voucher_type', '').strip().upper() == 'RCPT'
            and retail_obj
            and retail_obj.cash_ldgr
        ):
            from accounting.utils import get_customer_cash_received, get_company_cash_limits
            limit, _ = get_company_cash_limits(retail_obj)
            if limit is not None:   # None means enforcement is disabled by company setting
                cash_ldgr = retail_obj.cash_ldgr
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
            from accounting.utils import get_vendor_cash_paid_on_date, get_company_cash_limits
            _, limit_pm = get_company_cash_limits(retail_obj)
            if limit_pm is not None:   # None means enforcement is disabled by company setting
                cash_ldgr_pm = retail_obj.cash_ldgr
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

        # ── Cash/Bank side restriction for Receipt and Payment vouchers ───────
        # Receipt : cash/bank must only be DEBITED  (money coming in)
        # Payment : cash/bank must only be CREDITED (money going out)
        if vtype_upper in ('RCPT', 'PMNT'):
            for d in voucher_details:
                acct = d.get('account')
                if acct is None:
                    continue
                is_cash_bank = _has_role(acct, 'CA') or _has_role(acct, 'BA')
                if not is_cash_bank:
                    continue
                if vtype_upper == 'RCPT' and Decimal(str(d.get('credit', 0) or 0)) > 0:
                    raise ValidationError(
                        f"'{acct.ac_name}' is a Cash/Bank account and cannot be credited "
                        f"in a Receipt voucher. Cash/Bank accounts are always debited on receipt."
                    )
                if vtype_upper == 'PMNT' and Decimal(str(d.get('debit', 0) or 0)) > 0:
                    raise ValidationError(
                        f"'{acct.ac_name}' is a Cash/Bank account and cannot be debited "
                        f"in a Payment voucher. Cash/Bank accounts are always credited on payment."
                    )
        # ─────────────────────────────────────────────────────────────────────

        # ── Double-entry validation (must happen BEFORE creating the voucher) ──
        debit_total = Decimal('0')
        credit_total = Decimal('0')
        for d in voucher_details:
            debit_total += Decimal(str(d.get('debit') or 0))
            credit_total += Decimal(str(d.get('credit') or 0))

        if debit_total.quantize(Decimal('0.01')) != credit_total.quantize(Decimal('0.01')):
            raise ValidationError(
                f"Total debit and credit amounts must be equal. "
                f"Debit: {debit_total}, Credit: {credit_total}."
            )

        # Document-linked voucher types (purchase, sale, returns) carry the
        # source document's billno (e.g. "PV/V/R001/26-27/00002") which is
        # already unique and freshly generated by its own sequence. Reusing it
        # keeps the accounting voucher number identical to the document the
        # user sees in the form — no duplicate numbering schemes.
        _DOC_LINKED_TYPES = {
            global_vars.VoucherType.purc_sc,
            global_vars.VoucherType.sale,
            global_vars.VoucherType.purc_ret,
            global_vars.VoucherType.sale_ret,
        }

        if vtype_upper not in _DOC_LINKED_TYPES:
            # Pure accounting vouchers (JRNL/PMNT/CONTRA/RCPT/RCPT-SALE) — the
            # client sends a peeked value (peek_next_bill_number) which is
            # read-only and never increments the BillNumberSequence, so we
            # always regenerate to avoid UNIQUE constraint failures.
            #
            # Must use the canonical VoucherType prefix (e.g. "CNTR" not
            # "CONTRA") so the sequence key matches peek_next_bill_number.
            _VTYPE_TO_SEQ_PREFIX = {
                'JRNL':      global_vars.VoucherType.journal,
                'PMNT':      global_vars.VoucherType.pmnt,
                'CONTRA':    global_vars.VoucherType.cntr,
                'RCPT':      global_vars.VoucherType.rcpt,
                'RCPT-SALE': global_vars.VoucherType.rcpt_sale,
            }
            seq_prefix = _VTYPE_TO_SEQ_PREFIX.get(vtype_upper, vtype_upper)
            fy = getattr(retail_obj, 'active_fy', None) if retail_obj else None
            validated_data['voucher_no'] = generate_voucher_no(
                type=seq_prefix, retail=retail_obj, fiscal_year=fy
            )
            # Also persist the fiscal_year FK so bootstrap queries can find
            # these vouchers by FY in future sequence resyncs.
            if fy and 'fiscal_year' not in validated_data:
                validated_data['fiscal_year'] = fy

        voucher_main = VoucherMain.objects.create(
            **validated_data,
            amount=debit_total,
        )

        # ── Bill-wise allocation sanity: per-ledger, the sum of all ref_bill_no
        # line amounts must not exceed the party-leg amount on that ledger in
        # this voucher. (It's allowed to be less — that's an "on account"
        # balance for the remainder.) This catches fat-finger errors where the
        # user allocates ₹10,000 across bills while only receiving ₹8,000.
        if vtype_upper in ('PMNT', 'RCPT'):
            per_ledger_party = {}     # ledger_id → total party-leg amount in this voucher
            per_ledger_alloc = {}     # ledger_id → total allocated to specific bills
            for d in voucher_details:
                acct = d.get('account')
                if acct is None:
                    continue
                if _has_role(acct, 'CA') or _has_role(acct, 'BA'):
                    continue  # cash/bank legs are not party legs
                amt = Decimal(str(d.get('debit') or d.get('credit') or 0))
                per_ledger_party[acct.id] = per_ledger_party.get(acct.id, Decimal('0')) + amt
                if d.get('ref_bill_no'):
                    per_ledger_alloc[acct.id] = per_ledger_alloc.get(acct.id, Decimal('0')) + amt
            for ldgr_id, allocated in per_ledger_alloc.items():
                party_amt = per_ledger_party.get(ldgr_id, Decimal('0'))
                if allocated > party_amt + Decimal('0.01'):
                    raise ValidationError(
                        f"Bill allocation (₹{allocated}) exceeds the amount posted to "
                        f"this ledger (₹{party_amt}) in this voucher."
                    )

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
           
            # Auto-populate ref_sales_vou / ref_purchase_vou from ref_bill_no text
            # (backfill strongly-typed FK for new rows so reports don't need text matching)
            if detail.get('ref_bill_no') and not detail.get('ref_sales_vou') and not detail.get('ref_purchase_vou'):
                if vtype_upper in ('RCPT', 'RCPT-SALE'):
                    sv = SalesVou.objects.filter(billno=detail['ref_bill_no']).first()
                    if sv:
                        detail['ref_sales_vou'] = sv
                elif vtype_upper == 'PMNT':
                    pv = PurchaseVoucher.objects.filter(billno=detail['ref_bill_no']).first()
                    if pv:
                        detail['ref_purchase_vou'] = pv

            voucher_detail = VoucherDetail.objects.create(
                voucher_main=voucher_main,
                voucher_no=validated_data['voucher_no'],
                voucher_type=validated_data['voucher_type'],

                account=account_instance,
                **detail
            )

            # Reference Bills creation logic
            if detail.get('ref_bill_no'):
                ReferenceBills.objects.create(
                    ldgr=account_instance,
                    voucher=voucher_main,
                    amount=detail['debit'] if detail['debit'] else detail['credit'],
                    vendor_bill_no="",
                    ref_bill=voucher_detail,
                    ref_bill_txt=detail['ref_bill_no']
                )
            elif voucher_main.vendor_bill:
                # Link voucher detail to vendor's bill number (no ref_bill_no on the detail line)
                ReferenceBills.objects.create(
                    ldgr=account_instance,
                    voucher=voucher_main,
                    amount=detail['debit'] if detail['debit'] else detail['credit'],
                    vendor_bill_no=voucher_main.vendor_bill,
                    ref_bill=None,
                    ref_bill_txt=""
                )

            # Update due amount if PMNT voucher type
            if vtype_upper == "PMNT" and detail.get('ref_bill_no'):
                purchase_voucher = PurchaseVoucher.objects.select_for_update().filter(
                    billno=detail['ref_bill_no']
                ).first()
                if purchase_voucher:
                    # Ledger must match — can't pay Vendor A's bill from Vendor B's ledger
                    if purchase_voucher.ldgr_id != account_instance.id:
                        raise ValidationError(
                            f"Ledger mismatch: purchase {purchase_voucher.billno} belongs to "
                            f"'{purchase_voucher.ldgr.ac_name}', but this line is posted to "
                            f"'{account_instance.ac_name}'."
                        )
                    amt = Decimal(str(detail['debit'] or detail['credit'] or 0))
                    if amt > purchase_voucher.due_amt:
                        raise ValidationError(
                            f"Overpayment on purchase {purchase_voucher.billno}: "
                            f"outstanding ₹{purchase_voucher.due_amt}, attempted ₹{amt}."
                        )
                    purchase_voucher.due_amt -= amt
                    purchase_voucher.save()
                else:
                    # Allow JRNL voucher numbers as ref — outstanding tracked dynamically
                    is_jrnl = VoucherMain.objects.filter(
                        voucher_no=detail['ref_bill_no'], voucher_type='JRNL'
                    ).exists()
                    if not is_jrnl:
                        raise ValidationError(
                            f"Purchase voucher '{detail['ref_bill_no']}' not found — cannot allocate payment."
                        )

            if vtype_upper == "RCPT" and detail.get('ref_bill_no'):
                try:
                    sale_voucher = SalesVou.objects.select_for_update().get(billno=detail['ref_bill_no'])
                except SalesVou.DoesNotExist:
                    raise ValidationError(
                        f"Sales voucher '{detail['ref_bill_no']}' not found — cannot allocate receipt."
                    )
                if sale_voucher.ldgr_id != account_instance.id:
                    raise ValidationError(
                        f"Ledger mismatch: sale {sale_voucher.billno} belongs to "
                        f"'{sale_voucher.ldgr.ac_name}', but this line is posted to "
                        f"'{account_instance.ac_name}'."
                    )
                amt = Decimal(str(detail['debit'] or detail['credit'] or 0))
                if amt > sale_voucher.due_amt:
                    raise ValidationError(
                        f"Over-receipt on sale {sale_voucher.billno}: "
                        f"outstanding ₹{sale_voucher.due_amt}, attempted ₹{amt}."
                    )
                sale_voucher.due_amt -= amt
                sale_voucher.save()

            # ── JRNL vouchers can adjust invoice due_amt (credit notes,
            # post-billing discounts, bad-debt write-offs). The direction is
            # driven by which side (Dr/Cr) the party ledger is posted on,
            # matching the PMNT/RCPT semantics:
            #   - JRNL + ref_bill_no matching a SalesVou  + CREDIT on party
            #     ledger  ⇒ write down customer receivable (like an RCPT)
            #   - JRNL + ref_bill_no matching a Purchase  + DEBIT on party
            #     ledger  ⇒ write down vendor payable (like a PMNT)
            # If both match, prefer the one whose ledger matches account_instance.
            if vtype_upper in ("JRNL", "CN", "DN") and detail.get('ref_bill_no'):
                d_amt = Decimal(str(detail.get('debit') or 0))
                c_amt = Decimal(str(detail.get('credit') or 0))
                sv = SalesVou.objects.select_for_update().filter(
                    billno=detail['ref_bill_no'], ldgr_id=account_instance.id
                ).first()
                pv = PurchaseVoucher.objects.select_for_update().filter(
                    billno=detail['ref_bill_no'], ldgr_id=account_instance.id
                ).first()
                if sv and c_amt > 0:
                    if c_amt > sv.due_amt:
                        raise ValidationError(
                            f"JRNL adjustment ₹{c_amt} exceeds outstanding ₹{sv.due_amt} "
                            f"on sale {sv.billno}."
                        )
                    sv.due_amt -= c_amt
                    sv.save(update_fields=['due_amt'])
                elif pv and d_amt > 0:
                    if d_amt > pv.due_amt:
                        raise ValidationError(
                            f"JRNL adjustment ₹{d_amt} exceeds outstanding ₹{pv.due_amt} "
                            f"on purchase {pv.billno}."
                        )
                    pv.due_amt -= d_amt
                    pv.save(update_fields=['due_amt'])
                elif not sv and not pv:
                    raise ValidationError(
                        f"JRNL ref_bill_no '{detail['ref_bill_no']}' does not match any "
                        f"sale or purchase voucher for ledger '{account_instance.ac_name}'."
                    )


        return voucher_main
    
    def update(self, instance, validated_data):
        with transaction.atomic():
            detail_data = validated_data.pop('transactions', [])
            old_details = instance.transactions.all()

            voucher_type = validated_data.get('voucher_type', instance.voucher_type).strip().upper()

            # ── Cash/Bank side restriction (same rule as create) ──────────────
            if voucher_type in ('RCPT', 'PMNT'):
                for d in detail_data:
                    acct = d.get('account')
                    if acct is None:
                        continue
                    is_cash_bank = _has_role(acct, 'CA') or _has_role(acct, 'BA')
                    if not is_cash_bank:
                        continue
                    if voucher_type == 'RCPT' and Decimal(str(d.get('credit', 0) or 0)) > 0:
                        raise ValidationError(
                            f"'{acct.ac_name}' is a Cash/Bank account and cannot be credited "
                            f"in a Receipt voucher."
                        )
                    if voucher_type == 'PMNT' and Decimal(str(d.get('debit', 0) or 0)) > 0:
                        raise ValidationError(
                            f"'{acct.ac_name}' is a Cash/Bank account and cannot be debited "
                            f"in a Payment voucher."
                        )
            # ─────────────────────────────────────────────────────────────────

            for old_detail in old_details:
                ref_bill_no = old_detail.ref_bill_no
                amt = old_detail.debit or old_detail.credit or Decimal(0)
                if voucher_type == "PMNT" and ref_bill_no:
                    pv_rev = PurchaseVoucher.objects.select_for_update().filter(billno=ref_bill_no).first()
                    if pv_rev:
                        pv_rev.due_amt += amt
                        pv_rev.save()
                    elif not VoucherMain.objects.filter(voucher_no=ref_bill_no, voucher_type='JRNL').exists():
                        raise ValidationError(
                            f"Cannot reverse original allocation: purchase voucher '{ref_bill_no}' no longer exists."
                        )
                    # JRNL-based payments: no due_amt to reverse — outstanding computed dynamically
                elif voucher_type == "RCPT" and ref_bill_no:
                    try:
                        sale_voucher = SalesVou.objects.select_for_update().get(billno=ref_bill_no)
                        sale_voucher.due_amt += amt
                        sale_voucher.save()
                    except SalesVou.DoesNotExist:
                        raise ValidationError(
                            f"Cannot reverse original allocation: sales voucher '{ref_bill_no}' no longer exists."
                        )
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            vou_det = VoucherDetailSerializer(detail_data,many=True).data
            create_or_update_nested(VoucherDetailSerializer, instance, 'transactions',  'voucher_main',vou_det)
            for detail in vou_det:
                ref_bill_no = detail.get('ref_bill_no')
                amt = Decimal(detail.get('debit') or detail.get('credit') or 0)
                if voucher_type == "PMNT" and ref_bill_no:
                    pv_new = PurchaseVoucher.objects.select_for_update().filter(billno=ref_bill_no).first()
                    if pv_new:
                        if amt > pv_new.due_amt:
                            raise ValidationError(
                                f"Overpayment on purchase {pv_new.billno}: "
                                f"outstanding ₹{pv_new.due_amt}, attempted ₹{amt}."
                            )
                        pv_new.due_amt -= amt
                        pv_new.save()
                    elif not VoucherMain.objects.filter(voucher_no=ref_bill_no, voucher_type='JRNL').exists():
                        raise ValidationError(
                            f"Purchase voucher '{ref_bill_no}' not found — cannot allocate payment."
                        )
                    # JRNL-based payments: outstanding tracked dynamically — no due_amt update
                elif voucher_type == "RCPT" and ref_bill_no:
                    try:
                        sale_voucher = SalesVou.objects.select_for_update().get(billno=ref_bill_no)
                    except SalesVou.DoesNotExist:
                        raise ValidationError(
                            f"Sales voucher '{ref_bill_no}' not found — cannot allocate receipt."
                        )
                    if amt > sale_voucher.due_amt:
                        raise ValidationError(
                            f"Over-receipt on sale {sale_voucher.billno}: "
                            f"outstanding ₹{sale_voucher.due_amt}, attempted ₹{amt}."
                        )
                    sale_voucher.due_amt -= amt
                    sale_voucher.save()
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


class CreditDebitNoteSerializer(serializers.ModelSerializer):
    ldgr_name = serializers.CharField(source='ldgr.ac_name', read_only=True)
    adjustment_ldgr_name = serializers.CharField(source='adjustment_ldgr.ac_name', read_only=True)
    ref_bill_no = serializers.SerializerMethodField(read_only=True)

    class Meta:
        from .models import CreditDebitNote
        model = CreditDebitNote
        fields = [
            'id', 'note_type', 'note_no', 'date',
            'ldgr', 'ldgr_name',
            'adjustment_ldgr', 'adjustment_ldgr_name',
            'ref_sales_vou', 'ref_purchase_vou',
            'ref_sale_return', 'ref_purchase_return',
            'ref_bill_no',
            'reason', 'amount', 'taxable_value',
            'cgst_per', 'cgst_amt', 'sgst_per', 'sgst_amt',
            'igst_per', 'igst_amt',
            'ac_voucher', 'retail', 'fiscal_year', 'gstin_ref', 'branch_ref',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'note_no', 'ac_voucher', 'created_at', 'updated_at']

    def get_ref_bill_no(self, obj):
        if obj.ref_sales_vou_id:
            return obj.ref_sales_vou.billno
        if obj.ref_purchase_vou_id:
            return obj.ref_purchase_vou.billno
        return None

    @transaction.atomic
    def create(self, validated_data):
        from .models import CreditDebitNote
        from accounting.utils import generate_voucher_no, get_next_bill_number
        from mastersconfig.models import GSTINMaster

        note_type = validated_data['note_type']
        ldgr = validated_data['ldgr']
        adjustment_ldgr = validated_data['adjustment_ldgr']
        retail = validated_data['retail']
        gstin_ref = validated_data.get('gstin_ref')

        # Generate note_no in standard ERP format: CN/R001/26-27/00001
        validated_data['note_no'] = get_next_bill_number(retail, note_type)

        taxable = validated_data['taxable_value']
        cgst_amt = validated_data.get('cgst_amt', Decimal('0'))
        sgst_amt = validated_data.get('sgst_amt', Decimal('0'))
        igst_amt = validated_data.get('igst_amt', Decimal('0'))
        total = taxable + cgst_amt + sgst_amt + igst_amt
        validated_data['amount'] = total

        # Resolve GST ledgers from GSTINMaster
        gstin = gstin_ref or (GSTINMaster.objects.filter(retail=retail).first() if retail else None)

        # Validate GST ledgers exist when GST amounts are specified
        if cgst_amt > 0:
            if not gstin:
                raise ValidationError("CGST amount specified but no GSTIN is configured for this retail.")
            if note_type == 'CN' and not gstin.output_cgst:
                raise ValidationError("CGST amount specified but Output CGST ledger is not configured on GSTIN master.")
            if note_type == 'DN' and not gstin.input_cgst:
                raise ValidationError("CGST amount specified but Input CGST ledger is not configured on GSTIN master.")
        if sgst_amt > 0:
            if not gstin:
                raise ValidationError("SGST amount specified but no GSTIN is configured for this retail.")
            if note_type == 'CN' and not gstin.output_sgst:
                raise ValidationError("SGST amount specified but Output SGST ledger is not configured on GSTIN master.")
            if note_type == 'DN' and not gstin.input_sgst:
                raise ValidationError("SGST amount specified but Input SGST ledger is not configured on GSTIN master.")
        if igst_amt > 0:
            if not gstin:
                raise ValidationError("IGST amount specified but no GSTIN is configured for this retail.")
            if note_type == 'CN' and not gstin.output_igst:
                raise ValidationError("IGST amount specified but Output IGST ledger is not configured on GSTIN master.")
            if note_type == 'DN' and not gstin.input_igst:
                raise ValidationError("IGST amount specified but Input IGST ledger is not configured on GSTIN master.")

        # Build voucher detail lines
        voucher_details = []
        ref_bill_no = None
        if validated_data.get('ref_sales_vou'):
            ref_bill_no = validated_data['ref_sales_vou'].billno
        elif validated_data.get('ref_purchase_vou'):
            ref_bill_no = validated_data['ref_purchase_vou'].billno

        if note_type == 'CN':
            # Credit Note: Dr adjustment + Dr taxes, Cr customer
            voucher_details.append({
                'account': adjustment_ldgr.ac_name,
                'debit': float(taxable),
                'credit': 0,
            })
            if cgst_amt > 0 and gstin and gstin.output_cgst:
                voucher_details.append({
                    'account': gstin.output_cgst.ac_name,
                    'debit': float(cgst_amt),
                    'credit': 0,
                })
            if sgst_amt > 0 and gstin and gstin.output_sgst:
                voucher_details.append({
                    'account': gstin.output_sgst.ac_name,
                    'debit': float(sgst_amt),
                    'credit': 0,
                })
            if igst_amt > 0 and gstin and gstin.output_igst:
                voucher_details.append({
                    'account': gstin.output_igst.ac_name,
                    'debit': float(igst_amt),
                    'credit': 0,
                })
            # Party leg (credit reduces receivable)
            voucher_details.append({
                'account': ldgr.ac_name,
                'debit': 0,
                'credit': float(total),
                'ref_bill_no': ref_bill_no or '',
            })
        else:
            # Debit Note: Dr vendor (reduces payable), Cr adjustment + Cr taxes
            voucher_details.append({
                'account': ldgr.ac_name,
                'debit': float(total),
                'credit': 0,
                'ref_bill_no': ref_bill_no or '',
            })
            voucher_details.append({
                'account': adjustment_ldgr.ac_name,
                'debit': 0,
                'credit': float(taxable),
            })
            if cgst_amt > 0 and gstin and gstin.input_cgst:
                voucher_details.append({
                    'account': gstin.input_cgst.ac_name,
                    'debit': 0,
                    'credit': float(cgst_amt),
                })
            if sgst_amt > 0 and gstin and gstin.input_sgst:
                voucher_details.append({
                    'account': gstin.input_sgst.ac_name,
                    'debit': 0,
                    'credit': float(sgst_amt),
                })
            if igst_amt > 0 and gstin and gstin.input_igst:
                voucher_details.append({
                    'account': gstin.input_igst.ac_name,
                    'debit': 0,
                    'credit': float(igst_amt),
                })

        # Create the accounting voucher via JournalEntrySerializer
        vou_type = global_vars.VoucherType.credit_note if note_type == 'CN' else global_vars.VoucherType.debit_note
        journal_data = {
            'date': str(validated_data['date']),
            'voucher_no': generate_voucher_no(type=vou_type, retail=retail),
            'narration': f"{'Credit Note' if note_type == 'CN' else 'Debit Note'}: {validated_data.get('reason', '')}",
            'voucher_type': vou_type,
            'retail': retail.pk,
            'voucher_details': voucher_details,
        }
        request = self.context.get('request')
        je_serializer = JournalEntrySerializer(data=journal_data, context={'request': request})
        je_serializer.is_valid(raise_exception=True)
        voucher_main = je_serializer.save()

        # Create the CreditDebitNote record
        validated_data['ac_voucher'] = voucher_main
        request = self.context.get('request')
        _retail = validated_data.get('retail') or getattr(request, 'retail', None)
        if _retail:
            validated_data.setdefault('fiscal_year', getattr(_retail, 'active_fy', None))
        note = CreditDebitNote.objects.create(**validated_data)
        return note


# ---------------------------------------------------------------------------
# Fixed Assets serializers
# ---------------------------------------------------------------------------

from .models import (  # noqa: E402 — appended block; same module
    FixedAsset, FixedAssetSettings, IT_BLOCK_RATES,
)


class FixedAssetSerializer(serializers.ModelSerializer):
    current_wdv          = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_fully_depreciated = serializers.BooleanField(read_only=True)
    it_block_rate        = serializers.SerializerMethodField()
    asset_ledger_name    = serializers.CharField(source='asset_ledger.ac_name', read_only=True, default='')
    method_display       = serializers.CharField(source='get_depreciation_method_display', read_only=True)

    class Meta:
        model  = FixedAsset
        fields = '__all__'
        read_only_fields = (
            'retail', 'asset_ledger',
            'accumulated_depreciation', 'created_at',
            # Depreciation ledgers are set globally in Fixed Asset Settings — no
            # per-asset overrides allowed through the API.
            'accum_depreciation_ledger', 'depreciation_expense_ledger',
        )

    def get_it_block_rate(self, obj):
        if obj.it_block_category and obj.it_block_category in IT_BLOCK_RATES:
            return str(IT_BLOCK_RATES[obj.it_block_category][1])
        return None


class FixedAssetSettingsSerializer(serializers.ModelSerializer):
    expense_ldgr_name = serializers.CharField(
        source='default_depreciation_expense_ldgr.ac_name', read_only=True, default=''
    )
    accum_ldgr_name = serializers.CharField(
        source='default_accum_depreciation_ldgr.ac_name', read_only=True, default=''
    )

    class Meta:
        model  = FixedAssetSettings
        fields = '__all__'
