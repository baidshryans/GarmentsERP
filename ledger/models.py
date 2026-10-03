from decimal import Decimal

from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from core.scoping import FactoryScopedModel, FactoryScopedQuerySet

from .exceptions import PostedVoucherImmutable

ZERO = Decimal("0.00")


class AccountGroup(models.Model):
    class Nature(models.TextChoices):
        ASSET = "asset", "Asset"
        LIABILITY = "liability", "Liability"
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    class Statement(models.TextChoices):
        BALANCE_SHEET = "bs", "Balance sheet"
        PROFIT_LOSS = "pl", "Profit & loss"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="account_groups")
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    name = models.CharField(max_length=100)
    nature = models.CharField(max_length=10, choices=Nature.choices)
    statement = models.CharField(max_length=2, choices=Statement.choices)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    history = HistoricalRecords()

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="uniq_group_name_per_company"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError

        node = self.parent
        while node is not None:
            if node.pk == self.pk:
                raise ValidationError("A group cannot sit under itself.")
            node = node.parent
        if self.parent_id:
            self.nature = self.parent.nature
            self.statement = self.parent.statement


class Ledger(models.Model):
    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="ledgers")
    group = models.ForeignKey(AccountGroup, on_delete=models.PROTECT, related_name="ledgers")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, blank=True)
    system_key = models.CharField(
        max_length=40, null=True, blank=True,
        help_text="Stable handle code uses to find this ledger even if it is renamed",
    )
    bill_wise = models.BooleanField(default=False, help_text="Track outstanding bill by bill")
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="uniq_ledger_name_per_company"),
            models.UniqueConstraint(
                fields=["company", "system_key"], condition=Q(system_key__isnull=False),
                name="uniq_ledger_system_key",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def nature(self):
        return self.group.nature


class VoucherType(models.TextChoices):
    PAYMENT = "payment", "Payment"
    RECEIPT = "receipt", "Receipt"
    CONTRA = "contra", "Contra"
    JOURNAL = "journal", "Journal"
    SALES = "sales", "Sales"
    PURCHASE = "purchase", "Purchase"
    DEBIT_NOTE = "debit_note", "Debit note"
    CREDIT_NOTE = "credit_note", "Credit note"
    STOCK_JOURNAL = "stock_journal", "Stock journal"
    JOB_WORK_BILL = "job_work_bill", "Job work bill"
    PAYROLL = "payroll", "Payroll"
    OPENING = "opening", "Opening balance"


class VoucherQuerySet(FactoryScopedQuerySet):
    """Posted vouchers cannot be changed or deleted through the ORM either (BR-16)."""

    def _guard(self):
        if self.filter(status=Voucher.Status.POSTED).exists():
            raise PostedVoucherImmutable("Posted vouchers cannot be edited or deleted; reverse them instead.")

    def update(self, **kwargs):
        self._guard()
        return super().update(**kwargs)

    def delete(self):
        self._guard()
        return super().delete()


class Voucher(FactoryScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="vouchers")
    voucher_type = models.CharField(max_length=20, choices=VoucherType.choices)
    number = models.CharField(max_length=50, null=True, blank=True, help_text="Assigned when posted")
    date = models.DateField()
    financial_year = models.ForeignKey("core.FinancialYear", on_delete=models.PROTECT, related_name="vouchers")
    status = models.CharField(max_length=6, choices=Status.choices, default=Status.DRAFT)
    narration = models.CharField(max_length=500, blank=True)
    source_type = models.CharField(max_length=60, blank=True, help_text="app_label.model of the source document")
    source_id = models.PositiveIntegerField(null=True, blank=True)
    reverses = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversals"
    )
    reversal_reason = models.CharField(max_length=255, blank=True)
    total = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    posted_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    posted_at = models.DateTimeField(null=True, blank=True)

    objects = VoucherQuerySet.as_manager()
    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "number"], condition=Q(number__isnull=False), name="uniq_voucher_number"
            ),
            models.CheckConstraint(
                condition=Q(status="draft") | Q(number__isnull=False), name="posted_voucher_has_number"
            ),
            models.UniqueConstraint(
                fields=["reverses"], condition=Q(reverses__isnull=False), name="voucher_reversed_once"
            ),
        ]
        indexes = [models.Index(fields=["source_type", "source_id"])]

    def __str__(self):
        return self.number or f"Draft {self.get_voucher_type_display()} #{self.pk}"

    @property
    def is_posted(self):
        return self.status == self.Status.POSTED

    @property
    def is_reversed(self):
        return self.reversals.exists()

    def _db_status(self):
        return Voucher.objects.filter(pk=self.pk).values_list("status", flat=True).first()

    def save(self, *args, **kwargs):
        if self.pk and self._db_status() == self.Status.POSTED:
            raise PostedVoucherImmutable(f"{self.number} is posted and cannot be edited.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.pk and self._db_status() == self.Status.POSTED:
            raise PostedVoucherImmutable(f"{self.number} is posted and cannot be deleted.")
        return super().delete(*args, **kwargs)


class VoucherLineQuerySet(FactoryScopedQuerySet):
    def _guard(self):
        if self.filter(voucher__status=Voucher.Status.POSTED).exists():
            raise PostedVoucherImmutable("Lines of a posted voucher cannot be changed.")

    def update(self, **kwargs):
        self._guard()
        return super().update(**kwargs)

    def delete(self):
        self._guard()
        return super().delete()

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        ids = {o.voucher_id for o in objs}
        if Voucher.objects.filter(pk__in=ids, status=Voucher.Status.POSTED).exists():
            raise PostedVoucherImmutable("Lines cannot be added to a posted voucher.")
        return super().bulk_create(objs, *args, **kwargs)


class VoucherLine(FactoryScopedModel):
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveSmallIntegerField(default=1)
    ledger = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name="lines")
    debit = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    credit = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    narration = models.CharField(max_length=255, blank=True)

    objects = VoucherLineQuerySet.as_manager()
    history = HistoricalRecords()

    class Meta:
        ordering = ["voucher_id", "line_no"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(debit__gt=0, credit=0) | Q(credit__gt=0, debit=0)),
                name="line_exactly_one_side",
            ),
        ]

    def __str__(self):
        side = f"Dr {self.debit}" if self.debit else f"Cr {self.credit}"
        return f"{self.ledger} {side}"

    @property
    def amount(self):
        return self.debit or self.credit

    def save(self, *args, **kwargs):
        if Voucher.objects.filter(pk=self.voucher_id, status=Voucher.Status.POSTED).exists():
            raise PostedVoucherImmutable("Lines of a posted voucher cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if Voucher.objects.filter(pk=self.voucher_id, status=Voucher.Status.POSTED).exists():
            raise PostedVoucherImmutable("Lines of a posted voucher cannot be deleted.")
        return super().delete(*args, **kwargs)


class BillAllocation(models.Model):
    """Bill-wise settlement (ACC-14): a line either opens a bill, settles one, or sits as advance / on account."""

    class RefType(models.TextChoices):
        NEW = "new", "New reference"
        AGAINST = "against", "Against reference"
        ADVANCE = "advance", "Advance"
        ON_ACCOUNT = "on_account", "On account"

    line = models.ForeignKey(VoucherLine, on_delete=models.CASCADE, related_name="allocations")
    ref_type = models.CharField(max_length=10, choices=RefType.choices)
    reference = models.CharField(max_length=60, blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="allocation_positive")]

    def save(self, *args, **kwargs):
        if Voucher.objects.filter(pk=self.line.voucher_id, status=Voucher.Status.POSTED).exists():
            raise PostedVoucherImmutable("Allocations of a posted voucher cannot be changed.")
        super().save(*args, **kwargs)
