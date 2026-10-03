from decimal import Decimal

from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from core.scoping import FactoryScopedModel

ZERO = Decimal("0.00")
QZERO = Decimal("0.000")


class LabourRate(models.Model):
    """What a fabricator is paid for a process (JOB-06). Dated, so a change applies only to later challans (BR-12).

    A per piece | B per piece plus add-ons | C size-wise | D flat per lot.
    """

    class Type(models.TextChoices):
        PER_PIECE = "A", "A - per piece"
        ADDONS = "B", "B - per piece plus add-ons"
        SIZE_WISE = "C", "C - size-wise"
        FLAT = "D", "D - flat per lot"

    party = models.ForeignKey("masters.Party", on_delete=models.PROTECT, related_name="labour_rates")
    process = models.ForeignKey("masters.Process", on_delete=models.PROTECT, related_name="+")
    rate_type = models.CharField(max_length=1, choices=Type.choices, default=Type.PER_PIECE)
    base_rate = models.DecimalField("Rate per piece", max_digits=10, decimal_places=2, default=ZERO)
    flat_amount = models.DecimalField("Flat amount per lot", max_digits=12, decimal_places=2, default=ZERO)
    rework_rate = models.DecimalField("Rework rate per piece", max_digits=10, decimal_places=2, default=ZERO)
    effective_from = models.DateField()
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["party", "process", "-effective_from"]
        constraints = [
            models.UniqueConstraint(fields=["party", "process", "effective_from"], name="uniq_labour_rate_date"),
            models.CheckConstraint(
                condition=Q(base_rate__gte=0) & Q(flat_amount__gte=0) & Q(rework_rate__gte=0), name="labour_rate_non_negative"
            ),
        ]

    def __str__(self):
        return f"{self.party} / {self.process} ({self.rate_type}) from {self.effective_from}"


class LabourRateAddon(models.Model):
    rate = models.ForeignKey(LabourRate, on_delete=models.CASCADE, related_name="addons")
    name = models.CharField(max_length=60)
    amount = models.DecimalField("Per piece", max_digits=10, decimal_places=2)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount__gte=0), name="addon_non_negative")]


class LabourRateSize(models.Model):
    rate = models.ForeignKey(LabourRate, on_delete=models.CASCADE, related_name="sizes")
    size = models.ForeignKey("masters.Size", on_delete=models.PROTECT, related_name="+")
    amount = models.DecimalField("Per piece", max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["rate", "size"], name="uniq_rate_size"),
            models.CheckConstraint(condition=Q(amount__gte=0), name="rate_size_non_negative"),
        ]


class JobWorkChallan(FactoryScopedModel):
    """Issue of bundles and trims to a fabricator (E8.1). Always for a lot, hence for a production order (BR-04)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PARTLY = "partly_received", "Partly received"
        RECEIVED = "fully_received", "Fully received"
        BILLED = "billed", "Billed"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    class Kind(models.TextChoices):
        ISSUE = "issue", "Job work"
        REWORK = "rework", "Rework"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=50, null=True, blank=True)
    party = models.ForeignKey("masters.Party", on_delete=models.PROTECT, related_name="challans")
    lot = models.ForeignKey("production.Lot", on_delete=models.PROTECT, related_name="challans")
    step = models.ForeignKey("production.LotStep", on_delete=models.PROTECT, related_name="challans")
    kind = models.CharField(max_length=6, choices=Kind.choices, default=Kind.ISSUE)
    date = models.DateField()
    expected_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    rate_type = models.CharField(max_length=1, choices=LabourRate.Type.choices, default="A")
    flat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    remarks = models.CharField(max_length=255, blank=True)
    second_fabricator_ack = models.BooleanField(default=False, help_text="The user was warned another fabricator holds this lot (BR-05)")
    voucher = models.ForeignKey("ledger.Voucher", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    issued_at = models.DateTimeField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], condition=Q(number__isnull=False), name="uniq_challan_number"),
        ]

    def __str__(self):
        return self.number or f"Draft challan #{self.pk}"

    @property
    def is_open(self):
        return self.status in (self.Status.ISSUED, self.Status.PARTLY)


class ChallanBundle(models.Model):
    challan = models.ForeignKey(JobWorkChallan, on_delete=models.CASCADE, related_name="bundles")
    bundle = models.ForeignKey("production.Bundle", on_delete=models.PROTECT, related_name="challan_lines")
    qty_issued = models.PositiveIntegerField()
    rate = models.DecimalField("Rate per piece (when issued)", max_digits=10, decimal_places=2, default=ZERO)
    qty_received = models.PositiveIntegerField(default=0)
    qty_shortage = models.PositiveIntegerField(default=0)
    qty_accepted = models.PositiveIntegerField(default=0)
    qty_rejected = models.PositiveIntegerField(default=0)

    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["challan", "bundle"], name="uniq_challan_bundle"),
            models.CheckConstraint(condition=Q(qty_issued__gt=0), name="challan_bundle_qty_positive"),
        ]

    @property
    def pending(self):
        return max(0, self.qty_issued - self.qty_received - self.qty_shortage)


class ChallanTrim(models.Model):
    """Trims issued with a challan, per the BOM. The cost goes into the lot when the challan is issued."""

    challan = models.ForeignKey(JobWorkChallan, on_delete=models.CASCADE, related_name="trims")
    material = models.ForeignKey("masters.Material", on_delete=models.PROTECT, related_name="+")
    qty_issued = models.DecimalField(max_digits=14, decimal_places=3)
    value = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO, help_text="Cost when issued")
    qty_returned = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO)
    qty_missing = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(qty_issued__gt=0), name="challan_trim_qty_positive")]

    @property
    def unit_cost(self):
        return (self.value / self.qty_issued) if self.qty_issued else ZERO


class Receipt(FactoryScopedModel):
    """Goods back from a fabricator, counted by the supervisor (E8.2). Done by the fabricator is not a receipt (MOB-03)."""

    class Status(models.TextChoices):
        PENDING_APPROVAL = "pending_approval", "Over-receipt, needs approval"
        RECEIVED = "received", "Received, awaiting QC"
        QC_DONE = "qc_done", "QC done"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    challan = models.ForeignKey(JobWorkChallan, on_delete=models.PROTECT, related_name="receipts")
    number = models.CharField(max_length=50, null=True, blank=True)
    date = models.DateField()
    location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEIVED)
    approved_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], condition=Q(number__isnull=False), name="uniq_receipt_number"),
        ]

    def __str__(self):
        return self.number or f"Receipt #{self.pk}"


class ReceiptLine(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name="lines")
    challan_bundle = models.ForeignKey(ChallanBundle, on_delete=models.PROTECT, related_name="receipt_lines")
    qty_received = models.PositiveIntegerField()
    over_qty = models.PositiveIntegerField(default=0, help_text="Pieces above what was pending")
    shortage_qty = models.PositiveIntegerField(default=0, help_text="Pieces the fabricator did not return, written off to them")
    shortage_value = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    qc_done = models.BooleanField(default=False)

    history = HistoricalRecords()


class ReceiptTrim(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name="trims")
    challan_trim = models.ForeignKey(ChallanTrim, on_delete=models.PROTECT, related_name="receipts")
    qty_returned = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO)
    qty_missing = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO)


class QcResult(models.Model):
    """Accepted, rejected and rework pieces of one received line (E8.3). Only accepted pieces are ever paid."""

    class Destination(models.TextChoices):
        REJECTS = "rejects", "Rejects stock"
        SCRAP = "scrap", "Scrapped"

    line = models.OneToOneField(ReceiptLine, on_delete=models.PROTECT, related_name="qc")
    accepted = models.PositiveIntegerField()
    rejected = models.PositiveIntegerField(default=0)
    rework = models.PositiveIntegerField(default=0)
    reject_reason = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=8, choices=Destination.choices, default=Destination.REJECTS)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO, help_text="Rate that applies to these accepted pieces")
    is_rework_pass = models.BooleanField(default=False)
    checked_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    checked_at = models.DateTimeField(auto_now_add=True)
    bill_line = models.ForeignKey("jobwork.JobWorkBillLine", on_delete=models.PROTECT, null=True, blank=True, related_name="qc_results")

    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(accepted__gte=0), name="qc_accepted_non_negative"),
        ]


class JobWorkBill(FactoryScopedModel):
    """The fabricator's labour statement, built only from QC-accepted pieces (E8.4, JOB-07, BR-17)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=50, null=True, blank=True)
    party = models.ForeignKey("masters.Party", on_delete=models.PROTECT, related_name="job_work_bills")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    tds_template = models.ForeignKey("tax.TaxTemplate", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    gross = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    deductions = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    tds = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    net = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    voucher = models.ForeignKey("ledger.Voucher", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], condition=Q(number__isnull=False), name="uniq_jw_bill_number"),
        ]

    def __str__(self):
        return self.number or f"Draft bill #{self.pk}"


class JobWorkBillLine(models.Model):
    bill = models.ForeignKey(JobWorkBill, on_delete=models.CASCADE, related_name="lines")
    challan = models.ForeignKey(JobWorkChallan, on_delete=models.PROTECT, related_name="bill_lines")
    lot = models.ForeignKey("production.Lot", on_delete=models.PROTECT, related_name="+")
    description = models.CharField(max_length=200)
    qty = models.PositiveIntegerField()
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    amount = models.DecimalField(max_digits=16, decimal_places=2)

    history = HistoricalRecords()


class JobWorkBillDeduction(models.Model):
    class Kind(models.TextChoices):
        SHORTAGE = "shortage", "Shortage of pieces"
        MISSING_TRIMS = "missing_trims", "Missing trims"
        PENALTY = "penalty", "Rejection penalty"
        OTHER = "other", "Other"

    bill = models.ForeignKey(JobWorkBill, on_delete=models.CASCADE, related_name="deduction_lines")
    challan = models.ForeignKey(JobWorkChallan, on_delete=models.PROTECT, related_name="+")
    lot = models.ForeignKey("production.Lot", on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=14, choices=Kind.choices)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    source_receipt_line = models.ForeignKey(ReceiptLine, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    source_receipt_trim = models.ForeignKey(ReceiptTrim, on_delete=models.PROTECT, null=True, blank=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="deduction_positive")]
