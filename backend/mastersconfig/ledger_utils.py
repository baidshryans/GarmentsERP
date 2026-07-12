"""Shared helpers for resolving operational (system) ledgers.

Each helper prefers the configured FK on the master record and only falls back
to a get-or-create-by-name when the FK is unset — self-healing the FK the first
time it's needed, so callers can always reference the ledger by id.
"""

SHARED_INCENTIVE_NAME = "Sales Incentive"
CHEQUES_IN_HAND_NAME = "Cheques in Hand"


def get_or_create_shared_incentive_ledger(retail):
    """Return the single 'Sales Incentive' payable ledger for *retail*.

    Prefers ``retail.sales_incentive_ldgr``; otherwise finds/creates it under
    Sundry Creditors (SC role) and links the FK. Used as the credit side of
    every salesperson commission journal voucher — shared across salespersons.
    """
    from contacts.models import Ledger, LedgerRole
    from accounting.models import Account

    if retail is None:
        return None

    if retail.sales_incentive_ldgr_id:
        return retail.sales_incentive_ldgr

    ledger = (
        Ledger.objects
        .filter(retail_code=retail, ac_name=SHARED_INCENTIVE_NAME)
        .first()
    )
    if not ledger:
        sc_group = Account.objects.filter(code='CL-SC').first()
        ledger = Ledger.objects.create(
            ac_name=SHARED_INCENTIVE_NAME,
            display_name=SHARED_INCENTIVE_NAME,
            ac_group=sc_group,
            retail_code=retail,
            is_system=True,
        )
        LedgerRole.objects.create(ledger=ledger, role='SC', is_primary=True)

    retail.sales_incentive_ldgr = ledger
    retail.save(update_fields=["sales_incentive_ldgr"])
    return ledger


def get_cheques_in_hand_ledger(company):
    """Return the 'Cheques in Hand' suspense ledger.

    Prefers ``company.cheques_in_hand_ldgr``; otherwise finds/creates the
    system ledger (Current Assets — Cheques, CA-CHQ) and links the FK.
    """
    from contacts.models import Ledger, LedgerRole
    from accounting.models import Account

    if company is not None and company.cheques_in_hand_ldgr_id:
        return company.cheques_in_hand_ldgr

    ledger = Ledger.objects.filter(
        ac_name=CHEQUES_IN_HAND_NAME, is_system=True
    ).first()
    if not ledger:
        group = Account.objects.filter(code='CA-CHQ').first()
        ledger = Ledger.objects.create(
            ac_name=CHEQUES_IN_HAND_NAME,
            display_name=CHEQUES_IN_HAND_NAME,
            ac_group=group,
            is_system=True,
        )
        LedgerRole.objects.get_or_create(
            ledger=ledger, role='OTH', defaults={'is_primary': True}
        )

    if company is not None:
        company.cheques_in_hand_ldgr = ledger
        company.save(update_fields=["cheques_in_hand_ldgr"])
    return ledger
