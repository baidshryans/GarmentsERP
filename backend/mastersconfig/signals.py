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
]

# ── Operational ledger definitions (company-wide) ────────────────────────────
_OPERATIONAL_LEDGERS = [
    ('discount_ldgr',        'Discount',           'EX-OTH'),
    ('round_off_ldgr',       'Round_Off',          'EX-OTH'),
    ('hallmark_charge_ldgr', 'Hallmark_Charges',   'EX-OTH'),
    ('making_receive_ldgr',  'Making_Receive',     'IN-OTH'),
    ('gold_conversion_ldgr', 'Gold_Conversion',    'IN-OTH'),
    ('carriage_inward_ldgr', 'Carriage_Inward',    'EX-OTH'),
    ('making_charge_purchase_ldgr', 'Making_Charge_Purchase', 'EX-OTH'),
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
    for code in ('EX-OTH', 'IN-OTH'):
        acct_cache[code] = Account.objects.filter(code=code).first()

    update_fields = []
    for field_name, label, acct_code in _OPERATIONAL_LEDGERS:
        ac_name = f"{instance.company_name}_{label}"
        ledger = Ledger.objects.create(
            ac_name=ac_name,
            display_name=f"{instance.company_name} {label.replace('_', ' ')}",
            ac_group=acct_cache.get(acct_code),
            is_system=True,
        )
        LedgerRole.objects.create(ledger=ledger, role='OTH', is_primary=True)
        setattr(instance, field_name, ledger)
        update_fields.append(f"{field_name}_id")

    CompanyMaster.objects.filter(pk=instance.pk).update(
        **{f: getattr(instance, f) for f in update_fields}
    )


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
