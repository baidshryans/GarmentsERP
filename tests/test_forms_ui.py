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
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


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
