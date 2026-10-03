from decimal import Decimal

from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from core.scoping import FactoryScopedModel, FactoryScopedQuerySet

from .exceptions import MovementImmutable

ZERO = Decimal("0.00")
QZERO = Decimal("0.000")


class FabricRoll(models.Model):
    """One roll or dye lot of fabric (INV-03, PUR-02, PUR-03). Quantities live in RollBalance."""

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="rolls")
    material = models.ForeignKey("masters.Material", on_delete=models.PROTECT, related_name="rolls")
    label_code = models.CharField(max_length=20, unique=True, help_text="Printed on the roll label and scanned")
    vendor_roll_no = models.CharField(max_length=40, blank=True)
    supplier = models.ForeignKey("masters.Party", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    lot_no = models.CharField("Lot / shade", max_length=40, blank=True)
    gsm = models.PositiveSmallIntegerField(null=True, blank=True)
    width_cm = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    received_qty = models.DecimalField("Received (primary unit)", max_digits=14, decimal_places=3)
    received_length_m = models.DecimalField("Received (metres)", max_digits=14, decimal_places=3, null=True, blank=True)
    rate = models.DecimalField(max_digits=14, decimal_places=4, default=ZERO, help_text="Rate when received, for reference")
    received_date = models.DateField()
    source_type = models.CharField(max_length=60, blank=True)
    source_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-received_date", "label_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "vendor_roll_no"], condition=Q(supplier__isnull=False) & ~Q(vendor_roll_no=""),
                name="uniq_supplier_roll_no",
            ),
        ]

    def __str__(self):
        return f"{self.label_code} ({self.material.name})"


class RollBalanceQuerySet(FactoryScopedQuerySet):
    factory_lookup = "location__factory"


class StockBalance(models.Model):
    """Quantity and value of one item at one location. Rebuilt-able from StockMovement (they must agree)."""

    factory = models.ForeignKey("core.Factory", on_delete=models.PROTECT, related_name="+")
    location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+")
    material = models.ForeignKey("masters.Material", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    sku = models.ForeignKey("masters.SKU", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    qty = models.DecimalField(max_digits=16, decimal_places=3, default=QZERO)
    value = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)

    objects = FactoryScopedQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["location", "material"], condition=Q(material__isnull=False), name="uniq_balance_material"),
            models.UniqueConstraint(fields=["location", "sku"], condition=Q(sku__isnull=False), name="uniq_balance_sku"),
            models.CheckConstraint(
                condition=(Q(material__isnull=False, sku__isnull=True) | Q(material__isnull=True, sku__isnull=False)),
                name="balance_one_item",
            ),
        ]

    @property
    def item(self):
        return self.material or self.sku


class RollBalance(models.Model):
    """Quantity and value of one roll at one location (BR-02: an issue cannot exceed the roll's balance)."""

    roll = models.ForeignKey(FabricRoll, on_delete=models.PROTECT, related_name="balances")
    location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+")
    qty = models.DecimalField(max_digits=16, decimal_places=3, default=QZERO)
    value = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)

    objects = RollBalanceQuerySet.as_manager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["roll", "location"], name="uniq_roll_balance")]


class MovementQuerySet(FactoryScopedQuerySet):
    """The movement ledger is append-only. Corrections are new, opposite movements."""

    def update(self, **kwargs):
        raise MovementImmutable("Stock movements cannot be changed; post an opposite movement.")

    def delete(self):
        raise MovementImmutable("Stock movements cannot be deleted; post an opposite movement.")


class StockMovement(FactoryScopedModel):
    """Every quantity or value change of stock, anywhere (PRD 10.2 item 4)."""

    class Type(models.TextChoices):
        OPENING = "opening", "Opening stock"
        RECEIPT = "receipt", "Receipt"
        ISSUE = "issue", "Issue"
        TRANSFER_OUT = "transfer_out", "Transfer out"
        TRANSFER_IN = "transfer_in", "Transfer in"
        RETURN_OUT = "return_out", "Return to vendor"
        REVALUATION = "revaluation", "Value adjustment"
        ADJUSTMENT = "adjustment", "Adjustment"
        REVERSAL = "reversal", "Reversal"
        PRODUCTION = "production", "Production output"
        LOSS = "loss", "Loss / write-off"

    location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+")
    material = models.ForeignKey("masters.Material", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    sku = models.ForeignKey("masters.SKU", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    roll = models.ForeignKey(FabricRoll, on_delete=models.PROTECT, null=True, blank=True, related_name="movements")
    bundle = models.ForeignKey("production.Bundle", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    lot = models.ForeignKey("production.Lot", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    movement_type = models.CharField(max_length=14, choices=Type.choices)
    qty = models.DecimalField(max_digits=16, decimal_places=3, help_text="Signed: positive in, negative out")
    value = models.DecimalField(max_digits=18, decimal_places=2, help_text="Signed like qty")
    date = models.DateField()
    source_type = models.CharField(max_length=60, blank=True)
    source_id = models.PositiveIntegerField(null=True, blank=True)
    voucher = models.ForeignKey("ledger.Voucher", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = MovementQuerySet.as_manager()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(material__isnull=False, sku__isnull=True) | Q(material__isnull=True, sku__isnull=False)),
                name="movement_one_item",
            ),
            models.CheckConstraint(
                condition=~Q(qty=0) | Q(movement_type="revaluation"), name="movement_nonzero_qty_unless_revaluation"
            ),
        ]
        indexes = [models.Index(fields=["source_type", "source_id"])]

    @property
    def item(self):
        return self.material or self.sku

    def save(self, *args, **kwargs):
        if self.pk:
            raise MovementImmutable("Stock movements cannot be changed; post an opposite movement.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise MovementImmutable("Stock movements cannot be deleted; post an opposite movement.")


class ReorderLevel(models.Model):
    """Min / reorder / max for an item, optionally per factory (INV-06). StockAlert records each crossing below the minimum (E6.3)."""

    factory = models.ForeignKey("core.Factory", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    material = models.ForeignKey("masters.Material", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    style = models.ForeignKey("masters.Style", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    min_qty = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO)
    reorder_qty = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO)
    max_qty = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO)

    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(material__isnull=False, style__isnull=True) | Q(material__isnull=True, style__isnull=False)),
                name="reorder_one_item",
            ),
        ]


class StockAlert(models.Model):
    """Stock fell below an item's minimum (E6.3). One alert per crossing: it stays open until stock is back at or
    above the minimum, and only then can the item raise a new one. factory null = the combined stock of all factories."""

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    factory = models.ForeignKey("core.Factory", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    material = models.ForeignKey("masters.Material", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    style = models.ForeignKey("masters.Style", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    min_qty = models.DecimalField(max_digits=14, decimal_places=3, help_text="The minimum when the alert was raised")
    reorder_qty = models.DecimalField(max_digits=14, decimal_places=3, default=QZERO)
    qty_at_alert = models.DecimalField(max_digits=16, decimal_places=3)
    raised_at = models.DateTimeField(auto_now_add=True)
    cleared_at = models.DateTimeField(null=True, blank=True, help_text="Stock recovered to the minimum")
    acknowledged_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-raised_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(material__isnull=False, style__isnull=True) | Q(material__isnull=True, style__isnull=False)),
                name="stockalert_one_item",
            ),
        ]

    @property
    def item(self):
        return self.material or self.style

    @property
    def is_open(self):
        return self.cleared_at is None

    @classmethod
    def visible_to(cls, user):
        """Alerts of the user's factories; the combined-stock ones go to users who may see every factory."""
        if not user.is_authenticated:
            return cls.objects.none()
        ids = user.allowed_factory_ids()
        if ids is None:
            return cls.objects.all()
        return cls.objects.filter(factory_id__in=ids)


class StockTransfer(models.Model):
    """Move stock between locations or factories (E6.2). Between factories stock and value move when issued,
    into the destination's In Transit location, and into the final location when received."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued / in transit"
        RECEIVED = "received", "Received"

    class Document(models.TextChoices):
        CHALLAN = "challan", "Delivery challan"
        TAX_INVOICE = "tax_invoice", "Tax invoice"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=50, null=True, blank=True)
    from_factory = models.ForeignKey("core.Factory", on_delete=models.PROTECT, related_name="transfers_out")
    from_location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+")
    to_factory = models.ForeignKey("core.Factory", on_delete=models.PROTECT, related_name="transfers_in")
    to_location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    document_type = models.CharField(max_length=12, choices=Document.choices, default=Document.CHALLAN)
    vehicle_no = models.CharField(max_length=20, blank=True)
    eway_bill_no = models.CharField("E-way bill no.", max_length=20, blank=True)
    remarks = models.CharField(max_length=255, blank=True)
    voucher = models.ForeignKey("ledger.Voucher", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    issued_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], condition=Q(number__isnull=False), name="uniq_transfer_number"),
        ]

    def __str__(self):
        return self.number or f"Draft transfer #{self.pk}"

    @property
    def is_inter_factory(self):
        return self.from_factory_id != self.to_factory_id

    @classmethod
    def visible_to(cls, user):
        if not user.is_authenticated:
            return cls.objects.none()
        ids = user.allowed_factory_ids()
        if ids is None:
            return cls.objects.all()
        return cls.objects.filter(Q(from_factory_id__in=ids) | Q(to_factory_id__in=ids))


class StockTransferLine(models.Model):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name="lines")
    material = models.ForeignKey("masters.Material", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    sku = models.ForeignKey("masters.SKU", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    roll = models.ForeignKey(FabricRoll, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    qty = models.DecimalField(max_digits=16, decimal_places=3)
    value = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO, help_text="Set when issued")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(material__isnull=False, sku__isnull=True) | Q(material__isnull=True, sku__isnull=False)),
                name="transfer_line_one_item",
            ),
            models.CheckConstraint(condition=Q(qty__gt=0), name="transfer_line_qty_positive"),
        ]

    @property
    def item(self):
        return self.material or self.sku


class OpeningStock(models.Model):
    """An opening stock document: stock brought in at go-live with its value (INV, PRD E5/E6)."""

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    factory = models.ForeignKey("core.Factory", on_delete=models.PROTECT, related_name="+")
    location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=50, unique=True)
    date = models.DateField()
    voucher = models.ForeignKey("ledger.Voucher", on_delete=models.PROTECT, related_name="+")
    total_value = models.DecimalField(max_digits=18, decimal_places=2)
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
