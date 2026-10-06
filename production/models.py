from decimal import Decimal

from django.db import models
from django.db.models import F, Q
from simple_history.models import HistoricalRecords

from core.scoping import FactoryScopedModel

ZERO = Decimal("0.00")


class ProductionOrder(FactoryScopedModel):
    """An instruction to make goods, for stock or against a sale order (E7.1). The customer is never stored
    here, so production roles cannot see who an MTO order is for (BR-15); only a reference is kept."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        RELEASED = "released", "Released"
        IN_PRODUCTION = "in_production", "In production"
        PARTLY = "partly_completed", "Partly completed"
        COMPLETED = "completed", "Completed"
        CLOSED = "closed", "Closed"

    class Purpose(models.TextChoices):
        STOCK = "stock", "For stock"
        MTO = "mto", "Made to order"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=50, null=True, blank=True)
    date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    purpose = models.CharField(max_length=5, choices=Purpose.choices, default=Purpose.STOCK)
    order_reference = models.CharField(max_length=60, blank=True, help_text="MTO sale order number, never the customer")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    remarks = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    released_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(max_length=255, blank=True)
    closed_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, blank=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], condition=Q(number__isnull=False), name="uniq_prod_order_number"),
        ]

    def __str__(self):
        return self.number or f"Draft order #{self.pk}"

    @property
    def total_qty(self):
        return sum(l.total_qty for l in self.lines.all())


class ProductionOrderLine(models.Model):
    order = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name="lines")
    style = models.ForeignKey("masters.Style", on_delete=models.PROTECT, related_name="+")
    colour = models.ForeignKey("masters.Colour", on_delete=models.PROTECT, related_name="+")
    total_qty = models.PositiveIntegerField()
    bom_version = models.ForeignKey("masters.BomVersion", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    route = models.ForeignKey("masters.RouteTemplate", on_delete=models.PROTECT, null=True, blank=True, related_name="+")

    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(total_qty__gt=0), name="order_line_qty_positive"),
            models.UniqueConstraint(fields=["order", "style", "colour"], name="uniq_order_line_style_colour"),
        ]


class ProductionOrderLineSize(models.Model):
    """The size ratio entered once; qty is the line's total spread across the sizes (E7.1)."""

    line = models.ForeignKey(ProductionOrderLine, on_delete=models.CASCADE, related_name="sizes")
    size = models.ForeignKey("masters.Size", on_delete=models.PROTECT, related_name="+")
    ratio = models.PositiveSmallIntegerField()
    qty = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["line", "size"], name="uniq_order_line_size")]


class Lot(FactoryScopedModel):
    """One cutting of one style and colour (PRD section 4). The factory is where it is cut and costed first."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        CUTTING = "cutting", "Cutting"
        IN_PRODUCTION = "in_production", "In production"
        COMPLETED = "completed", "Completed"
        CLOSED = "closed", "Closed"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    lot_no = models.CharField(max_length=30)
    order_line = models.OneToOneField(ProductionOrderLine, on_delete=models.PROTECT, related_name="lot")
    style = models.ForeignKey("masters.Style", on_delete=models.PROTECT, related_name="lots")
    colour = models.ForeignKey("masters.Colour", on_delete=models.PROTECT, related_name="+")
    bom_version = models.ForeignKey("masters.BomVersion", on_delete=models.PROTECT, null=True, blank=True, related_name="lots")
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.PLANNED)
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["company", "lot_no"], name="uniq_lot_no")]

    def __str__(self):
        return self.lot_no

    @property
    def order(self):
        return self.order_line.order


class LotStep(models.Model):
    """One process on a lot's route, assigned at run time to a factory or a fabricator (PRD principle 3, E7.2)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"
        SKIPPED = "skipped", "Skipped"

    class Assignment(models.TextChoices):
        IN_HOUSE = "in_house", "In-house"
        SUBCONTRACT = "subcontract", "Subcontractor"

    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="steps")
    sequence = models.PositiveSmallIntegerField()
    process = models.ForeignKey("masters.Process", on_delete=models.PROTECT, related_name="+")
    is_mandatory = models.BooleanField(default=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    assignment = models.CharField(max_length=12, choices=Assignment.choices, default=Assignment.IN_HOUSE)
    factory = models.ForeignKey("core.Factory", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    party = models.ForeignKey("masters.Party", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    rate = models.DecimalField("Rate per piece", max_digits=10, decimal_places=2, default=ZERO)
    rework_rate = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    started_at = models.DateTimeField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["lot", "sequence"]
        constraints = [models.UniqueConstraint(fields=["lot", "sequence"], name="uniq_lot_step_sequence")]

    def __str__(self):
        return f"{self.lot} #{self.sequence} {self.process}"


class LotRouteChange(models.Model):
    """Every change to a running route, with who and why (E7.3)."""

    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="route_changes")
    action = models.CharField(max_length=20)
    detail = models.CharField(max_length=255)
    reason = models.CharField(max_length=255)
    user = models.ForeignKey("core.User", on_delete=models.PROTECT, related_name="+")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at", "-id"]


# ---------------------------------------------------------------- fabric and cutting (E7.4)

class FabricIssue(FactoryScopedModel):
    """Fabric issued from the store to the cutting floor for a lot, roll by roll."""

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, related_name="fabric_issues")
    from_location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+")
    to_location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+")
    date = models.DateField()
    mixed_shades = models.BooleanField(default=False, help_text="Rolls of different shade lots went into one lot")
    expected_pieces = models.PositiveIntegerField(null=True, blank=True, help_text="Pieces the BOM says this fabric should give")
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()


class FabricIssueLine(models.Model):
    issue = models.ForeignKey(FabricIssue, on_delete=models.CASCADE, related_name="lines")
    roll = models.ForeignKey("inventory.FabricRoll", on_delete=models.PROTECT, related_name="+")
    qty = models.DecimalField(max_digits=14, decimal_places=3)
    value = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(qty__gt=0), name="fabric_issue_qty_positive")]


class CuttingEntry(FactoryScopedModel):
    """A lay: pieces cut per size, fabric used, waste, remnant returned (E7.4)."""

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, related_name="cuttings")
    lay_no = models.PositiveSmallIntegerField()
    date = models.DateField()
    notes = models.CharField(max_length=255, blank=True)
    fabric_value = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    expected_fabric = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True,
                                          help_text="What the BOM says these pieces should use")
    expected_pieces = models.PositiveIntegerField(null=True, blank=True, help_text="Pieces the BOM says the fabric burnt should give")
    variance_pct = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    over_tolerance = models.BooleanField(default=False)
    bundled = models.BooleanField(default=False, help_text="Bundles and QR tags have been made from this lay")
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["lot", "lay_no"], name="uniq_cutting_lay")]


class CuttingSize(models.Model):
    entry = models.ForeignKey(CuttingEntry, on_delete=models.CASCADE, related_name="sizes")
    size = models.ForeignKey("masters.Size", on_delete=models.PROTECT, related_name="+")
    pieces = models.PositiveIntegerField()
    loss = models.PositiveIntegerField(default=0, help_text="Pieces cut but lost or spoiled before bundling")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entry", "size"], name="uniq_cutting_size"),
            models.CheckConstraint(condition=Q(loss__lte=F("pieces")), name="cutting_loss_within_pieces"),
        ]

    @property
    def good(self):
        return self.pieces - self.loss


class CuttingRollUse(models.Model):
    entry = models.ForeignKey(CuttingEntry, on_delete=models.CASCADE, related_name="rolls")
    roll = models.ForeignKey("inventory.FabricRoll", on_delete=models.PROTECT, related_name="+")
    used_qty = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0.000"))
    waste_qty = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0.000"))
    remnant_qty = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0.000"))
    value = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)


# ---------------------------------------------------------------- bundles (E7.5, E7.6)

class Bundle(models.Model):
    class Status(models.TextChoices):
        CUT = "cut", "Cut"
        AT_STAGE = "at_stage", "At stage"
        DONE = "done_by_fabricator", "Done by fabricator"
        RECEIVED = "received", "Received, awaiting QC"
        REWORK = "rework", "Awaiting rework"
        READY = "ready", "Ready for next stage"
        PACKED = "packed", "Packed"
        DISPATCHED = "dispatched", "Dispatched"
        SCRAPPED = "scrapped", "Written off"

    LIVE = ("cut", "at_stage", "done_by_fabricator", "received", "rework", "ready")

    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, related_name="bundles")
    entry = models.ForeignKey(CuttingEntry, on_delete=models.PROTECT, null=True, blank=True, related_name="bundles")
    bundle_no = models.CharField(max_length=40)
    sku = models.ForeignKey("masters.SKU", on_delete=models.PROTECT, related_name="bundles")
    qty = models.PositiveIntegerField(help_text="Pieces now in the bundle")
    original_qty = models.PositiveIntegerField()
    qr_token = models.CharField(max_length=40, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CUT)
    location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+")
    current_step = models.ForeignKey(LotStep, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    completed_seq = models.PositiveSmallIntegerField(default=0, help_text="Highest route step finished")
    rework_qty = models.PositiveIntegerField(default=0, help_text="Pieces QC sent back to the fabricator")
    is_rework = models.BooleanField(default=False, help_text="Moved back to an earlier stage; shown separately in WIP")
    split_from = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="splits",
                                   help_text="The bundle these pieces were taken out of (rework sent back at QC)")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["lot", "bundle_no"]
        constraints = [
            models.UniqueConstraint(fields=["lot", "bundle_no"], name="uniq_bundle_no_in_lot"),
            models.CheckConstraint(condition=Q(rework_qty__lte=F("qty")), name="bundle_rework_within_qty"),
        ]

    def __str__(self):
        return self.bundle_no

    @property
    def is_live(self):
        return self.status in self.LIVE


class StageMovement(FactoryScopedModel):
    """Any move or count of a bundle between stages or places. Quantities must balance (BR-21):
    qty_out + qty_extra = qty_in + loss + rejection + shortage. Moving to an earlier stage needs a reason (BR-22)."""

    class Kind(models.TextChoices):
        MOVE = "move", "Moved to stage"
        ISSUE = "issue", "Issued to fabricator"
        RECEIPT = "receipt", "Received from fabricator"
        QC = "qc", "QC result"
        PACK = "pack", "Packed"
        FACTORY = "factory", "Moved to another factory"
        WRITE_OFF = "write_off", "Written off"

    bundle = models.ForeignKey(Bundle, on_delete=models.PROTECT, related_name="movements")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    from_step = models.ForeignKey(LotStep, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    to_step = models.ForeignKey(LotStep, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    from_location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+")
    to_location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+")
    qty_out = models.PositiveIntegerField()
    qty_extra = models.PositiveIntegerField(default=0, help_text="Over-receipt that was approved")
    qty_in = models.PositiveIntegerField()
    loss = models.PositiveIntegerField(default=0)
    rejection = models.PositiveIntegerField(default=0)
    shortage = models.PositiveIntegerField(default=0)
    reason = models.CharField(max_length=255, blank=True)
    is_rework = models.BooleanField(default=False)
    challan = models.ForeignKey("jobwork.JobWorkChallan", on_delete=models.PROTECT, null=True, blank=True, related_name="movements")
    user = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(qty_in=F("qty_out") + F("qty_extra") - F("loss") - F("rejection") - F("shortage")),
                name="stage_move_balances_br21",
            ),
        ]


class PackEntry(FactoryScopedModel):
    """One packing of a lot's bundles into finished goods, with the boxes the pieces filled. A box is a count and
    a label: stock stays in pieces."""

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")
    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, related_name="pack_entries")
    date = models.DateField()
    location = models.ForeignKey("core.Location", on_delete=models.PROTECT, related_name="+")
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"{self.lot} packed {self.date}"

    @property
    def boxes(self):
        return sum(l.boxes for l in self.lines.all())


class PackEntryLine(models.Model):
    entry = models.ForeignKey(PackEntry, on_delete=models.CASCADE, related_name="lines")
    sku = models.ForeignKey("masters.SKU", on_delete=models.PROTECT, related_name="+")
    pieces = models.PositiveIntegerField()
    pieces_per_box = models.PositiveSmallIntegerField(help_text="The setting when these pieces were packed")
    full_boxes = models.PositiveIntegerField(default=0)
    short_box_qty = models.PositiveIntegerField(default=0, help_text="Pieces in the last, part-filled box")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entry", "sku"], name="uniq_pack_entry_sku"),
            models.CheckConstraint(condition=Q(pieces_per_box__gt=0) & Q(short_box_qty__lt=F("pieces_per_box"))
                                   & Q(pieces=F("full_boxes") * F("pieces_per_box") + F("short_box_qty")),
                                   name="pack_boxes_add_up"),
        ]

    @property
    def boxes(self):
        return self.full_boxes + (1 if self.short_box_qty else 0)


class LotCostEntry(models.Model):
    """Money on a lot: what it has cost so far, and where that cost sits (E7.11). Signed amounts."""

    class Kind(models.TextChoices):
        FABRIC = "fabric", "Fabric"
        TRIM = "trim", "Trims"
        LABOUR = "labour", "In-house labour"
        JOBWORK = "jobwork", "Job work"
        CHARGE = "charge", "Value-add charges"
        TRANSFER = "transfer", "Moved between factories"
        RELIEF = "relief", "Transferred to finished goods"
        WRITE_OFF = "write_off", "Written off"

    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, related_name="cost_entries")
    factory = models.ForeignKey("core.Factory", on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    date = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    source_type = models.CharField(max_length=60, blank=True)
    source_id = models.PositiveIntegerField(null=True, blank=True)
    voucher = models.ForeignKey("ledger.Voucher", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["lot", "id"]
