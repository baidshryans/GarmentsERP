from django.db import models
from django.contrib.auth.models import User

from mastersconfig.models import RetailMaster
from django.core.exceptions import ValidationError
# ── Constants ────────────────────────────────────────────────────────────────

TYPE_CHOICES = (
    ("CO",  "Customer"),
    ("DL",  "Dealer"),
    ("KR",  "Karigar"),
    ("VD",  "Vendor"),
    ("CA",  "Cash"),
    ("BA",  "Bank"),
    ("SC",  "Sundry Creditors"),
    ("SD",  "Sundry Debtors"),
    ("REF", "Refinery"),
    ("MLT", "Melting House"),
    ("EXP", "Expenses"),
    ("INC", "Income"),
    ("HM",  "Hallmark"),
    ("OTH", "Others"),
)

# Ledger types that represent people/businesses (parties)
PARTY_TYPES = {"CO", "DL", "KR", "VD", "SC", "SD", "REF", "MLT", "HM"}

# Ledger types that are non-personal (system/accounting)
NON_PERSONAL_TYPES = {"CA", "BA", "EXP", "INC", "OTH"}


class UserLocation(models.Model):
    user = models.OneToOneField(User,on_delete=models.CASCADE)
    location = models.ManyToManyField(RetailMaster)
    default_location = models.ForeignKey(RetailMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="default_retail")

    def clean(self):
        if self.default_location and not self.location.filter(id=self.default_location.id).exists():
            raise ValidationError({'default_location': 'Default location must be one of the selected locations'})

class Ledger(models.Model):
    salutation = models.CharField(max_length=10, null=True, blank=True)
    ac_name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)

    b2b = models.BooleanField(default=False, db_index=True)
    b2b_pricelist = models.ForeignKey(
        'mastersconfig.B2BPricelist', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ledgers',
    )
    retail_discount_pricelist = models.ForeignKey(
        'mastersconfig.RetailDiscountPricelist', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ledgers',
    )

    # type field removed — use LedgerRole.role with is_primary=True instead

    dob = models.DateField(null=True, blank=True)
    anniversary = models.DateField(null=True, blank=True)

    ac_group = models.ForeignKey(
        'accounting.Account', on_delete=models.SET_NULL, null=True, blank=True
    )

    # ── Billing Address ───────────────────────────────────────────────────────
    add1    = models.CharField(max_length=100, null=True, blank=True)
    add2    = models.CharField(max_length=100, null=True, blank=True)
    city    = models.CharField(max_length=100, null=True, blank=True)
    pincode = models.CharField(max_length=10,  null=True, blank=True)
    state   = models.CharField(max_length=100, null=True, blank=True)
    # ── Shipping Address (mirrors billing unless explicitly overridden) ────────
    ship_add1    = models.CharField(max_length=100, null=True, blank=True)
    ship_add2    = models.CharField(max_length=100, null=True, blank=True)
    ship_city    = models.CharField(max_length=100, null=True, blank=True)
    ship_pincode = models.CharField(max_length=10,  null=True, blank=True)
    ship_state   = models.CharField(max_length=100, null=True, blank=True)
    phone1 = models.CharField(max_length=20, null=True, blank=True)
    phone2 = models.CharField(max_length=20, null=True, blank=True)
    phone3 = models.CharField(max_length=20, null=True, blank=True)
    mobile1 = models.CharField(max_length=20, blank=True, db_index=True)
    mobile2 = models.CharField(max_length=20, null=True, blank=True)
    mobile3 = models.CharField(max_length=20, null=True, blank=True)
    fax = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    pan = models.CharField(max_length=20, null=True, blank=True)
    gst = models.CharField(max_length=20, null=True, blank=True)
    aadhar = models.CharField(max_length=20, null=True, blank=True)
    passport = models.CharField(max_length=20, null=True, blank=True)
    dl_no = models.CharField(max_length=20, null=True, blank=True)
    remarks = models.CharField(max_length=100, null=True, blank=True)
    retail_code = models.ForeignKey(
        RetailMaster, blank=True, null=True, on_delete=models.CASCADE
    )
    cheque_no = models.CharField(max_length=100, blank=True)

    tds_applicable    = models.BooleanField(default=False)
    tds_section       = models.ForeignKey('mastersconfig.TDSSectionMaster', on_delete=models.SET_NULL, null=True, blank=True, related_name='ledgers')
    tds_deductor_type = models.CharField(max_length=3, choices=[('IND', 'Individual/HUF'), ('CO', 'Company/Firm')], null=True, blank=True)

    is_system = models.BooleanField(
        default=False,
        help_text="Auto-created system ledger (Cash, GST registers, operational). Cannot be edited or deleted."
    )

    def __str__(self):
        return f'{self.ac_name} {self.pk}'

    @property
    def primary_role(self):
        """Return the role code marked as primary, or the first role, or None."""
        r = self.roles.filter(is_primary=True).first()
        if r:
            return r.role
        first = self.roles.first()
        return first.role if first else None

    def clean(self):
        """Type-specific validation is now handled in the serializer after roles are saved."""
        super().clean()
    class Meta:
        db_table = "ledger_master"
        indexes = [
            models.Index(fields=['ac_group'], name='idx_ldgr_acgroup'),
            models.Index(fields=['ac_name'], name='idx_ldgr_acname'),
        ]


# ── Proxy Models ─────────────────────────────────────────────────────────────
# These provide type-specific managers and convenience methods without any DB
# change. Use them in views/serializers when you know you're working with a
# specific ledger type.

class _LedgerTypeManager(models.Manager):
    """Custom manager that pre-filters by ledger role."""

    def __init__(self, ledger_type):
        super().__init__()
        self._ledger_type = ledger_type

    def get_queryset(self):
        return super().get_queryset().filter(roles__role=self._ledger_type).distinct()


class CustomerLedger(Ledger):
    objects = _LedgerTypeManager('CO')

    class Meta:
        proxy = True


class DealerLedger(Ledger):
    objects = _LedgerTypeManager('DL')

    class Meta:
        proxy = True


class KarigarLedger(Ledger):
    objects = _LedgerTypeManager('KR')

    class Meta:
        proxy = True


class BankLedger(Ledger):
    objects = _LedgerTypeManager('BA')

    class Meta:
        proxy = True


class CashLedger(Ledger):
    objects = _LedgerTypeManager('CA')

    class Meta:
        proxy = True


# ── Multi-Role Support ───────────────────────────────────────────────────────
# A single ledger can have multiple roles (e.g. a Dealer who is also a
# Customer). is_primary=True marks the main classification used for display.

class LedgerRole(models.Model):
    """Junction table allowing a ledger to hold multiple roles."""
    ledger = models.ForeignKey(
        Ledger, on_delete=models.CASCADE, related_name='roles'
    )
    role = models.CharField(max_length=50, choices=TYPE_CHOICES)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "ledger_role"
        unique_together = ('ledger', 'role')
        indexes = [
            models.Index(fields=['role'], name='idx_ldgrrole_role'),
            models.Index(fields=['role', 'ledger'], name='idx_ldgrrole_role_ldgr'),
        ]

    def __str__(self):
        return f'{self.ledger.ac_name} — {self.get_role_display()}'


class Documents(models.Model):
    ldgr = models.ForeignKey(Ledger, on_delete=models.CASCADE, related_name='documents')
    document = models.FileField(upload_to="documents-ldgr/%Y/%m/")
    original_name = models.CharField(max_length=255, blank=True)
    document_type = models.CharField(max_length=20, choices=(
        ('PAN', 'PAN Card'),
        ('AADHAR', 'Aadhar Card'),
        ('DL', 'Driving License'),
        ('PASSPORT', 'Passport'),
        ('VOTER', 'Voter ID'),
        ('GST', 'GST Certificate'),
        ('OTHER', 'Other'),
    ))
    uploaded_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = "ledger_documents"