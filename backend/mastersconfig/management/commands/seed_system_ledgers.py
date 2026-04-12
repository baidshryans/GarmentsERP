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
        # _OPERATIONAL_LEDGERS: (field_name, label, code, role) → code at index 2
        # _TRADING_LEDGERS:     (label, code, role)             → code at index 1
        # _MISC/_OFFICE:        (label, code)                   → code at index 1
        all_codes = (
            {row[2] for row in _OPERATIONAL_LEDGERS}
            | {row[1] for row in _TRADING_LEDGERS + _MISC_LEDGERS + _OFFICE_EQUIPMENT_LEDGERS}
            | {'CA-GST', 'CL-DT-GST', 'CA-CSH', 'CL-SC', 'CA-CHQ', 'EXP-IND',
               'EXP-IND-ADM', 'EXP-IND-SND', 'EXP-IND-MKT', 'EXP-IND-HR',
               'EXP-IND-RPM', 'EXP-IND-TRV', 'EXP-IND-FIN', 'EXP-IND-CMP',
               'EXP-IND-INS', 'EXP-IND-MSC', 'CAP-OWN'}
        )
        acct = {c: Account.objects.filter(code=c).first() for c in all_codes}

        def _ensure(ac_name, display_name, group_code, role='OTH'):
            group = acct.get(group_code)
            ldgr, created = Ledger.objects.get_or_create(
                ac_name=ac_name,
                is_system=True,
                defaults={'display_name': display_name, 'ac_group': group},
            )
            # Fix missing ac_group on existing ledgers (created before account groups were seeded)
            if not created and group and ldgr.ac_group_id != group.pk:
                ldgr.ac_group = group
                ldgr.save(update_fields=['ac_group'])
            # Fix wrong role on existing ledgers
            primary_role = LedgerRole.objects.filter(ledger=ldgr, is_primary=True).first()
            if primary_role is None:
                LedgerRole.objects.get_or_create(ledger=ldgr, role=role, defaults={'is_primary': True})
            elif primary_role.role != role and role != 'OTH':
                primary_role.role = role
                primary_role.save(update_fields=['role'])
            return ldgr, created

        # ── 0. Rename stale ledger names from old seeding (idempotent) ─────────
        # Maps old ac_name → (new ac_name, correct group_code, correct role)
        RENAMES = {
            'Discount':       ('Sales Discount',         'INC-DIR-SAL', 'INC'),
            'Making Receive': ('Making Charge Received', 'INC-DIR-SAL', 'INC'),
            'Sale Discount':  ('Sales Discount',         'INC-DIR-SAL', 'INC'),
        }
        with transaction.atomic():
            for old_name, (new_name, group_code, role) in RENAMES.items():
                group = acct.get(group_code)
                qs = Ledger.objects.filter(ac_name=old_name, is_system=True)
                if qs.exists() and not Ledger.objects.filter(ac_name=new_name, is_system=True).exists():
                    updated = qs.update(
                        ac_name=new_name,
                        display_name=new_name,
                        **(({'ac_group': group} if group else {})),
                    )
                    # Fix role
                    for ldgr in Ledger.objects.filter(ac_name=new_name, is_system=True):
                        pr = LedgerRole.objects.filter(ledger=ldgr, is_primary=True).first()
                        if pr and pr.role != role:
                            pr.role = role
                            pr.save(update_fields=['role'])
                    self.stdout.write(self.style.SUCCESS(f"  [RENAMED] '{old_name}' → '{new_name}'"))

        # ── 1. Company-level ledgers ─────────────────────────────────────────
        with transaction.atomic():
            for company in CompanyMaster.objects.select_for_update().all():
                update_fields = {}

                # FK-backed operational ledgers
                for field_name, label, code, role in _OPERATIONAL_LEDGERS:
                    ldgr, created = _ensure(label, label, code, role=role)
                    if created:
                        self.stdout.write(f"  [NEW] {label}")
                    fk_field = f"{field_name}_id"
                    if getattr(company, fk_field) is None:
                        update_fields[fk_field] = ldgr.pk

                # Trading ledgers — purchase (EXP) and sales (INC) roles
                for label, code, role in _TRADING_LEDGERS:
                    _, created = _ensure(label, label, code, role=role)
                    if created:
                        self.stdout.write(f"  [NEW] {label}")

                # Misc + equipment ledgers
                for label, code in _MISC_LEDGERS + _OFFICE_EQUIPMENT_LEDGERS:
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

        # ── 3. Global suspense ledgers (one each, shared across all retails) ────
        with transaction.atomic():
            _, created = _ensure("Cheques in Hand", "Cheques in Hand", "CA-CHQ", role="OTH")
            if created:
                self.stdout.write(f"  [NEW] Cheques in Hand")

        # ── 4. FixedAssetSettings — wire depreciation ledger defaults per retail ─
        with transaction.atomic():
            from accounting.models import FixedAssetSettings

            dep_expense = Ledger.objects.filter(
                ac_name='Depreciation Expense', is_system=True, retail_code__isnull=True
            ).first()
            accum_dep = Ledger.objects.filter(
                ac_name='Accumulated Depreciation', is_system=True, retail_code__isnull=True
            ).first()

            if not dep_expense:
                self.stdout.write(self.style.WARNING(
                    "  [SKIP] 'Depreciation Expense' ledger not found — run wizard company step first."
                ))
            elif not accum_dep:
                self.stdout.write(self.style.WARNING(
                    "  [SKIP] 'Accumulated Depreciation' ledger not found — run wizard company step first."
                ))
            else:
                for retail in RetailMaster.objects.all():
                    fa_settings, created = FixedAssetSettings.objects.get_or_create(retail=retail)
                    update_fields = []
                    if fa_settings.default_depreciation_expense_ldgr_id is None:
                        fa_settings.default_depreciation_expense_ldgr = dep_expense
                        update_fields.append('default_depreciation_expense_ldgr')
                    if fa_settings.default_accum_depreciation_ldgr_id is None:
                        fa_settings.default_accum_depreciation_ldgr = accum_dep
                        update_fields.append('default_accum_depreciation_ldgr')
                    if update_fields:
                        fa_settings.save(update_fields=update_fields)
                        self.stdout.write(self.style.SUCCESS(
                            f"  [FA Settings] Wired depreciation ledgers for: {retail.retail_code}"
                        ))

        self.stdout.write(self.style.SUCCESS("Done seeding system ledgers."))
