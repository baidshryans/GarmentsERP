"""Shared helpers for resolving operational ledgers per retail."""

SHARED_INCENTIVE_NAME = "Sales Incentive"


def get_or_create_shared_incentive_ledger(retail):
    """Return the single 'Sales Incentive' payable ledger for *retail*,
    creating it under Sundry Creditors (SC role) the first time it's needed.

    Used as the credit side of every salesperson commission journal voucher.
    All salespersons within a retail share this ledger — there is no
    per-salesperson commission ledger.
    """
    from contacts.models import Ledger, LedgerRole
    from accounting.models import Account

    if retail is None:
        return None

    ledger = (
        Ledger.objects
        .filter(retail_code=retail, ac_name=SHARED_INCENTIVE_NAME)
        .first()
    )
    if ledger:
        return ledger

    sc_group = Account.objects.filter(code='CL-SC').first()
    ledger = Ledger.objects.create(
        ac_name=SHARED_INCENTIVE_NAME,
        display_name=SHARED_INCENTIVE_NAME,
        ac_group=sc_group,
        retail_code=retail,
        is_system=True,
    )
    LedgerRole.objects.create(ledger=ledger, role='SC', is_primary=True)
    return ledger
