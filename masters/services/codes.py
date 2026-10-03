"""Barcodes and party codes from a counter table (database-neutral, no row locks)."""
from django.db import transaction
from django.db.models import F

from masters.models import CodeCounter

DEFAULTS = {
    "barcode": {"padding": 10, "prefix": ""},
    "party": {"padding": 4, "prefix": "P"},
    "roll": {"padding": 6, "prefix": "R"},
}


@transaction.atomic
def next_code(company, key: str) -> str:
    counter, _ = CodeCounter.objects.get_or_create(company=company, key=key, defaults=DEFAULTS[key])
    CodeCounter.objects.filter(pk=counter.pk).update(next_number=F("next_number") + 1)
    counter.refresh_from_db()
    return f"{counter.prefix}{counter.next_number - 1:0{counter.padding}d}"


def next_barcode(company) -> str:
    """Plain sequential numeric barcode; the length is the counter's `padding` (BAR-01, configurable)."""
    return next_code(company, "barcode")
