"""Shared set-up for sales tests: a style with SKUs and finished-goods stock, customers, and the GST switch."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from core.models import Location
from inventory.services.opening import OpeningItem, post_opening_stock
from masters.models import SKU, Colour, CustomerRate, PriceList, PriceListRate, Product, Size
from masters.services import parties, styles
from tax import services as tax_services
from tax.models import HSN

D = Decimal
DAY = date(2026, 6, 15)
GSTIN = "03ABCDE1234F1Z5"
BUYER_GSTIN = "27ABCDE1234F1Z5"


def gst_on(company, factory=None):
    tax_services.set_tax_status(company=company, kind="gst", enabled=True, effective_from=company.books_from,
                                registration_number=GSTIN)


def build(company, factory, owner, stock_qty=100, cost="300", hsn="6112"):
    """Style TP-1 in Black and Navy, sizes S-XL, `stock_qty` pieces of every SKU in the main godown at `cost` each.
    Customers: Punjab Traders (same state, no GSTIN) and Mumbai Mart (Maharashtra, with a GSTIN)."""
    sizes = {c: Size.objects.get(code=c) for c in ("S", "M", "L", "XL")}
    colours = {n: Colour.objects.get(name=n) for n in ("Black", "Navy")}
    style = styles.create_style(company=company, style_no="TP-1", product=Product.objects.get(code="JGR"), name="Track pant",
                                colours=list(colours.values()), sizes=list(sizes.values()), hsn=HSN.objects.get(code=hsn))
    godown = Location.objects.get(factory=factory, name="Main Godown")
    skus = {(c, s): SKU.objects.get(style=style, colour=colours[c], size=sizes[s]) for c in colours for s in sizes}
    if stock_qty:
        post_opening_stock(company=company, factory=factory, location=godown, user=owner,
                           entries=[OpeningItem(sku, D(stock_qty), D(cost)) for sku in skus.values()])
    local = parties.create_party(company=company, name="Punjab Traders", mobile="9811111100", is_customer=True,
                                 state_code="03", credit_days=30)
    far = parties.create_party(company=company, name="Mumbai Mart", mobile="9822222200", is_customer=True,
                               gstin=BUYER_GSTIN, state_code="27", credit_days=15)
    return SimpleNamespace(company=company, factory=factory, owner=owner, style=style, sizes=sizes, colours=colours,
                           skus=skus, sku=lambda c, s: skus[(c, s)], godown=godown, local=local, far=far)


def price_list(ns, rate, min_qty=1, effective=date(2026, 4, 1), name="Wholesale"):
    pl, _ = PriceList.objects.get_or_create(name=name, defaults={"kind": "wholesale"})
    PriceListRate.objects.create(price_list=pl, style=ns.style, min_qty=min_qty, rate=D(rate), effective_from=effective)
    return pl


def customer_rate(ns, party, rate, effective=date(2026, 4, 1)):
    return CustomerRate.objects.create(party=party, style=ns.style, rate=D(rate), effective_from=effective)
