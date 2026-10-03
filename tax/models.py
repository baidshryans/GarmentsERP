from django.db import models
from simple_history.models import HistoricalRecords

from core.validators import validate_gstin, validate_tan


class TaxSetting(models.Model):
    """GST / TDS switch with an effective date (E1.9, PRD 10.2). Append-only: a change is a new row.

    factory null means the company-wide setting; a factory row overrides it for that factory.
    GST and TDS are independent of each other.
    """

    class Kind(models.TextChoices):
        GST = "gst", "GST"
        TDS = "tds", "TDS"

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="tax_settings")
    factory = models.ForeignKey("core.Factory", on_delete=models.PROTECT, null=True, blank=True)
    kind = models.CharField(max_length=3, choices=Kind.choices)
    enabled = models.BooleanField()
    effective_from = models.DateField()
    registration_number = models.CharField(
        "GSTIN / TAN", max_length=15, blank=True,
        help_text="GSTIN when GST is on, TAN when TDS is on",
    )

    history = HistoricalRecords()

    class Meta:
        ordering = ["kind", "factory_id", "-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "factory", "kind", "effective_from"], name="uniq_tax_setting_per_date"
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.enabled and self.kind == self.Kind.GST and not self.registration_number:
            raise ValidationError("A GSTIN is required when GST is switched on.")
        if self.registration_number:
            (validate_gstin if self.kind == self.Kind.GST else validate_tan)(self.registration_number)

    def __str__(self):
        return f"{self.kind.upper()} {'on' if self.enabled else 'off'} from {self.effective_from}"


class HSN(models.Model):
    """HSN code master (MST-07). Rates are not stored here but in dated slabs."""

    code = models.CharField(max_length=8, unique=True)
    description = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["code"]
        verbose_name = "HSN code"

    def __str__(self):
        return f"{self.code} - {self.description}"


class HsnSlab(models.Model):
    """Value-based GST slab for apparel (TAX-02): the rate depends on the sale value per piece.

    value_to null means no upper limit. A rate change is a new slab row with a later
    effective_from, so it applies to future documents only (TAX-03, BR-12).
    """

    hsn = models.ForeignKey(HSN, on_delete=models.CASCADE, related_name="slabs")
    value_from = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Per piece, inclusive")
    value_to = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Per piece, inclusive; blank = no limit")
    gst_rate = models.DecimalField("GST %", max_digits=5, decimal_places=2)
    effective_from = models.DateField()

    history = HistoricalRecords()

    class Meta:
        ordering = ["hsn__code", "-effective_from", "value_from"]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.value_to is not None and self.value_to < self.value_from:
            raise ValidationError("The upper value cannot be below the lower value.")
        if not 0 <= self.gst_rate <= 100:
            raise ValidationError("GST % must be between 0 and 100.")

    def __str__(self):
        upper = self.value_to if self.value_to is not None else "up"
        return f"{self.hsn.code}: {self.value_from}-{upper} @ {self.gst_rate}%"
