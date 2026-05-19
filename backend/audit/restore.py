"""
Time-travel / restore engine.

Three public operations:

    state_at(model_label, object_pk, at_timestamp) → dict | None
        Reconstruct a row's state at a point in time by loading the CREATE
        snapshot and replaying UPDATE diffs forward up to `at_timestamp`.

    restore_row(model_label, object_pk, at_timestamp, user, reason)
        Write the reconstructed state back to the live row. Emits a new
        AuditEvent with action=RESTORE.

    restore_correlation(correlation_id, user, reason)
        DESTRUCTIVE: revert all rows touched in a correlation group to
        their pre-correlation state, AND delete any child rows that were
        created during the correlation. Brings a document fully back to
        its pre-edit shape.

All operations run inside a transaction. Restores themselves write
AuditEvent rows so the operation is auditable and itself reversible.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.apps import apps
from django.db import transaction

from . import _context as _ctx
from .models import AuditAction, AuditEvent


@dataclass
class RestoreSummary:
    creates: int = 0
    updates: int = 0
    deletes: int = 0
    blocked: list = field(default_factory=list)
    affected: list = field(default_factory=list)

    def as_dict(self):
        return {
            'creates': self.creates,
            'updates': self.updates,
            'deletes': self.deletes,
            'total_changes': self.creates + self.updates + self.deletes,
            'blocked': self.blocked,
            'affected': self.affected,
        }


# ── Mode 1: state at a point in time ─────────────────────────────────────────

def state_at(model_label: str, object_pk: Any, at_timestamp) -> dict | None:
    """Replay CREATE snapshot + UPDATE diffs up to `at_timestamp`.

    Returns None if the row didn't exist at that time (no CREATE before T,
    or a DELETE before T not followed by a re-CREATE).
    """
    events = AuditEvent.objects.filter(
        model_label=model_label,
        object_pk=str(object_pk),
        timestamp__lte=at_timestamp,
    ).order_by('timestamp')

    state: dict | None = None
    for ev in events:
        if ev.action == AuditAction.CREATE:
            state = dict(ev.snapshot or ev.changes or {})
        elif ev.action == AuditAction.UPDATE and state is not None:
            for fname, delta in (ev.changes or {}).items():
                if isinstance(delta, dict) and 'new' in delta:
                    state[fname] = delta['new']
        elif ev.action == AuditAction.DELETE:
            state = None
        elif ev.action == AuditAction.RESTORE and ev.snapshot:
            state = dict(ev.snapshot)
    return state


# ── Mode 2: restore a single row ─────────────────────────────────────────────

def restore_row(model_label: str, object_pk: Any, at_timestamp,
                user=None, reason: str = '') -> RestoreSummary:
    summary = RestoreSummary()
    target = state_at(model_label, object_pk, at_timestamp)
    if target is None:
        summary.blocked.append(
            f'No state for {model_label}#{object_pk} at {at_timestamp}'
        )
        return summary

    Model = _resolve_model(model_label)
    if Model is None:
        summary.blocked.append(f'Unknown model {model_label}')
        return summary

    defaults = _filter_writeable_fields(Model, target)
    with transaction.atomic(), \
         _ctx.context(user=user, source=f'restore:row', reason=reason):
        obj, created = Model.objects.update_or_create(pk=object_pk, defaults=defaults)
        # Mark the meta-event explicitly
        _record_restore_meta(
            model_label, str(object_pk), at_timestamp, snapshot=target,
            note='restore_row',
        )
        if created:
            summary.creates += 1
        else:
            summary.updates += 1
        summary.affected.append(f'{model_label}#{object_pk}')
    return summary


# ── Mode 3: destructive correlation rollback ────────────────────────────────

def restore_correlation(correlation_id, user=None, reason: str = '') -> RestoreSummary:
    """Undo every row touched in this correlation group, destructively.

    Rules:
      - For each (model, pk) that appears in the correlation:
          * CREATE events  → delete the live row (it shouldn't exist).
          * UPDATE events  → revert to the row's state just BEFORE the
                             earliest event in this correlation.
          * DELETE events  → recreate the row from the snapshot.
      - The restore writes new AuditEvent rows; the reversal is itself
        auditable.
    """
    summary = RestoreSummary()
    events  = list(
        AuditEvent.objects.filter(correlation_id=correlation_id)
        .exclude(action__in=[AuditAction.LOGIN, AuditAction.LOGOUT,
                             AuditAction.LOGIN_FAILED, AuditAction.RESTORE])
        .order_by('timestamp')
    )
    if not events:
        summary.blocked.append(f'No events for correlation {correlation_id}')
        return summary

    # Group events by (model_label, object_pk)
    by_target: dict[tuple, list[AuditEvent]] = {}
    for ev in events:
        by_target.setdefault((ev.model_label, ev.object_pk), []).append(ev)

    with transaction.atomic(), \
         _ctx.context(user=user, source='restore:correlation', reason=reason):

        for (label, pk), evs in by_target.items():
            Model = _resolve_model(label)
            if Model is None:
                summary.blocked.append(f'Unknown model {label}')
                continue

            first      = evs[0]
            last       = evs[-1]
            first_kind = first.action

            if first_kind == AuditAction.CREATE:
                # Created during this correlation → delete it.
                qs = Model.objects.filter(pk=pk)
                if qs.exists():
                    qs.delete()
                    summary.deletes += 1
                    summary.affected.append(f'{label}#{pk} (deleted, was created in correlation)')

            elif first_kind == AuditAction.UPDATE:
                # Get state just before the first event in this correlation.
                # state_at(t - epsilon) is equivalent to replaying everything
                # strictly before `first.timestamp`.
                prior = _state_strictly_before(label, pk, first.timestamp)
                if prior is None:
                    summary.blocked.append(
                        f'No prior state for {label}#{pk} — cannot revert update'
                    )
                    continue
                defaults = _filter_writeable_fields(Model, prior)
                Model.objects.filter(pk=pk).update(**defaults)
                summary.updates += 1
                summary.affected.append(f'{label}#{pk} (reverted)')

            elif first_kind == AuditAction.DELETE:
                # Deleted during this correlation → recreate from snapshot.
                snap = first.snapshot or {}
                defaults = _filter_writeable_fields(Model, snap)
                Model.objects.update_or_create(pk=pk, defaults=defaults)
                summary.creates += 1
                summary.affected.append(f'{label}#{pk} (recreated)')

            # Mark RESTORE meta for traceability
            _record_restore_meta(
                label, str(pk),
                at_timestamp=first.timestamp,
                snapshot=None,
                note=f'restore_correlation:{correlation_id}',
            )

    return summary


# ── Helpers ──────────────────────────────────────────────────────────────────

def _state_strictly_before(model_label, object_pk, timestamp):
    events = AuditEvent.objects.filter(
        model_label=model_label,
        object_pk=str(object_pk),
        timestamp__lt=timestamp,
    ).order_by('timestamp')

    state: dict | None = None
    for ev in events:
        if ev.action == AuditAction.CREATE:
            state = dict(ev.snapshot or ev.changes or {})
        elif ev.action == AuditAction.UPDATE and state is not None:
            for fname, delta in (ev.changes or {}).items():
                if isinstance(delta, dict) and 'new' in delta:
                    state[fname] = delta['new']
        elif ev.action == AuditAction.DELETE:
            state = None
    return state


def _resolve_model(model_label):
    try:
        app_label, model_name = model_label.split('.', 1)
        return apps.get_model(app_label, model_name)
    except Exception:
        return None


def _filter_writeable_fields(Model, snapshot: dict) -> dict:
    """Return a defaults dict suitable for update_or_create.

    Handles:
      - FK fields: snapshot stores {'pk': X, 'repr': '...'}; convert back to
        the attname (e.g. retail_id) with just the pk.
      - Skips m2m (we don't snapshot them) and unknown fields (schema drift).
      - Skips the primary key (passed separately).
    """
    out = {}
    by_name = {f.name: f for f in Model._meta.concrete_fields}
    for name, val in (snapshot or {}).items():
        field = by_name.get(name)
        if field is None:
            continue
        if field.primary_key:
            continue
        if field.is_relation and not field.many_to_many:
            if isinstance(val, dict) and 'pk' in val:
                out[field.attname] = val['pk']
            else:
                out[field.attname] = val
        else:
            out[name] = val
    return out


def _record_restore_meta(model_label, object_pk, at_timestamp, snapshot, note):
    """Write a RESTORE meta-event so the restore is itself auditable.

    This is separate from the actual UPDATE event that the restore's
    update_or_create() will produce via post_save — that one captures the
    field diff; this one records WHY (which T, which note).
    """
    state = _ctx._get_state()  # noqa: SLF001
    AuditEvent.objects.create(
        action=AuditAction.RESTORE,
        model_label=model_label,
        object_pk=str(object_pk),
        object_repr=f'{model_label}#{object_pk}',
        snapshot=snapshot,
        user=state.get('user'),
        username_snapshot=(state.get('username') or '')[:150],
        retail=state.get('retail'),
        session_key=(state.get('session_key') or '')[:40],
        ip_address=state.get('ip'),
        user_agent=(state.get('user_agent') or '')[:255],
        request_id=state.get('request_id'),
        correlation_id=state.get('correlation_id'),
        metadata={
            'restored_to': at_timestamp.isoformat() if hasattr(at_timestamp, 'isoformat') else str(at_timestamp),
            'reason':      state.get('reason') or '',
            'note':        note,
        },
    )
