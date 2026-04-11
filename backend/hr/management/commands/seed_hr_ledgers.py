"""
Seeds the 6 HR/payroll system ledgers and wires them as defaults in HRSettings
for every existing retail.  Safe to re-run — idempotent.

Usage:
    python manage.py seed_hr_ledgers
"""
from django.core.management.base import BaseCommand
from django.db import transaction

# (HRSettings field name, ledger display name, account-group code)
HR_LEDGER_DEFS = [
    ("salary_expense_ldgr",   "Salary Expense",           "EXP-IND-HR"),
    ("employee_payable_ldgr", "Salary Payable",            "CL-HR-SAL"),
    ("pf_payable_ldgr",       "PF Payable",               "CL-HR-PF"),
    ("esi_payable_ldgr",      "ESI Payable",              "CL-HR-ESI"),
    ("pt_payable_ldgr",       "Professional Tax Payable", "CL-HR-PT"),
    ("tds_payable_ldgr",      "TDS Payable",              "CL-DT-TDS"),
]


class Command(BaseCommand):
    help = "Seed HR/payroll system ledgers and apply them as defaults in HRSettings."

    def handle(self, *args, **options):
        from accounting.models import Account
        from contacts.models import Ledger, LedgerRole
        from mastersconfig.models import RetailMaster
        from hr.models import HRSettings

        # ── 1. Ensure all HR ledgers exist ───────────────────────────────────
        ledger_map = {}   # field_name → Ledger instance
        with transaction.atomic():
            for field_name, name, group_code in HR_LEDGER_DEFS:
                group = Account.objects.filter(code=group_code).first()
                ldgr, created = Ledger.objects.get_or_create(
                    ac_name=name,
                    is_system=True,
                    defaults={"display_name": name, "ac_group": group},
                )
                # Back-fill ac_group if missing (e.g. seeded before account groups existed)
                if not created and group and ldgr.ac_group_id != group.pk:
                    ldgr.ac_group = group
                    ldgr.save(update_fields=["ac_group"])
                # Ensure a primary role exists
                LedgerRole.objects.get_or_create(
                    ledger=ldgr, role="OTH", defaults={"is_primary": True}
                )
                ledger_map[field_name] = ldgr
                verb = "created" if created else "exists"
                self.stdout.write(f"  [{verb.upper()}] {name}")

        # ── 2. Wire as defaults in HRSettings for every retail ──────────────
        with transaction.atomic():
            for retail in RetailMaster.objects.all():
                settings, _ = HRSettings.objects.get_or_create(retail=retail)
                update_fields = []
                for field_name, ldgr in ledger_map.items():
                    # Only set if the field is currently blank (don't override custom choices)
                    if getattr(settings, f"{field_name}_id") is None:
                        setattr(settings, field_name, ldgr)
                        update_fields.append(field_name)
                if update_fields:
                    settings.save(update_fields=update_fields)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [DEFAULTS SET] {retail.retail_name}: {', '.join(update_fields)}"
                        )
                    )
                else:
                    self.stdout.write(f"  [SKIP] {retail.retail_name} — already configured")

        self.stdout.write(self.style.SUCCESS("HR ledgers seeded successfully."))
