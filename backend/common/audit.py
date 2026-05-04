"""
Multi-tenant aware historical record tracking for the Jewel India ERP.

Wraps django-simple-history's HistoricalRecords to add two extra columns on
every historical row:

  history_retail          FK → mastersconfig.RetailMaster
                          (taken from request.retail by the signal handler)
  history_transaction_id  UUID, identical for every row created during a
                          single HTTP request — lets the "Reverse this
                          operation" UI undo a parent voucher and all its
                          nested children atomically.
  history_change_reason   Free-text label set by business code at key events
                          (e.g. "Voucher cancelled", "Cheque deposited").

Pair with `common.middleware.TenantHistoryMiddleware`, which assigns a fresh
UUID to `request.history_transaction_id` on every request, and the
`pre_create_historical_record` signal handler in `common.signals`, which
copies the request context onto each new historical row before it's saved.
"""
from django.db import models as dj_models
from simple_history.models import HistoricalRecords


class TenantHistoricalRecords(HistoricalRecords):
    """
    Drop-in replacement for `simple_history.HistoricalRecords` that adds
    multi-tenant context. Use it the same way:

        from common.audit import TenantHistoricalRecords

        class VoucherMain(models.Model):
            ...
            history = TenantHistoricalRecords()
    """

    def __init__(self, *args, **kwargs):
        # Don't snapshot housekeeping timestamps that change on every save —
        # they bloat the history without adding signal.
        kwargs.setdefault('excluded_fields', ['updated_at'])
        super().__init__(*args, **kwargs)

    def get_extra_fields(self, model, fields):
        extra = super().get_extra_fields(model, fields)

        extra['history_retail'] = dj_models.ForeignKey(
            'mastersconfig.RetailMaster',
            null=True, blank=True,
            on_delete=dj_models.SET_NULL,
            related_name='+',
            db_index=True,
        )
        extra['history_transaction_id'] = dj_models.UUIDField(
            null=True, blank=True, db_index=True,
            help_text="Same UUID for every historical row written during one HTTP request — used for per-operation reversal.",
        )
        extra['history_change_reason'] = dj_models.CharField(
            max_length=200, null=True, blank=True,
            help_text="Optional human-readable label for this change.",
        )
        return extra
