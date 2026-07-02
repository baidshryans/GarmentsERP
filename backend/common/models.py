# The common app contains shared utilities (audit infrastructure, middleware,
# signal handlers) plus the ImportJob model used by background data imports.
# See audit.py, middleware.py, and signals.py for the utilities.
from django.conf import settings
from django.db import models


class ImportJob(models.Model):
    """Tracks a background legacy-data import run (status + captured output)."""
    STATUS_CHOICES = [
        ("PENDING", "Pending"), ("RUNNING", "Running"),
        ("COMPLETED", "Completed"), ("FAILED", "Failed"),
    ]
    kind = models.CharField(max_length=50)
    applied = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    output = models.TextField(blank=True, default="")
    reports = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"ImportJob {self.id} {self.kind} {self.status}"
