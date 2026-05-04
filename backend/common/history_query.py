"""
Cross-model audit log assembly.

Walks every Django model that registered a `TenantHistoricalRecords()` field
(which is every model in `common.audit`'s reach) and produces a unified view
of historical records suitable for the /settings/audit-log UI.

Each row in the unified view is a small dict with the exact shape the
existing AuditLog.jsx component expects, so we don't have to touch the
frontend renderer:

    {
        id            : "<live_model_label>:<history_id>",
        datetime      : "YYYY-MM-DD HH:MM:SS",
        event_type    : "CREATE" | "UPDATE" | "DELETE",
        app           : <app_label>,
        model         : <model_name>,
        object_repr   : <str(historical_instance)>,
        user          : <username or "System">,
        changed_fields: <JSON-serialisable diff string or null>,
        history_id    : <int>,
        live_pk       : <pk of the live row>,
        history_transaction_id : <UUID string or null>,
    }

Filtering supports the same parameters the old easy-audit view took
(from_date, to_date, model, user) plus retail (multi-tenant scope).
"""
from itertools import chain
from datetime import datetime, time
from django.apps import apps
from django.utils.timezone import localtime, make_aware
from simple_history.manager import HistoryManager


# ── Cache: list every (live_model, historical_model) pair we've registered ────

def get_tracked_models():
    """Return [(live_model, historical_model), ...] for every model that
    has a `TenantHistoricalRecords` (or any HistoryManager) field."""
    pairs = []
    for model in apps.get_models():
        history_attr = getattr(model, 'history', None)
        if history_attr is None:
            continue
        if not isinstance(history_attr, HistoryManager):
            continue
        # The historical model is exposed as `model.history.model`
        pairs.append((model, history_attr.model))
    return pairs


# ── Event-type mapping ───────────────────────────────────────────────────────

# simple_history history_type chars → human-readable verbs (must match what
# the frontend's EVENT_STYLE map expects)
EVENT_LABEL = {'+': 'CREATE', '~': 'UPDATE', '-': 'DELETE'}


# ── The aggregator ───────────────────────────────────────────────────────────

def _to_serializable(history_instance, live_model):
    """Build the dict that the frontend renders for one history row."""
    label = f"{live_model._meta.app_label}.{live_model._meta.model_name}"
    user = getattr(history_instance, 'history_user', None)
    user_label = user.username if user else 'System'

    txn_id = getattr(history_instance, 'history_transaction_id', None)

    # Object repr: use the historical instance's __str__ — historical models
    # inherit the live model's __str__, so this matches what easy-audit showed.
    try:
        repr_str = str(history_instance)
    except Exception:
        repr_str = f"{live_model.__name__} #{history_instance.history_id}"

    return {
        'id':            f"{label}:{history_instance.history_id}",
        'datetime':      localtime(history_instance.history_date).strftime('%Y-%m-%d %H:%M:%S'),
        'event_type':    EVENT_LABEL.get(history_instance.history_type, history_instance.history_type),
        'app':           live_model._meta.app_label,
        'model':         live_model._meta.model_name,
        'object_repr':   repr_str[:200],
        'user':          user_label,
        # Lazy: list view doesn't compute diffs (would be N+1 across all rows
        # and across all tracked models). The history detail endpoint can
        # compute on demand via simple-history's diff_against(prev_record).
        'changed_fields': None,
        'history_id':    history_instance.history_id,
        'live_pk':       history_instance.id,
        'history_transaction_id': str(txn_id) if txn_id else None,
        'history_change_reason':  getattr(history_instance, 'history_change_reason', None),
    }


def query_history(retail=None, from_date=None, to_date=None, model_name=None, user_id=None):
    """
    Returns an iterable of dicts (newest first) across every tracked model.
    Caller is responsible for paginating.
    """
    rows = []
    model_filter = (model_name or '').strip().lower()

    for live_model, historical_model in get_tracked_models():
        # Cheap pre-filter: skip whole model if user filtered to a specific name
        if model_filter and model_filter not in live_model._meta.model_name.lower():
            continue

        qs = historical_model.objects.all()

        if retail is not None and hasattr(historical_model, 'history_retail_id'):
            qs = qs.filter(history_retail=retail)

        if user_id:
            qs = qs.filter(history_user_id=user_id)

        if from_date:
            qs = qs.filter(history_date__date__gte=from_date)

        if to_date:
            qs = qs.filter(history_date__date__lte=to_date)

        # Recent first; cap per-model to keep memory bounded for the UNION.
        # The outer pagination then takes care of the actual page slice.
        qs = qs.select_related('history_user').order_by('-history_date')[:5000]

        for h in qs:
            rows.append(_to_serializable(h, live_model))

    rows.sort(key=lambda r: r['datetime'], reverse=True)
    return rows
