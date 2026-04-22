import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import RetailMaster, BranchMaster, GSTINMaster, CompanyMaster
from contacts.models import Ledger, LedgerRole

logger = logging.getLogger(__name__)


# ── GST register ledger definitions ──────────────────────────────────────────
_GST_REGISTERS = [
    ('input_cgst',  'Input CGST',  'CA-GST'),   # asset  — GST credit receivable
    ('input_sgst',  'Input SGST',  'CA-GST'),
    ('input_igst',  'Input IGST',  'CA-GST'),
    ('output_cgst', 'Output CGST', 'CL-DT-GST'),  # liability — GST payable
    ('output_sgst', 'Output SGST', 'CL-DT-GST'),
    ('output_igst', 'Output IGST', 'CL-DT-GST'),
    # RCM variants — reverse charge mechanism (old gold from unregistered sellers)
    ('input_cgst_rcm',  'Input CGST RCM',  'CA-GST'),
    ('input_sgst_rcm',  'Input SGST RCM',  'CA-GST'),
    ('input_igst_rcm',  'Input IGST RCM',  'CA-GST'),
    ('output_cgst_rcm', 'Output CGST RCM', 'CL-DT-GST'),
    ('output_sgst_rcm', 'Output SGST RCM', 'CL-DT-GST'),
    ('output_igst_rcm', 'Output IGST RCM', 'CL-DT-GST'),
]

# ── Operational ledger definitions (company-wide, stored as FK on CompanyMaster) ─
# (fk_field_name, ledger_label, account_group_code, ledger_role)
_OPERATIONAL_LEDGERS = [
    # sale_discount_ldgr removed — unused FK (no serializer reads it)
    ('discount_ldgr',               'Sales Discount',          'INC-DIR-SAL', 'INC'),
    ('round_off_ldgr',              'Round Off',               'EXP-IND-MSC', 'EXP'),
    ('hallmark_charge_ldgr',        'Hallmark Charges',        'EXP-DIR',     'EXP'),
    ('making_receive_ldgr',         'Making Charge Received',  'INC-DIR-SAL', 'INC'),
    # gold_conversion_ldgr omitted from seeding — assign manually per company
    ('carriage_inward_ldgr',        'Carriage Inward',         'EXP-DIR-FRT', 'EXP'),
    ('making_charge_paid_14k_ldgr', 'Making Charge Paid 14K',  'EXP-DIR-MKG', 'EXP'),
    ('making_charge_paid_18k_ldgr', 'Making Charge Paid 18K',  'EXP-DIR-MKG', 'EXP'),
    ('making_charge_paid_22k_ldgr', 'Making Charge Paid 22K',  'EXP-DIR-MKG', 'EXP'),
    ('making_receive_14k_ldgr',     'Making Charge Received 14K', 'INC-DIR-SAL', 'INC'),
    ('making_receive_18k_ldgr',     'Making Charge Received 18K', 'INC-DIR-SAL', 'INC'),
    ('making_receive_22k_ldgr',     'Making Charge Received 22K', 'INC-DIR-SAL', 'INC'),
]

# ── Trading ledgers (Purchase / Sales accounts, per commodity) ────────────────
# (label, account_code, ledger_role) — created once per company, not stored as FK on company
_TRADING_LEDGERS = [
    # Purchases → EXP-DIR-PUR, role EXP
    ('Gold Purchase',              'EXP-DIR-PUR', 'EXP'),
    ('Standard Bar Purchase',      'EXP-DIR-PUR', 'EXP'),
    ('Ornament Purchase',          'EXP-DIR-PUR', 'EXP'),
    ('Diamond Purchase',           'EXP-DIR-PUR', 'EXP'),
    ('Lab Grown Diamond Purchase', 'EXP-DIR-PUR', 'EXP'),
    ('Emerald Purchase',           'EXP-DIR-PUR', 'EXP'),
    ('Ruby Purchase',              'EXP-DIR-PUR', 'EXP'),
    ('Pearls Purchase',            'EXP-DIR-PUR', 'EXP'),
    ('Semi Precious Purchase',     'EXP-DIR-PUR', 'EXP'),
    ('Multi Sapphire Purchase',    'EXP-DIR-PUR', 'EXP'),
    ('Blue Sapphire Purchase',     'EXP-DIR-PUR', 'EXP'),
    ('Imitation Purchase',         'EXP-DIR-PUR', 'EXP'),
    ('Old Gold Purchase',          'EXP-DIR-PUR', 'EXP'),
    ('Other Purchase',             'EXP-DIR-PUR', 'EXP'),
    # Sales → INC-DIR-SAL, role INC
    ('Gold Sales',                 'INC-DIR-SAL', 'INC'),
    ('Standard Bar Sales',         'INC-DIR-SAL', 'INC'),
    ('Ornament Sales',             'INC-DIR-SAL', 'INC'),
    ('Diamond Sales',              'INC-DIR-SAL', 'INC'),
    ('Lab Grown Diamond Sales',    'INC-DIR-SAL', 'INC'),
    ('Emerald Sales',              'INC-DIR-SAL', 'INC'),
    ('Ruby Sales',                 'INC-DIR-SAL', 'INC'),
    ('Pearls Sales',               'INC-DIR-SAL', 'INC'),
    ('Semi Precious Sales',        'INC-DIR-SAL', 'INC'),
    ('Multi Sapphire Sales',       'INC-DIR-SAL', 'INC'),
    ('Blue Sapphire Sales',        'INC-DIR-SAL', 'INC'),
    ('Imitation Sales',            'INC-DIR-SAL', 'INC'),
    ('Old Gold Sales',             'INC-DIR-SAL', 'INC'),
    ('Other Sales',                'INC-DIR-SAL', 'INC'),
]

# ── Misc statutory / asset / expense ledgers ─────────────────────────────────
_MISC_LEDGERS = [
    ('Advance Income Tax',       'CA'),          # Current Assets
    ('Professional Tax (Staff)', 'CL'),          # Current Liabilities
    ('Discount Received',        'INC-IND'),     # Indirect Income
    ('Freight Outward',          'EXP-DIR-FRT'), # Direct Expenses > Freight
    # Administrative Expenses
    ('Rent',                     'EXP-IND-ADM'),
    ('Electricity & Power',      'EXP-IND-ADM'),
    ('Telephone & Internet',     'EXP-IND-ADM'),
    ('Printing & Stationery',    'EXP-IND-ADM'),
    ('Legal & Professional Fees','EXP-IND-ADM'),
    # Selling & Distribution Expenses
    ('Sales Commission',         'EXP-IND-SND'),
    # Marketing & Advertisement Expenses
    ('Advertisement & Publicity','EXP-IND-MKT'),
    # Employee & HR Expenses
    ('Salary & Wages',           'EXP-IND-HR'),
    # Repairs & Maintenance
    ('Repairs & Maintenance',    'EXP-IND-RPM'),
    # Travel & Conveyance
    ('Travel & Conveyance',      'EXP-IND-TRV'),
    # Bank Charges and Commission
    ('Bank Charges',             'EXP-IND-FIN'),
    ('Interest Paid',            'EXP-IND-FIN'),
    # Compliance & Regulatory Expenses
    ('Audit Fees',               'EXP-IND-CMP'),
    # Insurance Expenses
    ('Insurance',                'EXP-IND-INS'),
    # Miscellaneous Expenses
    ('Miscellaneous Expenses',   'EXP-IND-MSC'),

    ('Interest Received',        'INC-IND'),     # Indirect Income

    # ── HR / Payroll ledgers ─────────────────────────────────────────────────
    ('Employee Payable',         'CL'),          # Net salary payable to employees
    ('Provident Fund Payable',   'CL'),          # PF liability (employee + employer)
    ('ESI Payable',              'CL'),          # ESI liability (employee + employer)
    ('Professional Tax Payable', 'CL-DT'),       # PT deducted from employees
    ('TDS on Salary Payable',    'CL-DT-TDS'),   # TDS deducted from employees

    # ── Gold Scheme ──────────────────────────────────────────────────────────
    ('Gold Scheme Liability',    'CL'),          # Money collected under gold schemes

    # ── Fixed Asset / Depreciation ───────────────────────────────────────────
    ('Depreciation Expense',        'EXP-IND'),     # P&L charge for depreciation
    ('Accumulated Depreciation',    'FA-AD'),        # Contra-asset: total depreciation to date

    # ── Capital / Owner ──────────────────────────────────────────────────────
    ("Proprietor's Drawings",    'CAP-OWN'),     # Owner cash withdrawals from business

    # ── Tax ──────────────────────────────────────────────────────────────────
    ('Income Tax Payable',       'CL-DT'),       # Current-year income tax liability (Advance Income Tax is the asset side)

    # ── Adjustments ──────────────────────────────────────────────────────────
    ('Bad Debts Written Off',    'EXP-IND-ADM'), # Year-end write-off of uncollectable customer balances

    # ── General / Other ──────────────────────────────────────────────────────
    ('Customer Advance',         'CL'),          # Advance received on customer orders
    ('Suspense Account',         'CL'),          # Temporary parking for unmatched entries
    ('Opening Balance Equity',   'CAP-OWN'),     # Plug account for trial balance during setup
    ('Closing Stock',            'CA-STK'),      # Inventory asset — value injected from inventory module
    ('Stock-in-Transit',         'CA-STK'),      # Inventory moving between retail locations
]

# ── Office Equipment fixed-asset ledgers ──────────────────────────────────────
_OFFICE_EQUIPMENT_LEDGERS = [
    ('Mobile',           'FA-CE'),
    ('Computer',         'FA-CE'),
    ('Camera',           'FA-CE'),
    ('Printer',          'FA-CE'),
    ('Weighing Machine', 'FA-CE'),
]


@receiver(post_save, sender=GSTINMaster)
def create_gstin_gst_registers(sender, instance, created, **kwargs):
    """
    When a new GSTINMaster is created, auto-create 6 GST register ledgers
    (Input/Output CGST/SGST/IGST) and link them to the GSTINMaster.
    """
    if not created:
        return

    from accounting.models import Account

    acct_cache = {}
    for code in ('CA-GST', 'CL-DT-GST'):
        acct_cache[code] = Account.objects.filter(code=code).first()

    # Bulk-create GST register ledgers
    ledger_specs = []
    for field_name, label, acct_code in _GST_REGISTERS:
        ac_name = f"{instance.gstin}_{label.replace(' ', '_')}"
        ledger_specs.append((field_name, Ledger(
            ac_name=ac_name,
            display_name=f"{instance.gstin} {label}",
            ac_group=acct_cache.get(acct_code),
            is_system=True,
        )))

    new_ledgers = Ledger.objects.bulk_create([spec[1] for spec in ledger_specs])
    LedgerRole.objects.bulk_create([
        LedgerRole(ledger=ldgr, role='OTH', is_primary=True)
        for ldgr in new_ledgers
    ])

    update_fields = []
    for (field_name, _), ledger in zip(ledger_specs, new_ledgers):
        setattr(instance, field_name, ledger)
        update_fields.append(f"{field_name}_id")

    GSTINMaster.objects.filter(pk=instance.pk).update(
        **{f: getattr(instance, f) for f in update_fields}
    )


@receiver(post_save, sender=CompanyMaster)
def create_company_operational_ledgers(sender, instance, created, **kwargs):
    """
    When a new CompanyMaster is created, auto-create 5 operational ledgers
    (Discount, Round Off, Hallmark Charges, Making Receive, Gold Conversion).
    """
    if not created:
        return

    from accounting.models import Account

    acct_cache = {}
    for code in ('INC-DIR-SAL', 'EXP-IND', 'EXP-IND-MSC', 'EXP-DIR', 'EXP-DIR-FRT', 'EXP-DIR-MKG'):
        acct_cache[code] = Account.objects.filter(code=code).first()

    update_fields = []
    for field_name, label, acct_code, role in _OPERATIONAL_LEDGERS:
        ledger, _ = Ledger.objects.get_or_create(
            ac_name=label,
            is_system=True,
            defaults={
                'display_name': label,
                'ac_group': acct_cache.get(acct_code),
            },
        )
        LedgerRole.objects.get_or_create(ledger=ledger, role=role, defaults={'is_primary': True})
        setattr(instance, field_name, ledger)
        update_fields.append(f"{field_name}_id")

    CompanyMaster.objects.filter(pk=instance.pk).update(
        **{f: getattr(instance, f) for f in update_fields}
    )

    # ── Trading + misc + office equipment ledgers (no FK on CompanyMaster) ──
    extra_codes = {
        'EXP-DIR-PUR', 'INC-DIR-SAL', 'CA', 'CL', 'FA-CE',
        'INC-IND', 'EXP-DIR-FRT', 'EXP-IND',
        'EXP-IND-ADM', 'EXP-IND-SND', 'EXP-IND-MKT', 'EXP-IND-HR',
        'EXP-IND-RPM', 'EXP-IND-TRV', 'EXP-IND-FIN', 'EXP-IND-CMP',
        'EXP-IND-INS', 'EXP-IND-MSC',
        'CL-DT', 'CL-DT-TDS',
        'FA-AD', 'CAP-RES', 'CA-STK', 'CA-CSH',
    }
    extra_cache = {c: Account.objects.filter(code=c).first() for c in extra_codes}

    # Collect all ledgers to create, skipping any that already exist
    all_entries = (
        [(l, c, r) for l, c, r in _TRADING_LEDGERS] +
        [(l, c, 'OTH') for l, c in _MISC_LEDGERS] +
        [(l, c, 'OTH') for l, c in _OFFICE_EQUIPMENT_LEDGERS]
    )
    existing_names = set(
        Ledger.objects.filter(
            ac_name__in=[e[0] for e in all_entries], is_system=True
        ).values_list('ac_name', flat=True)
    )
    to_create = [(l, c, r) for l, c, r in all_entries if l not in existing_names]

    if to_create:
        new_ledgers = Ledger.objects.bulk_create([
            Ledger(
                ac_name=label,
                display_name=label,
                ac_group=extra_cache.get(code),
                is_system=True,
            )
            for label, code, _role in to_create
        ])
        LedgerRole.objects.bulk_create([
            LedgerRole(ledger=ldgr, role=role, is_primary=True)
            for ldgr, (_, _, role) in zip(new_ledgers, to_create)
        ])


@receiver(post_save, sender=RetailMaster)
def create_retail_ledgers(sender, instance, created, **kwargs):
    """
    When a new retail is created, auto-create a Cash-in-Hand ledger and assign it.
    """
    if not created:
        return

    ac_group = None
    try:
        from accounting.models import Account
        ac_group = Account.objects.filter(code='CA-CSH').first()
    except (ImportError, DatabaseError):
        # Accounting module unavailable or DB error — ledger created without a group
        pass

    ledger = Ledger.objects.create(
        ac_name=f"{instance.retail_code}_Cash",
        display_name=f"{instance.retail_code} Cash",
        ac_group=ac_group,
        is_system=True,
        retail_code=instance,
    )
    LedgerRole.objects.create(ledger=ledger, role='CA', is_primary=True)

    RetailMaster.objects.filter(pk=instance.pk).update(cash_ldgr_id=ledger.pk)

    # Auto-create TDS/TCS payable ledgers if sections are already seeded
    try:
        from mastersconfig.models import TDSSectionMaster, TCSSectionMaster
        from accounting.models import Account

        tds_group = Account.objects.filter(code='CL-DT-TDS').first()
        tcs_group = Account.objects.filter(code='CL-DT-TCS').first()

        for sec in TDSSectionMaster.objects.all():
            ledger_name = f"TDS Payable u/s {sec.section_code}"
            ldgr, created = Ledger.objects.get_or_create(
                ac_name=ledger_name,
                retail_code=instance,
                defaults={'display_name': ledger_name, 'ac_group': tds_group, 'is_system': True},
            )
            if created:
                LedgerRole.objects.get_or_create(ledger=ldgr, role='EXP', defaults={'is_primary': True})
            if not sec.ledger:
                sec.ledger = ldgr
                sec.save(update_fields=['ledger'])

        for sec in TCSSectionMaster.objects.all():
            ledger_name = f"TCS Payable u/s {sec.section_code}"
            ldgr, created = Ledger.objects.get_or_create(
                ac_name=ledger_name,
                retail_code=instance,
                defaults={'display_name': ledger_name, 'ac_group': tcs_group, 'is_system': True},
            )
            if created:
                LedgerRole.objects.get_or_create(ledger=ldgr, role='EXP', defaults={'is_primary': True})
            if not sec.ledger:
                sec.ledger = ldgr
                sec.save(update_fields=['ledger'])
    except (ImportError, DatabaseError, ObjectDoesNotExist):
        # Never block retail creation; TDS/TCS ledgers can be seeded manually later
        pass

    # Auto-create FixedAssetSettings and wire the two depreciation ledger defaults
    try:
        from accounting.models import FixedAssetSettings
        dep_expense = Ledger.objects.filter(
            ac_name='Depreciation Expense', is_system=True, retail_code__isnull=True
        ).first()
        accum_dep = Ledger.objects.filter(
            ac_name='Accumulated Depreciation', is_system=True, retail_code__isnull=True
        ).first()
        FixedAssetSettings.objects.get_or_create(
            retail=instance,
            defaults={
                'default_depreciation_expense_ldgr': dep_expense,
                'default_accum_depreciation_ldgr':   accum_dep,
            },
        )
    except (ImportError, DatabaseError, ObjectDoesNotExist):
        # Never block retail creation; FA settings can be configured manually later
        pass

    # Auto-assign every new retail to all superusers so they can always switch
    # between retails regardless of when the retail was created.
    try:
        from django.contrib.auth import get_user_model
        from contacts.models import UserLocation
        User = get_user_model()
        for superuser in User.objects.filter(is_superuser=True, is_active=True):
            ul, _ = UserLocation.objects.get_or_create(user=superuser)
            ul.location.add(instance)
            if ul.default_location is None:
                ul.default_location = instance
                ul.save(update_fields=['default_location'])
    except (ImportError, DatabaseError, ObjectDoesNotExist):
        # Never let this break retail creation; superuser access can be assigned manually
        pass
