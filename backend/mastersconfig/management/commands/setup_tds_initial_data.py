from django.core.management.base import BaseCommand
from mastersconfig.models import TDSSectionMaster, TCSSectionMaster, RetailMaster
from contacts.models import Ledger, LedgerRole
from accounting.models import Account


TDS_SECTIONS = [
    {
        'section_code': '194C',
        'description': 'Payments to Contractors (Job Work / Karigar)',
        'rate_individual': 1.0,
        'rate_company': 2.0,
        'rate_no_pan': 20.0,
        'threshold_single': 30000,
        'threshold_annual': 100000,
    },
    {
        'section_code': '194H',
        'description': 'Commission or Brokerage',
        'rate_individual': 5.0,
        'rate_company': 5.0,
        'rate_no_pan': 20.0,
        'threshold_single': None,
        'threshold_annual': 15000,
    },
    {
        'section_code': '194I',
        'description': 'Rent (Immovable Property)',
        'rate_individual': 10.0,
        'rate_company': 10.0,
        'rate_no_pan': 20.0,
        'threshold_single': None,
        'threshold_annual': 240000,
    },
    {
        'section_code': '194J',
        'description': 'Professional / Technical Fees',
        'rate_individual': 10.0,
        'rate_company': 10.0,
        'rate_no_pan': 20.0,
        'threshold_single': 30000,
        'threshold_annual': None,
    },
    {
        'section_code': '194Q',
        'description': 'Purchase of Goods (vendor turnover > 50L)',
        'rate_individual': 0.1,
        'rate_company': 0.1,
        'rate_no_pan': 5.0,
        'threshold_single': None,
        'threshold_annual': 5000000,
    },
]

TCS_SECTIONS = [
    {
        'section_code': '206C1H',
        'description': 'Sale of Goods (buyer purchase > 50L)',
        'rate': 0.1,
        'rate_no_pan': 1.0,
        'threshold_annual': 5000000,
    },
]


class Command(BaseCommand):
    help = 'Create initial TDS & TCS section master data and payable ledger accounts'

    def handle(self, *args, **options):
        # 1. Create TDS section records
        for sec_data in TDS_SECTIONS:
            obj, created = TDSSectionMaster.objects.get_or_create(
                section_code=sec_data['section_code'],
                defaults=sec_data,
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created TDS section: {obj.section_code}"))
            else:
                self.stdout.write(f"TDS already exists: {obj.section_code}")

        # 2. Create TCS section records
        for sec_data in TCS_SECTIONS:
            obj, created = TCSSectionMaster.objects.get_or_create(
                section_code=sec_data['section_code'],
                defaults=sec_data,
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created TCS section: {obj.section_code}"))
            else:
                self.stdout.write(f"TCS already exists: {obj.section_code}")

        # 3. Clean up: remove 206C1H from TDS table if it was seeded there previously
        stale = TDSSectionMaster.objects.filter(section_code='206C1H')
        if stale.exists():
            stale.delete()
            self.stdout.write(self.style.WARNING("Removed stale 206C1H from TDS section master"))

        # 4. Resolve account groups for TDS/TCS ledgers
        tds_group = Account.objects.filter(code='CL-DT-TDS').first()
        tcs_group = Account.objects.filter(code='CL-DT-TCS').first()

        # 5. Create TDS Payable ledger accounts per retail
        retails = RetailMaster.objects.all()
        if not retails.exists():
            self.stdout.write(self.style.WARNING("No RetailMaster found — skipping ledger creation"))
            return

        for retail in retails:
            # TDS Payable ledgers
            for sec in TDSSectionMaster.objects.all():
                ledger_name = f"TDS Payable u/s {sec.section_code}"
                ldgr, created = Ledger.objects.get_or_create(
                    ac_name=ledger_name,
                    retail_code=retail,
                    defaults={
                        'display_name': ledger_name,
                        'ac_group': tds_group,
                    }
                )
                if created:
                    LedgerRole.objects.get_or_create(ledger=ldgr, role='EXP', defaults={'is_primary': True})
                    self.stdout.write(self.style.SUCCESS(f"Created ledger: {ledger_name} for {retail.retail_code}"))
                else:
                    # Ensure EXP role exists on existing ledger
                    is_first = not ldgr.roles.exists()
                    LedgerRole.objects.get_or_create(ledger=ldgr, role='EXP', defaults={'is_primary': is_first})
                # Fix group if needed
                if tds_group and ldgr.ac_group != tds_group:
                    ldgr.ac_group = tds_group
                    ldgr.save(update_fields=['ac_group'])
                    self.stdout.write(self.style.WARNING(f"Updated {ledger_name} group"))
                # Link the ledger to the TDS section
                if not sec.ledger:
                    sec.ledger = ldgr
                    sec.save(update_fields=['ledger'])
                    self.stdout.write(self.style.SUCCESS(f"Linked {ledger_name} to section {sec.section_code}"))

            # TCS Payable ledgers
            for sec in TCSSectionMaster.objects.all():
                ledger_name = f"TCS Payable u/s {sec.section_code}"
                ldgr, created = Ledger.objects.get_or_create(
                    ac_name=ledger_name,
                    retail_code=retail,
                    defaults={
                        'display_name': ledger_name,
                        'ac_group': tcs_group,
                    }
                )
                if created:
                    LedgerRole.objects.get_or_create(ledger=ldgr, role='EXP', defaults={'is_primary': True})
                    self.stdout.write(self.style.SUCCESS(f"Created ledger: {ledger_name} for {retail.retail_code}"))
                else:
                    is_first = not ldgr.roles.exists()
                    LedgerRole.objects.get_or_create(ledger=ldgr, role='EXP', defaults={'is_primary': is_first})
                # Fix group if needed
                if tcs_group and ldgr.ac_group != tcs_group:
                    ldgr.ac_group = tcs_group
                    ldgr.save(update_fields=['ac_group'])
                    self.stdout.write(self.style.WARNING(f"Updated {ledger_name} group"))
                if not sec.ledger:
                    sec.ledger = ldgr
                    sec.save(update_fields=['ledger'])
                    self.stdout.write(self.style.SUCCESS(f"Linked {ledger_name} to section {sec.section_code}"))

        self.stdout.write(self.style.SUCCESS("TDS & TCS initial data setup complete."))
