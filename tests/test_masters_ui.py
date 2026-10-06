from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from core.models import Role
from masters.models import SKU, BomVersion, Colour, Material, Party, PriceList, Process, Product, RouteTemplate, Size, Style, Unit
from masters.services import parties, styles
from tests.conftest import make_user

D = Decimal


@pytest.fixture
def merch(company):
    user = make_user("merch", all_factories=True)
    user.roles.add(Role.objects.get(name="Merchandiser"))
    return user


@pytest.fixture
def client_for():
    def make(user):
        c = Client()
        c.force_login(user)
        return c

    return make


def _ids(model, **kw):
    return list(model.objects.filter(**kw).values_list("pk", flat=True))


def _style(company, no, colours=("Black",), sizes=("M",), product="TRK"):
    return styles.create_style(
        company=company, style_no=no, product=Product.objects.get(code=product), name=f"Style {no}",
        colours=list(Colour.objects.filter(name__in=colours)), sizes=list(Size.objects.filter(code__in=sizes)),
    )


def test_create_style_through_the_screen_makes_15_skus(company, merch, client_for):
    c = client_for(merch)
    r = c.post(reverse("style_new"), {
        "style_no": "jgr-104", "name": "Cuffed jogger", "product": Product.objects.get(code="JGR").pk,
        "colours": _ids(Colour, name__in=["Black", "Navy", "Grey Melange"]),
        "sizes": _ids(Size, code__in=["S", "M", "L", "XL", "XXL"]),
    })
    assert r.status_code == 302
    style = Style.objects.get(style_no="JGR-104")
    assert SKU.objects.filter(style=style).count() == 15
    html = c.get(reverse("style_detail", args=[style.pk])).content.decode()
    assert "Grey Melange" in html and SKU.objects.filter(style=style).first().barcode in html


def test_duplicate_style_no_is_refused_and_colours_required(company, merch, client_for):
    c = client_for(merch)
    data = {"style_no": "X1", "name": "x", "product": Product.objects.get(code="TRK").pk,
            "colours": _ids(Colour, name="Black"), "sizes": _ids(Size, code="M")}
    assert c.post(reverse("style_new"), data).status_code == 302
    assert c.post(reverse("style_new"), data).status_code == 200  # already exists
    assert c.post(reverse("style_new"), {**data, "style_no": "X2", "colours": []}).status_code == 200
    assert Style.objects.count() == 1


def test_screens_need_permission(company, factory, accountant, client_for):
    c = client_for(accountant)  # accountant has parties but not styles
    assert c.get(reverse("style_list")).status_code == 403
    assert c.get(reverse("party_list")).status_code == 200
    assert c.post(reverse("style_new"), {}).status_code == 403


def test_bom_screen_saves_size_wise_lines(company, merch, client_for):
    style = _style(company, "B1", sizes=("M", "XL"))
    fab = Material.objects.create(code="F1", name="Elastic", kind="trim", unit=Unit.objects.get(code="MTR"))
    fleece = Material.objects.create(code="FL1", name="Fleece", kind="fabric", unit=Unit.objects.get(code="KG"))
    xl, m = Size.objects.get(code="XL"), Size.objects.get(code="M")
    c = client_for(merch)
    form = c.get(reverse("bom_edit", args=[style.pk])).content.decode()
    assert "Used in" in form and "Elastic" in form and "Fleece" not in form       # fabric is not offered
    r = c.post(reverse("bom_edit", args=[style.pk]), {
        "material": [fab.pk, ""], "process": [Process.objects.get(code="EMB").pk, ""], "qty": ["0.45", ""], "wastage": ["3", ""],
        f"size_{m.pk}": ["", ""], f"size_{xl.pk}": ["0.52", ""],
        "charge_desc": ["Printing", ""], "charge_process": [Process.objects.get(code="PRINT").pk, ""],
        "charge_amount": ["4.5", ""],
    })
    assert r.status_code == 302
    v = BomVersion.objects.get(style=style)
    assert v.lines.get().size_overrides.get().qty_per_piece == D("0.52") and v.charges.get().amount_per_piece == D("4.50")
    assert v.lines.get().process.code == "EMB"
    assert "Embroidery" in c.get(reverse("style_detail", args=[style.pk])).content.decode()
    refused = c.post(reverse("bom_edit", args=[style.pk]), {
        "material": [fleece.pk], "process": [""], "qty": ["0.4"], "wastage": [""], f"size_{m.pk}": [""], f"size_{xl.pk}": [""],
        "charge_desc": [""], "charge_process": [""], "charge_amount": [""]})
    assert refused.status_code == 200 and b"is fabric" in refused.content
    bad = c.post(reverse("bom_edit", args=[style.pk]), {
        "material": [fab.pk], "qty": ["abc"], "wastage": [""], f"size_{m.pk}": [""], f"size_{xl.pk}": [""],
        "charge_desc": [""], "charge_process": [""], "charge_amount": [""],
    })
    assert bad.status_code == 200 and b"not a number" in bad.content


def test_changing_bom_used_by_a_lot_warns_and_versions(company, merch, client_for, monkeypatch):
    from masters.services import boms

    style = _style(company, "B2")
    fab = Material.objects.create(code="F2", name="Drawcord", kind="trim", unit=Unit.objects.get(code="MTR"))
    m = Size.objects.get(code="M")

    def payload(q):
        return {"material": [fab.pk], "qty": [q], "wastage": [""], f"size_{m.pk}": [""],
                "charge_desc": [""], "charge_process": [""], "charge_amount": [""]}

    c = client_for(merch)
    c.post(reverse("bom_edit", args=[style.pk]), payload("0.4"))
    monkeypatch.setattr(boms, "_USAGE_CHECKS", [lambda v: True])
    r = c.post(reverse("bom_edit", args=[style.pk]), payload("0.5"), follow=True)
    assert b"saved as version 2" in r.content and BomVersion.objects.filter(style=style).count() == 2


def test_route_screen_orders_steps_and_marks_optional(company, factory, merch, client_for):
    p = {code: Process.objects.get(code=code).pk for code in ("CUT", "STITCH", "EMB")}
    c = client_for(merch)
    r = c.post(reverse("route_new"), {
        "name": "Jogger route", "process": [p["CUT"], p["STITCH"], p["EMB"], ""],
        "mandatory_0": "on", "mandatory_1": "on",
        "assignment": ["in_house", "subcontract", "subcontract", "in_house"],
        "factory": [factory.pk, "", "", ""], "party": ["", "", "", ""], "rate": ["", "25", "6", ""],
    })
    assert r.status_code == 302
    steps = list(RouteTemplate.objects.get(name="Jogger route").steps.all())
    assert [s.process.code for s in steps] == ["CUT", "STITCH", "EMB"]
    assert [s.is_mandatory for s in steps] == [True, True, False]
    assert steps[1].assignment == "subcontract" and steps[1].rate == D("25.00")


def test_party_screen_rejects_duplicate_customer_mobile_naming_the_customer(company, accountant, client_for):
    parties.create_party(company=company, name="Mehta Traders", mobile="9876543210", is_customer=True)
    c = client_for(accountant)
    r = c.post(reverse("party_new"), {"name": "Another", "is_customer": "on", "mobile": "98765 43210", "is_active": "on"})
    assert r.status_code == 200 and b"Mehta Traders" in r.content
    ok = c.post(reverse("party_new"), {"name": "Gupta Garments", "is_customer": "on", "mobile": "9811122233",
                                       "gstin": "03ABCDE1234F1Z5", "is_active": "on"})
    assert ok.status_code == 302 and Party.objects.get(name="Gupta Garments").state_code == "03"


def test_party_screen_shows_friendly_errors(company, accountant, client_for):
    c = client_for(accountant)
    r = c.post(reverse("party_new"), {"name": "X", "mobile": "12345", "is_customer": "on", "is_active": "on"})
    assert b"10-digit" in r.content
    r = c.post(reverse("party_new"), {"name": "X", "mobile": "9811122233", "is_active": "on"})
    assert b"at least one role" in r.content
    assert not Party.objects.exists()


def test_customer_phone_hidden_from_roles_without_the_field_permission(company, client_for):
    parties.create_party(company=company, name="Mehta Traders", mobile="9876543210", is_customer=True)
    prod = make_user("prod", all_factories=True)
    role = Role.objects.create(name="Planner")
    role.permissions.create(screen="masters.party", action="view")
    prod.roles.add(role)
    c = client_for(prod)
    p = Party.objects.get()
    for url in (reverse("party_list"), reverse("party_detail", args=[p.pk])):
        assert b"9876543210" not in c.get(url).content
    assert b"Mehta" in c.get(reverse("search"), {"q": "Mehta"}).content
    assert b"Mehta" not in c.get(reverse("search"), {"q": "98765"}).content  # cannot find a party by hidden phone
    boss = make_user("own2", all_factories=True, is_superuser=True)
    assert b"9876543210" in client_for(boss).get(reverse("party_detail", args=[p.pk])).content


def test_type_ahead_search_by_style_barcode_material_party(company, merch, client_for):
    style = _style(company, "SRCH-1")
    Material.objects.create(code="FAB-77", name="Rib knit", kind="fabric", unit=Unit.objects.get(code="KG"))
    c = client_for(merch)
    assert b"SRCH-1" in c.get(reverse("search"), {"q": "srch"}).content
    barcode = SKU.objects.get(style=style).barcode
    assert b"SRCH-1" in c.get(reverse("search"), {"q": barcode[:6]}).content
    assert b"Rib knit" in c.get(reverse("search"), {"q": "rib"}).content
    assert c.get(reverse("search"), {"q": "s"}).content.strip() == b""  # needs two characters


def test_price_list_and_hsn_slab_screens_add_dated_rows(company, merch, accountant, client_for):
    style = _style(company, "P1")
    pl = PriceList.objects.create(name="Wholesale")
    c = client_for(merch)
    r = c.post(reverse("pricelist_detail", args=[pl.pk]),
               {"style": style.pk, "min_qty": 1, "rate": "499.00", "effective_from": "2026-05-01"})
    assert r.status_code == 302 and pl.rates.get().rate == D("499.00")
    from tax.models import HSN

    hsn = HSN.objects.get(code="6103")
    a = client_for(accountant)
    r = a.post(reverse("hsn_detail", args=[hsn.pk]),
               {"value_from": "0", "value_to": "", "gst_rate": "12", "effective_from": "2027-01-01"})
    assert r.status_code == 302 and hsn.slabs.count() == 3
    assert c.post(reverse("hsn_detail", args=[hsn.pk]), {}).status_code == 403  # merchandiser can only view


def test_simple_master_screens_create_a_colour_and_unit(company, merch, client_for):
    c = client_for(merch)
    assert c.post(reverse("colour_new"), {"name": "Olive", "is_active": "on"}).status_code == 302
    assert Colour.objects.filter(name="Olive").exists()
    assert b"Olive" in c.get(reverse("colour_list")).content
    assert c.post(reverse("unit_new"), {"code": "BOX", "name": "Box", "kind": "count", "is_active": "on"}).status_code == 302


def test_nav_lists_master_screens_by_permission(company, merch, accountant, client_for):
    html = client_for(merch).get(reverse("home")).content.decode()
    assert "Styles" in html and "Routes" in html and "Trial balance" not in html
    html = client_for(accountant).get(reverse("home")).content.decode()
    assert "Parties" in html and "Styles" not in html


def test_new_route_preselects_the_only_factory(company, factory, merch, client_for):
    page = client_for(merch).get(reverse("route_new")).content.decode()
    assert f'<option value="{factory.pk}" selected>' in page


def test_masters_lists_show_edit_and_delete_as_icons(company, owner, client_for):
    c = client_for(owner)
    s = _style(company, "ICO-1")
    p = parties.create_party(company=company, name="Icon Vendor", mobile="9800000001", is_vendor=True)
    page = c.get(reverse("style_list")).content.decode()
    assert reverse("style_edit", args=[s.pk]) in page and reverse("style_delete", args=[s.pk]) in page and "#i-trash" in page
    page = c.get(reverse("party_list")).content.decode()
    assert reverse("party_edit", args=[p.pk]) in page and reverse("party_delete", args=[p.pk]) in page
    for name in ("unit_list", "size_list", "colour_list", "product_list", "material_list", "process_list", "pricelist_list", "hsn_list", "route_list"):
        page = c.get(reverse(name)).content.decode()
        assert ">Edit<" not in page and ">Delete<" not in page, name           # text links are gone
    assert "#i-edit" in c.get(reverse("unit_list")).content.decode()
