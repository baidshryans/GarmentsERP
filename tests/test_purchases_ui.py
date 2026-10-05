from datetime import date
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from core.models import Location, Role
from inventory import barcode
from inventory.models import FabricRoll, StockTransfer
from inventory.services import stock
from masters.models import SKU, Colour, Material, Product, Size, Unit
from masters.services import parties, styles
from purchases.models import DebitNote, Grn, PurchaseInvoice, PurchaseOrder
from tax.models import TaxTemplate
from tests.conftest import make_user

D = Decimal


@pytest.fixture
def vendor(company):
    return parties.create_party(company=company, name="Yarn House", mobile="9833333333", is_vendor=True)


@pytest.fixture
def godown(factory):
    return Location.objects.get(factory=factory, name="Main Godown")


@pytest.fixture
def fabric(db):
    return Material.objects.create(code="FAB-1", name="Fleece", kind="fabric", unit=Unit.objects.get(code="KG"))


@pytest.fixture
def trim(db):
    return Material.objects.create(code="ZIP-1", name="Zipper", kind="trim", unit=Unit.objects.get(code="PCS"))


@pytest.fixture
def storekeeper(company, factory):
    u = make_user("keeper")
    u.roles.add(Role.objects.get(name="Store Keeper"))
    u.allowed_factories.add(factory)
    return u


def login(user):
    c = Client()
    c.force_login(user)
    return c


# ---------------- barcode ----------------

def test_code128_patterns_are_well_formed():
    assert len(barcode.PATTERNS) == 107
    for i, p in enumerate(barcode.PATTERNS[:106]):
        assert len(p) == 6 and sum(map(int, p)) == 11, i  # every symbol is 11 modules wide
    assert sum(map(int, barcode.PATTERNS[106])) == 13 and len(barcode.PATTERNS[106]) == 7  # stop pattern


def test_code128_checksum_and_svg():
    assert barcode.symbol_values("A") == [104, 33, (104 + 33) % 103, 106]
    assert barcode.symbol_values("0000000001")[-2] == (104 + sum(i * (ord(c) - 32) for i, c in enumerate("0000000001", 1))) % 103
    svg = barcode.svg("R000012")
    assert svg.startswith("<svg") and "<rect" in svg and "R000012" in svg
    with pytest.raises(ValueError):
        barcode.svg("")
    with pytest.raises(ValueError):
        barcode.svg("naïve")


# ---------------- purchase flow through the screens ----------------

def test_po_to_grn_to_invoice_through_the_screens(company, factory, vendor, owner, godown, fabric):
    c = login(owner)
    r = c.post(reverse("po_new"), {"vendor": vendor.pk, "factory": factory.pk, "date": "2026-06-15", "expected_date": "2026-06-30",
                                   "item": [f"m:{fabric.pk}", ""], "qty": ["100", ""], "rate": ["200", ""]})
    po = PurchaseOrder.objects.get()
    assert r.status_code == 302 and po.status == "draft"
    c.post(reverse("po_detail", args=[po.pk]), {"action": "submit"})
    po.refresh_from_db()
    assert po.status == "approved" and po.number  # 20,000 is under the limit
    page = c.get(reverse("grn_new"), {"po": po.pk}).content.decode()
    assert "Pending 100" in page

    r = c.post(reverse("grn_new"), {
        "po": po.pk, "vendor": vendor.pk, "factory": factory.pk, "location": godown.pk, "date": "2026-06-16",
        "item": [f"m:{fabric.pk}", ""], "rate": ["200", ""], "qty": ["", ""], "po_line": [po.lines.get().pk, ""],
        "rolls": ["R-1, 60, 55, LOT-A, 280, 180\nR-2, 40", ""]})
    grn = Grn.objects.get()
    assert r.status_code == 302 and grn.lines.get().rolls.count() == 2
    page = c.get(reverse("grn_detail", args=[grn.pk])).content.decode()
    assert "R-1" in page and "Finish QC" in page
    rolls = list(grn.lines.get().rolls.all())
    r = c.post(reverse("grn_detail", args=[grn.pk]), {
        "action": "finish_qc", f"roll_status_{rolls[0].pk}": "accepted", f"roll_status_{rolls[1].pk}": "rejected",
        f"roll_remark_{rolls[1].pk}": "stains"}, follow=True)
    grn.refresh_from_db()
    assert grn.status == "qc_done"
    c.post(reverse("grn_detail", args=[grn.pk]), {"action": "post"})
    grn.refresh_from_db()
    po.refresh_from_db()
    assert grn.status == "posted" and po.status == "partly_received"
    assert stock.on_hand(factory, fabric) == (D("60.000"), D("12000.00"))
    assert b"R000001" in c.get(reverse("grn_labels", args=[grn.pk])).content  # printable roll label with the label code

    line = grn.lines.get()
    inv_page = c.get(reverse("invoice_new"), {"vendor": vendor.pk, "factory": factory.pk}).content.decode()
    assert "Left to bill" in inv_page and f"use_{line.pk}" in inv_page
    gst = TaxTemplate.objects.get(name="GST 12% intra-state (CGST + SGST)")
    r = c.post(reverse("invoice_new"), {
        "vendor": vendor.pk, "factory": factory.pk, "vendor_invoice_no": "YH-77", "vendor_invoice_date": "2026-06-16",
        "date": "2026-06-17", f"use_{line.pk}": "on", f"qty_{line.pk}": "100", f"rate_{line.pk}": "200",
        "tax_mode": "template", "gst_template": gst.pk, "itc_claimable": "on", "tds_template": ""})
    inv = PurchaseInvoice.objects.get()
    assert r.status_code == 302 and inv.status == "draft" and inv.payable == D("22400.00")
    c.post(reverse("invoice_detail", args=[inv.pk]), {"action": "post"})
    inv.refresh_from_db()
    assert inv.status == "posted" and inv.number
    page = c.get(reverse("invoice_detail", args=[inv.pk])).content.decode()
    assert "Payable to vendor" in page and "1200" in page  # 12% of 20,000 is 2,400, shown as CGST 1,200 and SGST 1,200
    assert DebitNote.objects.filter(grn=grn).count() == 1


def test_invoice_screen_validation_and_overrides(company, factory, vendor, owner, godown, trim):
    from purchases.services import grn as grns

    g = grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=date(2026, 6, 15), user=owner,
                        lines=[grns.GrnLineSpec(item=trim, rate=D("10"), qty_received=D("100"))])
    grns.finish_qc(g, user=owner)
    grns.post_grn(g, user=owner)
    line = g.lines.get()
    c = login(owner)
    base = {"vendor": vendor.pk, "factory": factory.pk, "vendor_invoice_no": "T-1", "vendor_invoice_date": "2026-06-15",
            "date": "2026-06-15", f"use_{line.pk}": "on", f"qty_{line.pk}": "100", f"rate_{line.pk}": "10", "itc_claimable": "on"}
    r = c.post(reverse("invoice_new"), {**base, f"qty_{line.pk}": "500"})
    assert r.status_code == 200 and b"left to bill" in r.content
    r = c.post(reverse("invoice_new"), {**base, "tax_mode": "template"})
    assert b"Choose a GST template" in r.content
    gst = TaxTemplate.objects.get(name="GST 12% intra-state (CGST + SGST)")
    c.post(reverse("invoice_new"), {**base, "tax_mode": "template", "gst_template": gst.pk})
    inv = PurchaseInvoice.objects.get()
    cg = inv.tax_lines.get(component="cgst")
    r = c.post(reverse("invoice_detail", args=[inv.pk]), {"action": "overrides", f"amount_{cg.pk}": "50", f"reason_{cg.pk}": ""}, follow=True)
    assert b"reason" in r.content
    c.post(reverse("invoice_detail", args=[inv.pk]), {"action": "overrides", f"amount_{cg.pk}": "50", f"reason_{cg.pk}": "Vendor rounded"})
    assert PurchaseInvoice.objects.get().tax_lines.get(component="cgst").amount == D("50.00")
    c.post(reverse("invoice_detail", args=[inv.pk]), {"action": "discard"})
    assert not PurchaseInvoice.objects.exists()


def test_po_screen_owner_approval_and_permissions(company, factory, vendor, owner, accountant, trim):
    c = login(owner)
    c.post(reverse("po_new"), {"vendor": vendor.pk, "factory": factory.pk, "date": "2026-06-15", "item": [f"m:{trim.pk}"],
                               "qty": ["1000"], "rate": ["100"]})
    po = PurchaseOrder.objects.get()
    c.post(reverse("po_detail", args=[po.pk]), {"action": "submit"})
    po.refresh_from_db()
    assert po.status == "pending_approval"
    a = login(accountant)
    a.post(reverse("po_detail", args=[po.pk]), {"action": "approve"})
    po.refresh_from_db()
    assert po.status == "pending_approval"  # accountant has no approval right
    page = c.get(reverse("po_detail", args=[po.pk])).content.decode()
    assert "Approve" in page and "approval limit" in page
    c.post(reverse("po_detail", args=[po.pk]), {"action": "approve"})
    po.refresh_from_db()
    assert po.status == "approved"
    assert b"Nothing pending" not in c.get(reverse("po_pending")).content


def test_store_keeper_sees_receiving_screens_but_not_invoices_or_settings(company, storekeeper):
    c = login(storekeeper)
    assert c.get(reverse("grn_list")).status_code == 200
    assert c.get(reverse("stock_enquiry")).status_code == 200
    assert c.get(reverse("invoice_list")).status_code == 403
    assert c.get(reverse("inventory_settings")).status_code == 403
    assert c.get(reverse("po_new")).status_code == 403


def test_grn_screen_rejects_bad_roll_lines_with_a_clear_message(company, factory, vendor, owner, godown, fabric):
    c = login(owner)
    r = c.post(reverse("grn_new"), {"vendor": vendor.pk, "factory": factory.pk, "location": godown.pk, "date": "2026-06-16",
                                    "item": [f"m:{fabric.pk}"], "rate": ["200"], "qty": [""], "po_line": [""], "rolls": ["R-1"]})
    assert r.status_code == 200 and b"roll number and the quantity" in r.content and not Grn.objects.exists()


def test_debit_note_screens_post_a_return(company, factory, vendor, owner, godown, trim):
    from purchases.services import grn as grns

    g = grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=date(2026, 6, 15), user=owner,
                        lines=[grns.GrnLineSpec(item=trim, rate=D("10"), qty_received=D("100"))])
    grns.finish_qc(g, user=owner)
    grns.post_grn(g, user=owner)
    c = login(owner)
    r = c.post(reverse("debitnote_new"), {
        "vendor": vendor.pk, "factory": factory.pk, "date": "2026-06-20", "reason": "Wrong size", "gst_template": "",
        "itc_claimable": "on", "item": [f"m:{trim.pk}", ""], "location": [godown.pk, godown.pk], "roll": ["", ""],
        "qty": ["10", ""], "rate": ["10", ""]})
    note = DebitNote.objects.get(kind="return")
    assert r.status_code == 302 and note.total == D("100.00")
    c.post(reverse("debitnote_detail", args=[note.pk]), {"action": "post"})
    note.refresh_from_db()
    assert note.status == "posted" and stock.on_hand(factory, trim)[0] == D("90.000")


# ---------------- inventory screens ----------------

def test_stock_enquiry_is_scoped_hides_cost_and_shows_in_transit(company, factory, factory2, owner, storekeeper, godown, trim):
    from inventory.services import transfers
    from inventory.services.opening import OpeningItem, post_opening_stock

    post_opening_stock(company=company, factory=factory, location=godown, user=owner, entries=[OpeningItem(trim, D("100"), D("5"))])
    godown2 = Location.objects.get(factory=factory2, name="Main Godown")
    t = transfers.create_transfer(company=company, from_factory=factory, from_location=godown, to_factory=factory2,
                                  to_location=godown2, date=date(2026, 6, 15), user=owner, lines=[(trim, D("30"), None)])
    transfers.issue_transfer(t, user=owner)
    html = login(owner).get(reverse("stock_enquiry")).content.decode()
    assert "In transit" in html and "Zipper" in html and "500.00" in html or "350.00" in html
    keeper_html = login(storekeeper).get(reverse("stock_enquiry")).content.decode()
    assert "LDH2" not in keeper_html and "Average cost" not in keeper_html  # other factory hidden; cost hidden
    assert "Zipper" in keeper_html
    assert b"Average cost" in login(owner).get(reverse("stock_enquiry")).content


def test_transfer_screens_end_to_end(company, factory, factory2, owner, godown, trim):
    from inventory.services.opening import OpeningItem, post_opening_stock

    post_opening_stock(company=company, factory=factory, location=godown, user=owner, entries=[OpeningItem(trim, D("100"), D("5"))])
    godown2 = Location.objects.get(factory=factory2, name="Main Godown")
    c = login(owner)
    r = c.post(reverse("transfer_new"), {
        "from_factory": factory.pk, "from_location": godown.pk, "to_factory": factory2.pk, "to_location": godown2.pk,
        "date": "2026-06-15", "document_type": "challan", "item": [f"m:{trim.pk}", ""], "roll": ["", ""], "qty": ["25", ""]})
    t = StockTransfer.objects.get()
    assert r.status_code == 302 and t.status == "draft"
    c.post(reverse("transfer_detail", args=[t.pk]), {"action": "issue"})
    c.post(reverse("transfer_detail", args=[t.pk]), {"action": "eway", "eway_bill_no": "331000123456", "vehicle_no": "PB10AB1234"})
    t.refresh_from_db()
    assert t.status == "issued" and t.eway_bill_no == "331000123456"
    c.post(reverse("transfer_detail", args=[t.pk]), {"action": "receive"})
    t.refresh_from_db()
    assert t.status == "received"
    assert b"Received" in c.get(reverse("transfer_list")).content


def test_opening_stock_screen_posts_fabric_by_roll(company, factory, owner, godown, fabric, trim):
    c = login(owner)
    r = c.post(reverse("opening_stock"), {
        "factory": factory.pk, "location": godown.pk, "date": "2026-04-01",
        "item": [f"m:{fabric.pk}", f"m:{trim.pk}", ""], "qty": ["120", "300", ""], "rate": ["190", "2", ""],
        "roll_no": ["OLD-9", "", ""], "lot": ["L3", "", ""], "gsm": ["280", "", ""], "width": ["180", "", ""],
        "length": ["", "", ""], "supplier": ["", "", ""]})
    assert r.status_code == 302
    assert stock.on_hand(factory, fabric) == (D("120.000"), D("22800.00")) and FabricRoll.objects.get().lot_no == "L3"
    bad = c.post(reverse("opening_stock"), {
        "factory": factory.pk, "location": godown.pk, "item": [f"m:{fabric.pk}"], "qty": ["5"], "rate": ["1"],
        "roll_no": [""], "lot": [""], "gsm": [""], "width": [""], "length": [""], "supplier": [""]})
    assert bad.status_code == 200 and b"roll" in bad.content


def test_tag_printing_for_a_filtered_style(company, owner):
    s = styles.create_style(company=company, style_no="JGR-5", product=Product.objects.get(code="JGR"), name="Jogger", mrp=D("699"),
                            colours=list(Colour.objects.filter(name="Black")), sizes=list(Size.objects.filter(code__in=["M", "L"])))
    c = login(owner)
    page = c.get(reverse("tag_print"), {"style": s.pk}).content.decode()
    skus = list(SKU.objects.filter(style=s))
    assert all(k.barcode in page for k in skus)
    r = c.post(reverse("tag_print"), {f"qty_{skus[0].pk}": "3", f"qty_{skus[1].pk}": "", "layout": "thermal2"})
    html = r.content.decode()
    assert html.count('class="tag"') == 3 and skus[0].barcode in html and "<svg" in html and "MRP 699" in html
    assert c.post(reverse("tag_print"), {f"qty_{skus[0].pk}": "abc"}, follow=True).status_code == 200
    assert c.post(reverse("tag_print"), {f"qty_{skus[0].pk}": "999"}, follow=True).status_code == 200
    assert html.count("tag") >= 3


# ---------------- settings ----------------

@pytest.mark.raw_stock  # the direct issue stands in for cutting consumption (its GL entry arrives with production)
def test_valuation_setting_screen_changes_how_issues_are_valued(company, factory, owner, godown, fabric):
    from inventory.services.opening import OpeningItem, post_opening_stock

    c = login(owner)
    page = c.get(reverse("inventory_settings")).content.decode()
    assert "Weighted average" in page and "Specific cost per fabric roll" in page
    r = c.post(reverse("inventory_settings"), {"valuation_method": "specific_roll", "po_approval_limit": "75000", "bom_tolerance_pct": "5"})
    company.refresh_from_db()
    assert r.status_code == 302 and company.valuation_method == "specific_roll"
    assert company.po_approval_limit == D("75000") and not company.allow_negative_stock
    post_opening_stock(company=company, factory=factory, location=godown, user=owner, entries=[
        OpeningItem(fabric, D("100"), D("50"), vendor_roll_no="A"), OpeningItem(fabric, D("100"), D("70"), vendor_roll_no="B")])
    roll_b = FabricRoll.objects.get(vendor_roll_no="B")
    m = stock.post_movement(factory=factory, location=godown, item=fabric, qty=D("-10"), roll=roll_b, movement_type="issue",
                            date=date(2026, 6, 1), user=owner)
    assert m.value == D("-700.00")  # roll B's own cost, not the 60 average


def test_settings_need_permission_and_changes_are_logged(company, accountant):
    c = login(accountant)
    assert c.get(reverse("inventory_settings")).status_code == 403
    admin = make_user("adm")
    admin.roles.add(Role.objects.get(name="Administrator"))
    a = login(admin)
    assert a.get(reverse("inventory_settings")).status_code == 200
    a.post(reverse("inventory_settings"), {"valuation_method": "weighted_average", "allow_negative_stock": "on", "po_approval_limit": "10", "bom_tolerance_pct": "5"})
    company.refresh_from_db()
    assert company.allow_negative_stock and company.history.count() >= 2


def test_nav_shows_purchase_and_inventory_groups_by_permission(company, storekeeper, accountant):
    html = login(storekeeper).get(reverse("home")).content.decode()
    assert "Goods receipt (GRN)" in html and "Transfers" in html and "Purchase invoices" not in html
    html = login(accountant).get(reverse("home")).content.decode()
    assert "Purchase invoices" in html and "Debit notes" in html


# ---------------- the active factory drives the purchase screens ----------------

def _po_form(vendor, fabric, **extra):
    return {"vendor": vendor.pk, "date": "2026-06-15", "item": [f"m:{fabric.pk}"], "qty": ["10"], "rate": ["100"], **extra}


def test_new_documents_go_into_the_active_factory_whatever_the_form_says(company, factory, factory2, vendor, owner, fabric):
    c = login(owner)                                             # starts in the first factory
    c.post(reverse("factory_switch"), {"factory": factory2.pk})
    c.post(reverse("po_new"), _po_form(vendor, fabric, factory=factory.pk))
    assert PurchaseOrder.objects.get().factory == factory2


def test_all_factories_mode_is_view_only_for_purchases(company, factory, factory2, vendor, owner, fabric):
    c = login(owner)
    c.post(reverse("factory_switch"), {"factory": factory.pk})
    c.post(reverse("po_new"), _po_form(vendor, fabric))
    c.post(reverse("factory_switch"), {"factory": factory2.pk})
    c.post(reverse("po_new"), _po_form(vendor, fabric))
    assert PurchaseOrder.objects.count() == 2
    c.post(reverse("factory_switch"), {"factory": "all"})
    for name in ("po_new", "grn_new", "invoice_new", "debitnote_new"):
        r = c.get(reverse(name))
        assert r.status_code == 302 and "single factory" in str(list(r.wsgi_request._messages)[-1]), name
    c.post(reverse("po_new"), _po_form(vendor, fabric))
    assert PurchaseOrder.objects.count() == 2                    # nothing was saved in All mode
    assert len(c.get(reverse("po_list")).context["pos"]) == 2    # but the list shows every factory
    c.post(reverse("factory_switch"), {"factory": factory.pk})
    assert [p.factory for p in c.get(reverse("po_list")).context["pos"]] == [factory]


# ---------------- edit and delete: icons on lists, drafts only ----------------

def _draft_po(c, vendor, fabric):
    c.post(reverse("po_new"), _po_form(vendor, fabric))
    return PurchaseOrder.objects.latest("pk")


def _posted_grn(company, factory, vendor, godown, item, owner, qty="100"):
    from purchases.services import grn as grns

    g = grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=date(2026, 6, 15), user=owner,
                        lines=[grns.GrnLineSpec(item=item, rate=D("10"), qty_received=D(qty))])
    grns.finish_qc(g, user=owner)
    grns.post_grn(g, user=owner)
    return g


def test_lists_show_edit_and_delete_icons_for_drafts_only(company, factory, vendor, owner, godown, fabric, trim):
    c = login(owner)
    po = _draft_po(c, vendor, fabric)
    page = c.get(reverse("po_list")).content.decode()
    assert reverse("po_edit", args=[po.pk]) in page and reverse("po_delete", args=[po.pk]) in page
    assert 'aria-label="Edit"' in page and "#i-trash" in page and ">Edit<" not in page   # icons, not text
    c.post(reverse("po_detail", args=[po.pk]), {"action": "submit"})
    page = c.get(reverse("po_list")).content.decode()
    assert reverse("po_edit", args=[po.pk]) not in page and reverse("po_delete", args=[po.pk]) not in page
    g = _posted_grn(company, factory, vendor, godown, trim, owner)
    assert reverse("grn_delete", args=[g.pk]) not in c.get(reverse("grn_list")).content.decode()


def test_draft_po_is_deleted_but_an_approved_one_is_not(company, factory, vendor, owner, fabric):
    c = login(owner)
    po = _draft_po(c, vendor, fabric)
    assert b"Delete" in c.get(reverse("po_delete", args=[po.pk])).content
    assert c.post(reverse("po_delete", args=[po.pk])).status_code == 302
    assert not PurchaseOrder.objects.exists()
    po = _draft_po(c, vendor, fabric)
    c.post(reverse("po_detail", args=[po.pk]), {"action": "submit"})
    r = c.get(reverse("po_delete", args=[po.pk]))
    assert b"cannot be deleted" in r.content
    c.post(reverse("po_delete", args=[po.pk]))
    assert PurchaseOrder.objects.filter(pk=po.pk).exists()


def test_draft_grn_is_deleted_but_a_posted_one_is_not(company, factory, vendor, owner, godown, trim):
    from purchases.services import grn as grns

    c = login(owner)
    draft = grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=date(2026, 6, 15), user=owner,
                            lines=[grns.GrnLineSpec(item=trim, rate=D("10"), qty_received=D("5"))])
    c.post(reverse("grn_delete", args=[draft.pk]))
    assert not Grn.objects.filter(pk=draft.pk).exists()
    posted = _posted_grn(company, factory, vendor, godown, trim, owner)
    c.post(reverse("grn_delete", args=[posted.pk]))
    assert Grn.objects.filter(pk=posted.pk, status="posted").exists()


def test_draft_invoice_is_edited_then_deleted_and_a_posted_one_is_locked(company, factory, vendor, owner, godown, trim):
    g = _posted_grn(company, factory, vendor, godown, trim, owner)
    line = g.lines.get()
    c = login(owner)
    base = {"vendor": vendor.pk, "vendor_invoice_no": "E-1", "vendor_invoice_date": "2026-06-15", "date": "2026-06-15",
            f"use_{line.pk}": "on", f"qty_{line.pk}": "40", f"rate_{line.pk}": "10", "itc_claimable": "on", "tax_mode": "none"}
    c.post(reverse("invoice_new"), base)
    inv = PurchaseInvoice.objects.get()
    page = c.get(reverse("invoice_edit", args=[inv.pk])).content.decode()
    assert 'value="E-1"' in page and 'value="40"' in page                      # the form is filled from the draft
    r = c.post(reverse("invoice_edit", args=[inv.pk]), {**base, f"qty_{line.pk}": "60", "vendor_invoice_no": "E-2"})
    inv.refresh_from_db()
    assert r.status_code == 302 and inv.vendor_invoice_no == "E-2" and inv.lines.get().qty == D("60.000")
    assert PurchaseInvoice.objects.count() == 1                                # edited in place, not duplicated
    r = c.post(reverse("invoice_edit", args=[inv.pk]), {**base, f"qty_{line.pk}": "500"})
    assert r.status_code == 200 and b"left to bill" in r.content               # errors keep the form
    c.post(reverse("invoice_delete", args=[inv.pk]))
    assert not PurchaseInvoice.objects.exists()
    c.post(reverse("invoice_new"), base)
    inv = PurchaseInvoice.objects.get()
    c.post(reverse("invoice_detail", args=[inv.pk]), {"action": "post"})
    assert c.get(reverse("invoice_edit", args=[inv.pk])).status_code == 302
    c.post(reverse("invoice_delete", args=[inv.pk]))
    assert PurchaseInvoice.objects.filter(pk=inv.pk, status="posted").exists()


def test_draft_return_note_is_edited_then_deleted_and_a_posted_one_is_locked(company, factory, vendor, owner, godown, trim):
    _posted_grn(company, factory, vendor, godown, trim, owner)
    c = login(owner)
    form = {"vendor": vendor.pk, "date": "2026-06-20", "reason": "Wrong size", "gst_template": "", "itc_claimable": "on",
            "item": [f"m:{trim.pk}", ""], "location": [godown.pk, godown.pk], "roll": ["", ""], "qty": ["10", ""], "rate": ["10", ""]}
    c.post(reverse("debitnote_new"), form)
    note = DebitNote.objects.get(kind="return")
    page = c.get(reverse("debitnote_edit", args=[note.pk])).content.decode()
    assert "Wrong size" in page
    r = c.post(reverse("debitnote_edit", args=[note.pk]), {**form, "qty": ["20", ""], "reason": "Damaged"})
    note.refresh_from_db()
    assert r.status_code == 302 and note.total == D("200.00") and note.reason == "Damaged" and note.lines.count() == 1
    c.post(reverse("debitnote_delete", args=[note.pk]))
    assert not DebitNote.objects.filter(kind="return").exists()
    c.post(reverse("debitnote_new"), form)
    note = DebitNote.objects.get(kind="return")
    c.post(reverse("debitnote_detail", args=[note.pk]), {"action": "post"})
    assert c.get(reverse("debitnote_edit", args=[note.pk])).status_code == 302
    c.post(reverse("debitnote_delete", args=[note.pk]))
    assert DebitNote.objects.filter(pk=note.pk, status="posted").exists()


def test_deleting_a_draft_needs_edit_rights_and_the_documents_factory(company, factory, factory2, vendor, owner, godown, fabric, accountant):
    c = login(owner)
    c.post(reverse("factory_switch"), {"factory": factory2.pk})
    po = _draft_po(c, vendor, fabric)
    assert po.factory == factory2
    keeper = make_user("keeper2")
    keeper.roles.add(Role.objects.get(name="Store Keeper"))
    keeper.allowed_factories.add(factory)
    k = login(keeper)
    assert k.post(reverse("po_delete", args=[po.pk])).status_code == 403       # no PO rights at all
    a = login(accountant)                                                      # accountant is limited to the first factory
    assert a.post(reverse("po_delete", args=[po.pk])).status_code in (403, 404)
    assert PurchaseOrder.objects.filter(pk=po.pk).exists()
