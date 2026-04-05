from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import RetailMaster, BranchMaster
from contacts.models import Ledger, LedgerRole


# ── GST register ledger names per branch ─────────────────────────────────────
_GST_REGISTERS = [
    ('input_cgst',  'Input CGST',  'CA-GST'),   # asset  — GST credit receivable
    ('input_sgst',  'Input SGST',  'CA-GST'),
    ('input_igst',  'Input IGST',  'CA-GST'),
    ('output_cgst', 'Output CGST', 'CL-DT-GST'),  # liability — GST payable
    ('output_sgst', 'Output SGST', 'CL-DT-GST'),
    ('output_igst', 'Output IGST', 'CL-DT-GST'),
]


@receiver(post_save, sender=BranchMaster)
def create_branch_gst_registers(sender, instance, created, **kwargs):
    """
    When a new branch is created, auto-create 6 GST register ledgers
    (INPUT CGST/SGST/IGST + OUTPUT CGST/SGST/IGST) and link them to
    the branch.  All retails under this branch will share these ledgers.
    """
    if not created:
        return

    from accounting.models import Account

    # Pre-fetch account groups for GST ledgers
    acct_cache = {}
    for code in ('CA-GST', 'CL-DT-GST'):
        acct_cache[code] = Account.objects.filter(code=code).first()

    update_fields = []
    for field_name, label, acct_code in _GST_REGISTERS:
        ac_name = f"{instance.branch_code}_{label.replace(' ', '_')}"
        ledger = Ledger.objects.create(
            ac_name=ac_name,
            display_name=f"{instance.branch_name} {label}",
            mobile1=ac_name,
            ac_group=acct_cache.get(acct_code),
        )
        LedgerRole.objects.create(ledger=ledger, role='OTH', is_primary=True)
        setattr(instance, field_name, ledger)
        update_fields.append(f"{field_name}_id")

    # Bulk-save all 6 FK fields in a single UPDATE (avoids re-triggering post_save)
    BranchMaster.objects.filter(pk=instance.pk).update(
        **{f: getattr(instance, f) for f in update_fields}
    )


@receiver(post_save, sender=RetailMaster)
def create_cash_ledger(sender, instance, created, **kwargs):
    """
    When a new retail is created:
    1. Create a Cash-in-Hand ledger and assign it.
    2. Copy the parent branch's GST register ledgers to this retail.
    """
    if not created:
        return

    # ── 1. Cash ledger (existing behaviour) ──────────────────────────────────
    ac_group = None
    try:
        from accounting.models import Account
        ac_group = Account.objects.filter(code='CA-CSH').first()
    except Exception:
        pass

    ledger = Ledger.objects.create(
        ac_name=f"{instance.retail_code}_Cash",
        display_name=f"{instance.retail_code}_Cash",
        mobile1=f"{instance.retail_code}_Cash",
        ac_group=ac_group,
    )
    LedgerRole.objects.create(ledger=ledger, role='CA', is_primary=True)
    instance.cash_ldgr = ledger

    # ── 2. Assign branch GST registers to this retail ────────────────────────
    if instance.branch_id:
        branch = BranchMaster.objects.select_related(
            'input_cgst', 'input_sgst', 'input_igst',
            'output_cgst', 'output_sgst', 'output_igst',
        ).filter(pk=instance.branch_id).first()

        if branch:
            instance.input_cgst  = branch.input_cgst
            instance.input_sgst  = branch.input_sgst
            instance.input_igst  = branch.input_igst
            instance.output_cgst = branch.output_cgst
            instance.output_sgst = branch.output_sgst
            instance.output_igst = branch.output_igst

    instance.save()
