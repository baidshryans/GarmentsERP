from django.db import transaction

from core.seeding import register_seeder

from . import seed_data
from .models import AccountGroup, Ledger


@transaction.atomic
def seed_chart_of_accounts(company):
    """Idempotent: creates what is missing, never touches what the admin has edited."""
    groups = {}
    for order, (name, parent, nature, statement) in enumerate(seed_data.GROUPS):
        group, _ = AccountGroup.objects.get_or_create(
            company=company, name=name,
            defaults={
                "parent": groups.get(parent), "nature": nature, "statement": statement,
                "is_system": True, "sort_order": order,
            },
        )
        groups[name] = group
    for name, group_name, key, bill_wise in seed_data.LEDGERS:
        if Ledger.objects.filter(company=company, system_key=key).exists():
            continue
        Ledger.objects.get_or_create(
            company=company, name=name,
            defaults={"group": groups[group_name], "system_key": key, "bill_wise": bill_wise, "is_system": True},
        )


def register():
    register_seeder("chart_of_accounts", seed_chart_of_accounts, order=20)
