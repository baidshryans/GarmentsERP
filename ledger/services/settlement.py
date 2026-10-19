"""Which entries settle a bill (ACC-14), so a bill is never deleted while a payment still points at it."""
from ledger.models import BillAllocation, Voucher


def settled_against(voucher) -> list:
    """Posted vouchers that settle a bill this voucher opened: an "against" allocation on the same ledger and with
    the same reference as one of its "new" allocations. Entries that were reversed, and reversals, do not count."""
    opened = list(BillAllocation.objects.filter(line__voucher=voucher, ref_type=BillAllocation.RefType.NEW)
                  .values_list("line__ledger_id", "reference"))
    out = []
    for ledger_id, reference in opened:
        qs = (Voucher.objects.filter(status=Voucher.Status.POSTED, reverses__isnull=True, reversals__isnull=True,
                                     lines__ledger_id=ledger_id, lines__allocations__ref_type=BillAllocation.RefType.AGAINST,
                                     lines__allocations__reference=reference)
              .exclude(pk=voucher.pk).distinct().order_by("date", "pk"))
        out += [v for v in qs if v not in out]
    return out
