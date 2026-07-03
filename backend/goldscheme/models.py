import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone


class SchemeMaster(models.Model):
    """
    Definition of a gold savings / purchase scheme.
    Admin creates one per scheme type; customers enroll into these.
    """
    SCHEME_TYPES = [
        ('INSTALLMENT', 'Monthly Installment'),
        ('ACCUMULATION', 'Gold Accumulation'),
        ('LUMPSUM', 'One-Time Lump Sum'),
    ]
    GOLD_PRICE_MODES = [
        ('CURRENT', 'Current gold price at redemption'),
        ('ACCUMULATED', 'Gold accumulated at each payment rate'),
        ('LOCKED', 'Gold price locked at enrollment'),
    ]

    name              = models.CharField(max_length=100)
    scheme_code       = models.CharField(max_length=20, unique=True)
    scheme_type       = models.CharField(max_length=15, choices=SCHEME_TYPES)
    gold_price_mode   = models.CharField(max_length=12, choices=GOLD_PRICE_MODES)

    tenure_months     = models.PositiveIntegerField(default=11)
    min_amount        = models.DecimalField(max_digits=10, decimal_places=2, default=1000)
    max_amount        = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                             help_text="Leave blank for unlimited")

    accumulation_purity = models.ForeignKey(
        'goldrates.PurityMaster', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='accumulation_schemes',
        help_text="For ACCUMULATION type: purity at which gold is accumulated (e.g. 22K)"
    )

    has_diamond_benefit = models.BooleanField(default=False,
                                               help_text="Does this scheme offer diamond ornament discounts?")

    is_active         = models.BooleanField(default=True)
    description       = models.TextField(blank=True)
    terms_conditions  = models.TextField(blank=True)

    retail            = models.ForeignKey('mastersconfig.RetailMaster', on_delete=models.CASCADE,
                                           related_name='gold_schemes')
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scheme_master'
        indexes = [
            models.Index(fields=['retail', 'is_active'], name='idx_sm_retail_active'),
        ]

    def __str__(self):
        return f"{self.scheme_code} — {self.name}"


class SchemeBenefitTier(models.Model):
    """
    Tiered benefits per scheme: how many months → what discount.
    E.g. 6-8 months = 40% off making charges, 9-10 = 60%, 11 = 75%.
    """
    PRODUCT_TYPES = [
        ('GOLD', 'Gold Ornament'),
        ('DIAMOND', 'Diamond Ornament'),
    ]

    scheme             = models.ForeignKey(SchemeMaster, on_delete=models.CASCADE, related_name='benefit_tiers')
    product_type       = models.CharField(max_length=10, choices=PRODUCT_TYPES, default='GOLD')
    min_months         = models.PositiveIntegerField(help_text="Minimum months completed to qualify")
    max_months         = models.PositiveIntegerField(help_text="Maximum months for this tier")
    lc_discount_pct    = models.DecimalField(max_digits=5, decimal_places=2,
                                              help_text="Making/labour charge discount percentage")
    value_discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                              help_text="Additional discount on product value (diamond schemes)")

    class Meta:
        db_table = 'scheme_benefit_tier'
        unique_together = ('scheme', 'product_type', 'min_months')
        ordering = ['product_type', 'min_months']

    def __str__(self):
        return f"{self.scheme.scheme_code} | {self.product_type} | {self.min_months}-{self.max_months}m → {self.lc_discount_pct}% off LC"


class SchemeEnrollment(models.Model):
    """
    A customer's enrollment in a specific scheme.
    Tracks payments, accumulated gold, status, and redemption.
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('MATURED', 'Matured'),
        ('REDEEMED', 'Redeemed'),
        ('FORFEITED', 'Forfeited'),
        ('CANCELLED', 'Cancelled'),
    ]

    enrollment_no      = models.CharField(max_length=30, unique=True)
    uuid               = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True,
                                          help_text="Opaque public identifier used in customer-facing URLs.")
    scheme             = models.ForeignKey(SchemeMaster, on_delete=models.PROTECT, related_name='enrollments')
    customer           = models.ForeignKey('contacts.Ledger', on_delete=models.PROTECT,
                                            related_name='scheme_enrollments')

    start_date         = models.DateField()
    maturity_date      = models.DateField()
    installment_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('1'))],
        help_text="Fixed monthly amount (INSTALLMENT/ACCUMULATION) or lump sum (LUMPSUM)"
    )

    # For LOCKED price mode
    locked_gold_rate   = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                              help_text="Gold rate per gram locked at enrollment (LUMPSUM type)")
    locked_purity      = models.ForeignKey('goldrates.PurityMaster', null=True, blank=True,
                                            on_delete=models.SET_NULL, related_name='locked_enrollments')

    # Running totals (updated on each payment via signals)
    total_paid         = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gold_accumulated_wt = models.DecimalField(max_digits=10, decimal_places=3, default=0,
                                               help_text="For ACCUMULATION type: total gold grams")
    payments_made      = models.PositiveIntegerField(default=0)

    status             = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')

    # Redemption tracking
    redeemed_date      = models.DateField(null=True, blank=True)
    redeemed_sales_vou = models.ForeignKey('sales.SalesVou', null=True, blank=True,
                                            on_delete=models.SET_NULL, related_name='scheme_redemptions')
    lc_discount_applied = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                               help_text="Making charge discount applied at redemption")
    value_discount_applied = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                                  help_text="Value discount applied at redemption (diamond)")

    liability_ledger   = models.ForeignKey('contacts.Ledger', null=True, blank=True,
                                            on_delete=models.SET_NULL, related_name='scheme_liability_for',
                                            help_text="Per-enrollment scheme-advances sub-ledger (Cr on payment).")

    retail             = models.ForeignKey('mastersconfig.RetailMaster', on_delete=models.CASCADE,
                                            related_name='scheme_enrollments')
    fiscal_year        = models.ForeignKey('mastersconfig.FiscalYearMaster', on_delete=models.SET_NULL,
                                            null=True, blank=True)
    salesperson        = models.ForeignKey('mastersconfig.SalesPersonMaster', null=True, blank=True,
                                            on_delete=models.SET_NULL)
    remarks            = models.TextField(blank=True)
    enrollment_form_file = models.FileField(
        upload_to='scheme/enrollment_forms/%Y/%m/', null=True, blank=True,
        help_text="Signed enrollment form scan (PDF/JPG/PNG)."
    )
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scheme_enrollment'
        indexes = [
            models.Index(fields=['retail', 'status'], name='idx_se_retail_status'),
            models.Index(fields=['customer'], name='idx_se_customer'),
            models.Index(fields=['maturity_date'], name='idx_se_maturity'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(maturity_date__gte=models.F('start_date')),
                name='chk_maturity_after_start',
            ),
            models.UniqueConstraint(fields=['retail', 'fiscal_year', 'enrollment_no'], name='uniq_se_number'),
        ]

    def __str__(self):
        return f"{self.enrollment_no} — {self.customer.ac_name}"

    @property
    def months_completed(self):
        from dateutil.relativedelta import relativedelta
        today = date.today()
        if today < self.start_date:
            return 0
        delta = relativedelta(today, self.start_date)
        return delta.years * 12 + delta.months

    @property
    def is_matured(self):
        return date.today() >= self.maturity_date

    @property
    def applicable_benefit(self):
        """Returns the best GOLD benefit tier based on months completed."""
        months = self.months_completed
        return self.scheme.benefit_tiers.filter(
            product_type='GOLD',
            min_months__lte=months,
            max_months__gte=months,
        ).first()

    @property
    def applicable_diamond_benefit(self):
        """Returns the best DIAMOND benefit tier based on months completed."""
        if not self.scheme.has_diamond_benefit:
            return None
        months = self.months_completed
        return self.scheme.benefit_tiers.filter(
            product_type='DIAMOND',
            min_months__lte=months,
            max_months__gte=months,
        ).first()

    @property
    def next_installment_number(self):
        return self.payments_made + 1

    @property
    def remaining_installments(self):
        if self.scheme.scheme_type == 'LUMPSUM':
            return 0 if self.payments_made > 0 else 1
        return max(0, self.scheme.tenure_months - self.payments_made)


class SchemePayment(models.Model):
    """
    Individual payment record within a scheme enrollment.
    Each payment creates a SCHM accounting voucher via signals.
    """
    PAYMENT_MODES = [
        ('CASH', 'Cash'),
        ('BANK', 'Bank Transfer'),
        ('UPI', 'UPI'),
        ('CHEQUE', 'Cheque'),
        ('CARD', 'Card'),
    ]

    enrollment          = models.ForeignKey(SchemeEnrollment, on_delete=models.CASCADE, related_name='payments')
    payment_no          = models.CharField(max_length=30, unique=True)
    date                = models.DateField()
    amount              = models.DecimalField(max_digits=10, decimal_places=2,
                                               validators=[MinValueValidator(Decimal('1'))])
    payment_mode        = models.CharField(max_length=10, choices=PAYMENT_MODES)
    payment_ledger      = models.ForeignKey('contacts.Ledger', on_delete=models.PROTECT,
                                             related_name='scheme_payments_received',
                                             help_text="Cash/Bank ledger that received the payment")
    installment_number  = models.PositiveIntegerField()

    # For ACCUMULATION type
    gold_rate_at_payment = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                                help_text="Gold rate per gram at time of this payment")
    gold_weight_added    = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True,
                                                help_text="Grams of gold accumulated with this payment")

    # Accounting link
    voucher             = models.ForeignKey('accounting.VoucherMain', null=True, blank=True,
                                             on_delete=models.SET_NULL, related_name='scheme_payments')

    retail              = models.ForeignKey('mastersconfig.RetailMaster', on_delete=models.CASCADE,
                                             related_name='scheme_payments')
    fiscal_year         = models.ForeignKey('mastersconfig.FiscalYearMaster', on_delete=models.SET_NULL,
                                             null=True, blank=True)
    remarks             = models.CharField(max_length=200, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'scheme_payment'
        indexes = [
            models.Index(fields=['enrollment', 'date'], name='idx_sp_enrollment_date'),
            models.Index(fields=['retail', 'date'], name='idx_sp_retail_date'),
        ]
        ordering = ['date', 'installment_number']
        constraints = [
            models.UniqueConstraint(fields=['retail', 'fiscal_year', 'payment_no'], name='uniq_sp_number'),
        ]

    def __str__(self):
        return f"{self.payment_no} — ₹{self.amount} for {self.enrollment.enrollment_no}"


class SchemeNominee(models.Model):
    """One nominee per scheme enrollment. Captured at enrollment time."""
    RELATIONSHIP_CHOICES = [
        ('SPOUSE', 'Spouse'),
        ('SON', 'Son'),
        ('DAUGHTER', 'Daughter'),
        ('FATHER', 'Father'),
        ('MOTHER', 'Mother'),
        ('BROTHER', 'Brother'),
        ('SISTER', 'Sister'),
        ('OTHER', 'Other'),
    ]

    enrollment   = models.OneToOneField(
        SchemeEnrollment, on_delete=models.CASCADE,
        related_name='nominee', null=True, blank=True,
    )
    name         = models.CharField(max_length=120)
    mobile       = models.CharField(max_length=20)
    address      = models.TextField(blank=True)
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scheme_nominee'

    def __str__(self):
        return f"{self.name} ({self.get_relationship_display()}) — {self.enrollment.enrollment_no if self.enrollment else 'unlinked'}"


# ══════════════════════════════════════════════════════════════════════════════
#  Customer Portal Models
# ══════════════════════════════════════════════════════════════════════════════

class CustomerPortalCredential(models.Model):
    """Password credential for a customer to access the portal."""
    ledger        = models.OneToOneField('contacts.Ledger', on_delete=models.CASCADE,
                                          related_name='portal_credential')
    password_hash = models.CharField(max_length=128)
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customer_portal_credential'

    def __str__(self):
        return f"Portal credential for {self.ledger.ac_name}"

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password_hash)


class CustomerPortalAccount(models.Model):
    """Portal login identity. Owns an explicit set of linked ledgers — the sole
    basis for what the customer may see (never a live mobile match)."""
    primary_email  = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    phone          = models.CharField(max_length=20, blank=True, db_index=True)
    password_hash  = models.CharField(max_length=128, blank=True)
    is_active      = models.BooleanField(default=True)
    linked_ledgers = models.ManyToManyField('contacts.Ledger', related_name='portal_accounts', blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customer_portal_account'

    def __str__(self):
        return f"Portal account {self.primary_email}"

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return bool(self.password_hash) and check_password(raw_password, self.password_hash)


class CustomerPortalOTP(models.Model):
    """Temporary OTP for portal login verification."""
    mobile     = models.CharField(max_length=20, db_index=True)
    retail     = models.ForeignKey('mastersconfig.RetailMaster', on_delete=models.CASCADE)
    otp_code   = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    attempts   = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'customer_portal_otp'

    def __str__(self):
        return f"OTP for {self.mobile} ({self.retail.retail_code})"

    @property
    def is_expired(self):
        minutes = getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
        return timezone.now() > self.created_at + timedelta(minutes=minutes)


class CustomerPortalToken(models.Model):
    """Session token for authenticated portal customers."""
    token      = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    account    = models.ForeignKey('goldscheme.CustomerPortalAccount', on_delete=models.CASCADE,
                                    related_name='tokens', null=True, blank=True)
    ledger     = models.ForeignKey('contacts.Ledger', on_delete=models.CASCADE,
                                    related_name='portal_tokens', null=True, blank=True)
    retail     = models.ForeignKey('mastersconfig.RetailMaster', on_delete=models.CASCADE)
    mobile     = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'customer_portal_token'

    def __str__(self):
        return f"Portal token for {self.ledger.ac_name} ({self.mobile})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def save(self, *args, **kwargs):
        if not self.expires_at:
            hours = getattr(settings, 'PORTAL_TOKEN_EXPIRY_HOURS', 24)
            self.expires_at = timezone.now() + timedelta(hours=hours)
        super().save(*args, **kwargs)
