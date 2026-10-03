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


GST_RATES = [Decimal("0"), Decimal("5"), Decimal("12"), Decimal("18")]
# name, section, rate - to be confirmed by the accountant; every row is editable.
TDS_TEMPLATES = [
    ("TDS 194C - individual / HUF (1%)", "194C", Decimal("1")),
    ("TDS 194C - others (2%)", "194C", Decimal("2")),
    ("TDS 194Q - purchase of goods (0.1%)", "194Q", Decimal("0.1")),
]


@transaction.atomic
def seed_tax_templates(company=None):
    from .models import TaxTemplate, TaxTemplateLine

    def make(name, kind, lines, **flags):
        t, created = TaxTemplate.objects.get_or_create(name=name, defaults={"kind": kind, **flags})
        if created:
            for component, rate in lines:
                TaxTemplateLine.objects.create(template=t, component=component, rate=rate)

    for rate in GST_RATES:
        half = rate / 2
        r = f"{rate.normalize():f}"
        make(f"GST {r}% intra-state (CGST + SGST)", "gst", [("cgst", half), ("sgst", half)])
        make(f"GST {r}% inter-state (IGST)", "gst", [("igst", rate)], is_interstate=True)
        make(f"GST {r}% intra-state, reverse charge", "gst", [("cgst", half), ("sgst", half)], is_reverse_charge=True)
        make(f"GST {r}% inter-state, reverse charge", "gst", [("igst", rate)], is_interstate=True, is_reverse_charge=True)
    for name, section, rate in TDS_TEMPLATES:
        make(name, "tds", [("tds", rate)], section=section)


def register_templates():
    register_seeder("tax_templates", seed_tax_templates, order=45)
