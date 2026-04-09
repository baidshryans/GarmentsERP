"""
Signals for the Gold Scheme module.

1. Auto-create a SCHM accounting voucher when a SchemePayment is created.
2. Auto-create the "Scheme Liability" system ledger per retail when first needed.
"""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from global_vars import VoucherType
from .models import SchemePayment


def _get_or_create_scheme_liability_ledger(retail):
    """
    Get or create the system ledger for scheme liabilities.
    This is a Current Liability — money collected from customers under schemes.
    Accounting entry: Dr Cash/Bank → Cr Scheme Liability.
    """
    from contacts.models import Ledger, LedgerRole
    from accounting.models import Account

    ledger_name = "Gold Scheme Liability"
    ledger = Ledger.objects.filter(ac_name=ledger_name, is_system=True).first()

    if not ledger:
        # CL = Current Liabilities
        cl_group = Account.objects.filter(code='CL').first()
        ledger = Ledger.objects.create(
            ac_name=ledger_name,
            display_name=ledger_name,
            ac_group=cl_group,
            is_system=True,
        )
        LedgerRole.objects.get_or_create(ledger=ledger, role='OTH', defaults={'is_primary': True})

    return ledger


@receiver(post_save, sender=SchemePayment)
def create_scheme_voucher(sender, instance, created, **kwargs):
    """
    When a SchemePayment is created, auto-create an accounting voucher:
        Dr  payment_ledger (Cash/Bank)     amount
        Cr  Scheme Liability               amount
    """
    if not created:
        return

    if instance.voucher_id:
        return  # Already linked

    from accounting.models import VoucherMain, VoucherDetail
    from accounting.utils import generate_voucher_no

    payment = instance
    retail = payment.retail
    fiscal_year = payment.fiscal_year or getattr(retail, 'active_fy', None)

    scheme_liability = _get_or_create_scheme_liability_ledger(retail)
    voucher_no = generate_voucher_no(VoucherType.scheme, retail, fiscal_year)

    narration = (
        f"Scheme payment {payment.payment_no} — "
        f"{payment.enrollment.customer.ac_name} — "
        f"{payment.enrollment.scheme.name} (Inst #{payment.installment_number})"
    )

    with transaction.atomic():
        voucher = VoucherMain.objects.create(
            date=payment.date,
            voucher_no=voucher_no,
            narration=narration[:150],
            amount=payment.amount,
            voucher_type=VoucherType.scheme,
            retail=retail,
            fiscal_year=fiscal_year,
        )

        # Debit: Cash/Bank (the payment ledger)
        VoucherDetail.objects.create(
            voucher_main=voucher,
            voucher_no=voucher_no,
            voucher_type=VoucherType.scheme,
            account=payment.payment_ledger,
            debit=payment.amount,
            credit=0,
        )

        # Credit: Scheme Liability
        VoucherDetail.objects.create(
            voucher_main=voucher,
            voucher_no=voucher_no,
            voucher_type=VoucherType.scheme,
            account=scheme_liability,
            debit=0,
            credit=payment.amount,
        )

        # Link the voucher to the payment
        payment.voucher = voucher
        payment.save(update_fields=['voucher'])
