"""
Tenant-aware HistoryRequestMiddleware.

Wraps simple-history's middleware (which exposes the current request as
`HistoricalRecords.context.request`) and additionally stamps a fresh UUID
on `request.history_transaction_id`.

The signal handler in `common.signals` then copies `request.retail` and
`request.history_transaction_id` onto every historical row created during
the request, so the "Reverse this operation" UI can undo a parent voucher
and all its nested children atomically.
"""
import uuid
from asgiref.sync import iscoroutinefunction
from django.utils.decorators import sync_and_async_middleware

from simple_history.models import HistoricalRecords


@sync_and_async_middleware
def TenantHistoryMiddleware(get_response):
    """Function-style middleware compatible with simple-history >= 3.11."""
    if iscoroutinefunction(get_response):
        async def middleware(request):
            request.history_transaction_id = uuid.uuid4()
            HistoricalRecords.context.request = request
            try:
                return await get_response(request)
            finally:
                try:
                    del HistoricalRecords.context.request
                except AttributeError:
                    pass
    else:
        def middleware(request):
            request.history_transaction_id = uuid.uuid4()
            HistoricalRecords.context.request = request
            try:
                return get_response(request)
            finally:
                try:
                    del HistoricalRecords.context.request
                except AttributeError:
                    pass

    return middleware
