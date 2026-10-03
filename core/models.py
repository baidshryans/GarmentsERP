from datetime import date

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from .constants import INDIAN_STATES, PERMISSION_ACTIONS, SENSITIVE_FIELDS
from .validators import validate_gstin, validate_pan


class Company(models.Model):
    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=200, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state_code = models.CharField(max_length=2, choices=INDIAN_STATES)
    pincode = models.CharField(max_length=10, blank=True)
    pan = models.CharField(max_length=10, blank=True, validators=[validate_pan])
    base_currency = models.CharField(max_length=3, default="INR")
    fy_start_month = models.PositiveSmallIntegerField(default=4)
    books_from = models.DateField()
    setup_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Inventory and purchase settings (Step 3). Changes are kept in the model history.
    class Valuation(models.TextChoices):
        WEIGHTED_AVERAGE = "weighted_average", "Weighted average per item per factory"
        SPECIFIC_ROLL = "specific_roll", "Specific cost per fabric roll (other items: weighted average)"

    valuation_method = models.CharField(max_length=20, choices=Valuation.choices, default=Valuation.WEIGHTED_AVERAGE)
    allow_negative_stock = models.BooleanField(
        default=False, help_text="When off, an issue above the stock on hand is blocked (BR-02, BR-09)"
    )
    bom_tolerance_pct = models.DecimalField(
        "BOM variance tolerance %", max_digits=5, decimal_places=2, default=5,
        help_text="Fabric used beyond this many percent over or under the BOM is flagged (BR-10)",
    )
    po_approval_limit = models.DecimalField(
        max_digits=14, decimal_places=2, default=50000,
        help_text="A purchase order above this value needs the owner's approval (BR-19). 0 = every PO needs approval.",
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name


class FinancialYear(models.Model):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="financial_years")
    start_date = models.DateField()
    end_date = models.DateField()
    label = models.CharField(max_length=7, help_text='For example "26-27"')
    is_closed = models.BooleanField(default=False)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(fields=["company", "label"], name="uniq_fy_label_per_company"),
        ]

    def __str__(self):
        return f"FY {self.label}"

    @classmethod
    def label_for(cls, start: date) -> str:
        return f"{start.year % 100:02d}-{(start.year + 1) % 100:02d}"

    @classmethod
    def for_date(cls, company, on_date: date):
        fy = cls.objects.filter(company=company, start_date__lte=on_date, end_date__gte=on_date).first()
        if fy is None:
            from .exceptions import BusinessRuleError

            raise BusinessRuleError(f"No financial year is defined for {on_date:%d-%b-%Y}.")
        return fy


class FactoryQuerySet(models.QuerySet):
    """Factories are scoped by their own id (BR-23)."""

    def for_user(self, user):
        if not user.is_authenticated:
            return self.none()
        ids = user.allowed_factory_ids()
        return self if ids is None else self.filter(pk__in=ids)

    def unscoped(self):
        return self.all()


class Factory(models.Model):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="factories")
    code = models.CharField(max_length=10, help_text="Short code used in document numbers, for example LDH1")
    name = models.CharField(max_length=150)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state_code = models.CharField(max_length=2, choices=INDIAN_STATES)
    gstin = models.CharField("GSTIN", max_length=15, blank=True, validators=[validate_gstin])
    is_active = models.BooleanField(default=True)

    objects = FactoryQuerySet.as_manager()
    history = HistoricalRecords()

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uniq_factory_code_per_company"),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Location(models.Model):
    class Type(models.TextChoices):
        GODOWN = "godown", "Godown"
        CUTTING = "cutting", "Cutting floor"
        PROCESS = "process", "Process area"
        SHOWROOM = "showroom", "Showroom"
        DISPATCH = "dispatch", "Dispatch"
        TRANSIT = "transit", "In transit"
        FABRICATOR = "fabricator", "At a fabricator / subcontractor"
        REJECTS = "rejects", "Rejects"

    factory = models.ForeignKey(Factory, on_delete=models.PROTECT, related_name="locations")
    name = models.CharField(max_length=100)
    loc_type = models.CharField(max_length=10, choices=Type.choices)
    party = models.ForeignKey(
        "masters.Party", on_delete=models.PROTECT, null=True, blank=True, related_name="locations",
        help_text="For a fabricator's premises: whose it is",
    )
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["factory__code", "name"]
        constraints = [
            models.UniqueConstraint(fields=["factory", "name"], name="uniq_location_name_per_factory"),
        ]

    def __str__(self):
        return f"{self.factory.code} / {self.name}"


class Role(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_system = models.BooleanField(default=False)

    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RolePermission(models.Model):
    """Permission for one screen and one action (E1.6). Screen codes live in core.screens."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissions")
    screen = models.CharField(max_length=60)
    action = models.CharField(max_length=10, choices=[(a, a) for a in PERMISSION_ACTIONS])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["role", "screen", "action"], name="uniq_role_screen_action"),
        ]

    def __str__(self):
        return f"{self.role}: {self.screen}:{self.action}"


class FieldPermission(models.Model):
    """Grants a role sight of a sensitive field. Absent means hidden."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="field_permissions")
    field_key = models.CharField(max_length=40, choices=list(SENSITIVE_FIELDS.items()))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["role", "field_key"], name="uniq_role_field"),
        ]

    def __str__(self):
        return f"{self.role}: {self.field_key}"


class User(AbstractUser):
    mobile = models.CharField(max_length=15, unique=True, null=True, blank=True)
    roles = models.ManyToManyField(Role, blank=True, related_name="users")
    all_factories = models.BooleanField(
        default=False, help_text="Access every factory, including ones added later."
    )
    allowed_factories = models.ManyToManyField(Factory, blank=True, related_name="users")
    failed_logins = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    history = HistoricalRecords(excluded_fields=["password", "last_login", "failed_logins", "locked_until"])

    def save(self, *args, **kwargs):
        if self.mobile == "":
            self.mobile = None  # unique + blank must be NULL, not ""
        super().save(*args, **kwargs)

    # ---- factory scoping (BR-23) ----
    def allowed_factory_ids(self):
        """None means every factory; otherwise the set of allowed ids."""
        if self.is_superuser or self.all_factories:
            return None
        return set(self.allowed_factories.values_list("pk", flat=True))

    def can_access_factory(self, factory) -> bool:
        if not self.is_active:
            return False
        ids = self.allowed_factory_ids()
        return ids is None or factory.pk in ids

    # ---- permissions (E1.6) ----
    def has_screen_perm(self, screen: str, action: str) -> bool:
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        return RolePermission.objects.filter(
            role__users=self, screen=screen, action=action
        ).exists()

    def can_view_field(self, field_key: str) -> bool:
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        return FieldPermission.objects.filter(role__users=self, field_key=field_key).exists()

    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())


class NumberSeries(models.Model):
    """Counter table for document numbers (database-neutral, no row locks)."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="number_series")
    factory = models.ForeignKey(Factory, on_delete=models.PROTECT, related_name="number_series")
    doc_type = models.CharField(max_length=30)
    financial_year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT, related_name="number_series")
    prefix = models.CharField(max_length=10)
    padding = models.PositiveSmallIntegerField(default=4)
    next_number = models.PositiveIntegerField(default=1)

    history = HistoricalRecords()

    class Meta:
        verbose_name_plural = "number series"
        constraints = [
            models.UniqueConstraint(
                fields=["factory", "doc_type", "financial_year"], name="uniq_series_per_factory_type_fy"
            ),
        ]

    def __str__(self):
        return f"{self.prefix}/{self.factory.code}/{self.financial_year.label}"


class PeriodLock(models.Model):
    """Everything on or before locked_upto is closed. factory null = all factories (BR-20)."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    factory = models.ForeignKey(Factory, on_delete=models.PROTECT, null=True, blank=True)
    locked_upto = models.DateField()
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "factory"], name="uniq_lock_per_scope"),
        ]


class PeriodLockLog(models.Model):
    class Action(models.TextChoices):
        LOCK = "lock", "Locked"
        UNLOCK = "unlock", "Unlocked"

    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    factory = models.ForeignKey(Factory, on_delete=models.PROTECT, null=True, blank=True)
    action = models.CharField(max_length=6, choices=Action.choices)
    previous_upto = models.DateField(null=True, blank=True)
    new_upto = models.DateField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    reason = models.CharField(max_length=255)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]


class AuditEvent(models.Model):
    """Login activity log (SYS-10). Read-only in the admin."""

    class Event(models.TextChoices):
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"
        FAILED = "failed", "Failed login"
        LOCKED = "locked", "Account locked"

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    username = models.CharField(max_length=150, blank=True)
    event = models.CharField(max_length=10, choices=Event.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]
