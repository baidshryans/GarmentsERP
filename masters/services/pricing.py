"""Price lookups (PRC-01 to PRC-07). Rates are effective-dated, so a change affects only documents
dated on or after it; older orders keep the rate they were made at (PRC-06).

Sales (Step 6) combines these in the E4.3 order: customer rate, then price list slab, then last rate.
"""
from django.db.models import Case, IntegerField, Q, Value, When

from masters.models import CustomerRate, PriceListRate


def price_list_rate(price_list, style, size, qty, on_date):
    """Best matching per-piece rate, or None. Size-specific beats all-size; the highest quantity slab
    reached wins; within that the latest effective date on or before `on_date`."""
    rows = PriceListRate.objects.filter(
        price_list=price_list, style=style, effective_from__lte=on_date, min_qty__lte=qty
    ).filter(Q(size=size) | Q(size__isnull=True))
    # Rank explicitly: NULL ordering differs between SQLite and PostgreSQL.
    rows = rows.annotate(
        size_rank=Case(When(size__isnull=False, then=Value(1)), default=Value(0), output_field=IntegerField())
    )
    best = rows.order_by("-size_rank", "-min_qty", "-effective_from").first()
    return best.rate if best else None


def customer_rate(party, style, on_date):
    """Customer-specific rate for the style, else for the style's product category, else None."""
    base = CustomerRate.objects.filter(party=party, effective_from__lte=on_date)
    specific = base.filter(style=style).order_by("-effective_from").first()
    if specific:
        return specific.rate
    by_product = base.filter(product=style.product).order_by("-effective_from").first()
    return by_product.rate if by_product else None
