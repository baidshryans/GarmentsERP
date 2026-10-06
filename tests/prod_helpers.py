"""Shared set-up for production and job work tests: a style with BOM and route, stock, an order and a lot."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from core.models import Location
from inventory.models import FabricRoll
from inventory.services.opening import OpeningItem, post_opening_stock
from ledger.models import Ledger
from ledger.selectors import ledger_balance
from masters.models import Colour, Material, Product, RouteTemplate, Size, Unit
from masters.services import boms, parties, styles
from production.services import bundles as bundle_service
from production.services import cutting, orders

D = Decimal
DAY = date(2026, 6, 15)


def gl(company, key, factory=None):
    return ledger_balance(Ledger.objects.get(company=company, system_key=key), factory=factory)


def build(company, factory, owner, qty=100, ratios=None, with_stock=True, route="Standard track pant route"):
    """Style JGR-1 (Black, S-XL), a list of 1 zipper per piece (at stitching), standard route, a released order and its lot."""
    black = Colour.objects.get(name="Black")
    sizes = {c: Size.objects.get(code=c) for c in ("S", "M", "L", "XL")}
    style = styles.create_style(company=company, style_no="JGR-1", product=Product.objects.get(code="JGR"), name="Jogger",
                                colours=[black], sizes=list(sizes.values()))
    style.default_route = RouteTemplate.objects.get(name=route)
    style.save()
    fabric = Material.objects.create(code="FAB-1", name="Fleece", kind="fabric", unit=Unit.objects.get(code="KG"))
    zipper = Material.objects.create(code="ZIP-1", name="Zipper", kind="trim", unit=Unit.objects.get(code="PCS"))
    boms.save_bom(style, lines=[boms.BomLineSpec(zipper, D("1"))], user=owner)
    ns = SimpleNamespace(company=company, factory=factory, owner=owner, style=style, black=black, sizes=sizes,
                         fabric=fabric, zipper=zipper)
    if with_stock:
        godown = Location.objects.get(factory=factory, name="Main Godown")
        post_opening_stock(company=company, factory=factory, location=godown, user=owner, entries=[
            OpeningItem(fabric, D("100"), D("200"), vendor_roll_no="A", lot_no="L1"),
            OpeningItem(fabric, D("100"), D("220"), vendor_roll_no="B", lot_no="L1"),
            OpeningItem(zipper, D("1000"), D("2")),
        ])
        ns.roll_a = FabricRoll.objects.get(vendor_roll_no="A")
        ns.roll_b = FabricRoll.objects.get(vendor_roll_no="B")
    ratios = ratios or {sizes["S"]: 1, sizes["M"]: 2, sizes["L"]: 2, sizes["XL"]: 1}
    order = orders.create_order(company=company, factory=factory, date=DAY, user=owner,
                                lines=[orders.OrderLineSpec(style, black, qty, ratios)])
    ns.order = orders.release_order(order, user=owner)
    ns.lot = ns.order.lines.get().lot
    return ns


def cut(ns, bundle_size=25, burnt=("41", "2"), remnant="17", loss=None, estimate=None):
    """Issue 60 kg of roll A (expecting `estimate` pieces from it), cut 100 pieces (17/33/33/17) and make bundles.
    Returns the bundles."""
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=ns.owner, date=DAY, estimated_pieces=estimate)
    entry = cutting.record_cutting(
        lot=ns.lot, user=ns.owner, date=DAY,
        pieces={ns.sizes["S"]: 17, ns.sizes["M"]: 33, ns.sizes["L"]: 33, ns.sizes["XL"]: 17},
        rolls=[cutting.RollUseSpec(ns.roll_a, used=D(burnt[0]), waste=D(burnt[1]), remnant=D(remnant))])
    ns.entry = entry
    return cutting.create_bundles(entry, bundle_size=bundle_size, user=ns.owner, loss=loss)


def step(ns, code):
    return ns.lot.steps.get(process__code=code)


def go(ns, bundles, code, **kw):
    return bundle_service.move_bundles(bundles=bundles, to_step=step(ns, code), user=ns.owner, date=DAY, **kw)


def fabricator(company, name="Sharma Stitching", mobile="9811111111"):
    return parties.create_party(company=company, name=name, mobile=mobile, is_fabricator=True)
