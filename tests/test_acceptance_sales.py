"""BRD acceptance scenarios A4, A5, A6 (section 11.1), each told end to end through the screens and services; the autouse
fixture then checks the books tally and stock reconciles.

A7 (dealer bulk order with partial dispatch) is `test_partial_dispatch_packing_by_carton_..._A7` and A8 (credit note;
the advance is Release 2, E4.8) is `test_credit_note_reverses_gst_..._A8`, both in test_sales.py.
"""
from datetime import date
from decimal import Decimal

from django.test import Client
from django.urls import reverse

from core.models import Location, Role
from masters.models import SKU
from masters.services import parties
from production.services import bundles as bundle_service
from production.services import orders as prod_orders
from sales.models import SaleInvoice, SaleOrder
from sales.services import einvoice, invoices, orders as sale_orders, packing
from sales.services.common import settings_for
from tests import sales_helpers as sh
from tests.conftest import make_user
from tests.prod_helpers import DAY, build, gl
from tests.test_production import finish_route

D = Decimal


def login(user):
    c = Client()
    c.force_login(user)
    return c


def test_A4_scan_barcodes_at_billing_slab_gst_and_einvoice_with_eway_bill(company, factory, owner):
    ns = sh.build(company, factory, owner)
    sh.gst_on(company)
    s = settings_for(company)
    s.einvoice_enabled = True
    s.save()
    ns.far.price_list = sh.price_list(ns, "500")
    ns.far.save()
    c = login(owner)
    sku = ns.sku("Black", "M")
    item = c.get(reverse("sale_scan"), {"code": sku.barcode, "customer": ns.far.pk, "date": "2026-06-15"}).json()["items"][0]
    assert (item["label"], item["rate"]) == ("TP-1 · Black · M", "500.00")            # style, colour, size and rate fill themselves
    r = c.post(reverse("billing"), {"customer": ns.far.pk, "factory": factory.pk, "location": ns.godown.pk, "date": "2026-06-15",
                                     "action": "post", "tax_mode": "auto", "sku": [sku.pk, ns.sku("Black", "S").pk],
                                     "qty": ["60", "40"], "rate": ["", "3000"], "disc": ["", ""]})
    inv = SaleInvoice.objects.get()
    rates = {l.sku.size.code: l.gst_rate for l in inv.lines.all()}
    assert r.status_code == 302 and rates == {"M": D("5.00"), "S": D("18.00")}        # 500 a piece is 5%; 3,000 is 18%
    assert {t.component for t in inv.tax_lines.all()} == {"igst"}                       # Maharashtra buyer: IGST
    assert inv.gst_total == D("1500.00") + D("21600.00")
    c.post(reverse("saleinvoice_detail", args=[inv.pk]), {"action": "einvoice", "vehicle_no": "MH12AB1234", "distance_km": "1400"})
    inv.refresh_from_db()
    assert inv.einvoice_status == "generated" and inv.irn and inv.eway_bill_no and inv.qr_text   # IRN, QR and e-way bill saved
    payload = einvoice.build_payload(inv)
    assert payload["BuyerDtls"]["Gstin"] == sh.BUYER_GSTIN and {i["HsnCd"] for i in payload["ItemList"]} == {"6112"}
    # the same goods to a customer in the same state: CGST + SGST
    sku2 = ns.sku("Navy", "M")
    assert c.get(reverse("sale_scan"), {"code": sku2.barcode, "customer": ns.local.pk}).json()["ok"]
    c.post(reverse("billing"), {"customer": ns.local.pk, "factory": factory.pk, "location": ns.godown.pk, "date": "2026-06-15",
                                "action": "post", "tax_mode": "auto", "sku": [sku2.pk], "qty": ["1"], "rate": ["500"], "disc": [""]})
    local = SaleInvoice.objects.get(customer=ns.local)
    assert {t.component for t in local.tax_lines.all()} == {"cgst", "sgst"}


def test_A5_mto_order_traced_by_number_production_never_sees_the_customer_until_dispatch(company, factory, owner):
    ns = build(company, factory, owner)
    customer = parties.create_party(company=company, name="Dealer Dhillon", mobile="9877700000", is_customer=True, state_code="03")

    def sku_of(size):
        return SKU.objects.get(style=ns.style, colour=ns.black, size=ns.sizes[size])

    order = sale_orders.create_order(
        company=company, factory=factory, customer=customer, date=DAY, user=owner, order_type="mto", due_date=date(2026, 7, 15),
        lines=[sale_orders.OrderLineSpec(sku_of(s), D(q), D("400"), D("0")) for s, q in (("S", "17"), ("M", "33"), ("L", "33"), ("XL", "17"))])
    order = sale_orders.confirm_order(order, user=owner)
    po = prod_orders.release_order(order.production_order, user=owner)
    ns.lot = po.lines.get().lot
    bundles = finish_route(ns)
    # production traces it by the order number and sees specs, never the customer
    planner = make_user("planner2")
    planner.roles.add(Role.objects.get(name="Production Planner"))
    planner.allowed_factories.add(factory)
    pc = login(planner)
    page = pc.get(reverse("production_track"), {"q": order.number}).content.decode()
    assert ns.lot.lot_no in page and customer.name not in page and customer.mobile not in page
    po_page = pc.get(reverse("order_detail", args=[po.pk])).content.decode()
    assert order.number in po_page and customer.name not in po_page
    assert pc.get(reverse("saleorder_detail", args=[order.pk])).status_code == 403
    # sales sees the stage of the pieces at every step
    assert dict(sale_orders.production_stages(order)) == {"Packing": 100}
    assert "Packing: 100" in login(owner).get(reverse("saleorder_detail", args=[order.pk])).content.decode()
    bundle_service.pack_bundles(bundles=bundles, user=owner, date=DAY)
    assert dict(sale_orders.production_stages(order)) == {"Packed, in finished stock": 100}
    # dispatch from the finished goods in the Dispatch area
    dispatch = Location.objects.get(factory=factory, name="Dispatch")
    cartons = [packing.CartonSpec({sku_of("S"): D("17"), sku_of("M"): D("33")}), packing.CartonSpec({sku_of("L"): D("33"), sku_of("XL"): D("17")})]
    pl = packing.finalize_packing(packing.save_packing(order=order, location=dispatch, date=DAY, cartons=cartons, user=owner), user=owner)
    inv = invoices.post_invoice(invoices.invoice_from_packing(pl, user=owner, date=DAY), user=owner)
    assert inv.cogs_total == D("10030.00") and gl(company, "stock_finished", factory) == D("0.00")   # the lot's cost left with the goods
    assert gl(company, "sales_mto", factory) == D("-40000.00")                          # booked to Sales - Made to Order
    assert SaleOrder.objects.get(pk=order.pk).status == "dispatched"


def test_A6_price_list_rate_and_customer_discount_apply_to_a_new_order_and_old_orders_stay(company, factory, owner):
    ns = sh.build(company, factory, owner)
    ns.local.price_list, ns.local.discount_pct = sh.price_list(ns, "450"), D("5")
    ns.local.save()
    c = login(owner)
    black, m = ns.colours["Black"], ns.sizes["M"]

    def place(day):
        c.post(reverse("saleorder_new"), {"customer": ns.local.pk, "factory": factory.pk, "date": day, "order_type": "stock",
                                          "style": ns.style.pk, f"rate_{ns.style.pk}": "", f"disc_{ns.style.pk}": "",
                                          f"q_{ns.style.pk}_{black.pk}_{m.pk}": "20"})
        return SaleOrder.objects.latest("id").lines.get()

    first = place("2026-06-15")
    assert (first.rate, first.discount_pct, first.amount) == (D("450.00"), D("5.00"), D("8550.00"))
    sh.price_list(ns, "480", effective=date(2026, 7, 1))                                 # next month's price list
    second = place("2026-07-05")
    assert (second.rate, second.amount) == (D("480.00"), D("9120.00"))                    # the new order takes the new rate
    first.refresh_from_db()
    assert (first.rate, first.amount) == (D("450.00"), D("8550.00"))                      # the old order is unchanged
