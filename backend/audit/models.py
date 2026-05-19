"""
Single AuditEvent table — captures every CRUD, login, and restore.

Schema mirrors the spec in
C:/Users/baids/.claude/plans/i-want-you-to-rippling-eclipse.md. Snapshot
strategy: full state on CREATE/DELETE, diff-only on UPDATE. Reconstruct
state at time T by replaying CREATE snapshot + subsequent UPDATE diffs.

Tenant scope uses a FK to mastersconfig.RetailMaster to match the existing
TenantHistoryMiddleware pattern (request.retail).
"""
from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    CREATE       = 'CREATE',       'Create'
    UPDATE       = 'UPDATE',       'Update'
    DELETE       = 'DELETE',       'Delete'
    LOGIN        = 'LOGIN',        'Login'
    LOGOUT       = 'LOGOUT',       'Logout'
    LOGIN_FAILED = 'LOGIN_FAILED', 'Login failed'
    RESTORE      = 'RESTORE',      'Restore'
    BULK         = 'BULK',         'Bulk operation'
    CUSTOM       = 'CUSTOM',       'Custom'


class AuditEvent(models.Model):
    id                 = models.BigAutoField(primary_key=True)
    timestamp          = models.DateTimeField(auto_now_add=True, db_index=True)
    # 'YYYY-MM' — indexed partition key for fast retention pruning. Populated
    # in save() from timestamp; also serves as the partition-routing column
    # if/when the project migrates to Postgres native partitioning.
    created_month      = models.CharField(max_length=7, db_index=True)

    retail             = models.ForeignKey(
        'mastersconfig.RetailMaster',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        db_index=True,
    )
    user               = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    username_snapshot  = models.CharField(max_length=150, blank=True, default='')
    session_key        = models.CharField(max_length=40, blank=True, default='', db_index=True)
    ip_address         = models.GenericIPAddressField(null=True, blank=True)
    user_agent         = models.CharField(max_length=255, blank=True, default='')

    request_id         = models.UUIDField(null=True, blank=True, db_index=True)
    correlation_id     = models.UUIDField(null=True, blank=True, db_index=True)

    action             = models.CharField(
        max_length=20,
        choices=AuditAction.choices,
        db_index=True,
    )
    model_label        = models.CharField(max_length=120, blank=True, default='', db_index=True)
    object_pk          = models.CharField(max_length=64, blank=True, default='', db_index=True)
    object_repr        = models.CharField(max_length=255, blank=True, default='')

    changes            = models.JSONField(null=True, blank=True)
    snapshot           = models.JSONField(null=True, blank=True)

    is_parent_event    = models.BooleanField(default=False)
    metadata           = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'audit_event'
        indexes = [
            models.Index(fields=['retail', '-timestamp'], name='audit_retail_time_idx'),
            models.Index(fields=['model_label', 'object_pk', 'timestamp'],
                         name='audit_obj_time_idx'),
            models.Index(fields=['correlation_id'], name='audit_corr_idx'),
            models.Index(fields=['created_month'], name='audit_month_idx'),
        ]
        ordering = ('-timestamp',)

    def save(self, *args, **kwargs):
        # Populate created_month from timestamp (or now() if not yet set).
        if not self.created_month:
            from django.utils.timezone import now
            ts = self.timestamp or now()
            self.created_month = ts.strftime('%Y-%m')
        super().save(*args, **kwargs)

    def __str__(self):
        target = f"{self.model_label}#{self.object_pk}" if self.model_label else '-'
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {self.action} {target} by {self.username_snapshot or 'system'}"
