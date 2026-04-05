"""
Management command: migrate_gstin_structure

Migrates existing data to the GSTIN-centric architecture:
  1. Creates GSTINMaster records from each RetailMaster.gstin CharField
  2. Creates operational ledgers (Discount, Round Off, etc.) on each CompanyMaster
  3. Back-fills gstin_ref / branch_ref on existing vouchers

Run once after deploying the new models:
    python manage.py migrate_gstin_structure
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Migrate existing data to GSTIN-centric ledger architecture"

    def handle(self, *args, **options):
        self.stdout.write("=== migrate_gstin_structure starting ===\n")

        with transaction.atomic():
            self._migrate_companies()
            self._migrate_retails()
            self._backfill_voucher_refs()

        self.stdout.write(self.style.SUCCESS("=== migrate_gstin_structure complete ==="))

    # ── Step 1: Ensure each Company has operational ledgers ──────────────────

    def _migrate_companies(self):
        from mastersconfig.models import CompanyMaster
        from contacts.models import Ledger, LedgerRole
        from accounting.models import Account

        _OPERATIONAL = [
            ('discount_ldgr',        'Discount',           'EX-OTH'),
            ('round_off_ldgr',       'Round_Off',          'EX-OTH'),
            ('hallmark_charge_ldgr', 'Hallmark_Charges',   'EX-OTH'),
            ('making_receive_ldgr',  'Making_Receive',     'IN-OTH'),
            ('gold_conversion_ldgr', 'Gold_Conversion',    'IN-OTH'),
            ('carriage_inward_ldgr', 'Carriage_Inward',    'EX-OTH'),
            ('making_charge_purchase_ldgr', 'Making_Charge_Purchase', 'EX-OTH'),
        ]

        acct_cache = {
            'EX-OTH': Account.objects.filter(code='EX-OTH').first(),
            'IN-OTH': Account.objects.filter(code='IN-OTH').first(),
        }

        for company in CompanyMaster.objects.all():
            update = {}
            for field_name, label, acct_code in _OPERATIONAL:
                if getattr(company, f'{field_name}_id'):
                    continue  # already assigned
                ac_name = f"{company.company_name}_{label}"
                ledger, created = Ledger.objects.get_or_create(
                    ac_name=ac_name,
                    defaults={
                        'display_name': f"{company.company_name} {label.replace('_', ' ')}",
                        'mobile1': ac_name,
                        'ac_group': acct_cache.get(acct_code),
                        'is_system': True,
                    },
                )
                if created:
                    LedgerRole.objects.create(ledger=ledger, role='OTH', is_primary=True)
                    self.stdout.write(f"  Created ledger: {ac_name}")
                else:
                    self.stdout.write(f"  Reused ledger: {ac_name}")
                update[f'{field_name}_id'] = ledger.pk

            if update:
                CompanyMaster.objects.filter(pk=company.pk).update(**update)
                self.stdout.write(f"  Updated Company '{company.company_name}' with operational ledgers")

    # ── Step 2: Create GSTINMaster for each RetailMaster ─────────────────────

    def _migrate_retails(self):
        from django.db import connection
        from mastersconfig.models import RetailMaster, GSTINMaster

        # Check if the old gstin column still exists (it was removed by migration 0028)
        # Use PRAGMA for SQLite compatibility
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA table_info(retail_master)")
            columns = [row[1] for row in cursor.fetchall()]
        has_old_gstin = 'gstin' in columns

        if not has_old_gstin:
            self.stdout.write(
                "  Old 'gstin' column not found on retail_master — "
                "no GSTINMaster records will be created from legacy data."
            )
            return

        for retail in RetailMaster.objects.select_related('branch', 'gstin_master').all():
            if retail.gstin_master_id:
                self.stdout.write(f"  Retail '{retail.retail_code}' already has gstin_master — skipping")
                continue

            # Read old gstin value via raw SQL since the ORM field is gone
            from django.db import connection as conn
            with conn.cursor() as cur:
                cur.execute("SELECT gstin FROM retail_master WHERE id=%s", [retail.pk])
                row = cur.fetchone()
            old_gstin = row[0] if row else None

            if not old_gstin:
                self.stdout.write(f"  Retail '{retail.retail_code}' has no GSTIN — skipping")
                continue

            # GSTINMaster post_save signal creates 6 GST ledgers automatically
            gstin_obj, created = GSTINMaster.objects.get_or_create(
                gstin=old_gstin,
                defaults={'branch': retail.branch},
            )
            if created:
                self.stdout.write(f"  Created GSTINMaster: {old_gstin}")
            else:
                self.stdout.write(f"  Reused GSTINMaster: {old_gstin}")

            RetailMaster.objects.filter(pk=retail.pk).update(gstin_master=gstin_obj)

    # ── Step 3: Back-fill gstin_ref / branch_ref on existing vouchers ─────────

    def _backfill_voucher_refs(self):
        from mastersconfig.models import RetailMaster
        from accounting.models import VoucherMain
        from purchase.models import PurchaseVoucher, PurchaseReturn
        from sales.models import SalesVou

        for retail in RetailMaster.objects.select_related('gstin_master', 'branch').all():
            gm = retail.gstin_master
            br = retail.branch

            count = VoucherMain.objects.filter(retail=retail, gstin_ref__isnull=True).update(
                gstin_ref=gm, branch_ref=br
            )
            if count:
                self.stdout.write(f"  VoucherMain: updated {count} records for retail '{retail.retail_code}'")

            count = PurchaseVoucher.objects.filter(retail=retail, gstin_ref__isnull=True).update(
                gstin_ref=gm, branch_ref=br
            )
            if count:
                self.stdout.write(f"  PurchaseVoucher: updated {count} records for retail '{retail.retail_code}'")

            count = PurchaseReturn.objects.filter(retail=retail, gstin_ref__isnull=True).update(
                gstin_ref=gm, branch_ref=br
            )
            if count:
                self.stdout.write(f"  PurchaseReturn: updated {count} records for retail '{retail.retail_code}'")

            count = SalesVou.objects.filter(retail=retail, gstin_ref__isnull=True).update(
                gstin_ref=gm, branch_ref=br
            )
            if count:
                self.stdout.write(f"  SalesVou: updated {count} records for retail '{retail.retail_code}'")
