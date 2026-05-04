"""
Stamps multi-tenant context onto every historical record before it's saved.

simple-history fires `pre_create_historical_record` synchronously inside
the live model's save(), so the request stored on
`HistoricalRecords.context.request` (set by `TenantHistoryMiddleware`)
is still in scope. We pull `request.retail` and
`request.history_transaction_id` off it and copy them onto the new
historical row before it lands in the DB.

Models that didn't opt in via `TenantHistoricalRecords` won't have the
extra columns and are skipped silently.
"""
from django.dispatch import receiver
from simple_history.models import HistoricalRecords
from simple_history.signals import pre_create_historical_record


def _current_request():
    return getattr(HistoricalRecords.context, 'request', None)


@receiver(pre_create_historical_record)
def stamp_tenant_context(sender, **kwargs):
    history_instance = kwargs.get('history_instance')
    if history_instance is None:
        return

    # Skip models that aren't using TenantHistoricalRecords (they don't have
    # the extra columns we need to populate).
    if not hasattr(history_instance, 'history_retail_id'):
        return

    request = _current_request()
    if request is None:
        return

    retail = getattr(request, 'retail', None)
    if retail is not None and history_instance.history_retail_id is None:
        history_instance.history_retail = retail

    txn_id = getattr(request, 'history_transaction_id', None)
    if txn_id is not None and history_instance.history_transaction_id is None:
        history_instance.history_transaction_id = txn_id
