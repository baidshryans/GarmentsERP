"""Delete a hand-made entry (owner, 19 Oct 2026): a payment, receipt, contra or journal entered by hand is removed
completely, with its lines, bill allocations and history. An entry a document made goes with that document."""
from django.db import transaction

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services import purge
from core.services.periods import assert_period_open
from ledger.models import Voucher
from ledger.services.settlement import settled_against


def made_by(voucher):
    """The document or production step that made this entry, as (label, url), or None for a hand-made one."""
    from ledger.views import source_link

    link = source_link(voucher)
    if link is not None:
        return f"{link['label']} {link['number']}", link["url"]
    if voucher.source_type:
        return voucher.source_type.split(".")[-1], None
    return None


@transaction.atomic
def delete_voucher(voucher, *, user) -> None:
    voucher = Voucher.objects.select_related("company", "factory").get(pk=voucher.pk)
    assert_factory_access(user, voucher.factory)
    source = made_by(voucher)
    if source is not None or voucher.reverses_id or voucher.reversals.exists():
        name = source[0] if source else "another entry"
        raise BusinessRuleError(f"This entry was made by {name}. Delete that instead.")
    assert_period_open(voucher.company, voucher.factory, voucher.date)
    for other in settled_against(voucher):
        raise BusinessRuleError(f"{other.get_voucher_type_display()} {other.number} is settled against this entry. "
                                f"Delete the {other.get_voucher_type_display().lower()} first.")
    purge.vouchers(Voucher.objects.filter(pk=voucher.pk), lone=True)
