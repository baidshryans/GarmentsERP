"""Help page, outstanding-on-selection for vouchers, and the Receive / Pay buttons that open a pre-filled voucher."""
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from core.help import SECTION_FOR_PATH, anchor_for, render_guide
from ledger.models import AccountGroup, Ledger
from ledger.selectors import ledger_position
from ledger.settlement import settlement
from tests import sales_helpers as h
from tests.conftest import IN_YEAR
from tests.test_sales import quick_invoice
from tests.test_voucher_entry import rows

D = Decimal


@pytest.fixture
def client(owner):
    c = Client()
    c.force_login(owner)
    return c


@pytest.fixture
def ns(company, factory, owner):
    return h.build(company, factory, owner)


@pytest.fixture
def supplier(company):
    return Ledger.objects.create(company=company, name="Sharma Fabrics", bill_wise=True,
                                 group=AccountGroup.objects.get(company=company, name="Sundry Creditors"))


def book_vendor_bill(client, factory, supplier, amount="5000.00", ref="PI/77"):
    expense = Ledger.objects.get(system_key="office_expenses")
    body = {"factory": factory.pk, "date": IN_YEAR.isoformat(), "narration": "bill",
            **rows({"ledger": expense, "debit": amount}, {"ledger": supplier, "credit": amount, "ref_type": "new", "reference": ref})}
    r = client.post(reverse("voucher_journal"), body)
    assert r.status_code == 302, r.content.decode()[:400]


# ---------------------------------------------------------------- help

def test_help_page_renders_the_whole_guide(client):
    r = client.get(reverse("help"))
    page = r.content.decode()
    assert r.status_code == 200
    assert "Part A" in page and "Part B" in page
    assert 'id="s23"' in page and 'id="s27"' in page            # section anchors
    assert '<div class="table-scroll"><table>' in page           # tables render
    assert "<script" not in page.split('id="help-body"')[1].split("</article>")[0]   # guide text is never raw HTML


def test_help_needs_a_login(company):
    r = Client().get(reverse("help"))
    assert r.status_code == 302 and "login" in r["Location"]


def test_help_icon_and_menu_entry_are_on_every_page(client):
    page = client.get(reverse("home")).content.decode()
    assert 'aria-label="Help and user guide"' in page and "#i-help" in page
    assert "Help and user guide" in page and reverse("help") in page


def test_help_icon_opens_the_section_for_the_current_screen(client):
    page = client.get(reverse("move_bundles")).content.decode()
    assert f'{reverse("help")}#s23"' in page


def test_every_mapped_section_exists_in_the_guide():
    ids = render_guide()["sections"]
    for prefix, number in SECTION_FOR_PATH:
        assert f"s{number}" in ids, prefix
    assert anchor_for("/nowhere/") == ""


# ---------------------------------------------------------------- outstanding shown on selection

def test_ledger_endpoint_reports_the_outstanding_amount(client, factory, supplier):
    book_vendor_bill(client, factory, supplier)
    data = client.get(reverse("ledger_bills", args=[supplier.pk])).json()["position"]
    assert (data["outstanding"], data["outstanding_side"], data["open_bills"]) == ("5000.00", "Cr", 1)
    assert data["balance"] == "5000.00"


def test_ledger_position_is_information_only(ns, owner):
    quick_invoice(ns, qty="10", rate="500")
    pos = ledger_position(ns.local.customer_ledger, user=owner)
    assert pos["outstanding"] > 0 and pos["open_bills"] == 1


def test_voucher_screens_load_the_position_script(client):
    assert b"js/ledger_position.js" in client.get(reverse("voucher_journal")).content
    assert b'id="party-position"' in client.get(reverse("voucher_sales")).content


# ---------------------------------------------------------------- receive / pay buttons

def test_posted_invoice_offers_receive_payment_with_the_bill_prefilled(ns, client):
    inv = quick_invoice(ns, qty="10", rate="500")
    page = client.get(reverse("saleinvoice_detail", args=[inv.pk])).content.decode()
    assert "Receive money" in page and f"Outstanding {inv.total}" in page
    s = settlement(ns.owner, ledger=inv.customer.customer_ledger, reference=inv.number, direction="receive")
    assert s["due"] == inv.total and s["url"].startswith(reverse("voucher_receipt"))
    form = client.get(s["url"]).content.decode()
    assert f'value="{inv.number}"' in form and f'value="{inv.total}"' in form and '<option value="against" selected' in form


def test_receiving_the_money_settles_the_invoice_and_hides_the_button(ns, client):
    inv = quick_invoice(ns, qty="10", rate="500")
    bank = Ledger.objects.create(company=ns.company, name="HDFC", group=AccountGroup.objects.get(company=ns.company, name="Bank Accounts"))
    s = settlement(ns.owner, ledger=inv.customer.customer_ledger, reference=inv.number, direction="receive")
    r = client.post(reverse("voucher_receipt"), {
        "factory": ns.factory.pk, "date": h.DAY.isoformat(), "account": bank.pk, "narration": "rtgs",
        **rows({"ledger": inv.customer.customer_ledger, "amount": str(s["due"]), "ref_type": "against", "reference": inv.number})})
    assert r.status_code == 302
    page = client.get(reverse("saleinvoice_detail", args=[inv.pk])).content.decode()
    assert "Settled" in page and "Receive money" not in page


def test_vendor_bill_offers_pay_and_the_prefill_ignores_other_voucher_types(client, factory, supplier, owner):
    book_vendor_bill(client, factory, supplier)
    s = settlement(owner, ledger=supplier, reference="PI/77", direction="pay")
    assert s["due"] == D("5000.00") and s["url"].startswith(reverse("voucher_payment"))
    assert b'value="PI/77"' in client.get(s["url"]).content
    # a journal never pre-fills from the query string
    assert b'value="PI/77"' not in client.get(reverse("voucher_journal") + "?ledger=1&ref=PI/77").content
    # a receipt link for a payable bill finds nothing to receive
    assert settlement(owner, ledger=supplier, reference="PI/77", direction="receive")["due"] == 0


def test_no_button_without_permission_to_enter_vouchers(ns, company, factory):
    from tests.test_sales_ui import user_with

    inv = quick_invoice(ns, qty="10", rate="500")
    clerk = user_with("Billing Clerk", "clerk", factory)
    s = settlement(clerk, ledger=inv.customer.customer_ledger, reference=inv.number, direction="receive")
    assert s["due"] == inv.total and s["url"] is None


def test_prefill_rejects_a_foreign_ledger_id(client):
    page = client.get(reverse("voucher_receipt") + "?ledger=999999&amount=5&ref=X").content
    assert b'value="X"' not in page
