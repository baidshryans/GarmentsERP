from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import RetailMaster, BranchMaster, GSTINMaster, CompanyMaster
from contacts.models import Ledger, LedgerRole


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
_OPERATIONAL_LEDGERS = [
    ('sale_discount_ldgr',          'Sale Discount',          'EXP-IND-MSC'),
    ('discount_ldgr',               'Discount',               'EX-OTH'),
    ('round_off_ldgr',              'Round Off',              'EX-OTH'),
    ('hallmark_charge_ldgr',        'Hallmark Charges',       'EX-OTH'),
    ('making_receive_ldgr',         'Making Receive',         'IN-OTH'),
    ('gold_conversion_ldgr',        'Gold Conversion',        'IN-OTH'),
    ('carriage_inward_ldgr',        'Carriage Inward',        'EX-OTH'),
    ('making_charge_purchase_ldgr', 'Making Charge Purchase', 'EX-OTH'),
]

# ── Trading ledgers (Purchase / Sales accounts, per commodity) ────────────────
# (label, account_code) — created once per company, not stored as FK on company
_TRADING_LEDGERS = [
    # Purchases → EXP-DIR-PUR
    ('Gold Purchase',           'EXP-DIR-PUR'),
    ('Diamond Purchase',        'EXP-DIR-PUR'),
    ('Emerald Purchase',        'EXP-DIR-PUR'),
    ('Ruby Purchase',           'EXP-DIR-PUR'),
    ('Semi Precious Purchase',  'EXP-DIR-PUR'),
    ('Old Gold Purchase',       'EXP-DIR-PUR'),
    ('Standard Bar Purchase',   'EXP-DIR-PUR'),
    ('Other Purchase',          'EXP-DIR-PUR'),
    # Sales → INC-DIR-SAL
    ('Gold Sales',              'INC-DIR-SAL'),
    ('Diamond Sales',           'INC-DIR-SAL'),
    ('Emerald Sales',           'INC-DIR-SAL'),
    ('Ruby Sales',              'INC-DIR-SAL'),
    ('Semi Precious Sales',     'INC-DIR-SAL'),
    ('Standard Bar Sales',      'INC-DIR-SAL'),
    ('Other Sales',             'INC-DIR-SAL'),
]

# ── Misc statutory / asset / expense ledgers ─────────────────────────────────
_MISC_LEDGERS = [
    ('Advance Income Tax',       'CA'),          # Current Assets
    ('Professional Tax (Staff)', 'CL'),          # Current Liabilities
    ('Discount Received',        'INC-IND'),     # Indirect Income
    ('Freight Outward',          'EXP-DIR-FRT'), # Direct Expenses > Freight
    ('Bank Charges',             'EXP-IND-BNK'), # Indirect Expenses > Bank Charges
    ('Interest Received',        'INC-IND'),     # Indirect Income
    ('Interest Paid',            'EXP-IND'),     # Indirect Expenses
    ('Sales Commission',         'EXP-IND'),     # Indirect Expenses
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

    update_fields = []
    for field_name, label, acct_code in _GST_REGISTERS:
        ac_name = f"{instance.gstin}_{label.replace(' ', '_')}"
        ledger = Ledger.objects.create(
            ac_name=ac_name,
            display_name=f"{instance.gstin} {label}",
            ac_group=acct_cache.get(acct_code),
            is_system=True,
        )
        LedgerRole.objects.create(ledger=ledger, role='OTH', is_primary=True)
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
    for code in ('EX-OTH', 'IN-OTH', 'EXP-IND-MSC'):
        acct_cache[code] = Account.objects.filter(code=code).first()

    update_fields = []
    for field_name, label, acct_code in _OPERATIONAL_LEDGERS:
        ledger, _ = Ledger.objects.get_or_create(
            ac_name=label,
            is_system=True,
            defaults={
                'display_name': label,
                'ac_group': acct_cache.get(acct_code),
            },
        )
        LedgerRole.objects.get_or_create(ledger=ledger, role='OTH', defaults={'is_primary': True})
        setattr(instance, field_name, ledger)
        update_fields.append(f"{field_name}_id")

    CompanyMaster.objects.filter(pk=instance.pk).update(
        **{f: getattr(instance, f) for f in update_fields}
    )

    # ── Trading + misc + office equipment ledgers (no FK on CompanyMaster) ──
    extra_codes = {
        'EXP-DIR-PUR', 'INC-DIR-SAL', 'CA', 'CL', 'FA-CE',
        'INC-IND', 'EXP-DIR-FRT', 'EXP-IND-BNK', 'EXP-IND',
    }
    extra_cache = {c: Account.objects.filter(code=c).first() for c in extra_codes}

    def _make(label, code, role='OTH'):
        if Ledger.objects.filter(ac_name=label, is_system=True).exists():
            return
        ldgr = Ledger.objects.create(
            ac_name=label,
            display_name=label,
            ac_group=extra_cache.get(code),
            is_system=True,
        )
        LedgerRole.objects.create(ledger=ldgr, role=role, is_primary=True)

    for label, code in _TRADING_LEDGERS:
        _make(label, code)
    for label, code in _MISC_LEDGERS:
        _make(label, code)
    for label, code in _OFFICE_EQUIPMENT_LEDGERS:
        _make(label, code)


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
    except Exception:
        pass

    ledger = Ledger.objects.create(
        ac_name=f"{instance.retail_code}_Cash",
        display_name=f"{instance.retail_code} Cash",
        ac_group=ac_group,
        is_system=True,
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
    except Exception:
        pass  # Never block retail creation

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
    except Exception:
        pass  # Never let this break retail creation
