from decimal import Decimal

from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from core.scoping import FactoryScopedModel

ZERO = Decimal("0.00")
QZERO = Decimal("0.000")


class ItemLineMixin(models.Model):
    """A document line for a material or a finished-goods SKU."""

    material = models.ForeignKey("masters.Material", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    sku = models.ForeignKey("masters.SKU", on_delete=models.PROTECT, null=True, blank=True, related_name="+")

    class Meta:
        abstract = True

    @property
    def item(self):
        return self.material or self.sku


def one_item_constraint(name):
    return models.CheckConstraint(
        condition=(Q(material__isnull=False, sku__isnull=True) | Q(material__isnull=True, sku__isnull=False)), name=name
    )


# ---------------------------------------------------------------- purchase order (E5.1)

class PurchaseOrder(FactoryScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending_approval", "Pending approval"
        APPROVED = "approved", "Approved"
        PARTLY = "partly_received", "Partly received"
        RECEIVED = "received", "Received"
        CLOSED = "closed", "Closed"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=50, null=True, blank=True)
    vendor = models.ForeignKey("masters.Party", on_delete=models.PROTECT, related_name="purchase_orders")
    date = models.DateField()
    expected_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    remarks = models.CharField(max_length=255, blank=True)
    approved_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(max_length=255, blank=True, help_text="Short-close reason")
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], condition=Q(number__isnull=False), name="uniq_po_number"),
        ]

    def __str__(self):
        return self.number or f"Draft PO #{self.pk}"

    @property
    def total(self):
        return sum((l.amount for l in self.lines.all()), ZERO)


class PurchaseOrderLine(ItemLineMixin):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    qty = models.DecimalField(max_digits=14, decimal_places=3)
    rate = models.DecimalField(max_digits=14, decimal_places=4)

    history = HistoricalRecords()

    class Meta:
        constraints = [one_item_constraint("po_line_one_item"), models.CheckConstraint(condition=Q(qty__gt=0), name="po_qty_positive"),
                       models.CheckConstraint(condition=Q(rate__gte=0), name="po_rate_non_negative")]

    @property
    def amount(self):
        return (self.qty * self.rate).quantize(Decimal("0.01"))


# ---------------------------------------------------------------- GRN (E5.2, E5.3)

class Grn(FactoryScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QC_DONE = "qc_done", "QC done"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=50, null=True, blank=True)
    location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+")
    vendor = models.ForeignKey("masters.Party", on_delete=models.PROTECT, related_name="grns")
    po = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, null=True, blank=True, related_name="grns")
    date = models.DateField()
    vendor_challan_no = models.CharField(max_length=40, blank=True)
    vendor_challan_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    remarks = models.CharField(max_length=255, blank=True)
    voucher = models.ForeignKey("ledger.Voucher", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], condition=Q(number__isnull=False), name="uniq_grn_number"),
        ]

    def __str__(self):
        return self.number or f"Draft GRN #{self.pk}"


class QcStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"
    ACCEPTED_REMARK = "accepted_remark", "Accepted with remark"


class GrnLine(ItemLineMixin):
    grn = models.ForeignKey(Grn, on_delete=models.CASCADE, related_name="lines")
    po_line = models.ForeignKey(PurchaseOrderLine, on_delete=models.PROTECT, null=True, blank=True, related_name="grn_lines")
    qty_received = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO, help_text="For fabric: the total of its rolls")
    qty_accepted = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO)
    qty_rejected = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO)
    rate = models.DecimalField(max_digits=14, decimal_places=4)
    qc_status = models.CharField(max_length=16, choices=QcStatus.choices, default=QcStatus.PENDING)
    remark = models.CharField(max_length=255, blank=True)
    value = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO,
                                help_text="Stock value booked when the GRN was posted (credited to Goods Received Not Billed)")

    history = HistoricalRecords()

    class Meta:
        constraints = [one_item_constraint("grn_line_one_item"),
                       models.CheckConstraint(condition=Q(rate__gte=0), name="grn_rate_non_negative")]

    @property
    def is_fabric_rolls(self):
        return self.material_id is not None and self.material.kind == "fabric"


class GrnRoll(models.Model):
    """One received roll (E5.2). The FabricRoll and its label are created when the GRN is posted."""

    line = models.ForeignKey(GrnLine, on_delete=models.CASCADE, related_name="rolls")
    vendor_roll_no = models.CharField(max_length=40)
    lot_no = models.CharField("Lot / shade", max_length=40, blank=True)
    gsm = models.PositiveSmallIntegerField(null=True, blank=True)
    width_cm = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    qty = models.DecimalField("Quantity (primary unit)", max_digits=14, decimal_places=3)
    length_m = models.DecimalField("Length (metres)", max_digits=14, decimal_places=3, null=True, blank=True)
    qc_status = models.CharField(max_length=16, choices=QcStatus.choices, default=QcStatus.PENDING)
    remark = models.CharField(max_length=255, blank=True)
    roll = models.ForeignKey("inventory.FabricRoll", on_delete=models.PROTECT, null=True, blank=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(qty__gt=0), name="grn_roll_qty_positive")]


# ---------------------------------------------------------------- purchase invoice (E5.4)

class PurchaseInvoice(FactoryScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    class TaxMode(models.TextChoices):
        NONE = "none", "No tax"
        TEMPLATE = "template", "GST template"
        REVERSE_CHARGE = "reverse_charge", "Reverse charge"
        MANUAL = "manual", "Tax lines entered by hand"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=50, null=True, blank=True)
    vendor = models.ForeignKey("masters.Party", on_delete=models.PROTECT, related_name="purchase_invoices")
    vendor_invoice_no = models.CharField(max_length=40)
    vendor_invoice_date = models.DateField()
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    tax_mode = models.CharField(max_length=14, choices=TaxMode.choices, default=TaxMode.NONE)
    gst_template = models.ForeignKey("tax.TaxTemplate", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    itc_claimable = models.BooleanField("Input credit claimable", default=True,
                                        help_text="If not, the GST is added to the item cost")
    tds_template = models.ForeignKey("tax.TaxTemplate", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    is_direct = models.BooleanField("Direct purchase", default=False,
                                    help_text="Booked without a GRN: posting also brings the goods into stock at the location")
    location = models.ForeignKey("core.Location", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                                 help_text="Direct purchase: where the goods are received")
    subtotal = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    gst_total = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    tds_total = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    payable = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    voucher = models.ForeignKey("ledger.Voucher", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], condition=Q(number__isnull=False), name="uniq_pi_number"),
            models.UniqueConstraint(
                fields=["company", "vendor", "vendor_invoice_no"], condition=~Q(status="cancelled"),
                name="uniq_vendor_invoice_no",
            ),
        ]

    def __str__(self):
        return self.number or f"Draft invoice #{self.pk}"


class PurchaseInvoiceLine(ItemLineMixin):
    """Bills a GRN line, or (direct purchase) an item that comes into stock with the invoice itself."""

    invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE, related_name="lines")
    grn_line = models.ForeignKey(GrnLine, on_delete=models.PROTECT, null=True, blank=True, related_name="invoice_lines")
    qty = models.DecimalField(max_digits=14, decimal_places=3, help_text="As billed by the vendor")
    rate = models.DecimalField(max_digits=14, decimal_places=4)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    qty_accepted_part = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO)
    qty_rejected_part = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO)
    grni_cleared = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    recoverable_amount = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO,
                                             help_text="Billed value (and its tax) of rejected pieces, claimable from the vendor")
    rate_variance = models.BooleanField(default=False, help_text="Rate differs from the last purchase rate (BR-13)")

    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(qty__gt=0), name="pi_qty_positive"),
            models.CheckConstraint(
                condition=(Q(grn_line__isnull=False, material__isnull=True, sku__isnull=True)
                           | Q(grn_line__isnull=True, material__isnull=False, sku__isnull=True)
                           | Q(grn_line__isnull=True, material__isnull=True, sku__isnull=False)),
                name="pi_line_grn_or_one_item"),
        ]

    @property
    def billed_item(self):
        return self.grn_line.item if self.grn_line_id else self.item


class PurchaseInvoiceTax(models.Model):
    invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE, related_name="tax_lines")
    kind = models.CharField(max_length=3, choices=[("gst", "GST"), ("tds", "TDS")])
    component = models.CharField(max_length=4)
    rate = models.DecimalField(max_digits=6, decimal_places=3, default=ZERO)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    is_override = models.BooleanField(default=False)
    reason = models.CharField(max_length=255, blank=True)

    history = HistoricalRecords()


# ---------------------------------------------------------------- debit note (PUR-09, E5.3)

class DebitNote(FactoryScopedModel):
    class Kind(models.TextChoices):
        REJECTION = "rejection", "Rejected at GRN (billed by vendor)"
        RETURN = "return", "Return of stocked goods"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=50, null=True, blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    vendor = models.ForeignKey("masters.Party", on_delete=models.PROTECT, related_name="debit_notes")
    grn = models.ForeignKey(Grn, on_delete=models.PROTECT, null=True, blank=True, related_name="debit_notes")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    reason = models.CharField(max_length=255, blank=True)
    gst_template = models.ForeignKey("tax.TaxTemplate", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                                     help_text="Return notes only: GST reversed on the returned goods")
    itc_claimable = models.BooleanField(default=True)
    subtotal = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    tax_total = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    total = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    voucher = models.ForeignKey("ledger.Voucher", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], condition=Q(number__isnull=False), name="uniq_dn_number"),
        ]

    def __str__(self):
        return self.number or f"Draft debit note #{self.pk}"


class DebitNoteLine(ItemLineMixin):
    note = models.ForeignKey(DebitNote, on_delete=models.CASCADE, related_name="lines")
    grn_line = models.ForeignKey(GrnLine, on_delete=models.PROTECT, null=True, blank=True, related_name="debit_lines")
    location = models.ForeignKey("core.Location", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                                 help_text="Return notes: where the goods are taken from")
    roll = models.ForeignKey("inventory.FabricRoll", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    qty = models.DecimalField(max_digits=14, decimal_places=3)
    rate = models.DecimalField(max_digits=14, decimal_places=4)
    amount = models.DecimalField(max_digits=16, decimal_places=2)

    history = HistoricalRecords()

    class Meta:
        constraints = [one_item_constraint("dn_line_one_item"), models.CheckConstraint(condition=Q(qty__gt=0), name="dn_qty_positive")]
