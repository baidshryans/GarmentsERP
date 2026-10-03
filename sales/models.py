from decimal import Decimal

from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from core.scoping import FactoryScopedModel

ZERO = Decimal("0.00")
QZERO = Decimal("0.000")


class SaleSetting(models.Model):
    """Company-wide sales switches (E4.3, E4.4, E4.5). One row per company."""

    class Rounding(models.TextChoices):
        NONE = "none", "No rounding"
        RUPEE = "rupee", "Round invoice total to the nearest rupee"

    company = models.OneToOneField("core.Company", on_delete=models.CASCADE, related_name="sale_setting")
    rounding = models.CharField(max_length=5, choices=Rounding.choices, default=Rounding.RUPEE)
    max_discount_pct = models.DecimalField("Discount limit %", max_digits=5, decimal_places=2, default=Decimal("10.00"),
                                           help_text="Above this a user needs the 'Discount above the limit' permission")
    einvoice_enabled = models.BooleanField("E-invoicing switched on", default=False,
                                           help_text="Shows the e-invoice and e-way bill buttons on invoices (needs GST registration)")
    eway_threshold = models.DecimalField("E-way bill above", max_digits=12, decimal_places=2, default=Decimal("50000.00"))

    history = HistoricalRecords()

    def __str__(self):
        return f"Sales settings of {self.company}"


# ---------------------------------------------------------------- sale order (E4.1, E4.7)

class SaleOrder(FactoryScopedModel):
    class Type(models.TextChoices):
        STOCK = "stock", "Ready stock"
        MTO = "mto", "Made to order"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONFIRMED = "confirmed", "Confirmed"
        PARTLY = "partly_dispatched", "Partly dispatched"
        DISPATCHED = "dispatched", "Fully invoiced"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=50, null=True, blank=True)
    customer = models.ForeignKey("masters.Party", on_delete=models.PROTECT, related_name="sale_orders")
    order_type = models.CharField(max_length=5, choices=Type.choices, default=Type.STOCK)
    date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=18, choices=Status.choices, default=Status.DRAFT)
    remarks = models.CharField(max_length=255, blank=True)
    production_order = models.ForeignKey("production.ProductionOrder", on_delete=models.PROTECT, null=True, blank=True,
                                         related_name="+", help_text="MTO: the production requirement raised for this order")
    close_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], condition=Q(number__isnull=False), name="uniq_saleorder_number"),
        ]

    def __str__(self):
        return self.number or f"Draft order #{self.pk}"

    @property
    def total_qty(self):
        return sum((l.qty for l in self.lines.all()), QZERO)

    @property
    def total(self):
        return sum((l.amount for l in self.lines.all()), ZERO)

    @property
    def balance_qty(self):
        return sum((l.balance for l in self.lines.all()), QZERO)


class SaleOrderLine(models.Model):
    order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="lines")
    sku = models.ForeignKey("masters.SKU", on_delete=models.PROTECT, related_name="+")
    qty = models.DecimalField(max_digits=14, decimal_places=3)
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)
    qty_packed = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO,
                                     help_text="On packing lists that are not cancelled")
    qty_invoiced = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO)

    history = HistoricalRecords()

    class Meta:
        ordering = ["sku__style__style_no", "sku__colour__name", "sku__size__sort_order"]
        constraints = [
            models.CheckConstraint(condition=Q(qty__gt=0), name="saleorder_qty_positive"),
            models.CheckConstraint(condition=Q(rate__gte=0), name="saleorder_rate_non_negative"),
            models.CheckConstraint(condition=Q(discount_pct__gte=0, discount_pct__lte=100), name="saleorder_disc_range"),
            models.UniqueConstraint(fields=["order", "sku"], name="uniq_saleorder_sku"),
        ]

    @property
    def amount(self):
        return (self.qty * self.rate * (Decimal("100") - self.discount_pct) / 100).quantize(Decimal("0.01"))

    @property
    def balance(self):
        """Still to be invoiced."""
        return self.qty - self.qty_invoiced

    @property
    def to_pack(self):
        """Still to be packed."""
        return self.qty - self.qty_packed


# ---------------------------------------------------------------- packing list and cartons (E4.6)

class PackingList(FactoryScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PACKED = "packed", "Packed"
        INVOICED = "invoiced", "Invoiced"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=50, null=True, blank=True)
    order = models.ForeignKey(SaleOrder, on_delete=models.PROTECT, related_name="packing_lists")
    location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+",
                                 help_text="Where the goods are packed from")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    transporter = models.ForeignKey("masters.Party", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    lr_no = models.CharField("LR / docket no", max_length=40, blank=True)
    lr_date = models.DateField(null=True, blank=True)
    vehicle_no = models.CharField(max_length=20, blank=True)
    remarks = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], condition=Q(number__isnull=False), name="uniq_packing_number"),
        ]

    def __str__(self):
        return self.number or f"Draft packing list #{self.pk}"

    @property
    def total_qty(self):
        return sum((l.qty for c in self.cartons.all() for l in c.lines.all()), QZERO)


class Carton(models.Model):
    packing = models.ForeignKey(PackingList, on_delete=models.CASCADE, related_name="cartons")
    carton_no = models.PositiveSmallIntegerField()
    code = models.CharField(max_length=40, unique=True, help_text="Printed on the carton label and scanned at billing")

    history = HistoricalRecords()

    class Meta:
        ordering = ["packing", "carton_no"]
        constraints = [models.UniqueConstraint(fields=["packing", "carton_no"], name="uniq_carton_no")]

    def __str__(self):
        return self.code

    @property
    def total_qty(self):
        return sum((l.qty for l in self.lines.all()), QZERO)


class CartonLine(models.Model):
    carton = models.ForeignKey(Carton, on_delete=models.CASCADE, related_name="lines")
    sku = models.ForeignKey("masters.SKU", on_delete=models.PROTECT, related_name="+")
    qty = models.DecimalField(max_digits=14, decimal_places=3)

    history = HistoricalRecords()

    class Meta:
        ordering = ["sku__style__style_no", "sku__colour__name", "sku__size__sort_order"]
        constraints = [
            models.CheckConstraint(condition=Q(qty__gt=0), name="cartonline_qty_positive"),
            models.UniqueConstraint(fields=["carton", "sku"], name="uniq_carton_sku"),
        ]


# ---------------------------------------------------------------- sale invoice (E4.2-E4.5)

class SaleInvoice(FactoryScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    class TaxMode(models.TextChoices):
        AUTO = "auto", "GST from the HSN slab"
        TEMPLATE = "template", "One GST template for the invoice"
        NONE = "none", "No GST on this invoice"

    class EInvoice(models.TextChoices):
        NONE = "none", "Not sent"
        GENERATED = "generated", "Generated"
        FAILED = "failed", "Failed"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=50, null=True, blank=True)
    customer = models.ForeignKey("masters.Party", on_delete=models.PROTECT, related_name="sale_invoices")
    order = models.ForeignKey(SaleOrder, on_delete=models.PROTECT, null=True, blank=True, related_name="invoices")
    packing = models.ForeignKey(PackingList, on_delete=models.PROTECT, null=True, blank=True, related_name="invoices")
    location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+",
                                 help_text="Where the goods leave from")
    date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    place_of_supply = models.CharField(max_length=2, blank=True, help_text="State code; decides CGST + SGST or IGST")
    tax_mode = models.CharField(max_length=10, choices=TaxMode.choices, default=TaxMode.NONE)
    gst_template = models.ForeignKey("tax.TaxTemplate", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    tax_note = models.CharField(max_length=255, blank=True,
                                help_text="Why GST was waived or changed from the suggestion (logged, E4.4)")
    suggested_tax = models.CharField(max_length=120, blank=True, help_text="What the system suggested, kept for the log")
    subtotal = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO, help_text="After discount, before GST")
    discount_total = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    gst_total = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    round_off = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO)
    total = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    cogs_total = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    voucher = models.ForeignKey("ledger.Voucher", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    transporter = models.ForeignKey("masters.Party", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    lr_no = models.CharField("LR / docket no", max_length=40, blank=True)
    vehicle_no = models.CharField(max_length=20, blank=True)
    # e-invoice and e-way bill (E4.5); filled by the provider behind sales.services.einvoice
    einvoice_status = models.CharField(max_length=10, choices=EInvoice.choices, default=EInvoice.NONE)
    irn = models.CharField("IRN", max_length=64, blank=True)
    ack_no = models.CharField(max_length=30, blank=True)
    ack_date = models.DateTimeField(null=True, blank=True)
    qr_text = models.TextField(blank=True)
    einvoice_error = models.CharField(max_length=500, blank=True)
    eway_bill_no = models.CharField("E-way bill no", max_length=20, blank=True)
    eway_valid_until = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], condition=Q(number__isnull=False), name="uniq_saleinvoice_number"),
        ]

    def __str__(self):
        return self.number or f"Draft sale invoice #{self.pk}"


class SaleInvoiceLine(models.Model):
    invoice = models.ForeignKey(SaleInvoice, on_delete=models.CASCADE, related_name="lines")
    sku = models.ForeignKey("masters.SKU", on_delete=models.PROTECT, related_name="+")
    order_line = models.ForeignKey(SaleOrderLine, on_delete=models.PROTECT, null=True, blank=True, related_name="invoice_lines")
    qty = models.DecimalField(max_digits=14, decimal_places=3)
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)
    amount = models.DecimalField(max_digits=16, decimal_places=2, help_text="qty x rate less discount")
    hsn = models.CharField(max_length=8, blank=True)
    gst_template = models.ForeignKey("tax.TaxTemplate", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)
    tax_amount = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    cost_value = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO, help_text="Stock value that left, set at posting")
    qty_returned = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO, help_text="On posted credit notes")

    history = HistoricalRecords()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(qty__gt=0), name="saleinv_qty_positive"),
            models.CheckConstraint(condition=Q(rate__gte=0), name="saleinv_rate_non_negative"),
            models.CheckConstraint(condition=Q(discount_pct__gte=0, discount_pct__lte=100), name="saleinv_disc_range"),
        ]

    @property
    def returnable(self):
        return self.qty - self.qty_returned


class SaleInvoiceTax(models.Model):
    """GST per component and rate, totalled from the lines for printing and posting."""

    invoice = models.ForeignKey(SaleInvoice, on_delete=models.CASCADE, related_name="tax_lines")
    component = models.CharField(max_length=4)
    rate = models.DecimalField(max_digits=6, decimal_places=3, default=ZERO)
    taxable = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    amount = models.DecimalField(max_digits=16, decimal_places=2)

    history = HistoricalRecords()

    class Meta:
        ordering = ["rate", "component"]


class SaleInvoiceLineTax(models.Model):
    line = models.ForeignKey(SaleInvoiceLine, on_delete=models.CASCADE, related_name="taxes")
    component = models.CharField(max_length=4)
    rate = models.DecimalField(max_digits=6, decimal_places=3, default=ZERO)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    returned = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO, help_text="Reversed by posted credit notes")

    history = HistoricalRecords()


# ---------------------------------------------------------------- credit note (sales return)

class SaleCreditNote(FactoryScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=50, null=True, blank=True)
    customer = models.ForeignKey("masters.Party", on_delete=models.PROTECT, related_name="sale_credit_notes")
    invoice = models.ForeignKey(SaleInvoice, on_delete=models.PROTECT, related_name="credit_notes")
    location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+",
                                 help_text="Where the returned goods are taken back")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    reason = models.CharField(max_length=255)
    subtotal = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    gst_total = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    round_off = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO)
    total = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    voucher = models.ForeignKey("ledger.Voucher", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], condition=Q(number__isnull=False), name="uniq_salecn_number"),
        ]

    def __str__(self):
        return self.number or f"Draft credit note #{self.pk}"


class SaleCreditNoteLine(models.Model):
    note = models.ForeignKey(SaleCreditNote, on_delete=models.CASCADE, related_name="lines")
    invoice_line = models.ForeignKey(SaleInvoiceLine, on_delete=models.PROTECT, related_name="credit_lines")
    qty = models.DecimalField(max_digits=14, decimal_places=3)
    amount = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    cost_value = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)

    history = HistoricalRecords()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(qty__gt=0), name="salecn_qty_positive")]


class SaleCreditNoteLineTax(models.Model):
    line = models.ForeignKey(SaleCreditNoteLine, on_delete=models.CASCADE, related_name="taxes")
    source = models.ForeignKey(SaleInvoiceLineTax, on_delete=models.PROTECT, related_name="+")
    component = models.CharField(max_length=4)
    rate = models.DecimalField(max_digits=6, decimal_places=3, default=ZERO)
    amount = models.DecimalField(max_digits=16, decimal_places=2)

    history = HistoricalRecords()
