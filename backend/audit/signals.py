"""
Auto-discovery of every audited model + signal handlers that write
AuditEvent rows on every save / delete / login.

Design notes:
  - pre_save stashes the pre-image (full field snapshot) keyed by
    (model, pk) on a thread-local map. post_save reads it back and
    computes the diff.
  - On CREATE (pre-image absent → new instance), we store the full
    snapshot + changes=that-same-snapshot for searchability.
  - On UPDATE, we store only the diff in `changes` and leave snapshot=None
    (state can be reconstructed by replaying CREATE + diffs forward).
  - On DELETE, post_delete captures the full snapshot before the row
    vanishes.
  - All audit writes are wrapped in a try/except — never let the audit
    layer break business code.
"""
from __future__ import annotations

import threading
import uuid

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db.models.signals import post_delete, post_save, pre_save

from . import _context as _ctx
from .registry import (
    field_is_denied,
    get_audited_models,
    is_audited,
    is_parent_model,
)
from .serializers import compute_diff, snapshot_instance


# Per-thread map: { (Model, pk) → snapshot_dict } captured at pre_save time.
_presave = threading.local()


def _presave_map():
    m = getattr(_presave, 'map', None)
    if m is None:
        m = {}
        _presave.map = m
    return m


# ── Core signal handlers ─────────────────────────────────────────────────────

def _capture_pre_save(sender, instance, **kwargs):
    if not is_audited(sender):
        return
    if _ctx.get('bulk_active'):
        return
    pk = instance.pk
    if pk is None:
        return  # CREATE — no pre-image to capture
    try:
        prior = sender.objects.filter(pk=pk).first()
        if prior is None:
            return
        _presave_map()[(sender, pk)] = snapshot_instance(prior)
    except Exception:
        # Defensive: never crash a save because audit failed.
        pass


def _capture_post_save(sender, instance, created, **kwargs):
    if not is_audited(sender):
        return
    if _ctx.get('bulk_active'):
        return
    try:
        _write_save_event(sender, instance, created)
    except Exception:
        pass
    finally:
        _presave_map().pop((sender, instance.pk), None)


def _capture_post_delete(sender, instance, **kwargs):
    if not is_audited(sender):
        return
    if _ctx.get('bulk_active'):
        return
    try:
        _write_delete_event(sender, instance)
    except Exception:
        pass


# ── Event writers ────────────────────────────────────────────────────────────

import logging
_log = logging.getLogger('audit')


def _warn_missing_attribution(label, action, kwargs):
    """Log a warning if a CRUD event lacks user or retail attribution.

    Helps spot code paths where audit context isn't engaged (cron jobs that
    forgot `audit.context(...)`, signals firing during migrations, etc.).
    The event is still written — losing audit data is worse than logging
    an incomplete row.
    """
    if action in ('LOGIN', 'LOGOUT', 'LOGIN_FAILED'):
        return  # auth events legitimately have no retail (and no user on failures)
    if kwargs.get('user') is None or kwargs.get('retail') is None:
        _log.warning(
            'audit: %s %s missing attribution — user=%s retail=%s',
            action, label,
            kwargs.get('user'),
            kwargs.get('retail'),
        )


def _write_save_event(model, instance, created):
    from .models import AuditAction, AuditEvent

    label = f'{model._meta.app_label}.{model.__name__}'
    after = snapshot_instance(instance)
    pk    = instance.pk

    if created:
        action   = AuditAction.CREATE
        changes  = after
        snapshot = after
    else:
        before  = _presave_map().get((model, pk))
        diff    = compute_diff(model, before, after, field_is_denied)
        if not diff:
            # Nothing meaningful changed (only deny-listed fields like
            # updated_at). Skip — keeps the log clean.
            return
        action   = AuditAction.UPDATE
        changes  = diff
        snapshot = None

    common = _common_kwargs()
    _warn_missing_attribution(label, action, common)
    AuditEvent.objects.create(
        action=action,
        model_label=label,
        object_pk=str(pk) if pk is not None else '',
        object_repr=_safe_repr(instance),
        changes=changes,
        snapshot=snapshot,
        is_parent_event=_should_be_parent(label, pk),
        **common,
    )


def _write_delete_event(model, instance):
    from .models import AuditAction, AuditEvent

    label = f'{model._meta.app_label}.{model.__name__}'
    pk    = instance.pk
    snap  = snapshot_instance(instance)

    common = _common_kwargs()
    _warn_missing_attribution(label, 'DELETE', common)
    AuditEvent.objects.create(
        action=AuditAction.DELETE,
        model_label=label,
        object_pk=str(pk) if pk is not None else '',
        object_repr=_safe_repr(instance),
        changes=None,
        snapshot=snap,
        is_parent_event=_should_be_parent(label, pk),
        **common,
    )


def _safe_repr(instance):
    try:
        return str(instance)[:200]
    except Exception:
        return f'{instance.__class__.__name__}#{getattr(instance, "pk", "?")}'


def _common_kwargs():
    """Fields populated from the thread-local request/context.

    Resolves user/retail/session LAZILY by inspecting the live request
    object stashed on the thread-local. DRF Token authentication runs
    during view dispatch (not middleware), so middleware-time values for
    request.user are AnonymousUser. By the time a signal fires inside a
    view, the request has been fully authenticated and the values are
    correct.
    """
    state = _ctx._get_state()  # noqa: SLF001

    # Lazy resolution — prefer live request values
    user     = state.get('user')
    username = state.get('username') or ''
    retail   = state.get('retail')
    session_key = state.get('session_key') or ''

    request = state.get('request')
    if request is not None:
        live_user = getattr(request, 'user', None)
        if live_user is not None and getattr(live_user, 'is_authenticated', False):
            user     = live_user
            username = getattr(live_user, 'username', '') or username
        live_retail = getattr(request, 'retail', None)
        if live_retail is not None:
            retail = live_retail
        live_session = getattr(request, 'session', None)
        if live_session is not None:
            sk = getattr(live_session, 'session_key', None)
            if sk:
                session_key = sk

    md = {}
    if state.get('source'):
        md['source'] = state['source']
    if state.get('reason'):
        md['reason'] = state['reason']

    return {
        'user':              user,
        'username_snapshot': (username or '')[:150],
        'retail':            retail,
        'session_key':       (session_key or '')[:40],
        'ip_address':        state.get('ip'),
        'user_agent':        (state.get('user_agent') or '')[:255],
        'request_id':        state.get('request_id'),
        'correlation_id':    state.get('correlation_id') or state.get('request_id') or uuid.uuid4(),
        'metadata':          md or None,
    }


def _should_be_parent(model_label, pk):
    """Decide whether this event is the parent of its correlation group.

    Rules:
      1. Caller invoked audit.mark_parent(instance) → True.
      2. Model is in PARENT_MODELS and we haven't emitted a parent yet
         in this correlation → True.
      3. We haven't emitted a parent yet AND no model in this correlation
         has matched (2) → first event becomes parent by default.
         (Implemented lazily: rule 2 will overwrite later if a true parent
         model appears; we accept this tiny race for simplicity.)
    """
    state = _ctx._get_state()  # noqa: SLF001
    if state.get('parent_emitted'):
        # If a forced-parent or true-parent fires now, override the earlier
        # one — but we keep it simple: only the FIRST event of a correlation
        # is the parent. Forced parents are honoured up-front.
        if _ctx.is_forced_parent(model_label, pk):
            state['parent_emitted'] = True
            return True
        return False

    # First event of the correlation:
    forced = _ctx.is_forced_parent(model_label, pk)
    if forced or _is_parent_label(model_label) or True:
        state['parent_emitted'] = True
        return True
    return False


def _is_parent_label(model_label):
    from .registry import PARENT_MODELS
    return model_label in PARENT_MODELS


# ── Login / Logout / Failed login ────────────────────────────────────────────

def _log_login(sender, request, user, **kwargs):
    _write_auth_event('LOGIN', request, user)


def _log_logout(sender, request, user, **kwargs):
    _write_auth_event('LOGOUT', request, user)


def _log_login_failed(sender, credentials, request=None, **kwargs):
    username = (credentials or {}).get('username') or ''
    _write_auth_event('LOGIN_FAILED', request, None, username=username)


def _write_auth_event(action, request, user, username=None):
    from .models import AuditEvent

    try:
        ip   = None
        ua   = ''
        sess = ''
        retail = None
        if request is not None:
            fwd = request.META.get('HTTP_X_FORWARDED_FOR')
            ip = fwd.split(',')[0].strip() if fwd else request.META.get('REMOTE_ADDR')
            ua = (request.META.get('HTTP_USER_AGENT', '') or '')[:255]
            sess = (getattr(getattr(request, 'session', None), 'session_key', '') or '')[:40]
            retail = getattr(request, 'retail', None)

        AuditEvent.objects.create(
            action=action,
            user=user,
            username_snapshot=(getattr(user, 'username', None) or username or '')[:150],
            retail=retail,
            session_key=sess,
            ip_address=ip,
            user_agent=ua,
            request_id=_ctx.get('request_id'),
            correlation_id=_ctx.get('correlation_id') or _ctx.get('request_id') or uuid.uuid4(),
            # Auth events are standalone — each one is its own "transaction"
            # in the audit feed, not a child of something else.
            is_parent_event=True,
            metadata={'auth_event': True},
        )
    except Exception:
        pass


# ── Wire-up ──────────────────────────────────────────────────────────────────

def connect_all():
    """Connect signal handlers to every audited model. Idempotent."""
    for model in get_audited_models():
        # weak=False is required because the handlers are module-level
        # functions and Django's default weak refs may garbage-collect them.
        pre_save.connect(_capture_pre_save, sender=model, weak=False,
                         dispatch_uid=f'audit.pre_save.{model._meta.label}')
        post_save.connect(_capture_post_save, sender=model, weak=False,
                          dispatch_uid=f'audit.post_save.{model._meta.label}')
        post_delete.connect(_capture_post_delete, sender=model, weak=False,
                            dispatch_uid=f'audit.post_delete.{model._meta.label}')

    user_logged_in.connect(_log_login, weak=False,
                           dispatch_uid='audit.user_logged_in')
    user_logged_out.connect(_log_logout, weak=False,
                            dispatch_uid='audit.user_logged_out')
    user_login_failed.connect(_log_login_failed, weak=False,
                              dispatch_uid='audit.user_login_failed')
