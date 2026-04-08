"""
Seeds all system ledgers for existing companies, GSTINs, and retails.
Safe to re-run — uses get_or_create / existence checks (idempotent).

Usage:
    python manage.py seed_system_ledgers
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Seed / backfill all system ledgers for existing companies, GSTINs, and retails"

    def handle(self, *args, **options):
        from accounting.models import Account
        from contacts.models import Ledger, LedgerRole
        from mastersconfig.models import CompanyMaster, GSTINMaster, RetailMaster
        from mastersconfig.signals import (
            _OPERATIONAL_LEDGERS, _TRADING_LEDGERS,
            _MISC_LEDGERS, _OFFICE_EQUIPMENT_LEDGERS, _GST_REGISTERS,
        )

        # ── Account group cache ──────────────────────────────────────────────
        all_codes = {
            code
            for *_, code in _OPERATIONAL_LEDGERS + _TRADING_LEDGERS + _MISC_LEDGERS + _OFFICE_EQUIPMENT_LEDGERS
        } | {'CA-GST', 'CL-DT-GST', 'CA-CSH'}
        acct = {c: Account.objects.filter(code=c).first() for c in all_codes}

        def _ensure(ac_name, display_name, group_code, role='OTH'):
            ldgr, created = Ledger.objects.get_or_create(
                ac_name=ac_name,
                is_system=True,
                defaults={'display_name': display_name, 'ac_group': acct.get(group_code)},
            )
            LedgerRole.objects.get_or_create(ledger=ldgr, role=role, defaults={'is_primary': True})
            return ldgr, created

        # ── 1. Company-level ledgers ─────────────────────────────────────────
        with transaction.atomic():
            for company in CompanyMaster.objects.select_for_update().all():
                update_fields = {}

                # FK-backed operational ledgers
                for field_name, label, code in _OPERATIONAL_LEDGERS:
                    ldgr, created = _ensure(label, label, code)
                    if created:
                        self.stdout.write(f"  [NEW] {label}")
                    fk_field = f"{field_name}_id"
                    if getattr(company, fk_field) is None:
                        update_fields[fk_field] = ldgr.pk

                # Non-FK ledgers: trading, misc, equipment
                for label, code in _TRADING_LEDGERS + _MISC_LEDGERS + _OFFICE_EQUIPMENT_LEDGERS:
                    _, created = _ensure(label, label, code)
                    if created:
                        self.stdout.write(f"  [NEW] {label}")

                if update_fields:
                    CompanyMaster.objects.filter(pk=company.pk).update(**update_fields)
                    self.stdout.write(
                        self.style.SUCCESS(f"  Updated FK links for company: {company.company_name}")
                    )

        # ── 2. GSTIN-level GST register ledgers ──────────────────────────────
        with transaction.atomic():
            for gstin in GSTINMaster.objects.select_for_update().all():
                update_fields = {}
                for field_name, label, code in _GST_REGISTERS:
                    ac_name = f"{gstin.gstin}_{label.replace(' ', '_')}"
                    ldgr, created = Ledger.objects.get_or_create(
                        ac_name=ac_name,
                        is_system=True,
                        defaults={'display_name': f"{gstin.gstin} {label}", 'ac_group': acct.get(code)},
                    )
                    LedgerRole.objects.get_or_create(ledger=ldgr, role='OTH', defaults={'is_primary': True})
                    if created:
                        self.stdout.write(f"  [NEW] {ac_name}")
                    fk_field = f"{field_name}_id"
                    if getattr(gstin, fk_field) is None:
                        update_fields[fk_field] = ldgr.pk

                if update_fields:
                    GSTINMaster.objects.filter(pk=gstin.pk).update(**update_fields)

        self.stdout.write(self.style.SUCCESS("Done seeding system ledgers."))
