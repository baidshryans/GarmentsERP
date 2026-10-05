"""Reset the database to a clean start (Settings -> Reset database).

Keeps the masters and the setup; deletes every transaction. This is the one place that is allowed to remove posted vouchers
and stock movements, so it goes below the ORM guards (_raw_delete) and runs in a single transaction: either everything is
cleared or nothing is.

KEPT: company, financial years, factories, locations, users, roles and permissions, chart of accounts (groups and ledgers,
without any balance), the tax setup, every master (styles, SKUs, BOM, materials, parties, price lists, processes, routes,
units, sizes, colours), labour rates, reorder levels, sales settings, and the model history of those records.
CLEARED: vouchers and bill allocations, stock, rolls and movements, purchases, production, job work, sales, alerts, daily
summaries, period locks, the login log, and the history of all of those. Document numbers start again from 1 and
financial years are reopened."""
import sqlite3
from datetime import datetime
from pathlib import Path

from django.apps import apps
from django.db import connection, transaction

from core.exceptions import BusinessRuleError

# Whole apps that are masters or setup: nothing in them is ever deleted.
KEEP_APPS = {"masters", "tax"}
# Models kept from the apps that otherwise hold transactions ("app_label.modelname").
KEEP_MODELS = {
    "core.company", "core.financialyear", "core.factory", "core.location", "core.role", "core.rolepermission",
    "core.fieldpermission", "core.user", "core.numberseries",
    "ledger.accountgroup", "ledger.ledger",
    "inventory.reorderlevel",
    "jobwork.labourrate", "jobwork.labourrateaddon", "jobwork.labourratesize",
    "sales.salesetting",
}
# Apps whose models are looked at. Third-party apps (auth, sessions, admin) are left alone.
OWN_APPS = {"core", "ledger", "tax", "masters", "inventory", "production", "jobwork", "purchases", "sales", "reports", "api"}


def _label(model):
    return model._meta.label_lower


def _is_kept(model):
    return model._meta.app_label in KEEP_APPS or _label(model) in KEEP_MODELS


def models_to_clear():
    """The models whose rows are all deleted, in an order that suits foreign keys (referencing rows first)."""
    wipe = []
    for model in apps.get_models(include_auto_created=True):
        if model._meta.app_label not in OWN_APPS:
            continue
        if model._meta.auto_created:
            # many-to-many link tables follow the model that owns them
            owner = model._meta.auto_created
            if not _is_kept(owner):
                wipe.append(model)
            continue
        if _is_historical(model):
            if not _is_kept(model.instance_type):
                wipe.append(model)
            continue
        if not _is_kept(model):
            wipe.append(model)
    return _order(wipe)


def _is_historical(model):
    return hasattr(model, "instance_type") and hasattr(model, "history_date")


def _order(models):
    """Delete a model before the models its foreign keys point at (so a PROTECT never blocks); cycles fall back to the
    given order and rely on the database checking constraints at commit."""
    wanted = set(models)
    pending = {m: {f.related_model for f in m._meta.concrete_fields
                   if f.is_relation and f.related_model in wanted and f.related_model is not m} for m in models}
    # a model can go once nothing pending still refers to it
    ordered = []
    while pending:
        free = [m for m in pending if not any(m in deps for other, deps in pending.items() if other is not m)]
        if not free:
            free = [next(iter(pending))]
        for m in free:
            ordered.append(m)
            del pending[m]
    return ordered


def counts():
    """How many rows would be cleared, per model with something in it, for the confirmation page."""
    rows = []
    for model in models_to_clear():
        if _is_historical(model) or model._meta.auto_created:
            continue
        n = model._base_manager.count()
        if n:
            rows.append((model._meta.verbose_name_plural.title(), n))
    return sorted(rows, key=lambda r: -r[1])


def _backup_sqlite():
    """A copy of the database file taken before anything is deleted. Only for SQLite; other engines use their own backups."""
    if connection.vendor != "sqlite":
        return None
    name = connection.settings_dict["NAME"]
    if not name or str(name) == ":memory:":
        return None
    target = Path(name).with_name(f"{Path(name).stem}-before-reset-{datetime.now():%Y%m%d-%H%M%S}{Path(name).suffix}")
    src = sqlite3.connect(str(name))
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return target


def reset_transactions(*, user, backup=True):
    """Delete all transactional data, keep the masters. Returns (rows_deleted, backup_path)."""
    from core.models import FinancialYear, NumberSeries

    if not user.is_superuser:
        raise BusinessRuleError("Only the system owner (a superuser) can reset the database.")
    path = _backup_sqlite() if backup else None
    deleted = 0
    with transaction.atomic():
        for model in models_to_clear():
            deleted += model._base_manager.all()._raw_delete(using=connection.alias)
        NumberSeries.objects.update(next_number=1)
        FinancialYear.objects.update(is_closed=False)
        connection.check_constraints()
    return deleted, path
