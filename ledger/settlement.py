"""'Receive payment' and 'Pay' buttons on documents that open a bill on a party's ledger.

The button only opens the Receipt or Payment voucher with a row already set to settle that bill. The voucher
screen and the posting engine still make every decision, so nothing here posts or bypasses a rule.
"""
from decimal import Decimal
from urllib.parse import urlencode

from django.urls import reverse

from .selectors import bill_outstanding

ZERO = Decimal("0.00")


def settlement(user, *, ledger, reference, direction, narration=""):
    """What is still open on this document's bill, and the link to settle it.

    direction "receive": a customer bill (the ledger is debited, so open means a debit balance).
    direction "pay": a vendor or fabricator bill (open means a credit balance).
    Returns {"due", "settled", "url"}; "url" is None when the user may not enter vouchers or nothing is open.
    """
    signed = bill_outstanding(ledger, reference, user=user)
    due = signed if direction == "receive" else -signed
    due = due if due > 0 else ZERO
    url = None
    if due and user.has_screen_perm("ledger.voucher", "create"):
        query = urlencode({"ledger": ledger.pk, "amount": f"{due:.2f}", "ref": reference, "narration": narration})
        url = f"{reverse('voucher_receipt' if direction == 'receive' else 'voucher_payment')}?{query}"
    return {"due": due, "settled": due == 0, "url": url}
