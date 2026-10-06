"""Sales screens end to end through the HTTP layer: grid order, scan, billing, packing and labels, invoice, e-invoice,
credit note, permissions and factory scoping."""
from datetime import date
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from core.models import Role
from sales.models import Carton, PackingList, SaleCreditNote, SaleInvoice, SaleOrder
from sales.services import orders, packing
from sales.services.common import settings_for
from tests import sales_helpers as h
from tests.conftest import make_user
from tests.test_sales import confirmed_order, pack, quick_invoice

D = Decimal
DAY = h.DAY


@pytest.fixture
def ns(company, factory, owner):
    return h.build(company, factory, owner)


def login(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def owner_c(owner):
    return login(owner)


def user_with(role_name, username, factory):
    u = make_user(username)
    u.roles.add(Role.objects.get(name=role_name))
    u.allowed_factories.add(factory)
    return u


def test_every_sales_screen_opens_for_the_owner(ns, owner_c):
    inv = quick_invoice(ns)
    order = confirmed_order(ns)
    p = pack(ns, order, [{"S": "5"}])
    for name, args in [("sales_settings", []), ("saleorder_list", []), ("saleorder_new", []), ("saleorder_pending", []),
                       ("saleorder_detail", [order.pk]), ("saleorder_edit", [orders.create_order(
                           company=ns.company, factory=ns.factory, customer=ns.local, date=DAY, user=ns.owner,
                           lines=[orders.OrderLineSpec(ns.sku("Black", "M"), D("1"), D("500"))]).pk]),
                       ("packing_list", []), ("packing_detail", [p.pk]), ("packing_print", [p.pk]), ("carton_labels", [p.pk]),
                       ("billing", []), ("saleinvoice_list", []), ("saleinvoice_detail", [inv.pk]), ("saleinvoice_print", [inv.pk]),
                       ("salecn_new", [inv.pk]), ("salecn_list", [])]:
        r = owner_c.get(reverse(name, args=args))
        assert r.status_code == 200, name
    assert owner_c.get(reverse("packing_new", args=[order.pk])).status_code == 200


def test_the_grid_shows_colours_as_rows_sizes_as_columns_and_saves_an_order(ns, owner_c, company):
    ns.local.price_list = h.price_list(ns, "450")
    ns.local.save()
    r = owner_c.get(reverse("saleorder_grid"), {"style": ns.style.pk, "customer": ns.local.pk, "date": "2026-06-15"})
    html = r.content.decode()
    assert r.status_code == 200 and 'value="450.00"' in html and "price list" in html
    assert html.count('class="cell"') == 8                                           # 2 colours x 4 sizes
    black, m, s = ns.colours["Black"], ns.sizes["M"], ns.sizes["S"]
    navy = ns.colours["Navy"]
    r = owner_c.post(reverse("saleorder_new"), {
        "customer": ns.local.pk, "factory": ns.factory.pk, "date": "2026-06-15", "order_type": "stock", "style": ns.style.pk,
        f"rate_{ns.style.pk}": "", f"disc_{ns.style.pk}": "",
        f"q_{ns.style.pk}_{black.pk}_{s.pk}": "10", f"q_{ns.style.pk}_{black.pk}_{m.pk}": "20", f"q_{ns.style.pk}_{navy.pk}_{m.pk}": "5"})
    order = SaleOrder.objects.get()
    assert r.status_code == 302 and r["Location"] == reverse("saleorder_detail", args=[order.pk])
    assert order.total_qty == D("35") and {l.rate for l in order.lines.all()} == {D("450.00")}      # rate from the price list
    r = owner_c.post(reverse("saleorder_detail", args=[order.pk]), {"action": "confirm"}, follow=True)
    assert SaleOrder.objects.get().status == "confirmed" and "confirmed" in r.content.decode()
    r = owner_c.get(reverse("saleorder_edit", args=[order.pk]))
    assert r.status_code == 302                                                       # confirmed: no more editing


def test_the_order_form_offers_every_field_and_the_style_picker(ns, owner_c):
    html = owner_c.get(reverse("saleorder_new")).content.decode()
    for name in ("customer", "date", "due_date", "order_type", "remarks", "style_pick"):
        assert f'name="{name}"' in html, name
    assert reverse("saleorder_grid") in html and ns.style.style_no in html
    assert 'name="date" type="date" value=""' not in html                              # the date starts on today


def test_an_order_with_a_bad_cell_shows_the_error_and_keeps_what_was_typed(ns, owner_c):
    black, m = ns.colours["Black"], ns.sizes["M"]
    r = owner_c.post(reverse("saleorder_new"), {
        "customer": ns.local.pk, "factory": ns.factory.pk, "date": "2026-06-15", "order_type": "stock", "style": ns.style.pk,
        f"rate_{ns.style.pk}": "500", f"disc_{ns.style.pk}": "", f"q_{ns.style.pk}_{black.pk}_{m.pk}": "2.5"})
    html = r.content.decode()
    assert r.status_code == 200 and "whole pieces" in html and 'value="2.5"' in html and not SaleOrder.objects.exists()


def test_production_never_sees_the_customer_of_a_made_to_order_order_A5(ns, owner_c, company, factory):
    black, m = ns.colours["Black"], ns.sizes["M"]
    owner_c.post(reverse("saleorder_new"), {
        "customer": ns.far.pk, "factory": ns.factory.pk, "date": "2026-06-15", "order_type": "mto", "style": ns.style.pk,
        f"rate_{ns.style.pk}": "520", f"disc_{ns.style.pk}": "0", f"q_{ns.style.pk}_{black.pk}_{m.pk}": "40"})
    order = SaleOrder.objects.get()
    owner_c.post(reverse("saleorder_detail", args=[order.pk]), {"action": "confirm"})
    order.refresh_from_db()
    planner = user_with("Production Planner", "planner", factory)
    c = login(planner)
    assert c.get(reverse("saleorder_list")).status_code == 403                          # no sales screens at all
    assert c.get(reverse("saleorder_detail", args=[order.pk])).status_code == 403
    r = c.get(reverse("order_detail", args=[order.production_order_id]))
    html = r.content.decode()
    assert r.status_code == 200 and order.number in html
    assert ns.far.name not in html and ns.far.mobile not in html and h.BUYER_GSTIN not in html


def test_scan_adds_a_piece_at_the_customers_rate_and_rejects_unknown_codes_A4(ns, owner_c):
    ns.local.price_list = h.price_list(ns, "450")
    ns.local.discount_pct = D("5")
    ns.local.save()
    sku = ns.sku("Black", "M")
    r = owner_c.get(reverse("sale_scan"), {"code": sku.barcode, "customer": ns.local.pk, "date": "2026-06-15"}).json()
    assert r["ok"] and r["items"] == [{"sku": sku.pk, "label": "TP-1 · Black · M", "qty": 1, "rate": "450.00",
                                         "source": "price list", "disc": "5.00"}]
    bad = owner_c.get(reverse("sale_scan"), {"code": "0000000000", "customer": ns.local.pk}).json()
    assert bad == {"ok": False, "error": "Unknown barcode 0000000000."}
    assert owner_c.get(reverse("sale_scan"), {"code": ""}).json()["ok"] is False
    # a carton label brings in everything in the carton
    order = confirmed_order(ns)
    p = pack(ns, order, [{"S": "10", "M": "5"}])
    code = Carton.objects.get(packing=p).code
    r = owner_c.get(reverse("sale_scan"), {"code": code, "customer": ns.local.pk, "date": "2026-06-15"}).json()
    assert r["ok"] and sorted(i["qty"] for i in r["items"]) == [5, 10]


def test_billing_posts_an_invoice_with_gst_for_scanned_goods_A4(ns, owner_c, company, factory):
    h.gst_on(company)
    ns.local.price_list = h.price_list(ns, "500")
    ns.local.save()
    sku = ns.sku("Black", "M")
    r = owner_c.post(reverse("billing"), {
        "customer": ns.local.pk, "factory": factory.pk, "location": ns.godown.pk, "date": "2026-06-15", "action": "post",
        "tax_mode": "auto", "sku": [sku.pk], "qty": ["12"], "rate": [""], "disc": [""]})
    inv = SaleInvoice.objects.get()
    assert r.status_code == 302 and inv.status == "posted" and inv.subtotal == D("6000.00") and inv.gst_total == D("300.00")
    page = owner_c.get(reverse("saleinvoice_detail", args=[inv.pk])).content.decode()
    assert "CGST" in page and "SGST" in page and "IGST" not in page
    printed = owner_c.get(reverse("saleinvoice_print", args=[inv.pk])).content.decode()
    assert "TAX INVOICE" in printed and inv.number in printed and "6300.00" in printed


def test_billing_can_waive_gst_on_one_invoice_and_needs_a_reason(ns, owner_c, company, factory):
    h.gst_on(company)
    sku = ns.sku("Black", "M")
    base = {"customer": ns.local.pk, "factory": factory.pk, "location": ns.godown.pk, "date": "2026-06-15", "action": "post",
            "tax_mode": "none", "sku": [sku.pk], "qty": ["2"], "rate": ["500"], "disc": ["0"]}
    r = owner_c.post(reverse("billing"), base)
    assert r.status_code == 200 and "reason for issuing this bill without GST" in r.content.decode() and not SaleInvoice.objects.exists()
    r = owner_c.post(reverse("billing"), {**base, "tax_note": "Export under LUT"})
    inv = SaleInvoice.objects.get()
    assert r.status_code == 302 and inv.gst_total == 0 and inv.total == D("1000.00")
    assert "No GST charged: Export under LUT" in owner_c.get(reverse("saleinvoice_print", args=[inv.pk])).content.decode()


def test_enter_in_a_billing_field_saves_a_draft_and_does_not_post(ns, owner_c, factory):
    html = owner_c.get(reverse("billing")).content.decode()
    assert html.index('name="action" value="draft"') < html.index('name="action" value="post"')   # the default submit is the safe one
    assert 'hidden tabindex="-1" name="action" value="draft"' in html


def test_draft_invoice_gst_can_be_changed_before_posting(ns, owner_c, company):
    h.gst_on(company)
    inv = quick_invoice(ns, post=False)
    assert inv.gst_total == D("250.00")
    r = owner_c.post(reverse("saleinvoice_detail", args=[inv.pk]), {"action": "tax", "tax_mode": "none", "tax_note": "Sample, not for sale"})
    inv.refresh_from_db()
    assert r.status_code == 302 and inv.tax_mode == "none" and inv.gst_total == 0 and inv.total == D("5000.00")
    owner_c.post(reverse("saleinvoice_detail", args=[inv.pk]), {"action": "tax", "tax_mode": "auto"})
    inv.refresh_from_db()
    assert inv.tax_mode == "auto" and inv.gst_total == D("250.00")
    owner_c.post(reverse("saleinvoice_detail", args=[inv.pk]), {"action": "post"})
    inv.refresh_from_db()
    assert inv.status == "posted"
    r = owner_c.post(reverse("saleinvoice_detail", args=[inv.pk]), {"action": "tax", "tax_mode": "none", "tax_note": "late"}, follow=True)
    inv.refresh_from_db()
    assert inv.gst_total == D("250.00") and "Only a draft bill can be edited" in r.content.decode()


def test_packing_screens_create_cartons_labels_and_an_invoice_for_the_packed_pieces_A7(ns, owner_c, factory):
    order = confirmed_order(ns)
    s_id, m_id = ns.sku("Black", "S").pk, ns.sku("Black", "M").pk
    r = owner_c.post(reverse("packing_new", args=[order.pk]), {
        "n": "2", "location": ns.godown.pk, "date": "2026-06-15", "lr_no": "LR-9", "vehicle_no": "pb 08 x 1",
        f"c1_{s_id}": "10", f"c1_{m_id}": "5", f"c2_{s_id}": "5"})
    p = PackingList.objects.get()
    assert r.status_code == 302 and p.status == "draft" and p.total_qty == D("20")
    r = owner_c.post(reverse("packing_new", args=[order.pk]), {"n": "2", "add_carton": "1", "location": ns.godown.pk,
                                                                "date": "2026-06-15", f"c1_{s_id}": "7"})
    assert r.status_code == 200 and 'name="c3_%d"' % s_id in r.content.decode() and 'value="7"' in r.content.decode()
    owner_c.post(reverse("packing_detail", args=[p.pk]), {"action": "finalize"})
    p.refresh_from_db()
    assert p.status == "packed"
    labels = owner_c.get(reverse("carton_labels", args=[p.pk])).content.decode()
    assert "Carton 1 of 2" in labels and "Carton 2 of 2" in labels and "<svg" in labels and Carton.objects.first().code in labels
    assert "Punjab Traders" in labels
    sheet = owner_c.get(reverse("packing_print", args=[p.pk])).content.decode()
    assert "PACKING LIST" in sheet and "Carton 2" in sheet
    r = owner_c.post(reverse("packing_detail", args=[p.pk]), {"action": "invoice"})
    inv = SaleInvoice.objects.get()
    assert r.status_code == 302 and r["Location"] == reverse("saleinvoice_detail", args=[inv.pk]) and inv.lines.count() == 2
    owner_c.post(reverse("saleinvoice_detail", args=[inv.pk]), {"action": "post"})
    order.refresh_from_db()
    assert order.status == "partly_dispatched"
    book = owner_c.get(reverse("saleorder_pending")).content.decode()
    assert order.number in book and "<strong>40</strong>" in book                       # 60 ordered, 20 dispatched


def test_einvoice_screen_generates_and_shows_the_numbers_and_prints_the_qr(ns, owner_c, company):
    h.gst_on(company)
    s = settings_for(company)
    s.einvoice_enabled = True
    s.save()
    inv = quick_invoice(ns, ns.far, qty="90", rate="600")
    page = owner_c.get(reverse("saleinvoice_detail", args=[inv.pk])).content.decode()
    assert "Send e-invoice and e-way bill" in page
    r = owner_c.post(reverse("saleinvoice_detail", args=[inv.pk]), {"action": "einvoice"}, follow=True)
    assert "e-way bill" in r.content.decode().lower() and SaleInvoice.objects.get().irn == ""     # needs a vehicle: refused
    owner_c.post(reverse("saleinvoice_detail", args=[inv.pk]), {"action": "einvoice", "vehicle_no": "HR55X1234", "distance_km": "300"})
    inv.refresh_from_db()
    assert inv.einvoice_status == "generated" and inv.eway_bill_no
    printed = owner_c.get(reverse("saleinvoice_print", args=[inv.pk])).content.decode()
    assert inv.irn in printed and inv.eway_bill_no in printed and "<svg" in printed
    local = quick_invoice(ns, ns.local)
    assert "Send e-invoice" not in owner_c.get(reverse("saleinvoice_detail", args=[local.pk])).content.decode()


def test_credit_note_screens_return_goods_and_reduce_the_outstanding_A8(ns, owner_c, company):
    h.gst_on(company)
    inv = quick_invoice(ns, qty="10", rate="500")
    line = inv.lines.get()
    r = owner_c.post(reverse("salecn_new", args=[inv.pk]), {"date": "2026-06-20", "location": ns.godown.pk, "reason": "Torn",
                                                            f"qty_{line.pk}": "3"})
    note = SaleCreditNote.objects.get()
    assert r.status_code == 302 and note.total == D("1575.00") and note.status == "draft"
    page = owner_c.get(reverse("salecn_detail", args=[note.pk])).content.decode()
    assert "CGST" in page and "1575.00" in page
    owner_c.post(reverse("salecn_detail", args=[note.pk]), {"action": "post"})
    note.refresh_from_db()
    assert note.status == "posted" and note.number.startswith("SCN/")
    r = owner_c.post(reverse("salecn_new", args=[inv.pk]), {"date": "2026-06-20", "location": ns.godown.pk, "reason": "Too many",
                                                            f"qty_{line.pk}": "8"})
    assert r.status_code == 200 and "only 7" in r.content.decode()
    owner_c.post(reverse("salecn_detail", args=[note.pk]), {"action": "cancel", "reason": "mistake"})
    note.refresh_from_db()
    assert note.status == "cancelled"


def test_roles_and_scoping_on_the_sales_screens(ns, company, factory, factory2, owner):
    inv = quick_invoice(ns, post=False)
    clerk = user_with("Billing Clerk", "clerk", factory)
    c = login(clerk)
    assert c.get(reverse("saleinvoice_list")).status_code == 200 and c.get(reverse("billing")).status_code == 200
    assert c.get(reverse("salecn_list")).status_code == 200
    r = c.post(reverse("saleinvoice_detail", args=[inv.pk]), {"action": "cancel", "reason": "x"})
    assert r.status_code == 403                                                          # cancelling is not a clerk's right
    sales_person = login(user_with("Salesperson", "sp", factory))
    assert sales_person.get(reverse("saleorder_new")).status_code == 200
    assert sales_person.get(reverse("saleinvoice_list")).status_code == 403
    assert sales_person.get(reverse("billing")).status_code == 403
    assert sales_person.get(reverse("sale_scan"), {"code": "x"}).status_code == 403
    stranger = login(user_with("Billing Clerk", "other", factory2))
    assert stranger.get(reverse("saleinvoice_detail", args=[inv.pk])).status_code == 404
    assert "No bills yet" in stranger.get(reverse("saleinvoice_list")).content.decode()
    order = confirmed_order(ns)
    assert stranger.get(reverse("saleorder_detail", args=[order.pk])).status_code == 404
    assert stranger.get(reverse("packing_new", args=[order.pk])).status_code == 404
    anon = Client()
    assert anon.get(reverse("saleinvoice_list")).status_code == 302
    assert login(make_user("nobody")).get(reverse("sales_settings")).status_code == 403


def test_sales_settings_can_be_changed(ns, owner_c, company):
    r = owner_c.post(reverse("sales_settings"), {"rounding": "none", "max_discount_pct": "7.5", "eway_threshold": "60000",
                                                  "einvoice_enabled": "on"})
    s = settings_for(company)
    assert r.status_code == 302 and (s.rounding, s.max_discount_pct, s.eway_threshold, s.einvoice_enabled) == (
        "none", D("7.50"), D("60000.00"), True)
    owner_c.post(reverse("sales_settings"), {"rounding": "none", "max_discount_pct": "150", "eway_threshold": "1"})
    assert settings_for(company).max_discount_pct == D("7.50")


def test_blank_selects_from_the_browser_are_handled_not_500s(ns, owner_c, factory):
    """A browser posts an empty string for an unchosen select; none of these may crash."""
    sku = ns.sku("Black", "M")
    assert owner_c.get(reverse("sale_scan"), {"code": sku.barcode, "customer": "", "date": ""}).json()["items"][0]["rate"] == ""
    assert owner_c.get(reverse("saleorder_grid"), {"style": ns.style.pk, "customer": "", "date": "bad"}).status_code == 200
    assert owner_c.get(reverse("saleorder_grid"), {"style": "", "customer": ""}).content == b""
    r = owner_c.post(reverse("billing"), {"customer": "", "factory": factory.pk, "location": ns.godown.pk, "date": "2026-06-15",
                                          "action": "post", "tax_mode": "auto", "gst_template": "", "sku": [sku.pk],
                                          "qty": ["1"], "rate": ["500"], "disc": [""]})
    assert r.status_code == 200 and "Choose the customer." in r.content.decode()
    r = owner_c.post(reverse("saleorder_new"), {"customer": "", "factory": factory.pk, "date": "2026-06-15", "order_type": "stock"})
    assert r.status_code == 200 and "Choose the customer." in r.content.decode()
    order = confirmed_order(ns)
    s_id = ns.sku("Black", "S").pk
    r = owner_c.post(reverse("packing_new", args=[order.pk]), {"n": "1", "location": ns.godown.pk, "date": "2026-06-15",
                                                                "transporter": "", "lr_no": "", "lr_date": "", "vehicle_no": "",
                                                                f"c1_{s_id}": "4"})
    assert r.status_code == 302 and PackingList.objects.get().total_qty == D("4")


def test_the_nav_lists_the_sales_screens(owner_c):
    html = owner_c.get(reverse("home")).content.decode()
    for text in ("Sale orders", "Packing and dispatch", "Quick billing (barcode)", "Bills", "Returns from customer", "Sales settings"):
        assert text in html


# ---------------- the active factory drives the sales screens ----------------

def test_sales_entries_use_the_active_factory_and_all_mode_is_view_only(ns, owner_c, factory, factory2):
    black, m = ns.colours["Black"], ns.sizes["M"]
    order_form = {"customer": ns.local.pk, "factory": factory.pk, "date": "2026-06-15", "order_type": "stock", "style": ns.style.pk,
                  f"rate_{ns.style.pk}": "450", f"disc_{ns.style.pk}": "", f"q_{ns.style.pk}_{black.pk}_{m.pk}": "5"}
    owner_c.post(reverse("factory_switch"), {"factory": factory2.pk})
    owner_c.post(reverse("saleorder_new"), order_form)
    assert SaleOrder.objects.get().factory == factory2                 # the form's factory value is ignored
    assert len(owner_c.get(reverse("saleorder_list")).context["orders"]) == 1
    owner_c.post(reverse("factory_switch"), {"factory": factory.pk})
    assert len(owner_c.get(reverse("saleorder_list")).context["orders"]) == 0
    owner_c.post(reverse("factory_switch"), {"factory": "all"})
    assert len(owner_c.get(reverse("saleorder_list")).context["orders"]) == 1
    for name in ("saleorder_new", "billing"):
        r = owner_c.get(reverse(name))
        assert r.status_code == 302 and "single factory" in str(list(r.wsgi_request._messages)[-1]), name
    owner_c.post(reverse("saleorder_new"), order_form)
    assert SaleOrder.objects.count() == 1                                # nothing was saved in All mode


def test_the_packing_form_fills_cartons_from_pieces_per_box(ns, owner_c, company):
    order = confirmed_order(ns)
    plain = owner_c.get(reverse("packing_new", args=[order.pk])).content.decode()
    assert "Fill cartons from pieces per box" not in plain                  # nothing is set yet
    none = owner_c.get(reverse("packing_new", args=[order.pk]), {"fill": "box"}).content.decode()
    assert "No style on this order has its pieces per box set" in none
    company.pieces_per_box = 12
    company.save()
    assert "Fill cartons from pieces per box" in owner_c.get(reverse("packing_new", args=[order.pk])).content.decode()
    html = owner_c.get(reverse("packing_new", args=[order.pk]), {"fill": "box"}).content.decode()
    lines = list(order.lines.order_by("id"))
    first = lines[0]
    full, rest = divmod(int(first.qty), 12)
    assert f'name="c1_{first.sku_id}" value="{12 if full else rest}"' in html           # one SKU to a carton
    cartons = sum(-(-int(l.qty) // 12) for l in lines)
    assert f'name="c{min(cartons, 30)}_' in html and f'name="c{min(cartons, 30) + 1}_' not in html
    if rest:
        assert f'name="c{full + 1}_{first.sku_id}" value="{rest}"' in html              # the short last carton
