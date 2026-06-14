"""Per-enrollment scheme-advances sub-ledger creation."""
from django.db import transaction


def get_or_create_enrollment_liability_ledger(enrollment):
    """
    Return the per-enrollment 'Scheme Advances' sub-ledger, creating it if needed.
    Idempotent: if enrollment.liability_ledger is already set, returns it unchanged.
    """
    if enrollment.liability_ledger_id:
        return enrollment.liability_ledger

    from contacts.models import Ledger, LedgerRole
    from accounting.models import Account

    customer = enrollment.customer
    group = Account.objects.filter(code='CL-SCH').first()
    name = f"Scheme A/c — {customer.ac_name} ({enrollment.enrollment_no})"

    with transaction.atomic():
        ledger = Ledger.objects.create(
            ac_name=name,
            display_name=name[:100],
            ac_group=group,
            is_system=True,
            retail_code=enrollment.retail,
            mobile1=getattr(customer, 'mobile1', '') or '',
            pan=getattr(customer, 'pan', None),
        )
        LedgerRole.objects.get_or_create(ledger=ledger, role='OTH', defaults={'is_primary': True})
        enrollment.liability_ledger = ledger
        enrollment.save(update_fields=['liability_ledger', 'updated_at'])

    return ledger


def get_or_create_forfeiture_income_ledger(retail):
    """
    Get or create the system 'Scheme Forfeiture Income' ledger (Indirect Income).
    Used when a cancelled enrollment's balance is forfeited to the shop.
    """
    from contacts.models import Ledger, LedgerRole
    from accounting.models import Account

    ledger_name = "Scheme Forfeiture Income"
    ledger = Ledger.objects.filter(ac_name=ledger_name, is_system=True).first()
    if ledger:
        return ledger

    group = Account.objects.filter(code='INC-IND').first()  # Indirect Income
    with transaction.atomic():
        ledger = Ledger.objects.create(
            ac_name=ledger_name,
            display_name=ledger_name,
            ac_group=group,
            is_system=True,
            retail_code=retail,
        )
        LedgerRole.objects.get_or_create(ledger=ledger, role='OTH', defaults={'is_primary': True})

    return ledger
