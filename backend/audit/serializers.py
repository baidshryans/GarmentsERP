"""
Field-aware value serialisation for storing CREATE snapshots and UPDATE
diffs in AuditEvent.changes / .snapshot.

All values are converted to JSON-safe Python primitives. The shapes are
chosen so the restore code can round-trip them back into model fields.
"""
import datetime
import decimal
import uuid

from django.db import models as dj_models


def serialize_value(field, value):
    """Convert `value` (raw model attribute) into a JSON-safe representation."""
    if value is None:
        return None

    # FK / OneToOne — store (pk, str(related)) so the UI can render a label
    # without a join and the restore code can re-resolve by pk.
    if isinstance(field, (dj_models.ForeignKey, dj_models.OneToOneField)):
        try:
            related = value if hasattr(value, 'pk') else None
            if related is not None:
                return {'pk': _scalar(related.pk), 'repr': str(related)[:200]}
        except Exception:
            pass
        # value may already be the raw pk (when reading from _state)
        return {'pk': _scalar(value), 'repr': None}

    if isinstance(field, dj_models.ManyToManyField):
        try:
            return [_scalar(v.pk) for v in value.all()]
        except Exception:
            return list(value) if value else []

    if isinstance(field, dj_models.FileField):
        try:
            return value.name if value else None
        except Exception:
            return str(value)

    if isinstance(field, dj_models.JSONField):
        return value

    return _scalar(value)


def _scalar(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        return value.total_seconds()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode('utf-8')
        except Exception:
            return repr(value)
    return str(value)


def snapshot_instance(instance):
    """Return a JSON-safe dict of every concrete field on `instance`.

    Used for CREATE and DELETE events (full snapshot). M2M relationships
    are intentionally omitted — they fire their own m2m_changed signals
    and are not represented atomically on the parent row.
    """
    out = {}
    for field in instance._meta.concrete_fields:
        try:
            value = getattr(instance, field.attname, None) if field.is_relation else getattr(instance, field.name, None)
            if field.is_relation:
                # For FK fields, attname gives the raw pk; resolve to (pk, repr)
                try:
                    related = getattr(instance, field.name, None)
                except Exception:
                    related = None
                if related is not None:
                    out[field.name] = {'pk': _scalar(getattr(related, 'pk', None)), 'repr': str(related)[:200]}
                else:
                    out[field.name] = {'pk': _scalar(value), 'repr': None} if value is not None else None
            else:
                out[field.name] = serialize_value(field, value)
        except Exception:
            out[field.name] = None
    return out


def compute_diff(model, before_snapshot, after_snapshot, field_is_denied):
    """Return {field: {'old': X, 'new': Y}} for fields that changed.

    `field_is_denied(model, name)` filters out fields we never record
    (e.g. updated_at).
    """
    if before_snapshot is None or after_snapshot is None:
        return {}
    changed = {}
    for name, new_val in after_snapshot.items():
        if field_is_denied(model, name):
            continue
        old_val = before_snapshot.get(name)
        if old_val != new_val:
            changed[name] = {'old': old_val, 'new': new_val}
    return changed
