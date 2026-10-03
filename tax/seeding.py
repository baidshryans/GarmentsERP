from datetime import date
from decimal import Decimal

from django.db import transaction

from core.seeding import register_seeder

from .models import HSN, HsnSlab

# Knitted apparel HSN codes used by the business. Editable data; the accountant must confirm.
HSN_CODES = [
    ("6103", "Men's or boys' suits, trousers and shorts, knitted"),
    ("6104", "Women's or girls' suits, trousers and shorts, knitted"),
    ("6109", "T-shirts, singlets and other vests, knitted"),
    ("6110", "Jerseys, pullovers, sweatshirts and hoodies, knitted"),
    ("6112", "Track suits, ski suits and swimwear, knitted"),
]
# Value-based slabs: per-piece value up to 2,500 -> 5%, above -> 18% (in force from 22 Sep 2025).
SLAB_EFFECTIVE = date(2025, 9, 22)
SLABS = [(Decimal("0"), Decimal("2500.00"), Decimal("5.00")), (Decimal("2500.01"), None, Decimal("18.00"))]


@transaction.atomic
def seed_hsn(company=None):
    for code, description in HSN_CODES:
        hsn, created = HSN.objects.get_or_create(code=code, defaults={"description": description})
        if created:
            for lo, hi, rate in SLABS:
                HsnSlab.objects.create(hsn=hsn, value_from=lo, value_to=hi, gst_rate=rate, effective_from=SLAB_EFFECTIVE)


def register():
    register_seeder("hsn", seed_hsn, order=40)
