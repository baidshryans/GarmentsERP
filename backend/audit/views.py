"""
Audit log API — replaces common.history_query.query_history.

Implementation lives in plain helper functions (`_log_list_impl`, etc.)
so the legacy /userauth/api/audit-log/* endpoints in userauth.views can
delegate cleanly without nested @api_view wrapping.

The list-row JSON shape is intentionally identical to the old
simple-history-backed view so AuditLog.jsx renders without any changes.
"""
import re

from django.apps import apps
from django.conf import settings
from django.utils.timezone import localtime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AuditAction, AuditEvent


# Matches Django's default repr "<ModelName> object (<pk>)" or
# "<ModelName> object". When stored object_repr matches this, we re-derive
# a better label by loading the live row and inspecting its fields.
_DEFAULT_REPR_RE = re.compile(r'^\w+\s+object(\s+\(\d+\))?$')

# Field names we'll try, in order, when computing a "smart" label for any
# model whose __str__ falls back to Django default. First non-empty wins.
_LABEL_FIELD_CANDIDATES = (
    'name', 'display_name', 'retail_name', 'company_name', 'branch_name',
    'ledger_name', 'ac_name', 'item_name', 'group_name',
    'barcode', 'huid', 'billno', 'voucher_no', 'invoice_no', 'order_no',
    'po_no', 'code', 'retail_code', 'item_code',
    'title', 'label', 'description', 'remarks',
)


def _smart_label(model_label, object_pk, cache):
    """Best-effort human label for (model, pk) — used when the stored
    object_repr is Django's "<Model> object (n)" default.

    Strategy: load the live row, prefer __str__ if it's non-default,
    otherwise walk a list of common text-ish field names and return the
    first non-empty value. Falls back to "<Model> #<pk>".

    `cache` is a per-request dict to avoid repeating lookups across the
    page (e.g. if the same row is the parent of N audit events).
    """
    key = (model_label, str(object_pk))
    if key in cache:
        return cache[key]
    label = None
    try:
        app_label, model_name = model_label.split('.', 1)
        Model = apps.get_model(app_label, model_name)
        inst = Model._default_manager.filter(pk=object_pk).first()
        if inst is not None:
            s = str(inst)
            if not _DEFAULT_REPR_RE.match(s.strip()):
                label = s
            else:
                # Build a map of concrete fields so we can skip relations —
                # FKs str() back to "<RelatedModel> object (n)" which is
                # exactly the default we're trying to avoid.
                concrete = {
                    f.name: f for f in Model._meta.concrete_fields
                    if not f.is_relation
                }
                for fname in _LABEL_FIELD_CANDIDATES:
                    if fname not in concrete:
                        continue
                    v = getattr(inst, fname, None)
                    if v:
                        label = f'{Model.__name__} {v}'
                        break
            if label is None:
                label = f'{Model.__name__} #{object_pk}'
    except Exception:
        label = None
    cache[key] = label
    return label


def _resolve_repr(ev, cache):
    """Return the best repr to show in the UI for this event.

    Prefer the stored object_repr UNLESS it matches Django's default
    pattern, in which case re-derive from the live row.
    """
    stored = (ev.object_repr or '').strip()
    if stored and not _DEFAULT_REPR_RE.match(stored):
        return stored
    if not ev.model_label or not ev.object_pk:
        return stored
    smart = _smart_label(ev.model_label, ev.object_pk, cache)
    return smart or stored


EVENT_LABEL = {
    AuditAction.CREATE:       'CREATE',
    AuditAction.UPDATE:       'UPDATE',
    AuditAction.DELETE:       'DELETE',
    AuditAction.LOGIN:        'LOGIN',
    AuditAction.LOGOUT:       'LOGOUT',
    AuditAction.LOGIN_FAILED: 'LOGIN_FAILED',
    AuditAction.RESTORE:      'RESTORE',
    AuditAction.BULK:         'BULK',
    AuditAction.CUSTOM:       'CUSTOM',
}


def _serialize_row(ev: AuditEvent, label_cache: dict | None = None) -> dict:
    if label_cache is None:
        label_cache = {}

    app, model = '', ''
    if ev.model_label and '.' in ev.model_label:
        app, model = ev.model_label.split('.', 1)
        model = model.lower()

    reason = ''
    if isinstance(ev.metadata, dict):
        reason = ev.metadata.get('reason') or ev.metadata.get('source') or ''

    # Retail label: __str__ from the live FK (RetailMaster.__str__ returns
    # retail_name), with id-fallback. Lookup is cached across the page.
    retail_label = ''
    retail_id    = None
    if ev.retail_id is not None:
        retail_id = ev.retail_id
        cache_key = ('__retail__', ev.retail_id)
        if cache_key in label_cache:
            retail_label = label_cache[cache_key]
        else:
            try:
                retail_label = str(ev.retail) if ev.retail else f'Retail #{ev.retail_id}'
            except Exception:
                retail_label = f'Retail #{ev.retail_id}'
            label_cache[cache_key] = retail_label

    return {
        'id':            f'{ev.model_label or "auth"}:{ev.id}',
        'datetime':      localtime(ev.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
        'event_type':    EVENT_LABEL.get(ev.action, ev.action),
        'app':           app,
        'model':         model,
        'object_repr':   _resolve_repr(ev, label_cache),
        'user':          ev.username_snapshot or 'System',
        'user_id':       ev.user_id,
        'retail':        retail_label,
        'retail_id':     retail_id,
        'ip_address':    ev.ip_address or '',
        'changed_fields': _short_change_summary(ev),
        'history_id':    ev.id,
        'live_pk':       ev.object_pk or None,
        'history_transaction_id': str(ev.correlation_id) if ev.correlation_id else None,
        'history_change_reason':  reason,
        'is_parent_event': ev.is_parent_event,
    }


def _short_change_summary(ev: AuditEvent):
    if not ev.changes or not isinstance(ev.changes, dict):
        return None
    if ev.action == AuditAction.UPDATE:
        return ', '.join(list(ev.changes.keys())[:6])
    return None


def _is_admin(request) -> bool:
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return bool(getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False))


def _scalar(v):
    if isinstance(v, dict) and 'repr' in v and 'pk' in v:
        return v.get('repr') or v.get('pk')
    return v if v is None or isinstance(v, (str, int, float, bool)) else str(v)


# ── Helper implementations (share between /audit/* and legacy /userauth/*) ──

def _log_list_impl(request) -> Response:
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)

    qs = AuditEvent.objects.all()

    # Show events for the active retail PLUS retail-less system events
    # (background jobs, login attempts, etc.) so admins see the full
    # activity picture and don't lose visibility into cron / system writes.
    from django.db.models import Q
    retail = getattr(request, 'retail', None)
    if retail is not None:
        qs = qs.filter(Q(retail=retail) | Q(retail__isnull=True))

    model_name = (request.GET.get('model') or '').strip().lower()
    if model_name:
        qs = qs.filter(model_label__icontains=model_name)

    user_id = request.GET.get('user')
    if user_id:
        qs = qs.filter(user_id=user_id)

    action = (request.GET.get('action') or '').strip().upper()
    if action:
        qs = qs.filter(action=action)

    correlation = request.GET.get('correlation')
    if correlation:
        qs = qs.filter(correlation_id=correlation)
    elif request.GET.get('all') != 'true':
        # Default: one row per transaction. Children are fetched on
        # expand via the correlation endpoint. Pass ?all=true to see
        # every individual event.
        qs = qs.filter(is_parent_event=True)

    from_date = request.GET.get('from_date')
    if from_date:
        qs = qs.filter(timestamp__date__gte=from_date)
    to_date = request.GET.get('to_date')
    if to_date:
        qs = qs.filter(timestamp__date__lte=to_date)

    qs = qs.order_by('-timestamp')

    try:
        page = max(int(request.GET.get('page', 1)), 1)
    except (TypeError, ValueError):
        page = 1
    page_size = getattr(settings, 'LOG_PAGE_SIZE', 50)
    total = qs.count()
    offset = (page - 1) * page_size
    cache = {}
    rows = [_serialize_row(ev, cache) for ev in qs[offset: offset + page_size]]

    return Response({
        'count':     total,
        'page':      page,
        'page_size': page_size,
        'num_pages': max(1, (total + page_size - 1) // page_size),
        'results':   rows,
    })


def _log_detail_impl(request) -> Response:
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)

    raw = (request.GET.get('id') or '').strip()
    if not raw:
        return Response({'detail': 'id parameter required.'}, status=400)

    try:
        event_id = int(raw.rsplit(':', 1)[-1])
    except ValueError:
        return Response({'detail': f'Malformed id: {raw}'}, status=400)

    try:
        ev = AuditEvent.objects.get(pk=event_id)
    except AuditEvent.DoesNotExist:
        return Response({'detail': f'Event {event_id} not found.'}, status=404)

    changes = []
    if ev.action == AuditAction.UPDATE and isinstance(ev.changes, dict):
        for fname, delta in ev.changes.items():
            if isinstance(delta, dict):
                changes.append({
                    'field': fname,
                    'old':   _scalar(delta.get('old')),
                    'new':   _scalar(delta.get('new')),
                })
    elif ev.action == AuditAction.CREATE and isinstance(ev.changes, dict):
        for fname, val in ev.changes.items():
            changes.append({'field': fname, 'old': None, 'new': _scalar(val)})
    elif ev.action == AuditAction.DELETE and isinstance(ev.snapshot, dict):
        for fname, val in ev.snapshot.items():
            changes.append({'field': fname, 'old': _scalar(val), 'new': None})

    return Response({
        'history_id':   ev.id,
        'event_type':   EVENT_LABEL.get(ev.action, ev.action),
        'action':       ev.action,
        'datetime':     localtime(ev.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
        'user':         ev.username_snapshot or 'System',
        'object_repr':  ev.object_repr or '',
        'model_label':  ev.model_label,
        'object_pk':    ev.object_pk,
        'correlation_id': str(ev.correlation_id) if ev.correlation_id else None,
        'is_parent_event': ev.is_parent_event,
        'metadata':     ev.metadata or {},
        'changes':      changes,
    })


def _log_correlation_impl(request) -> Response:
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)

    cid = (request.GET.get('id') or '').strip()
    if not cid:
        return Response({'detail': 'id parameter required.'}, status=400)

    qs = AuditEvent.objects.filter(correlation_id=cid).order_by(
        '-is_parent_event', 'timestamp',
    )
    cache = {}
    return Response({'results': [_serialize_row(ev, cache) for ev in qs]})


def _reverse_correlation_impl(request) -> Response:
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)

    from .restore import restore_correlation

    cid = request.data.get('correlation_id') or request.data.get('history_transaction_id')
    if not cid:
        return Response({'detail': 'correlation_id is required.'}, status=400)
    reason = request.data.get('reason') or ''
    try:
        summary = restore_correlation(cid, user=request.user, reason=reason)
    except Exception as exc:
        return Response({'detail': f'Reversal failed: {exc}'}, status=500)
    return Response({'summary': summary.as_dict()})


def _restore_row_impl(request) -> Response:
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)

    from django.utils.dateparse import parse_datetime
    from django.utils.timezone import is_aware, make_aware

    from .restore import restore_row

    model_label = request.data.get('model_label')
    object_pk   = request.data.get('object_pk')
    raw_ts      = request.data.get('at_timestamp')
    reason      = request.data.get('reason') or ''
    if not (model_label and object_pk and raw_ts):
        return Response({'detail': 'model_label, object_pk, and at_timestamp are required.'}, status=400)

    ts = parse_datetime(raw_ts)
    if ts is None:
        return Response({'detail': 'at_timestamp must be ISO 8601.'}, status=400)
    if not is_aware(ts):
        ts = make_aware(ts)

    try:
        summary = restore_row(model_label, object_pk, ts, user=request.user, reason=reason)
    except Exception as exc:
        return Response({'detail': f'Restore failed: {exc}'}, status=500)
    return Response({'summary': summary.as_dict()})


# ── URL-bound views ──────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_log_list(request):
    return _log_list_impl(request)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_log_detail(request):
    return _log_detail_impl(request)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_log_correlation(request):
    return _log_correlation_impl(request)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reverse_correlation_view(request):
    return _reverse_correlation_impl(request)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def restore_row_view(request):
    return _restore_row_impl(request)
