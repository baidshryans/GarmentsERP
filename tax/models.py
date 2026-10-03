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
