"""
Centralised configuration of what gets audited and how.

Editing this file is the only on-going maintenance the audit app requires.
Adding a new top-level voucher model → list it in PARENT_MODELS.
Silencing a chatty/ticker model → add to DENY_LIST.
"""

# Models that must NOT be audited (audit table itself, internal Django
# bookkeeping, and noisy/ticker tables).
DENY_LIST = {
    'audit.AuditEvent',
    'sessions.Session',
    'admin.LogEntry',
    'contenttypes.ContentType',
    'auth.Permission',
    'authtoken.Token',
    'authtoken.TokenProxy',
    'migrations.Migration',

    # Noisy tickers / feeds — pollute audit log without business value.
    # Add more as we discover them. Pattern: high-frequency price/rate
    # records, calculator caches, background-job scratch tables.
    'goldrates.GoldRate',           # gold-rate ticker
    'goldrates.GoldRateHistory',
    'goldrates.GoldRateLog',

    # Historical tables created by django-simple-history live in many apps
    # and are added to DENY_LIST dynamically below (see is_audited()).
}


# Top-level "business document" models. The first event of a request that
# touches one of these is marked is_parent_event=True so the audit-log UI
# can render it as the header of a collapsible group (parent + line items).
PARENT_MODELS = {
    # Sales
    'sales.SalesVou',
    'sales.SaleReturn',
    'sales.SalesApproval',
    'sales.SalesApprovalReturn',
    'sales.CustomerOrder',
    'sales.Quotation',

    # Purchase
    'purchase.PurchaseVoucher',
    'purchase.PurchaseReturn',
    'purchase.PurchaseOrder',

    # Manufacturing job tickets
    'manufacturing.KarigarIssue',
    'manufacturing.KarigarReceive',
    'manufacturing.HallmarkIssue',
    'manufacturing.HallmarkReceive',
    'manufacturing.RefinaryIssue',
    'manufacturing.RefinaryReceive',
    'manufacturing.MeltingIssue',
    'manufacturing.MeltingReceive',
    'manufacturing.RepairJobCard',

    # Inventory transactions
    'inventory.InventoryTransfer',
    'inventory.StockAdjustment',
}


# Field names to ignore when computing diffs (i.e. don't count as a change).
# '__default__' applies to every model; per-model overrides go under the
# model's label key.
FIELD_DENY = {
    '__default__': {
        'updated_at', 'last_modified', 'modified_on', 'modified_at',
        '_change_reason', '_history_user', '_history_date',
    },
}


# Class-name patterns for historical_* tables created by simple-history.
# We never audit those — they are themselves an audit artefact.
_HISTORICAL_PREFIXES = ('Historical',)


def is_audited(model):
    """Return True if `model` should be auto-attached to signal handlers."""
    if model._meta.abstract or model._meta.proxy:
        return False
    label = f'{model._meta.app_label}.{model.__name__}'
    if label in DENY_LIST:
        return False
    # django-simple-history's historical_* models — skip
    if model.__name__.startswith(_HISTORICAL_PREFIXES):
        return False
    return True


def is_parent_model(model):
    label = f'{model._meta.app_label}.{model.__name__}'
    return label in PARENT_MODELS


def field_is_denied(model, field_name):
    label = f'{model._meta.app_label}.{model.__name__}'
    if field_name in FIELD_DENY.get('__default__', set()):
        return True
    if field_name in FIELD_DENY.get(label, set()):
        return True
    return False


def get_audited_models():
    """Yield every concrete model that should be auto-audited."""
    from django.apps import apps
    for model in apps.get_models():
        if is_audited(model):
            yield model
