from decimal import Decimal

from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from core.constants import INDIAN_STATES
from core.validators import validate_gstin, validate_pan

ZERO = Decimal("0.00")


# ---------------------------------------------------------------- basic lists

class Unit(models.Model):
    class Kind(models.TextChoices):
        COUNT = "count", "Count"
        WEIGHT = "weight", "Weight"
        LENGTH = "length", "Length"

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50)
    kind = models.CharField(max_length=6, choices=Kind.choices, default=Kind.COUNT)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class UnitConversion(models.Model):
    """1 from_unit = factor to_unit (PUR-04), for example 1 GRS = 144 PCS."""

    from_unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="+")
    to_unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="+")
    factor = models.DecimalField(max_digits=18, decimal_places=6)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["from_unit", "to_unit"], name="uniq_unit_conversion"),
            models.CheckConstraint(condition=Q(factor__gt=0), name="unit_factor_positive"),
        ]

    def __str__(self):
        return f"1 {self.from_unit} = {self.factor.normalize()} {self.to_unit}"


class Size(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=30)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["sort_order", "code"]

    def __str__(self):
        return self.code


class Colour(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=10, blank=True)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    """Internal product codes (MST-01): TRK, JGR, TSH, SET."""

    code = models.CharField(max_length=5, unique=True)
    name = models.CharField(max_length=60)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Material(models.Model):
    """Fabric, trims and packing material (MST-03, MST-05)."""

    class Kind(models.TextChoices):
        FABRIC = "fabric", "Fabric"
        TRIM = "trim", "Trim / accessory"
        PACKING = "packing", "Packing material"

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="materials")
    composition = models.CharField(max_length=120, blank=True)
    gsm = models.PositiveSmallIntegerField(null=True, blank=True)
    width_cm = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


# ---------------------------------------------------------------- process and route

class Process(models.Model):
    class Kind(models.TextChoices):
        CUTTING = "cutting", "Cutting"
        STITCHING = "stitching", "Stitching"
        VALUE_ADD = "value_add", "Value-add (embroidery, printing, washing, dyeing)"
        FINISHING = "finishing", "Ironing and finishing"
        QC = "qc", "Quality check"
        PACKING = "packing", "Packing"

    code = models.CharField(max_length=15, unique=True)
    name = models.CharField(max_length=60)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    no_loss = models.BooleanField(
        "No loss allowed", default=False,
        help_text="Pieces out must equal pieces in when this is done in-house (e.g. ironing)")
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "processes"

    def __str__(self):
        return self.name


class RouteTemplate(models.Model):
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RouteStep(models.Model):
    """One process on a route (E2.3). Assignment is a default; each lot can change it later (E7.2)."""

    class Assignment(models.TextChoices):
        IN_HOUSE = "in_house", "In-house"
        SUBCONTRACT = "subcontract", "Subcontractor"

    template = models.ForeignKey(RouteTemplate, on_delete=models.CASCADE, related_name="steps")
    sequence = models.PositiveSmallIntegerField()
    process = models.ForeignKey(Process, on_delete=models.PROTECT, related_name="route_steps")
    is_mandatory = models.BooleanField(default=True)
    assignment = models.CharField(max_length=12, choices=Assignment.choices, default=Assignment.IN_HOUSE)
    default_factory = models.ForeignKey("core.Factory", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    default_party = models.ForeignKey("masters.Party", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    rate = models.DecimalField("Default rate per piece", max_digits=10, decimal_places=2, default=ZERO)

    history = HistoricalRecords()

    class Meta:
        ordering = ["template", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["template", "sequence"], name="uniq_route_sequence"),
            models.CheckConstraint(condition=Q(rate__gte=0), name="route_rate_non_negative"),
        ]

    def __str__(self):
        return f"{self.template} #{self.sequence} {self.process}"


# ---------------------------------------------------------------- styles and SKUs

class Style(models.Model):
    style_no = models.CharField(max_length=30, unique=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="styles")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    hsn = models.ForeignKey("tax.HSN", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    default_route = models.ForeignKey(RouteTemplate, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    mrp = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pieces_per_box = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Pieces packed in one box. Blank = the company's setting.")
    image = models.ImageField(upload_to="styles/original/", blank=True)
    thumbnail = models.ImageField(upload_to="styles/thumb/", blank=True, editable=False)
    is_archived = models.BooleanField(default=False, help_text="Discontinued; stays searchable with full history")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["style_no"]

    def __str__(self):
        return f"{self.style_no} - {self.name}"


class StyleColour(models.Model):
    style = models.ForeignKey(Style, on_delete=models.CASCADE, related_name="style_colours")
    colour = models.ForeignKey(Colour, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["style", "colour"], name="uniq_style_colour")]


class StyleSize(models.Model):
    style = models.ForeignKey(Style, on_delete=models.CASCADE, related_name="style_sizes")
    size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["style", "size"], name="uniq_style_size")]


class SKU(models.Model):
    """Style x colour x size. Stock, prices and barcodes all hang off this."""

    style = models.ForeignKey(Style, on_delete=models.PROTECT, related_name="skus")
    colour = models.ForeignKey(Colour, on_delete=models.PROTECT, related_name="skus")
    size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name="skus")
    barcode = models.CharField(max_length=20, unique=True)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["style__style_no", "colour__name", "size__sort_order"]
        constraints = [models.UniqueConstraint(fields=["style", "colour", "size"], name="uniq_sku_combo")]

    def __str__(self):
        return f"{self.style.style_no}/{self.colour}/{self.size}"


class CodeCounter(models.Model):
    """Counter table for barcodes and party codes (database-neutral; no row locks)."""

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT)
    key = models.CharField(max_length=30)
    next_number = models.PositiveIntegerField(default=1)
    padding = models.PositiveSmallIntegerField(default=10, help_text="Digit length of the generated code")
    prefix = models.CharField(max_length=5, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "key"], name="uniq_counter_key")]


# ---------------------------------------------------------------- BOM

class BomVersion(models.Model):
    """A style's bill of materials. Saving a change to a version that lots already use creates a new one."""

    style = models.ForeignKey(Style, on_delete=models.CASCADE, related_name="bom_versions")
    version_no = models.PositiveSmallIntegerField()
    is_current = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey("core.User", on_delete=models.PROTECT, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["style", "-version_no"]
        constraints = [
            models.UniqueConstraint(fields=["style", "version_no"], name="uniq_bom_version"),
            models.UniqueConstraint(fields=["style"], condition=Q(is_current=True), name="one_current_bom_per_style"),
        ]

    def __str__(self):
        return f"{self.style.style_no} BOM v{self.version_no}"


class BomLine(models.Model):
    version = models.ForeignKey(BomVersion, on_delete=models.CASCADE, related_name="lines")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="+")
    qty_per_piece = models.DecimalField(max_digits=12, decimal_places=4, help_text="In the material's unit")
    wastage_pct = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)

    class Meta:
        ordering = ["id"]
        constraints = [models.CheckConstraint(condition=Q(qty_per_piece__gt=0), name="bom_qty_positive")]


class BomLineSize(models.Model):
    """Size-specific consumption that overrides the line's default (E2.2: consumption per piece by size)."""

    line = models.ForeignKey(BomLine, on_delete=models.CASCADE, related_name="size_overrides")
    size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name="+")
    qty_per_piece = models.DecimalField(max_digits=12, decimal_places=4)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["line", "size"], name="uniq_bom_line_size"),
            models.CheckConstraint(condition=Q(qty_per_piece__gt=0), name="bom_size_qty_positive"),
        ]


class BomCharge(models.Model):
    """Fixed per-piece charge in the BOM: embroidery, printing, washing."""

    version = models.ForeignKey(BomVersion, on_delete=models.CASCADE, related_name="charges")
    description = models.CharField(max_length=80)
    process = models.ForeignKey(Process, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    amount_per_piece = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount_per_piece__gte=0), name="bom_charge_non_negative")]


# ---------------------------------------------------------------- price lists

class PriceList(models.Model):
    class Kind(models.TextChoices):
        MRP = "mrp", "MRP"
        WHOLESALE = "wholesale", "Wholesale"
        DISTRIBUTOR = "distributor", "Distributor"
        RETAIL = "retail", "Retail"
        SPECIAL = "special", "Customer-specific"

    name = models.CharField(max_length=80, unique=True)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.WHOLESALE)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PriceListRate(models.Model):
    """Rate per piece. Effective-dated and append-only: a change is a new row (PRC-06)."""

    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name="rates")
    style = models.ForeignKey(Style, on_delete=models.PROTECT, related_name="price_rates")
    size = models.ForeignKey(Size, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                             help_text="Blank = all sizes of the style")
    min_qty = models.PositiveIntegerField(default=1, help_text="Quantity slab: applies from this many pieces")
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    effective_from = models.DateField()

    history = HistoricalRecords()

    class Meta:
        ordering = ["price_list", "style", "min_qty", "-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["price_list", "style", "size", "min_qty", "effective_from"], name="uniq_price_rate_row"
            ),
            models.CheckConstraint(condition=Q(rate__gte=0), name="price_rate_non_negative"),
        ]


# ---------------------------------------------------------------- parties

class Party(models.Model):
    """Customer, vendor, fabricator, agent or transporter. One record can hold several roles."""

    class Category(models.TextChoices):
        WHOLESALER = "wholesaler", "Wholesaler"
        DISTRIBUTOR = "distributor", "Distributor"
        RETAILER = "retailer", "Retailer"
        ONLINE = "online", "Online seller"
        WALKIN = "walkin", "Walk-in"
        INSTITUTIONAL = "institutional", "Institutional"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="parties")
    code = models.CharField(max_length=20)
    name = models.CharField("Firm name", max_length=200)
    contact_person = models.CharField(max_length=100, blank=True)

    is_customer = models.BooleanField(default=False)
    is_vendor = models.BooleanField(default=False)
    is_fabricator = models.BooleanField(default=False)
    is_agent = models.BooleanField(default=False)
    is_transporter = models.BooleanField(default=False)

    mobile = models.CharField(max_length=10)
    mobile2 = models.CharField(max_length=10, blank=True)
    mobile3 = models.CharField(max_length=10, blank=True)
    landline = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    gstin = models.CharField("GSTIN", max_length=15, blank=True, validators=[validate_gstin])
    pan = models.CharField("PAN", max_length=10, blank=True, validators=[validate_pan])
    state_code = models.CharField("State", max_length=2, choices=INDIAN_STATES, blank=True)

    category = models.CharField(max_length=14, choices=Category.choices, blank=True)
    price_list = models.ForeignKey(PriceList, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    discount_pct = models.DecimalField("Discount %", max_digits=5, decimal_places=2, default=ZERO)
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    credit_days = models.PositiveSmallIntegerField(default=0)
    payment_terms = models.CharField(max_length=120, blank=True)
    agent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    transporter = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    destination = models.CharField(max_length=100, blank=True)
    tds_section = models.CharField(
        max_length=10, blank=True, help_text="A suggestion only; TDS is applied only when chosen on the bill"
    )

    customer_ledger = models.ForeignKey("ledger.Ledger", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    payable_ledger = models.ForeignKey("ledger.Ledger", on_delete=models.PROTECT, null=True, blank=True, related_name="+")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "parties"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uniq_party_code"),
            # One mobile maps to one customer, and to one fabricator (who logs in with it) - BR-06, CRM-08.
            models.UniqueConstraint(fields=["mobile"], condition=Q(is_customer=True), name="uniq_customer_mobile"),
            models.UniqueConstraint(fields=["mobile"], condition=Q(is_fabricator=True), name="uniq_fabricator_mobile"),
            models.CheckConstraint(
                condition=Q(is_customer=True) | Q(is_vendor=True) | Q(is_fabricator=True)
                | Q(is_agent=True) | Q(is_transporter=True),
                name="party_has_a_role",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def roles(self):
        flags = [("is_customer", "Customer"), ("is_vendor", "Vendor"), ("is_fabricator", "Fabricator"),
                 ("is_agent", "Agent"), ("is_transporter", "Transporter")]
        return [label for attr, label in flags if getattr(self, attr)]


class PartyAddress(models.Model):
    class Kind(models.TextChoices):
        BILLING = "billing", "Billing"
        SHIPPING = "shipping", "Shipping"

    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name="addresses")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    line1 = models.CharField(max_length=200)
    line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state_code = models.CharField(max_length=2, choices=INDIAN_STATES, blank=True)
    pincode = models.CharField(max_length=10, blank=True)

    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["party"], condition=Q(kind="billing"), name="one_billing_address"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.line1}"


class CustomerRate(models.Model):
    """Special rate for one customer, per style or per product category (PRC-03). Effective-dated."""

    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name="special_rates")
    style = models.ForeignKey(Style, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    effective_from = models.DateField()

    history = HistoricalRecords()

    class Meta:
        ordering = ["party", "-effective_from"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(style__isnull=False, product__isnull=True) | Q(style__isnull=True, product__isnull=False)),
                name="customer_rate_style_xor_product",
            ),
            models.CheckConstraint(condition=Q(rate__gte=0), name="customer_rate_non_negative"),
        ]
