"""Default masters seeded by the setup wizard (BRD SYS-04): units, sizes, colours, products,
processes and two routes. All editable; re-running only adds what is missing."""
from decimal import Decimal

from django.db import transaction

from core.seeding import register_seeder

from .models import Colour, Process, Product, RouteStep, RouteTemplate, Size, Unit, UnitConversion

UNITS = [
    ("PCS", "Pieces", "count"), ("DZN", "Dozen", "count"), ("GRS", "Gross", "count"), ("SET", "Set", "count"),
    ("KG", "Kilogram", "weight"), ("GM", "Gram", "weight"),
    ("MTR", "Metre", "length"), ("CM", "Centimetre", "length"),
]
CONVERSIONS = [("DZN", "PCS", "12"), ("GRS", "PCS", "144"), ("KG", "GM", "1000"), ("MTR", "CM", "100")]
SIZES = ["S", "M", "L", "XL", "XXL", "FREE", "2-4Y", "4-6Y", "6-8Y", "8-10Y", "10-12Y", "12-14Y"]
COLOURS = ["Black", "Navy", "Grey Melange", "Charcoal", "White", "Maroon", "Royal Blue", "Bottle Green"]
PRODUCTS = [("TRK", "Track pant"), ("JGR", "Jogger"), ("TSH", "T-shirt"), ("SET", "Tracksuit")]
# code, name, kind
PROCESSES = [
    ("CUT", "Cutting", "cutting"), ("STITCH", "Stitching", "stitching"), ("EMB", "Embroidery", "value_add"),
    ("PRINT", "Printing", "value_add"), ("PRINTEMB", "Printing and embroidery", "value_add"),
    ("WASH", "Washing", "value_add"), ("DYE", "Dyeing", "value_add"),
    ("IRON", "Ironing and pressing", "finishing"), ("FINISH", "Thread cutting and finishing", "finishing"),
    ("QC", "Quality check", "qc"), ("PACK", "Packing", "packing"),
]
NO_LOSS = {"IRON"}   # pieces out must equal pieces in
# process code, mandatory, assignment
STANDARD_ROUTE = [
    ("CUT", True, "in_house"), ("STITCH", True, "subcontract"), ("EMB", False, "subcontract"),
    ("PRINT", False, "subcontract"), ("WASH", False, "subcontract"), ("IRON", True, "in_house"),
    ("FINISH", True, "in_house"), ("QC", True, "in_house"), ("PACK", True, "in_house"),
]
# Printing and embroidery before stitching; the stitched pieces are checked when they are received from the
# fabricator, so there is no separate QC stage.
PRINT_FIRST_ROUTE = [
    ("CUT", True, "in_house"), ("PRINTEMB", True, "in_house"), ("STITCH", True, "subcontract"),
    ("IRON", True, "in_house"), ("PACK", True, "in_house"),
]
ROUTES = {"Standard track pant route": STANDARD_ROUTE, "Print first, stitch outside route": PRINT_FIRST_ROUTE}


@transaction.atomic
def seed_masters(company=None):
    units = {code: Unit.objects.get_or_create(code=code, defaults={"name": n, "kind": k})[0] for code, n, k in UNITS}
    for a, b, factor in CONVERSIONS:
        UnitConversion.objects.get_or_create(from_unit=units[a], to_unit=units[b], defaults={"factor": Decimal(factor)})
    for i, code in enumerate(SIZES):
        Size.objects.get_or_create(code=code, defaults={"name": code, "sort_order": i})
    for name in COLOURS:
        Colour.objects.get_or_create(name=name)
    for code, name in PRODUCTS:
        Product.objects.get_or_create(code=code, defaults={"name": name})
    processes = {c: Process.objects.get_or_create(code=c, defaults={"name": n, "kind": k, "no_loss": c in NO_LOSS})[0]
                 for c, n, k in PROCESSES}
    for name, steps in ROUTES.items():
        route, created = RouteTemplate.objects.get_or_create(name=name)
        if created:
            for seq, (code, mandatory, assignment) in enumerate(steps, start=1):
                RouteStep.objects.create(
                    template=route, sequence=seq, process=processes[code], is_mandatory=mandatory, assignment=assignment
                )


def register():
    register_seeder("masters", seed_masters, order=30)
