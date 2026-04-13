from django.db import models
from django.contrib.auth.models import User


class CarryForwardLog(models.Model):
    """Records each carry-forward event for audit purposes."""
    retail = models.ForeignKey(
        'mastersconfig.RetailMaster', on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="Retail carried forward (NULL = all retails)"
    )
    cutoff_date = models.DateField(help_text="The date at which old data was cut off")
    old_db_filename = models.CharField(
        max_length=500, blank=True,
        help_text="Filename of the backup (informational only — no runtime dependency)"
    )
    new_fy_code = models.CharField(max_length=10, blank=True, help_text="FY code created for the new period")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[('success', 'Success'), ('failed', 'Failed')],
        default='success',
    )
    master_rows_copied = models.PositiveIntegerField(default=0)
    live_rows_copied = models.PositiveIntegerField(default=0)
    ledgers_with_opening = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'carry_forward_log'
        ordering = ['-created_at']

    def __str__(self):
        return f"CarryForward {self.cutoff_date} ({self.status})"
