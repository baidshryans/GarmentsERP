"""Lighter entry forms (docs/superpowers/specs/2026-10-06-lighter-forms-design.md): what is needed every time is in
view, the rest folds under "More options", a supplier / customer / fabricator must be chosen, and fields that apply
to one choice only show for that choice. Nothing here changes what a form saves."""
import re
from datetime import date
from decimal import Decimal

import pytest
from django import forms
from django.template import Context, Template
from django.test import Client
from django.urls import reverse

from core import forms_ui
from core.models import Location
from jobwork.models import JobWorkChallan, LabourRate
from jobwork.services import rates
from masters.models import Material, Process, Size, Unit
from masters.services import parties
from purchases.models import DebitNote, Grn, PurchaseOrder
from purchases.services import orders as po_service
from sales.models import SaleInvoice, SaleOrder
from tests import prod_helpers as ph
from tests import sales_helpers as sh

D = Decimal
DAY = date(2026, 6, 15)


def login(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def owner_c(owner):
    return login(owner)


def html_of(response):
    assert response.status_code == 200, response.status_code
    return response.content.decode()


def folds(html):
    """Every folded section on a page: (is it open, its summary text, its body)."""
    out = []
    for is_open, summary, body in re.findall(
            r'<details class="more[^"]*"( open)?><summary>(.*?)</summary><div class="more-body">(.*?)</div></details>', html, re.S):
        out.append((bool(is_open), re.sub(r"<[^>]+>", " ", summary), body))
    return out


def fold_of(html, name):
    """The folded section holding the field posted as `name`, or None when the field is in plain view."""
    for section in folds(html):
        if f'name="{name}"' in section[2]:
            return section
    return None


def in_view(html, *names):
    """These fields are on the page and outside every fold."""
    return all(f'name="{n}"' in html and fold_of(html, n) is None for n in names)


def folded(html, *names, title="More options", is_open=False):
    """These fields sit in one folded section with this title, open or closed as given."""
    sections = [fold_of(html, n) for n in names]
    return (all(s is not None for s in sections) and len({s[2] for s in sections}) == 1
            and sections[0][0] is is_open and sections[0][1].strip().startswith(title))


def chosen(html, select_id):
    """The value a select starts on: "" when it starts on its blank "Choose…" line."""
    body = re.search(rf'<select id="{select_id}"[^>]*>(.*?)</select>', html, re.S).group(1)
    picked = re.findall(r'<option value="([^"]*)"[^>]*\bselected\b', body)
    return picked[-1] if picked else re.search(r'<option value="([^"]*)"', body).group(1)


def starts_blank(html, select_id):
    body = re.search(rf'<select id="{select_id}"[^>]*>(.*?)</select>', html, re.S).group(1)
    return body.lstrip().startswith('<option value="">Choose…</option>') and chosen(html, select_id) == ""


def flashed(html):
    """The words on the screen itself: the page between the menu and the footer, without markup or scripts."""
    main = html.split("<main", 1)[1].split("</main>", 1)[0] if "<main" in html else html
    main = re.sub(r"<script\b.*?</script>", " ", main, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", main))


# ================================================================ the one rule

def test_a_fold_stays_closed_while_every_field_inside_holds_its_default():
    assert forms_ui.more_open(None, ["notes"]) is False
    assert forms_ui.more_open({}, ["notes", "expected_date"]) is False
    assert forms_ui.more_open({"notes": "  ", "expected_date": None}, ["notes", "expected_date"]) is False
    assert forms_ui.more_open({"discount": "0.00", "active": True, "tds": ""}, {"discount": 0, "active": True, "tds": None}) is False
    assert forms_ui.more_open({"discount": D("0"), "active": "on"}, {"discount": "0", "active": True}) is False


def test_a_fold_opens_when_a_field_inside_differs_from_its_default():
    assert forms_ui.more_open({"notes": "call first"}, ["notes"]) is True
    assert forms_ui.more_open({"discount": "2.5"}, {"discount": 0}) is True
    assert forms_ui.more_open({"active": False}, {"active": True}) is True
    assert forms_ui.more_open({}, {"itc": "on"}) is True                 # a ticked-by-default box that came back unticked
    assert forms_ui.more_open({"location": "7"}, {"location": 4}) is True
    assert forms_ui.more_open({"other": "typed"}, ["notes"]) is False    # a field outside the fold never opens it


def test_a_fold_opens_when_a_field_inside_has_an_error():
    assert forms_ui.more_open({}, ["notes", "email"], errors=["email"]) is True
    assert forms_ui.more_open({}, ["notes"], errors=["name"]) is False   # an error on a field in plain view


class _SampleForm(forms.Form):
    name = forms.CharField()
    email = forms.EmailField(required=False)
    discount = forms.DecimalField(required=False, initial=0)
    active = forms.BooleanField(required=False, initial=True)
    more_fields = ("email", "discount", "active", "not_on_this_form")
    more_label = "email, discount"


def test_a_django_form_names_its_folded_fields_once():
    blank = forms_ui.more_form(_SampleForm())
    assert blank["names"] == ["email", "discount", "active"] and blank["open"] is False and blank["label"] == "email, discount"
    assert forms_ui.more_form(_SampleForm({"name": "A", "discount": "0", "active": "on"}))["open"] is False
    assert forms_ui.more_form(_SampleForm({"name": "A", "discount": "5", "active": "on"}))["open"] is True
    assert forms_ui.more_form(_SampleForm({"name": "A", "active": "on", "email": "nope"}))["open"] is True      # an error
    assert forms_ui.more_form(_SampleForm({"name": "A", "discount": "0"}))["open"] is True                      # unticked
    assert forms_ui.more_form(_SampleForm(initial={"email": "a@b.in"}))["open"] is True                         # a saved value
    assert forms_ui.more_form(forms.Form())["fields"] == []


def _render(source, **ctx):
    return Template("{% load forms_ui %}" + source).render(Context(ctx))


def test_the_more_tag_writes_one_markup_for_every_form():
    html = _render('{% more "expected by, notes" open=flag %}<input name="notes">{% endmore %}', flag=False)
    assert html == ('<details class="more"><summary><span class="more-title">More options</span>'
                    '<span class="more-inside muted">expected by, notes</span></summary>'
                    '<div class="more-body"><input name="notes"></div></details>')
    html = _render('{% more "transporter" open=flag title="Transport details" cls="island" %}x{% endmore %}', flag=True)
    assert html.startswith('<details class="more island" open><summary><span class="more-title">Transport details</span>')
    assert folds(_render('{% more inside open=1 %}<input name="a">{% endmore %}', inside="a <b>"))[0][0] is True
    assert "&lt;b&gt;" in _render('{% more inside %}x{% endmore %}', inside="a <b>")


def test_the_more_open_tag_uses_the_same_rule():
    assert _render('{% more_open vals "a b" as o %}{{ o }}', vals={"a": "", "b": ""}) == "False"
    assert _render('{% more_open vals "a b" as o %}{{ o }}', vals={"b": "x"}) == "True"
    assert _render('{% more_open vals "a b" as o %}{{ o }}', vals=None) == "False"


def test_a_field_for_one_choice_is_hidden_by_the_server_for_the_others():
    assert _render('{% show_when "tax_mode" mode "template manual" %}', mode="none") == 'data-show-when="tax_mode=template manual" hidden'
    assert _render('{% show_when "tax_mode" mode "template manual" %}', mode="manual") == 'data-show-when="tax_mode=template manual"'
    assert _render('{% show_when "rate_type" t "A B" "off" %}', t="D") == 'data-show-when="rate_type=A B" data-off-when-hidden hidden'


# ================================================================ quick billing (the pattern on a real form)

@pytest.fixture
def ns(company, factory, owner):
    return sh.build(company, factory, owner)


def test_quick_billing_folds_only_the_notes(ns, owner_c):
    html = html_of(owner_c.get(reverse("billing")))
    assert in_view(html, "customer", "location", "date")
    assert folded(html, "notes") and "notes" in fold_of(html, "notes")[1]
    assert '<label for="notes">Notes</label>' in html


def test_quick_billing_opens_the_fold_when_the_notes_come_back(ns, owner_c):
    r = owner_c.post(reverse("billing"), {"customer": ns.local.pk, "location": ns.godown.pk, "date": DAY.isoformat(),
                                          "notes": "deliver by hand", "action": "draft"})
    html = html_of(r)                                   # no pieces: refused, and the form comes back
    assert folded(html, "notes", is_open=True) and 'value="deliver by hand"' in html


def test_quick_billing_shows_the_gst_template_only_for_that_choice(ns, owner_c):
    sh.gst_on(ns.company)
    html = html_of(owner_c.get(reverse("billing")))
    assert 'data-show-when="tax_mode=template" hidden><label for="gst_template">' in html
    assert 'data-show-when="tax_mode=template none" hidden><label for="tax_note">' in html
    assert "js/reveal.js" in html and "data-tax-show" not in html
    r = owner_c.post(reverse("billing"), {"customer": ns.local.pk, "location": ns.godown.pk, "date": DAY.isoformat(),
                                          "tax_mode": "none", "tax_note": "", "action": "draft"})
    html = html_of(r)
    assert 'data-show-when="tax_mode=template" hidden>' in html
    assert 'data-show-when="tax_mode=template none"><label for="tax_note">' in html


# ================================================================ a supplier, customer or fabricator must be chosen

@pytest.fixture
def vendor(company):
    return parties.create_party(company=company, name="Yarn House", mobile="9833333333", is_vendor=True)


@pytest.fixture
def second_vendor(company):
    return parties.create_party(company=company, name="Aman Trims", mobile="9833333334", is_vendor=True)


@pytest.fixture
def trim(db):
    return Material.objects.create(code="ZIP-9", name="Zip puller", kind="trim", unit=Unit.objects.get(code="PCS"))


@pytest.fixture
def fabric(db):
    return Material.objects.create(code="FAB-9", name="Terry", kind="fabric", unit=Unit.objects.get(code="KG"))


@pytest.fixture
def godown(factory):
    return Location.objects.get(factory=factory, name="Main Godown")


def test_a_purchase_order_needs_its_supplier_chosen(company, factory, owner_c, vendor, second_vendor, trim):
    assert starts_blank(html_of(owner_c.get(reverse("po_new"))), "vendor")
    typed = {"vendor": "", "date": "2026-06-15", "expected_date": "2026-06-30", "remarks": "urgent",
             "item": [f"m:{trim.pk}", ""], "qty": ["120", ""], "rate": ["3.5", ""]}
    html = html_of(owner_c.post(reverse("po_new"), typed))
    assert "Choose the supplier." in flashed(html) and not PurchaseOrder.objects.exists()
    assert f'<option value="m:{trim.pk}" selected>' in html and 'name="qty" value="120"' in html and 'name="rate" value="3.5"' in html
    assert 'value="2026-06-30"' in html and 'value="urgent"' in html and starts_blank(html, "vendor")
    r = owner_c.post(reverse("po_new"), {**typed, "vendor": second_vendor.pk})
    assert r.status_code == 302 and PurchaseOrder.objects.get().vendor == second_vendor


def test_goods_received_needs_its_supplier_chosen_unless_the_order_names_one(company, factory, owner, owner_c, vendor,
                                                                              second_vendor, trim, fabric, godown):
    assert starts_blank(html_of(owner_c.get(reverse("grn_new"))), "vendor")
    typed = {"vendor": "", "location": godown.pk, "date": "2026-06-16", "vendor_challan_no": "CH-5", "remarks": "two bales",
             "item": [f"m:{trim.pk}", f"m:{fabric.pk}", ""], "rate": ["2", "210", ""], "qty": ["40", "", ""],
             "po_line": ["", "", ""], "rolls": ["", "R-1, 24.5\nR-2, 30", ""]}
    html = html_of(owner_c.post(reverse("grn_new"), typed))
    assert "Choose the supplier." in flashed(html) and not Grn.objects.exists() and starts_blank(html, "vendor")
    assert 'name="qty" value="40"' in html and "R-1, 24.5\nR-2, 30</textarea>" in html and 'value="CH-5"' in html
    assert f'<option value="m:{fabric.pk}" selected>' in html and 'value="two bales"' in html
    po = po_service.create_and_submit(company=company, factory=factory, vendor=second_vendor, date=DAY, user=owner,
                                      lines=[po_service.POLineSpec(trim, D("10"), D("2"))])
    assert chosen(html_of(owner_c.get(reverse("grn_new"), {"po": po.pk})), "vendor") == str(second_vendor.pk)
    r = owner_c.post(reverse("grn_new"), {**typed, "vendor": vendor.pk})
    assert r.status_code == 302 and Grn.objects.get().vendor == vendor


def test_a_return_to_the_supplier_needs_its_supplier_chosen(company, factory, owner_c, vendor, second_vendor, trim, godown):
    assert starts_blank(html_of(owner_c.get(reverse("debitnote_new"))), "vendor")
    typed = {"vendor": "", "date": "2026-06-16", "reason": "wrong shade", "item": [f"m:{trim.pk}"], "location": [godown.pk],
             "roll": [""], "qty": ["7"], "rate": ["2.25"]}
    html = html_of(owner_c.post(reverse("debitnote_new"), typed))
    assert "Choose the supplier." in flashed(html) and not DebitNote.objects.exists() and starts_blank(html, "vendor")
    assert 'value="wrong shade"' in html and 'name="qty" value="7"' in html and 'name="rate" value="2.25"' in html
    assert f'<option value="m:{trim.pk}" selected>' in html


def test_a_sale_order_needs_its_customer_chosen(ns, owner_c):
    assert starts_blank(html_of(owner_c.get(reverse("saleorder_new"))), "customer")
    black, m = ns.colours["Black"], ns.sizes["M"]
    typed = {"customer": "", "date": DAY.isoformat(), "due_date": "2026-07-01", "order_type": "stock", "remarks": "by road",
             "style": [ns.style.pk], f"rate_{ns.style.pk}": "450", f"disc_{ns.style.pk}": "",
             f"q_{ns.style.pk}_{black.pk}_{m.pk}": "12"}
    html = html_of(owner_c.post(reverse("saleorder_new"), typed))
    assert "Choose the customer." in flashed(html) and not SaleOrder.objects.exists() and starts_blank(html, "customer")
    assert f'name="q_{ns.style.pk}_{black.pk}_{m.pk}" value="12"' in html and 'value="2026-07-01"' in html and 'value="by road"' in html
    r = owner_c.post(reverse("saleorder_new"), {**typed, "customer": ns.far.pk})
    assert r.status_code == 302 and SaleOrder.objects.get().customer == ns.far


def test_quick_billing_needs_its_customer_chosen_unless_the_link_names_one(ns, owner_c):
    assert starts_blank(html_of(owner_c.get(reverse("billing"))), "customer")
    assert chosen(html_of(owner_c.get(reverse("billing"), {"customer": ns.far.pk})), "customer") == str(ns.far.pk)
    sku = ns.sku("Black", "M")
    typed = {"customer": "", "location": ns.godown.pk, "date": DAY.isoformat(), "action": "draft", "notes": "counter sale",
             "sku": [sku.pk], "qty": ["3"], "rate": ["500"], "disc": ["2"]}
    html = html_of(owner_c.post(reverse("billing"), typed))
    assert "Choose the customer." in flashed(html) and not SaleInvoice.objects.exists() and starts_blank(html, "customer")
    assert f'<tr data-sku="{sku.pk}">' in html and 'name="qty" value="3"' in html and 'name="rate" value="500"' in html
    assert 'value="counter sale"' in html
    r = owner_c.post(reverse("billing"), {**typed, "customer": ns.local.pk})
    assert r.status_code == 302 and SaleInvoice.objects.get().customer == ns.local


@pytest.fixture
def job(company, factory, owner):
    job = ph.build(company, factory, owner)
    job.bundles = ph.cut(job)
    job.fab = ph.fabricator(company)
    job.other = ph.fabricator(company, name="Gill Tailors", mobile="9811111199")
    for fab in (job.fab, job.other):
        rates.save_rate(party=fab, process=ph.step(job, "STITCH").process, rate_type="A", base_rate=D("25"),
                        effective_from=date(2026, 4, 1))
    return job


def test_sending_to_a_fabricator_needs_the_fabricator_chosen(job, owner_c):
    stitch = ph.step(job, "STITCH")
    assert stitch.party_id is None
    opened = {"lot": job.lot.pk, "step": stitch.pk}
    assert starts_blank(html_of(owner_c.get(reverse("challan_new"), opened)), "party")
    typed = {**opened, "kind": "issue", "factory": job.factory.pk, "party": "", "date": DAY.isoformat(),
             "expected_date": "2026-06-25", "remarks": "handle with care", "bundle": [job.bundles[0].pk, job.bundles[1].pk]}
    html = html_of(owner_c.post(reverse("challan_new"), typed))
    assert "Choose the fabricator." in flashed(html) and not JobWorkChallan.objects.exists() and starts_blank(html, "party")
    assert html.count('name="bundle"') > 2 and html.count(" checked") == 2      # the two ticked bundles stay ticked
    assert 'value="2026-06-25"' in html and 'value="handle with care"' in html
    r = owner_c.post(reverse("challan_new"), {**typed, "party": job.other.pk})
    assert r.status_code == 302, re.findall(r"<li class=.error.>(.*?)</li>", r.content.decode())
    assert JobWorkChallan.objects.get().party == job.other


def test_sending_to_a_fabricator_keeps_the_fabricator_the_step_or_the_link_names(job, owner_c):
    stitch = ph.step(job, "STITCH")
    opened = {"lot": job.lot.pk, "step": stitch.pk}
    assert chosen(html_of(owner_c.get(reverse("challan_new"), {**opened, "party": job.other.pk})), "party") == str(job.other.pk)
    stitch.party = job.fab
    stitch.save()
    assert chosen(html_of(owner_c.get(reverse("challan_new"), opened)), "party") == str(job.fab.pk)
    # what the user picked wins over the step's own fabricator when the form comes back
    html = html_of(owner_c.post(reverse("challan_new"), {**opened, "kind": "issue", "factory": job.factory.pk,
                                                         "party": job.other.pk, "date": DAY.isoformat()}))
    assert chosen(html, "party") == str(job.other.pk) and html.count("selected>Gill Tailors") == 1
    assert "selected>Sharma Stitching" not in html


def test_a_labour_rate_needs_its_fabricator_and_process_chosen(job, owner_c):
    html = html_of(owner_c.get(reverse("rate_new")))
    assert starts_blank(html, "party") and starts_blank(html, "process")
    stitch, s, m = Process.objects.get(code="STITCH"), Size.objects.get(code="S"), Size.objects.get(code="M")
    typed = {"party": "", "process": stitch.pk, "rate_type": "B", "effective_from": "2026-06-01", "base_rate": "22",
             "flat_amount": "", "rework_rate": "4", "addon_name": ["Embroidery", "", ""], "addon_amount": ["3.5", "", ""],
             f"size_{s.pk}": "20", f"size_{m.pk}": "21"}
    html = html_of(owner_c.post(reverse("rate_new"), typed))
    assert "Choose the fabricator." in flashed(html) and LabourRate.objects.count() == 2 and starts_blank(html, "party")
    assert chosen(html, "process") == str(stitch.pk) and chosen(html, "rate_type") == "B"
    assert re.search(r'name="base_rate"[^>]* value="22"', html) and 'value="Embroidery"' in html
    assert 'value="3.5"' in html and re.search(rf'name="size_{s.pk}"[^>]* value="20"', html)
    assert re.search(rf'name="size_{m.pk}"[^>]* value="21"', html)
    html = html_of(owner_c.post(reverse("rate_new"), {**typed, "party": job.fab.pk, "process": ""}))
    assert "Choose the process." in flashed(html) and LabourRate.objects.count() == 2
    assert chosen(html, "party") == str(job.fab.pk) and starts_blank(html, "process")
    r = owner_c.post(reverse("rate_new"), {**typed, "party": job.fab.pk})
    rate = LabourRate.objects.get(rate_type="B")
    assert r.status_code == 302 and rate.party == job.fab and rate.base_rate == D("22") and rate.addons.get().amount == D("3.5")


def test_the_labour_rate_form_opens_on_the_fabricator_a_link_names(job, owner_c):
    stitch = Process.objects.get(code="STITCH")
    html = html_of(owner_c.get(reverse("rate_new"), {"party": job.fab.pk, "process": stitch.pk}))
    assert chosen(html, "party") == str(job.fab.pk) and chosen(html, "process") == str(stitch.pk)


# ================================================================ masters

PARTY_FOLDED = ("contact_person", "mobile2", "mobile3", "landline", "email", "pan", "tds_section", "category", "price_list",
                "discount_pct", "credit_limit", "credit_days", "payment_terms", "agent", "transporter", "destination",
                "is_agent", "is_transporter", "is_active")


def test_a_new_party_asks_for_the_firm_what_it_is_and_a_mobile(company, owner_c):
    html = html_of(owner_c.get(reverse("party_new")))
    assert in_view(html, "name", "mobile", "is_customer", "is_vendor", "is_fabricator")
    assert folded(html, "gstin", *PARTY_FOLDED)
    text = flashed(html)
    for words in ("Firm name", "This party is a", "Customer", "Supplier", "Fabricator", "TDS section", "Active", "GSTIN", "PAN"):
        assert words in text, words
    for old in ("Is vendor", "Is customer", "Is fabricator", "Is agent", "Is transporter", "Tds section", "Is active", "Gstin"):
        assert old not in text, old
    assert 'name="is_active" id="id_is_active" checked' in html or re.search(r'name="is_active"[^>]*checked', html)
    for name in ("name", "mobile", "is_vendor", "email", "tds_section", "is_active"):      # every input keeps its label
        assert f'<label for="id_{name}">' in html, name


def test_a_gst_registered_company_is_asked_for_the_gstin_every_time(company, owner_c):
    sh.gst_on(company)
    html = html_of(owner_c.get(reverse("party_new")))
    assert in_view(html, "name", "mobile", "gstin") and folded(html, *PARTY_FOLDED)


def test_the_party_form_still_opens_ticked_for_the_role_a_link_names(company, owner_c):
    html = html_of(owner_c.get(reverse("party_new"), {"role": "vendor"}))
    assert re.search(r'name="is_vendor"[^>]*checked', html) and not re.search(r'name="is_customer"[^>]*checked', html)
    assert folded(html, *PARTY_FOLDED)


def test_the_party_fold_opens_for_a_saved_value_and_for_an_error(company, owner_c):
    plain = parties.create_party(company=company, name="Plain Traders", mobile="9800000001", is_customer=True)
    assert folded(html_of(owner_c.get(reverse("party_edit", args=[plain.pk]))), *PARTY_FOLDED)
    terms = parties.create_party(company=company, name="Credit Traders", mobile="9800000002", is_customer=True, credit_days=30)
    assert folded(html_of(owner_c.get(reverse("party_edit", args=[terms.pk]))), *PARTY_FOLDED, is_open=True)
    off = parties.create_party(company=company, name="Old Traders", mobile="9800000003", is_customer=True, is_active=False)
    assert folded(html_of(owner_c.get(reverse("party_edit", args=[off.pk]))), *PARTY_FOLDED, is_open=True)
    html = html_of(owner_c.post(reverse("party_new"), {"name": "Nayi Firm", "mobile": "9800000004", "is_customer": "on",
                                                       "is_active": "on", "email": "not-an-email"}))
    assert folded(html, *PARTY_FOLDED, is_open=True) and 'class="error"' in fold_of(html, "email")[2]


def test_saving_a_party_from_the_short_form_saves_what_it_always_did(company, owner_c):
    from masters.models import Party

    html = html_of(owner_c.get(reverse("party_new"), {"role": "customer"}))
    untouched = {"discount_pct": "0", "credit_limit": "0", "credit_days": "0", "is_active": "on"}
    for name, value in untouched.items():           # the folded fields post their defaults when left alone
        assert re.search(rf'name="{name}"[^>]*(value="{value}"|checked)', html), name
    r = owner_c.post(reverse("party_new"), {"name": "Short Form Traders", "mobile": "9800000005", "is_customer": "on", **untouched})
    party = Party.objects.get(name="Short Form Traders")
    assert r.status_code == 302 and party.is_customer and party.is_active and not party.is_vendor
    assert (party.discount_pct, party.credit_limit, party.credit_days, party.email, party.gstin) == (D("0"), D("0"), 0, "", "")


STYLE_FOLDED = ("description", "mrp", "image", "is_archived")


def test_a_new_style_folds_what_is_rarely_filled(company, owner_c):
    html = html_of(owner_c.get(reverse("style_new")))
    assert in_view(html, "style_no", "name", "product", "default_route", "colours", "sizes")
    assert folded(html, "hsn", *STYLE_FOLDED)
    text = flashed(html)
    assert "HSN code" in text and "MRP" in text and "Archived" in text
    assert "Hsn" not in text and "Mrp" not in text and "Is archived" not in text
    sh.gst_on(company)
    html = html_of(owner_c.get(reverse("style_new")))
    assert in_view(html, "style_no", "name", "product", "default_route", "hsn") and folded(html, *STYLE_FOLDED)


def test_the_style_fold_opens_for_a_saved_value_and_for_an_error(ns, owner_c):
    assert folded(html_of(owner_c.get(reverse("style_edit", args=[ns.style.pk]))), *STYLE_FOLDED, is_open=True)   # it has an HSN code
    sh.gst_on(ns.company)
    assert folded(html_of(owner_c.get(reverse("style_edit", args=[ns.style.pk]))), *STYLE_FOLDED)                 # now in plain view
    ns.style.mrp = D("999")
    ns.style.save()
    assert folded(html_of(owner_c.get(reverse("style_edit", args=[ns.style.pk]))), *STYLE_FOLDED, is_open=True)
    html = html_of(owner_c.post(reverse("style_new"), {"style_no": "N-1", "name": "New", "mrp": "abc"}))
    assert folded(html, *STYLE_FOLDED, is_open=True) and 'class="error"' in fold_of(html, "mrp")[2]


def test_a_new_material_asks_for_four_things_and_is_active(company, owner_c):
    html = html_of(owner_c.get(reverse("material_new")))
    assert in_view(html, "code", "name", "kind", "unit") and folded(html, "composition", "gsm", "width_cm")
    assert 'name="is_active"' not in html                      # a new one is active; the box appears on edit
    text = flashed(html)
    assert "GSM" in text and "Width (cm)" in text and "Gsm" not in text and "Width cm" not in text
    r = owner_c.post(reverse("material_new"), {"code": "RIB-1", "name": "Rib", "kind": "fabric", "unit": Unit.objects.get(code="KG").pk})
    rib = Material.objects.get(code="RIB-1")
    assert r.status_code == 302 and rib.is_active and rib.gsm is None and rib.composition == ""


def test_the_material_fold_on_edit_holds_active_and_opens_when_it_matters(company, owner_c, trim):
    url = reverse("material_edit", args=[trim.pk])
    html = html_of(owner_c.get(url))
    assert folded(html, "composition", "gsm", "width_cm", "is_active") and '<label for="id_is_active">Active</label>' in html
    trim.gsm = 180
    trim.save()
    assert folded(html_of(owner_c.get(url)), "composition", "gsm", "width_cm", "is_active", is_open=True)
    trim.gsm, trim.is_active = None, False
    trim.save()
    assert folded(html_of(owner_c.get(url)), "is_active", is_open=True)
    html = html_of(owner_c.post(url, {"code": trim.code, "name": trim.name, "kind": trim.kind, "unit": trim.unit_id,
                                      "is_active": "on", "gsm": "heavy"}))
    assert folded(html, "gsm", is_open=True) and 'class="error"' in fold_of(html, "gsm")[2]
    r = owner_c.post(url, {"code": trim.code, "name": trim.name, "kind": trim.kind, "unit": trim.unit_id})
    trim.refresh_from_db()
    assert r.status_code == 302 and trim.is_active is False     # an unticked Active on edit still switches it off


def test_small_masters_show_active_only_on_edit(company, owner_c):
    from masters.models import Colour

    html = html_of(owner_c.get(reverse("colour_new")))
    assert 'name="is_active"' not in html and not folds(html)
    assert owner_c.post(reverse("colour_new"), {"name": "Olive"}).status_code == 302
    olive = Colour.objects.get(name="Olive")
    assert olive.is_active
    html = html_of(owner_c.get(reverse("colour_edit", args=[olive.pk])))
    assert in_view(html, "name", "code", "is_active") and '<label for="id_is_active">Active</label>' in html and "Is active" not in html
    owner_c.post(reverse("colour_edit", args=[olive.pk]), {"name": "Olive"})
    olive.refresh_from_db()
    assert olive.is_active is False


def test_the_bom_folds_only_its_version_note(ns, owner_c, trim):
    url = reverse("bom_edit", args=[ns.style.pk])
    html = html_of(owner_c.get(url))
    assert in_view(html, "material", "qty", "wastage", "charge_desc") and folded(html, "notes")
    assert '<label for="notes">Version note</label>' in html and f'name="size_{ns.sizes["S"].pk}"' in html
    html = html_of(owner_c.post(url, {"material": [trim.pk], "qty": ["lots"], "wastage": [""], "notes": "new zip",
                                      **{f"size_{s.pk}": [""] for s in ns.sizes.values()},
                                      "charge_desc": [""], "charge_process": [""], "charge_amount": [""]}))
    assert folded(html, "notes", is_open=True) and 'value="new zip"' in html


# ================================================================ buying

def hidden_for_choice(html, name):
    """Is the field posted as `name` inside a block the server has hidden for the current choice?"""
    block = re.search(rf'<div[^>]*data-show-when="[^"]*"[^>]*>(?:(?!data-show-when).)*?name="{name}"', html, re.S)
    assert block, name
    return bool(re.match(r'<div[^>]*[" ]hidden>', block.group(0)))


def test_the_purchase_order_shows_supplier_date_and_lines(company, factory, owner, owner_c, vendor, trim):
    html = html_of(owner_c.get(reverse("po_new")))
    assert in_view(html, "vendor", "date", "item", "qty", "rate") and folded(html, "expected_date", "remarks")
    assert '<label for="vendor">Supplier</label>' in html and '<label for="remarks">Notes</label>' in html
    assert '<label for="expected_date">Expected by</label>' in html
    text = flashed(html)
    assert "Vendor" not in text and "Remarks" not in text
    assert html.index('value="draft">Save draft') < html.index('value="submit">Save and submit')      # the safe button first
    po = po_service.create_po(company=company, factory=factory, vendor=vendor, date=DAY, user=owner, remarks="by Friday",
                              lines=[po_service.POLineSpec(trim, D("10"), D("2"))])
    assert folded(html_of(owner_c.get(reverse("po_edit", args=[po.pk]))), "expected_date", "remarks", is_open=True)
    html = html_of(owner_c.post(reverse("po_new"), {"vendor": vendor.pk, "date": "2026-06-15", "expected_date": "soon",
                                                    "item": [f"m:{trim.pk}"], "qty": ["1"], "rate": ["1"]}))
    assert folded(html, "expected_date", "remarks", is_open=True) and "not a valid date" in flashed(html)


def test_a_purchase_order_saved_from_the_short_form_is_the_same_order(company, factory, owner_c, vendor, trim):
    r = owner_c.post(reverse("po_new"), {"vendor": vendor.pk, "date": "2026-06-15", "expected_date": "", "remarks": "",
                                         "item": [f"m:{trim.pk}"], "qty": ["12"], "rate": ["3"]})
    po = PurchaseOrder.objects.get()
    assert r.status_code == 302 and (po.expected_date, po.remarks, po.status) == (None, "", "draft")
    assert po.lines.get().qty == D("12")


def test_goods_received_shows_supplier_place_date_and_lines(company, factory, owner_c, vendor, trim, godown):
    html = html_of(owner_c.get(reverse("grn_new")))
    assert in_view(html, "vendor", "location", "date", "item", "rate", "qty", "rolls")
    assert folded(html, "vendor_challan_no", "vendor_challan_date", "remarks")
    text = flashed(html)
    assert "Goods received (GRN)" in text and "Supplier's challan no." in text and "Notes" in text
    assert "New GRN" not in text and "Vendor" not in text and "vendor" not in text and "Remarks" not in text
    for label in ('<label for="vendor">Supplier</label>', '<label for="vcn">', '<label for="vcd">', '<label for="rem">Notes</label>'):
        assert label in html
    r = owner_c.post(reverse("grn_new"), {"vendor": vendor.pk, "location": godown.pk, "date": "2026-06-16",
                                          "vendor_challan_no": "", "vendor_challan_date": "", "remarks": "",
                                          "item": [f"m:{trim.pk}"], "rate": ["2"], "qty": ["40"], "po_line": [""], "rolls": [""]},
                     follow=True)
    grn = Grn.objects.get()
    assert (grn.vendor_challan_no, grn.vendor_challan_date, grn.remarks) == ("", None, "")
    assert "Goods received saved. Now record the QC result for each line." in flashed(r.content.decode())
    grn.vendor_challan_no = "CH-9"
    grn.save()
    html = html_of(owner_c.get(reverse("grn_edit", args=[grn.pk])))
    assert "Edit goods received" in flashed(html) and "Edit GRN" not in html
    assert folded(html, "vendor_challan_no", "remarks", is_open=True)


@pytest.fixture
def received(company, factory, owner, vendor, trim, godown):
    from purchases.services import grn as grns

    g = grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=DAY, user=owner,
                        lines=[grns.GrnLineSpec(item=trim, rate=D("10"), qty_received=D("100"))])
    grns.finish_qc(g, user=owner)
    return grns.post_grn(g, user=owner)


def test_the_supplier_bill_shows_the_bill_its_lines_and_one_gst_choice(received, owner_c, vendor):
    line = received.lines.get()
    html = html_of(owner_c.get(reverse("invoice_new"), {"vendor": vendor.pk}))
    assert in_view(html, "vendor_invoice_no", "vendor_invoice_date", f"use_{line.pk}", f"qty_{line.pk}", "tax_mode")
    assert folded(html, "gst_template", "manual_cgst", "manual_sgst", "manual_igst", "itc_claimable", "tds_template",
                  title="Tax (GST / TDS)")
    assert folded(html, "date", "notes")
    assert chosen(html, "tax_mode") == "none"
    text = flashed(html)
    for words in ("New supplier bill", "Supplier's bill no.", "Bill date", "Received goods to bill", "Received rate",
                  "Against goods received (GRN)", "Booking date", "Notes"):
        assert words in text, words
    for old in ("purchase invoice", "Vendor", "vendor", "GRN lines", "GRN rate"):
        assert old not in text, old
    for name in ("gst_template", "manual_cgst", "itc_claimable"):       # no GST chosen: none of its details show
        assert hidden_for_choice(html, name), name
    assert 'data-show-when="tax_mode=template reverse_charge" data-off-when-hidden hidden' in html and "js/reveal.js" in html
    assert re.search(r'name="itc_claimable" checked', html)             # hidden, and still posts what it always did


def test_the_supplier_bill_shows_only_the_details_of_the_gst_choice(received, owner_c, vendor):
    line = received.lines.get()
    base = {"vendor": vendor.pk, "vendor_invoice_no": "", "vendor_invoice_date": "2026-06-15", "date": "2026-06-15",
            f"use_{line.pk}": "on", f"qty_{line.pk}": "100", f"rate_{line.pk}": "10", "itc_claimable": "on"}
    shown = {"none": (), "template": ("gst_template", "itc_claimable"), "reverse_charge": ("gst_template", "itc_claimable"),
             "manual": ("manual_cgst", "manual_sgst", "manual_igst", "itc_claimable")}
    for mode, visible in shown.items():
        html = html_of(owner_c.post(reverse("invoice_new"), {**base, "tax_mode": mode}))     # no bill number: it comes back
        assert chosen(html, "tax_mode") == mode
        for name in ("gst_template", "manual_cgst", "manual_sgst", "manual_igst", "itc_claimable"):
            assert hidden_for_choice(html, name) is (name not in visible), (mode, name)
        assert folded(html, "gst_template", "tds_template", title="Tax (GST / TDS)", is_open=mode != "none"), mode


def test_the_supplier_bill_folds_open_for_tds_a_booking_date_or_notes(received, owner_c, vendor):
    from tax.models import TaxTemplate

    line = received.lines.get()
    base = {"vendor": vendor.pk, "vendor_invoice_no": "", "vendor_invoice_date": "2026-06-15",
            f"use_{line.pk}": "on", f"qty_{line.pk}": "100", f"rate_{line.pk}": "10", "itc_claimable": "on", "tax_mode": "none"}
    tds = TaxTemplate.objects.filter(kind="tds", is_active=True).first()
    html = html_of(owner_c.post(reverse("invoice_new"), {**base, "tds_template": tds.pk}))
    assert folded(html, "tds_template", title="Tax (GST / TDS)", is_open=True) and folded(html, "date", "notes")
    html = html_of(owner_c.post(reverse("invoice_new"), {**base, "notes": "second copy"}))
    assert folded(html, "date", "notes", is_open=True) and folded(html, "tds_template", title="Tax (GST / TDS)")
    html = html_of(owner_c.post(reverse("invoice_new"), {**base, "date": "2026-06-20"}))
    assert folded(html, "date", "notes", is_open=True)


def test_a_supplier_bill_saved_from_the_short_form_is_the_same_bill(received, owner_c, vendor):
    from django.utils import timezone
    from purchases.models import PurchaseInvoice

    line = received.lines.get()
    html = html_of(owner_c.get(reverse("invoice_new"), {"vendor": vendor.pk}))
    today = timezone.localdate().isoformat()
    assert re.search(rf'name="date" type="date" value="{today}"', html)          # the folded booking date posts today
    r = owner_c.post(reverse("invoice_new"), {
        "vendor": vendor.pk, "vendor_invoice_no": "YH-1", "vendor_invoice_date": "2026-06-15", "date": "2026-06-15",
        f"use_{line.pk}": "on", f"qty_{line.pk}": "100", f"rate_{line.pk}": "10", "tax_mode": "none", "itc_claimable": "on",
        "manual_cgst": "", "manual_sgst": "", "manual_igst": "", "tds_template": "", "notes": ""}, follow=True)
    inv = PurchaseInvoice.objects.get()
    assert (inv.tax_mode, inv.gst_template, inv.itc_claimable, inv.tds_template, inv.notes) == ("none", None, True, None, "")
    assert inv.payable == D("1000.00") and "Supplier bill saved as a draft." in flashed(r.content.decode())
    assert "Edit draft supplier bill" in flashed(html_of(owner_c.get(reverse("invoice_edit", args=[inv.pk]))))


def test_the_direct_supplier_bill_keeps_its_place_in_view(company, owner_c, vendor):
    html = html_of(owner_c.get(reverse("invoice_new"), {"vendor": vendor.pk, "mode": "direct"}))
    assert in_view(html, "vendor_invoice_no", "vendor_invoice_date", "location", "item", "qty", "rate", "tax_mode")
    assert folded(html, "date", "notes")


def test_the_return_to_supplier_shows_supplier_date_reason_and_lines(company, factory, owner, owner_c, vendor, trim, godown, received):
    from purchases.services import debit_notes
    from tax.models import TaxTemplate

    html = html_of(owner_c.get(reverse("debitnote_new")))
    assert in_view(html, "vendor", "date", "reason", "item", "location", "roll", "qty", "rate")
    assert folded(html, "gst_template", "itc_claimable", title="Tax (GST)")
    text = flashed(html)
    assert "Return to supplier" in text and "Vendor" not in text and "vendor" not in text and "debit note" not in text.lower()
    assert re.search(r'name="itc_claimable" checked', html)
    gst = TaxTemplate.objects.filter(kind="gst", is_active=True, is_reverse_charge=False).first()
    typed = {"vendor": vendor.pk, "date": "2026-06-16", "reason": "", "item": [f"m:{trim.pk}"], "location": [godown.pk],
             "roll": [""], "qty": ["bad"], "rate": ["2"]}
    assert folded(html_of(owner_c.post(reverse("debitnote_new"), {**typed, "itc_claimable": "on"})), "gst_template", title="Tax (GST)")
    assert folded(html_of(owner_c.post(reverse("debitnote_new"), typed)), "itc_claimable", title="Tax (GST)", is_open=True)
    html = html_of(owner_c.post(reverse("debitnote_new"), {**typed, "itc_claimable": "on", "gst_template": gst.pk}))
    assert folded(html, "gst_template", "itc_claimable", title="Tax (GST)", is_open=True)
    note = debit_notes.create_return_note(company=company, factory=factory, vendor=vendor, date=DAY, user=owner, reason="shade",
                                          lines=[debit_notes.ReturnLineSpec(item=trim, qty=D("5"), rate=D("10"), location=godown)])
    html = html_of(owner_c.get(reverse("debitnote_edit", args=[note.pk])))
    assert folded(html, "gst_template", "itc_claimable", title="Tax (GST)") and chosen(html, "vendor") == str(vendor.pk)


# ================================================================ making and job work

def test_the_production_order_shows_dates_and_lines(job, owner_c):
    html = html_of(owner_c.get(reverse("order_new")))
    assert in_view(html, "date", "due_date", "style", "colour", "qty", "ratios")
    assert folded(html, "purpose", "order_reference", "remarks") and chosen(html, "purpose") == "stock"
    assert '<label for="due_date">Due by</label>' in html and '<label for="remarks">Notes</label>' in html
    text = flashed(html)
    assert "Due date" not in text and "Remarks" not in text
    assert "customer" not in text.lower().replace("never sees the customer", "")      # BR-15: no customer on a production screen
    typed = {"date": "2026-06-15", "due_date": "", "purpose": "stock", "order_reference": "", "remarks": "",
             "style": [job.style.pk], "colour": [job.black.pk], "qty": ["many"], "ratios": ["S:1"]}
    assert folded(html_of(owner_c.post(reverse("order_new"), typed)), "purpose", "order_reference", "remarks")
    for change in ({"purpose": "mto"}, {"order_reference": "SO-12"}, {"remarks": "rush"}):
        html = html_of(owner_c.post(reverse("order_new"), {**typed, **change}))
        assert folded(html, "purpose", "order_reference", "remarks", is_open=True), change


def test_a_production_order_saved_from_the_short_form_is_the_same_order(job, owner_c):
    from production.models import ProductionOrder

    before = set(ProductionOrder.objects.values_list("pk", flat=True))
    r = owner_c.post(reverse("order_new"), {"date": "2026-06-15", "due_date": "", "purpose": "stock", "order_reference": "",
                                            "remarks": "", "style": [job.style.pk], "colour": [job.black.pk], "qty": ["60"],
                                            "ratios": ["S:1, M:2"]})
    order = ProductionOrder.objects.exclude(pk__in=before).get()
    assert r.status_code == 302 and (order.purpose, order.order_reference, order.remarks, order.due_date) == ("stock", "", "", None)
    assert folded(html_of(owner_c.get(reverse("order_edit", args=[order.pk]))), "purpose", "order_reference", "remarks")


def test_sending_to_a_fabricator_does_not_ask_the_kind_for_normal_job_work(job, owner_c):
    stitch = ph.step(job, "STITCH")
    html = html_of(owner_c.get(reverse("challan_new"), {"lot": job.lot.pk, "step": stitch.pk}))
    assert in_view(html, "party", "date", "expected_date", "bundle") and 'id="lot"' in html and 'id="step"' in html
    assert folded(html, "remarks") and folded(html, "kind") and chosen(html, "kind") == "issue"
    text = flashed(html)
    assert "Send to fabricator" in text and "Expected by" in text and "Notes" in text
    for old in ("New challan", "Issue to a fabricator", "Save challan", "Expected back by", "Remarks"):
        assert old not in text, old
    assert html.index('value="draft">Save</button>') < html.index('value="issue">Save and issue</button>')     # the safe one first
    assert '<input type="hidden" name="kind" value="issue">' in html
    # rework arrives by its own link: the kind is then shown, already chosen
    html = html_of(owner_c.get(reverse("challan_new"), {"lot": job.lot.pk, "step": stitch.pk, "kind": "rework"}))
    assert folded(html, "kind", is_open=True) and chosen(html, "kind") == "rework" and "for rework" in flashed(html)
    assert '<input type="hidden" name="kind" value="rework">' in html
    html = html_of(owner_c.post(reverse("challan_new"), {"lot": job.lot.pk, "step": stitch.pk, "kind": "issue", "party": "",
                                                         "date": DAY.isoformat(), "remarks": "fragile"}))
    assert folded(html, "remarks", is_open=True)


@pytest.fixture
def out(job):
    from jobwork.services import challans

    return challans.create_and_issue(company=job.company, factory=job.factory, party=job.fab, lot=job.lot,
                                     step=ph.step(job, "STITCH"), bundles=job.bundles[:2], date=DAY, user=job.owner)


def test_receiving_from_a_fabricator_folds_the_place_it_is_received_into(job, out, owner_c):
    from jobwork.models import Receipt

    url = reverse("receipt_new", args=[out.pk])
    html = html_of(owner_c.get(url))
    first = out.bundles.first()
    assert in_view(html, "date", f"use_{first.pk}", f"count_{first.pk}") and folded(html, "location")
    usual = Location.objects.get(factory=job.factory, loc_type="process")
    assert chosen(html, "location") == str(usual.pk)                        # prefilled, exactly as before
    assert '<label for="location">Receive into</label>' in html
    if out.trims.exists():
        assert in_view(html, f"returned_{out.trims.first().pk}")
    other = Location.objects.filter(factory=job.factory, is_active=True).exclude(
        loc_type__in=("transit", "fabricator", "rejects", "process")).first()
    html = html_of(owner_c.post(url, {"date": DAY.isoformat(), "location": other.pk}))       # nothing ticked: it comes back
    assert folded(html, "location", is_open=True) and chosen(html, "location") == str(other.pk)
    r = owner_c.post(url, {"date": DAY.isoformat(), "location": usual.pk, f"use_{first.pk}": "on",
                           f"count_{first.pk}": str(first.qty_issued)})
    assert r.status_code == 302 and Receipt.objects.get().location == usual


def test_the_labour_bill_folds_tds_and_notes(job, out, owner_c):
    from jobwork.services import receipts
    from jobwork.services.receipts import Counted
    from tax.models import TaxTemplate

    receipt = receipts.create_receipt(challan=out, user=job.owner, date=DAY,
                                      counts=[Counted(cb, cb.qty_issued) for cb in out.bundles.all()])
    for line in receipt.lines.all():
        receipts.record_qc(receipt_line=line, accepted=line.qty_received, user=job.owner)
    html = html_of(owner_c.get(reverse("bill_new"), {"party": job.fab.pk}))
    assert in_view(html, "date") and 'id="party"' in html and 'name="qc_' in html
    assert folded(html, "tds_template", "notes") and "TDS, notes" in fold_of(html, "notes")[1]
    tds = TaxTemplate.objects.filter(kind="tds", is_active=True).first()
    html = html_of(owner_c.post(reverse("bill_new"), {"party": job.fab.pk, "date": "not-a-date", "tds_template": tds.pk,
                                                      "notes": "june work"}))
    assert folded(html, "tds_template", "notes", is_open=True) and chosen(html, "tds") == str(tds.pk)
    assert 'value="june work"' in html and 'value="not-a-date"' in html
    html = html_of(owner_c.post(reverse("bill_new"), {"party": job.fab.pk, "date": "not-a-date", "tds_template": "", "notes": ""}))
    assert folded(html, "tds_template", "notes")


RATE_FIELDS = {"A": ("base_rate",), "B": ("base_rate", "addon_name", "addon_amount"), "C": ("size_",), "D": ("flat_amount",)}


def test_the_labour_rate_names_its_types_in_plain_words(job, owner_c):
    html = html_of(owner_c.get(reverse("rate_new")))
    assert in_view(html, "party", "process", "rate_type", "effective_from", "base_rate") and folded(html, "rework_rate")
    options = re.findall(r'<option value="([A-D])"[^>]*>([^<]+)</option>', re.search(r'<select id="rate_type".*?</select>', html, re.S).group(0))
    assert options == [("A", "Per piece"), ("B", "Per piece plus extras"), ("C", "Different rate per size"), ("D", "Fixed amount per lot")]
    text = flashed(html)
    for old in ("(A, B)", "(D)", "type B", "type C", "A - per piece", "Add-ons", "Flat amount"):
        assert old not in text, old
    assert "js/reveal.js" in html and chosen(html, "rate_type") == "A"
    for name in ("party", "process", "rate_type", "effective_from", "base_rate", "flat_amount", "rework_rate"):
        assert f'<label for="{name}">' in html, name


def test_the_labour_rate_shows_only_the_fields_of_the_chosen_type(job, owner_c):
    s = Size.objects.get(code="S")
    for rate_type, shown in RATE_FIELDS.items():
        html = html_of(owner_c.post(reverse("rate_new"), {"party": "", "process": "", "rate_type": rate_type,
                                                          "effective_from": "2026-06-01", "addon_name": ["", "", ""],
                                                          "addon_amount": ["", "", ""]}))
        assert chosen(html, "rate_type") == rate_type
        for name in ("base_rate", "addon_name", "flat_amount", f"size_{s.pk}"):
            wanted = any(name.startswith(prefix) for prefix in shown)
            assert hidden_for_choice(html, name) is (not wanted), (rate_type, name)
            block = re.search(rf'<div[^>]*data-show-when="[^"]*"[^>]*>(?:(?!data-show-when).)*?name="{name}"', html, re.S).group(0)
            assert "data-off-when-hidden" in block.split(">", 1)[0]        # a rate typed for another type is never sent
        assert folded(html, "rework_rate")
    html = html_of(owner_c.post(reverse("rate_new"), {"party": "", "process": "", "rate_type": "A", "rework_rate": "4"}))
    assert folded(html, "rework_rate", is_open=True)


def test_each_labour_rate_type_saves_what_it_always_did(job, owner_c):
    wash, s, m = Process.objects.get(code="WASH"), Size.objects.get(code="S"), Size.objects.get(code="M")
    base = {"party": job.fab.pk, "process": wash.pk}
    # the fields of the other types are not sent at all, as when the browser has switched them off
    assert owner_c.post(reverse("rate_new"), {**base, "rate_type": "A", "effective_from": "2026-05-01", "base_rate": "12"}).status_code == 302
    assert owner_c.post(reverse("rate_new"), {**base, "rate_type": "B", "effective_from": "2026-05-02", "base_rate": "12",
                                              "addon_name": ["Print", ""], "addon_amount": ["2", ""]}).status_code == 302
    assert owner_c.post(reverse("rate_new"), {**base, "rate_type": "C", "effective_from": "2026-05-03",
                                              f"size_{s.pk}": "10", f"size_{m.pk}": "11"}).status_code == 302
    assert owner_c.post(reverse("rate_new"), {**base, "rate_type": "D", "effective_from": "2026-05-04", "flat_amount": "900",
                                              "rework_rate": "3"}).status_code == 302
    got = {r.rate_type: r for r in LabourRate.objects.filter(process=wash)}
    assert (got["A"].base_rate, got["A"].flat_amount, got["A"].rework_rate, got["A"].addons.count()) == (D("12"), D("0"), D("0"), 0)
    assert (got["B"].base_rate, got["B"].addons.get().name, got["B"].addons.get().amount) == (D("12"), "Print", D("2"))
    assert (got["C"].base_rate, sorted(x.amount for x in got["C"].sizes.all())) == (D("0"), [D("10"), D("11")])
    assert (got["D"].flat_amount, got["D"].base_rate, got["D"].rework_rate) == (D("900"), D("0"), D("3"))
    # and sent blank, as a browser without the script would send them: the same rates
    r = owner_c.post(reverse("rate_new"), {**base, "rate_type": "D", "effective_from": "2026-05-05", "flat_amount": "950",
                                           "base_rate": "", "rework_rate": "", "addon_name": ["", "", ""],
                                           "addon_amount": ["", "", ""], f"size_{s.pk}": ""})
    again = LabourRate.objects.get(process=wash, effective_from=date(2026, 5, 5))
    assert r.status_code == 302 and (again.flat_amount, again.base_rate, again.addons.count(), again.sizes.count()) == (D("950"), D("0"), 0, 0)
    listing = flashed(html_of(owner_c.get(reverse("rate_list"))))
    assert "Per piece plus extras" in listing and "Fixed amount per lot" in listing and "A - per piece" not in listing


def test_a_labour_rate_is_refused_in_plain_words(job, owner_c):
    wash = Process.objects.get(code="WASH")
    base = {"party": job.fab.pk, "process": wash.pk, "effective_from": "2026-05-01"}
    for rate_type, message in (("A", "Enter the rate per piece."), ("B", "Enter the rate per piece and at least one extra."),
                               ("C", "Enter the rate for each size."), ("D", "Enter the fixed amount per lot.")):
        text = flashed(html_of(owner_c.post(reverse("rate_new"), {**base, "rate_type": rate_type})))
        assert message in text and "Type " not in text, rate_type
