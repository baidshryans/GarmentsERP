"""Which rate a customer gets (E4.3, PRC-03). The order of lookup is fixed:

1. the customer's own rate for the style (or its product), 2. the customer's price list with the quantity slab,
3. the last rate this customer was billed for the style. Rates are effective-dated, so old documents are untouched.
"""
from dataclasses import dataclass
from decimal import Decimal

from masters.models import CustomerRate, PriceListRate
from sales.models import SaleInvoiceLine


@dataclass
class Price:
    rate: Decimal
    source: str  # "customer rate", "price list", "last rate"


def resolve(customer, sku, qty, on_date):
    """The suggested rate for one SKU, or None when nothing applies (the user then types it)."""
    style = sku.style
    own = (CustomerRate.objects.filter(party=customer, style=style, effective_from__lte=on_date).order_by("-effective_from").first()
           or CustomerRate.objects.filter(party=customer, product=style.product, effective_from__lte=on_date)
           .order_by("-effective_from").first())
    if own is not None:
        return Price(own.rate, "customer rate")
    if customer.price_list_id:
        rows = PriceListRate.objects.filter(price_list_id=customer.price_list_id, style=style, effective_from__lte=on_date,
                                            min_qty__lte=int(qty))
        rows = [r for r in rows.order_by("-effective_from", "-min_qty") if r.size_id in (None, sku.size_id)]
        if rows:
            # latest effective date first, then the widest slab reached, then a size-specific row over a style-wide one
            best = max(rows, key=lambda r: (r.effective_from, r.min_qty, r.size_id is not None))
            return Price(best.rate, "price list")
    last = (SaleInvoiceLine.objects.filter(invoice__customer=customer, invoice__status="posted", sku__style=style)
            .order_by("-invoice__date", "-id").first())
    if last is not None:
        return Price(last.rate, "last rate")
    return None
