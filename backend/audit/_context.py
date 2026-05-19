"""
Thread-local audit context — the bridge between HTTP requests (or
background-job blocks) and the signal handlers that write AuditEvent rows.

The middleware (and the `context()` context manager for non-request code)
sets fields here. The signal handlers read them when constructing each
AuditEvent. Everything is plain attribute access; no DB calls.

Two helpers also live here so the public API surface is small:
  - mark_parent(instance): force the next event for `instance` to be marked
    is_parent_event=True (overrides registry heuristic).
  - audited_bulk(reason): context manager / decorator that emits a single
    summary AuditEvent for a bulk operation that bypasses signals
    (queryset.update(), bulk_create, etc.).
"""
from __future__ import annotations

import contextlib
import threading
import uuid


_storage = threading.local()


def _get_state():
    state = getattr(_storage, 'state', None)
    if state is None:
        state = {
            'request_id': None,
            'correlation_id': None,
            'user': None,
            'username': '',
            'session_key': '',
            'ip': None,
            'user_agent': '',
            'retail': None,
            'source': None,             # e.g. 'cron:gold_rate_sync'
            'reason': None,             # free-text user reason
            # bookkeeping: have we already emitted a parent event in this
            # correlation? prevents two parents per group.
            'parent_emitted': False,
            # set of (model_label, pk-or-id) the caller has explicitly tagged
            # via mark_parent() — those become parents regardless of
            # PARENT_MODELS heuristic.
            'forced_parents': set(),
            # When inside an `audited_bulk` block, signal handlers should
            # suppress per-row events; the block writes one summary instead.
            'bulk_active': False,
            'bulk_summary': None,       # dict accumulating counts inside block
        }
        _storage.state = state
    return state


def get(name, default=None):
    return _get_state().get(name, default)


def set_field(name, value):
    _get_state()[name] = value


def clear():
    _storage.state = None


# ── Public API ───────────────────────────────────────────────────────────────

@contextlib.contextmanager
def context(user=None, retail=None, source=None, reason=None, correlation_id=None):
    """Set audit context for a block of code that has no HTTP request.

    Typical use: management commands, Celery tasks, cron jobs.

        with audit.context(user=admin_user, source='cron:rollover'):
            run_rollover()

    Nested calls stack (previous values are restored on exit).
    """
    state = _get_state()
    saved = {k: state[k] for k in
             ('user', 'username', 'retail', 'source', 'reason',
              'request_id', 'correlation_id', 'parent_emitted')}
    if user is not None:
        state['user'] = user
        state['username'] = getattr(user, 'username', '') or ''
    if retail is not None:
        state['retail'] = retail
    if source is not None:
        state['source'] = source
    if reason is not None:
        state['reason'] = reason
    new_corr = correlation_id or uuid.uuid4()
    state['correlation_id'] = new_corr
    if state['request_id'] is None:
        state['request_id'] = new_corr
    state['parent_emitted'] = False
    try:
        yield
    finally:
        for k, v in saved.items():
            state[k] = v


def mark_parent(instance):
    """Force `instance`'s next signal event to be marked is_parent_event=True.

    Useful in views that orchestrate an unusual flow where the registry
    heuristic would pick the wrong parent.
    """
    key = (
        f'{instance._meta.app_label}.{instance.__class__.__name__}',
        str(getattr(instance, 'pk', '') or ''),
    )
    _get_state()['forced_parents'].add(key)


def is_forced_parent(model_label, pk):
    return (model_label, str(pk or '')) in _get_state()['forced_parents']


@contextlib.contextmanager
def audited_bulk(reason: str, model_label: str | None = None):
    """Mark a block as a bulk operation.

    Per-row signals fired inside the block are still written (so we don't
    silently lose data), but the block also writes one summary AuditEvent
    of action=BULK with `metadata={'reason': ..., 'rows_affected': ...}`.

    Use this around `queryset.update()`, `bulk_create`, `bulk_update`, and
    `queryset.delete()` — operations Django runs at the SQL level that
    skip pre_save/post_save/post_delete signals entirely. Without this
    wrapper, those operations leave NO audit trail.
    """
    from .models import AuditEvent, AuditAction
    state = _get_state()
    state['bulk_active'] = True
    state['bulk_summary'] = {'reason': reason, 'model_label': model_label, 'rows_affected': None}
    try:
        yield state['bulk_summary']
    finally:
        summary = state['bulk_summary']
        state['bulk_active'] = False
        state['bulk_summary'] = None
        try:
            AuditEvent.objects.create(
                action=AuditAction.BULK,
                model_label=model_label or '',
                user=state.get('user'),
                username_snapshot=state.get('username') or '',
                retail=state.get('retail'),
                session_key=state.get('session_key') or '',
                ip_address=state.get('ip'),
                user_agent=state.get('user_agent') or '',
                request_id=state.get('request_id'),
                correlation_id=state.get('correlation_id') or state.get('request_id') or uuid.uuid4(),
                metadata={
                    'kind': 'bulk',
                    'reason': summary.get('reason'),
                    'rows_affected': summary.get('rows_affected'),
                    'source': state.get('source'),
                },
            )
        except Exception:
            # Never let audit failures crash business code.
            pass
