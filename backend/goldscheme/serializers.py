from decimal import Decimal
from rest_framework import serializers
from .models import SchemeMaster, SchemeBenefitTier, SchemeEnrollment, SchemePayment, SchemeNominee


# ── Benefit Tier ──────────────────────────────────────────────────────────────

class SchemeBenefitTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeBenefitTier
        fields = ['id', 'product_type', 'min_months', 'max_months',
                  'lc_discount_pct', 'value_discount_pct']


class SchemeNomineeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeNominee
        fields = ['id', 'name', 'mobile', 'address', 'relationship']
        extra_kwargs = {
            'address': {'required': False, 'allow_blank': True},
        }


# ── Scheme Master ─────────────────────────────────────────────────────────────

class SchemeMasterListSerializer(serializers.ModelSerializer):
    benefit_tiers = SchemeBenefitTierSerializer(many=True, read_only=True)
    active_enrollments = serializers.SerializerMethodField()
    purity_name = serializers.CharField(source='accumulation_purity.purity', read_only=True, default=None)

    class Meta:
        model = SchemeMaster
        fields = [
            'id', 'name', 'scheme_code', 'scheme_type', 'gold_price_mode',
            'tenure_months', 'min_amount', 'max_amount',
            'accumulation_purity', 'purity_name',
            'has_diamond_benefit', 'is_active',
            'description', 'terms_conditions',
            'benefit_tiers', 'active_enrollments',
            'created_at',
        ]

    def get_active_enrollments(self, obj):
        # Use annotated value from queryset if available (avoids N+1)
        if hasattr(obj, '_active_enrollment_count'):
            return obj._active_enrollment_count
        return obj.enrollments.filter(status__in=('ACTIVE', 'MATURED')).count()


class SchemeMasterWriteSerializer(serializers.ModelSerializer):
    benefit_tiers = SchemeBenefitTierSerializer(many=True, required=False)

    class Meta:
        model = SchemeMaster
        fields = [
            'id', 'name', 'scheme_code', 'scheme_type', 'gold_price_mode',
            'tenure_months', 'min_amount', 'max_amount',
            'accumulation_purity', 'has_diamond_benefit',
            'is_active', 'description', 'terms_conditions',
            'benefit_tiers',
        ]

    def create(self, validated_data):
        tiers_data = validated_data.pop('benefit_tiers', [])
        scheme = SchemeMaster.objects.create(**validated_data)
        for tier in tiers_data:
            SchemeBenefitTier.objects.create(scheme=scheme, **tier)
        return scheme

    def update(self, instance, validated_data):
        tiers_data = validated_data.pop('benefit_tiers', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tiers_data is not None:
            instance.benefit_tiers.all().delete()
            for tier in tiers_data:
                SchemeBenefitTier.objects.create(scheme=instance, **tier)

        return instance


# ── Enrollment ────────────────────────────────────────────────────────────────

class SchemeEnrollmentListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.ac_name', read_only=True)
    scheme_name = serializers.CharField(source='scheme.name', read_only=True)
    scheme_code = serializers.CharField(source='scheme.scheme_code', read_only=True)
    scheme_type = serializers.CharField(source='scheme.scheme_type', read_only=True)
    months_completed = serializers.IntegerField(read_only=True)
    is_matured = serializers.BooleanField(read_only=True)
    remaining_installments = serializers.IntegerField(read_only=True)
    applicable_benefit = serializers.SerializerMethodField()
    nominee = SchemeNomineeSerializer(read_only=True)
    enrollment_form_file = serializers.FileField(read_only=True)

    class Meta:
        model = SchemeEnrollment
        fields = [
            'id', 'enrollment_no', 'scheme', 'scheme_name', 'scheme_code', 'scheme_type',
            'customer', 'customer_name',
            'start_date', 'maturity_date', 'installment_amount',
            'locked_gold_rate', 'locked_purity',
            'total_paid', 'gold_accumulated_wt', 'payments_made',
            'status', 'months_completed', 'is_matured', 'remaining_installments',
            'applicable_benefit',
            'redeemed_date', 'lc_discount_applied', 'value_discount_applied',
            'salesperson', 'remarks', 'nominee', 'enrollment_form_file', 'created_at',
        ]

    def get_applicable_benefit(self, obj):
        tier = obj.applicable_benefit
        if not tier:
            return None
        return {
            'lc_discount_pct': float(tier.lc_discount_pct),
            'value_discount_pct': float(tier.value_discount_pct),
        }


class SchemeEnrollmentCreateSerializer(serializers.Serializer):
    scheme = serializers.PrimaryKeyRelatedField(queryset=SchemeMaster.objects.all())
    customer = serializers.IntegerField(help_text="Ledger ID of the customer")
    installment_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    salesperson = serializers.IntegerField(required=False, allow_null=True)
    start_date = serializers.DateField(required=False)
    remarks = serializers.CharField(required=False, default='', allow_blank=True)
    nominee = SchemeNomineeSerializer(required=True)
    enrollment_form_file = serializers.FileField(required=False, allow_null=True)


# ── Payment ───────────────────────────────────────────────────────────────────

class SchemePaymentListSerializer(serializers.ModelSerializer):
    enrollment_no = serializers.CharField(source='enrollment.enrollment_no', read_only=True)
    payment_ledger_name = serializers.CharField(source='payment_ledger.ac_name', read_only=True)
    voucher_no = serializers.CharField(source='voucher.voucher_no', read_only=True, default=None)

    class Meta:
        model = SchemePayment
        fields = [
            'id', 'enrollment', 'enrollment_no', 'payment_no', 'date',
            'amount', 'payment_mode', 'payment_ledger', 'payment_ledger_name',
            'installment_number',
            'gold_rate_at_payment', 'gold_weight_added',
            'voucher', 'voucher_no',
            'remarks', 'created_at',
        ]


class SchemePaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_mode = serializers.ChoiceField(choices=SchemePayment.PAYMENT_MODES)
    payment_ledger = serializers.IntegerField(help_text="Ledger ID of the cash/bank account")
    date = serializers.DateField(required=False)
    remarks = serializers.CharField(required=False, default='')
