"""
Universal audit-event app.

One central AuditEvent table records every CRUD across every model in the
project (auto-discovered, no per-model wiring), plus login/logout events.
Parent + child rows from the same HTTP request are grouped by correlation_id
so a voucher edit and its line-item changes render as one logical
transaction. Restore-to-any-prior-state is supported by replaying CREATE
snapshots and UPDATE diffs forward.

Public API:

    from audit import context, mark_parent, audited_bulk

    with context(user=user, source='cron:gold_rate_sync'):
        ...  # any DB writes inside emit AuditEvent rows tagged source=...

    mark_parent(instance)              # force this instance's event to be the parent

    with audited_bulk(reason='nightly rebalance'):
        Model.objects.filter(...).update(...)   # one summary event, not skipped
"""
default_app_config = 'audit.apps.AuditConfig'

from ._context import context, mark_parent, audited_bulk  # noqa: E402,F401
