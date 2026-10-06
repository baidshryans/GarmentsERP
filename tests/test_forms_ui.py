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
