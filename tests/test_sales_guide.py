"""The selling guide: where a sale is on its way from order to paid, and the one thing it needs next (guided
selling, piece 2d). One test per row of the spec's table, then agreement between the order, packing-list and bill
guides, permissions, each offered link followed to the screen it opens, and the made-to-order row."""
import re
from datetime import date
from decimal import Decimal
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from django.test import Client
from django.urls import reverse
from django.utils.html import escape

from core.exceptions import BusinessRuleError
from core.models import Location, Role, RolePermission
from inventory.models import StockMovement
from inventory.services.opening import OpeningItem, post_opening_stock
from ledger.models import Ledger, Voucher
from ledger.selectors import bill_outstanding
from ledger.services.manual import Row, post_manual_voucher
from ledger.settlement import settlement
from sales.models import PackingList, SaleCreditNote, SaleInvoice, SaleOrder
from sales.services import credit_notes, invoices, orders, packing
from sales.services.guide import (
    creditnote_guide, due, invoice_guide, invoice_next, order_guide, order_next, packing_guide, packing_next,
)
from tests import sales_helpers as h
from tests.conftest import make_user
from tests.test_sales import confirmed_order, pack, quick_invoice

D = Decimal
DAY = h.DAY
WHO = "Receive money from Punjab Traders"


@pytest.fixture
def ns(company, factory, owner):
    return h.build(company, factory, owner)


def draft_order(ns, qty="30", order_type="stock", sizes=("S", "M")):
    return orders.create_order(company=ns.company, factory=ns.factory, customer=ns.local, date=DAY, user=ns.owner,
                               order_type=order_type,
                               lines=[orders.OrderLineSpec(ns.sku("Black", s), D(qty), D("500"), D("0")) for s in sizes])


def draft_pack(ns, order, cartons):
    specs = [packing.CartonSpec({ns.sku("Black", s): D(q) for s, q in c.items()}) for c in cartons]
    return packing.save_packing(order=order, location=ns.godown, date=DAY, cartons=specs, user=ns.owner)


ALL = [{"S": "30", "M": "30"}]


def draft_bill(ns, p):
    return invoices.invoice_from_packing(p, user=ns.owner, date=DAY)


def billed(ns, p):
    return invoices.post_invoice(draft_bill(ns, p), user=ns.owner)


def receive(ns, inv, amount):
    cash = Ledger.objects.get(company=ns.company, system_key="cash")
    return post_manual_voucher(
        company=ns.company, factory=ns.factory, vtype="receipt", on_date=DAY, narration="", header={"account": str(cash.pk)},
        rows=[Row(ledger=str(inv.customer.customer_ledger_id), amount=str(amount), ref_type="against", reference=inv.number)],
        user=ns.owner)


def draft_return(ns, inv, qty="3"):
    return credit_notes.save_credit_note(invoice=inv, location=ns.godown, date=DAY, lines=[(inv.lines.first(), D(qty))],
                                         reason="Torn", user=ns.owner)


def order_of(o):
    return SaleOrder.objects.select_related("customer", "factory", "production_order").get(pk=o.pk)


def packing_of(p):
    return PackingList.objects.select_related("order__customer", "factory", "location").get(pk=p.pk)


def inv_of(i):
    return SaleInvoice.objects.select_related("customer", "factory", "order", "packing").get(pk=i.pk)


def note_of(n):
    return SaleCreditNote.objects.select_related("customer", "factory", "invoice").get(pk=n.pk)


def offered(g):
    return [a for a in [g["primary"], *g["others"]] if a]


def seen(g):
    return [(a["label"], a["url"]) for a in offered(g)]


def states(g):
    return {s["label"]: s["state"] for s in g["journey"]}


def details(g):
    return {s["label"]: s["detail"] for s in g["journey"] if s["detail"]}


def current(g):
    return [s["label"] for s in g["journey"] if s["current"]]


def receive_link(inv, amount):
    return reverse("voucher_receipt") + "?" + urlencode({
        "ledger": inv.customer.customer_ledger_id, "amount": amount, "ref": inv.number,
        "narration": f"Received against {inv.number}"})


def role_user(name, grants, factory):
    """A user whose own role holds exactly these screen permissions: {screen: [actions]}."""
    role = Role.objects.create(name=f"{name} role")
    for screen, actions in grants.items():
        for action in actions:
            RolePermission.objects.create(role=role, screen=screen, action=action)
    u = make_user(name)
    u.roles.add(role)
    u.allowed_factories.add(factory)
    return u


def seeded(role, name, factory):
    u = make_user(name)
    u.roles.add(Role.objects.get(name=role))
    u.allowed_factories.add(factory)
    return u


def login(user):
    c = Client()
    c.force_login(user)
    return c


def follow_links(ns, g, user=None):
    """Open every offered link as the user would, and check the screen it lands on really offers that step for that
    very document."""
    c = login(user or ns.owner)
    for a in offered(g):
        r = c.get(a["url"])
        assert r.status_code == 200, a
        html, ctx, label = r.content.decode(), r.context, a["label"]
        if label == "Confirm order":
            assert a["url"] == reverse("saleorder_detail", args=[ctx["order"].pk])
            assert ctx["order"].status == "draft" and 'name="action" value="confirm"' in html
        elif label == "Pack goods":
            order = ctx["order"]
            assert a["url"] == reverse("packing_new", args=[order.pk]) and ctx["packing"] is None
            assert order.status in ("confirmed", "partly_dispatched") and any(row["left"] > 0 for row in ctx["rows"])
            assert f"{sum(int(row['left']) for row in ctx['rows'])} pieces" in a["hint"]
        elif label == "Finish packing":
            assert a["url"] == reverse("packing_detail", args=[ctx["p"].pk])
            assert ctx["p"].status == "draft" and 'name="action" value="finalize"' in html
        elif label == "Make bill":
            assert a["url"] == reverse("packing_detail", args=[ctx["p"].pk])
            assert ctx["p"].status == "packed" and ctx["invoice"] is None and 'name="action" value="invoice"' in html
        elif label == "Post bill":
            assert a["url"] == reverse("saleinvoice_detail", args=[ctx["inv"].pk])
            assert ctx["inv"].status == "draft" and 'name="action" value="post"' in html
        elif label == WHO:
            # Money received opens with one row filled in: this customer, the amount the button promised, against this bill
            asked = {k: v[0] for k, v in parse_qs(urlsplit(a["url"]).query).items()}
            row = ctx["rows"][0]
            assert ctx["vtype"] == "receipt" and urlsplit(a["url"]).path == reverse("voucher_receipt")
            assert (row["ledger"], row["amount"], row["reference"], row["ref_type"]) == (
                str(ns.local.customer_ledger_id), asked["amount"], asked["ref"], "against")
            assert D(asked["amount"]) > 0 and f"{asked['amount']} is still to be received on {asked['ref']}" in a["hint"]
            assert SaleInvoice.objects.filter(customer=ns.local, status="posted", number=asked["ref"]).exists()
            assert f'value="{asked["amount"]}"' in html and f'value="{asked["ref"]}"' in html
        elif label == "Post return":
            note = ctx["note"]
            assert a["url"] == reverse("salecn_detail", args=[note.pk])
            assert note.status == "draft" and 'name="action" value="post"' in html
        else:
            raise AssertionError(f"a link the guide should not offer: {a}")


# ---------------- one test per row of the table ----------------

def test_a_draft_order_is_confirmed(ns):
    o = draft_order(ns)
    g = order_guide(order_of(o), ns.owner)
    assert seen(g) == [("Confirm order", reverse("saleorder_detail", args=[o.pk]))]
    assert states(g) == {"Ordered": "done", "Confirmed": "now", "Packed": "todo", "Billed": "todo", "Paid": "todo"}
    assert current(g) == ["Confirmed"] and details(g) == {"Ordered": "60 pieces"}
    assert not g["complete"] and not g["closed"] and g["pack"] is None
    assert order_next(order_of(o), ns.owner)["label"] == "Confirm order"
    follow_links(ns, g)


def test_a_confirmed_order_with_pieces_to_pack_asks_to_pack_them(ns):
    o = confirmed_order(ns)
    g = order_guide(order_of(o), ns.owner)
    assert seen(g) == [("Pack goods", reverse("packing_new", args=[o.pk]))]
    assert g["primary"]["hint"] == f"60 pieces of {o.number} are still to be packed."
    assert states(g) == {"Ordered": "done", "Confirmed": "done", "Packed": "now", "Billed": "todo", "Paid": "todo"}
    assert details(g)["Packed"] == "0 of 60" and current(g) == ["Packed"]
    assert g["pack"] == g["primary"]
    follow_links(ns, g)


def test_a_draft_packing_list_asks_to_be_finished_and_the_order_stops_asking_to_pack(ns):
    o = confirmed_order(ns)
    p = draft_pack(ns, o, [{"S": "10"}])
    g = order_guide(order_of(o), ns.owner)
    assert seen(g) == [("Finish packing", reverse("packing_detail", args=[p.pk]))]
    assert details(g)["Packed"] == "0 of 60"                       # a draft list is not packed yet
    # 50 pieces are on no packing list: a second list can be started before the first is finished
    assert (g["pack"]["label"], g["pack"]["url"]) == ("Pack goods", reverse("packing_new", args=[o.pk]))
    assert "50 pieces" in g["pack"]["hint"]
    pg = packing_guide(packing_of(p), ns.owner)
    assert seen(pg) == seen(g)
    assert states(pg) == {"Ordered": "done", "Confirmed": "done", "Packed": "now", "Billed": "todo", "Paid": "todo"}
    assert details(pg) == {"Packed": "10 pieces"}
    assert packing_next(packing_of(p), ns.owner)["label"] == "Finish packing"
    follow_links(ns, g)


def test_a_draft_list_holding_everything_leaves_no_second_route(ns):
    o = confirmed_order(ns)
    draft_pack(ns, o, ALL)
    g = order_guide(order_of(o), ns.owner)
    assert [a["label"] for a in offered(g)] == ["Finish packing"] and g["pack"] is None


def test_a_packed_list_with_no_bill_asks_for_the_bill_and_the_rest_of_the_order_comes_first(ns):
    o = confirmed_order(ns)
    p = pack(ns, o, [{"S": "10", "M": "10"}])
    g = order_guide(order_of(o), ns.owner)
    assert seen(g) == [("Pack goods", reverse("packing_new", args=[o.pk])), ("Make bill", reverse("packing_detail", args=[p.pk]))]
    assert "40 pieces" in g["primary"]["hint"] and details(g)["Packed"] == "20 of 60"
    assert states(g) == {"Ordered": "done", "Confirmed": "done", "Packed": "now", "Billed": "now", "Paid": "todo"}
    pg = packing_guide(packing_of(p), ns.owner)
    assert seen(pg) == [("Make bill", reverse("packing_detail", args=[p.pk]))]
    assert pg["primary"]["hint"] == f"{p.number} is packed and has no bill yet."
    assert states(pg) == {"Ordered": "done", "Confirmed": "done", "Packed": "done", "Billed": "now", "Paid": "todo"}
    follow_links(ns, g)


def test_a_draft_bill_asks_to_be_posted_and_its_packing_list_is_not_billed_again(ns):
    o = confirmed_order(ns)
    p = pack(ns, o, ALL)
    inv = draft_bill(ns, p)
    want = [("Post bill", reverse("saleinvoice_detail", args=[inv.pk]))]
    g = order_guide(order_of(o), ns.owner)
    assert seen(g) == want and g["pack"] is None
    assert states(g) == {"Ordered": "done", "Confirmed": "done", "Packed": "done", "Billed": "now", "Paid": "todo"}
    assert seen(packing_guide(packing_of(p), ns.owner)) == want
    ig = invoice_guide(inv_of(inv), ns.owner)
    assert seen(ig) == want
    assert states(ig) == {"Ordered": "done", "Confirmed": "done", "Packed": "done", "Billed": "now", "Paid": "todo"}
    assert details(ig) == {"Billed": "30000.00"}
    assert invoice_next(inv_of(inv), ns.owner)["label"] == "Post bill"
    follow_links(ns, g)


def test_a_posted_bill_asks_for_the_money_the_ledger_says_is_still_to_come(ns):
    o = confirmed_order(ns)
    p = pack(ns, o, ALL)
    inv = billed(ns, p)
    assert inv.total == D("30000.00")
    g = order_guide(order_of(o), ns.owner)
    assert seen(g) == [(WHO, receive_link(inv, "30000.00"))]
    assert states(g) == {"Ordered": "done", "Confirmed": "done", "Packed": "done", "Billed": "done", "Paid": "now"}
    assert details(g) == {"Ordered": "60 pieces", "Packed": "60 of 60", "Billed": "30000.00", "Paid": "30000.00 to receive"}
    assert not g["complete"]
    follow_links(ns, g)
    receive(ns, inv, "12000")
    for guide, doc in ((order_guide, order_of(o)), (packing_guide, packing_of(p)), (invoice_guide, inv_of(inv))):
        g = guide(doc, ns.owner)
        assert seen(g) == [(WHO, receive_link(inv, "18000.00"))], guide.__name__
        assert details(g)["Paid"] == "18000.00 to receive" and current(g) == ["Paid"]
        follow_links(ns, g)
    # the figure is the one the bill page's Outstanding pill is built from
    s = settlement(ns.owner, ledger=ns.local.customer_ledger, reference=inv.number, direction="receive",
                   narration=f"Received against {inv.number}")
    assert s["due"] == D("18000.00") and s["url"] == g["primary"]["url"]


def test_a_sale_that_is_paid_is_complete_on_every_page(ns):
    o = confirmed_order(ns)
    p = pack(ns, o, ALL)
    inv = billed(ns, p)
    receive(ns, inv, "30000")
    assert order_of(o).status == "dispatched"
    for guide, doc in ((order_guide, order_of(o)), (packing_guide, packing_of(p)), (invoice_guide, inv_of(inv))):
        g = guide(doc, ns.owner)
        assert offered(g) == [] and g["complete"] and not g["closed"] and g["waiting"] == "", guide.__name__
        assert set(states(g).values()) == {"done"} and current(g) == []
    assert order_next(order_of(o), ns.owner) is None and invoice_next(inv_of(inv), ns.owner) is None
    assert packing_next(packing_of(p), ns.owner) is None


def test_a_bill_made_by_quick_billing_starts_at_billed(ns):
    inv = quick_invoice(ns, post=False)
    g = invoice_guide(inv_of(inv), ns.owner)
    assert [s["label"] for s in g["journey"]] == ["Billed", "Paid"]
    assert seen(g) == [("Post bill", reverse("saleinvoice_detail", args=[inv.pk]))] and states(g) == {"Billed": "now", "Paid": "todo"}
    follow_links(ns, g)
    inv = invoices.post_invoice(inv, user=ns.owner)
    g = invoice_guide(inv_of(inv), ns.owner)
    assert seen(g) == [(WHO, receive_link(inv, "5000.00"))] and states(g) == {"Billed": "done", "Paid": "now"}
    follow_links(ns, g)
    receive(ns, inv, "5000")
    g = invoice_guide(inv_of(inv), ns.owner)
    assert g["complete"] and offered(g) == []


def test_a_draft_return_asks_to_be_posted_and_a_posted_one_comes_off_what_is_to_be_received(ns):
    o = confirmed_order(ns)
    p = pack(ns, o, ALL)
    inv = billed(ns, p)
    note = draft_return(ns, inv, "4")                               # 4 pieces at 500
    post = ("Post return", reverse("salecn_detail", args=[note.pk]))
    for guide, doc in ((order_guide, order_of(o)), (packing_guide, packing_of(p)), (invoice_guide, inv_of(inv))):
        g = guide(doc, ns.owner)
        assert seen(g) == [post, (WHO, receive_link(inv, "30000.00"))], guide.__name__
    ng = creditnote_guide(note_of(note), ns.owner)
    assert seen(ng) == [post] and states(ng) == {"Return saved": "done", "Return posted": "now"}
    follow_links(ns, g)
    follow_links(ns, ng)
    credit_notes.post_credit_note(note, user=ns.owner)
    ng = creditnote_guide(note_of(note), ns.owner)
    assert offered(ng) == [] and ng["complete"] and details(ng) == {"Return posted": "2000.00"}
    # the return's own voucher settles the bill, so the ledger already says 28,000: nothing is taken off twice
    assert bill_outstanding(ns.local.customer_ledger, inv.number, user=ns.owner) == D("28000.00")
    g = invoice_guide(inv_of(inv), ns.owner)
    assert seen(g) == [(WHO, receive_link(inv, "28000.00"))] and details(g)["Paid"] == "28000.00 to receive"
    follow_links(ns, g)
    receive(ns, inv, "28000")
    assert invoice_guide(inv_of(inv), ns.owner)["complete"]
    assert order_guide(order_of(o), ns.owner)["complete"]


def test_a_return_after_the_money_came_asks_for_nothing_more(ns):
    inv = quick_invoice(ns)
    receive(ns, inv, "5000")
    credit_notes.post_credit_note(draft_return(ns, inv, "2"), user=ns.owner)      # the credit stays on account
    g = invoice_guide(inv_of(inv), ns.owner)
    assert offered(g) == [] and g["complete"] and due(inv_of(inv), ns.owner, {}) == D("0")


def test_cancelled_documents_ask_for_nothing(ns):
    o = confirmed_order(ns)
    p = pack(ns, o, ALL)
    inv = billed(ns, p)
    note = credit_notes.cancel_credit_note(draft_return(ns, inv), user=ns.owner)
    assert offered(creditnote_guide(note_of(note), ns.owner)) == [] and creditnote_guide(note_of(note), ns.owner)["closed"]
    invoices.cancel_invoice(inv, user=ns.owner, reason="wrong")
    g = invoice_guide(inv_of(inv), ns.owner)
    assert offered(g) == [] and g["closed"] and not g["complete"] and set(states(g).values()) == {"todo"}
    assert invoice_next(inv_of(inv), ns.owner) is None
    # the packing list is packed again and asks for a new bill
    assert [a["label"] for a in offered(packing_guide(packing_of(p), ns.owner))] == ["Make bill"]
    packing.cancel_packing(p, user=ns.owner, reason="wrong")
    g = packing_guide(packing_of(p), ns.owner)
    assert offered(g) == [] and g["closed"] and packing_next(packing_of(p), ns.owner) is None
    assert [a["label"] for a in offered(order_guide(order_of(o), ns.owner))] == ["Pack goods"]
    orders.cancel_order(o, user=ns.owner, reason="customer left")
    g = order_guide(order_of(o), ns.owner)
    assert offered(g) == [] and g["closed"] and not g["complete"] and g["pack"] is None and g["waiting"] == ""
    assert set(states(g).values()) == {"todo"} and order_next(order_of(o), ns.owner) is None


def test_a_closed_order_asks_for_no_more_packing_but_what_went_is_still_billed_and_paid(ns):
    o = confirmed_order(ns)
    p = pack(ns, o, [{"S": "10"}])
    inv = billed(ns, p)
    orders.close_order(o, user=ns.owner, reason="The customer will not take the rest")
    g = order_guide(order_of(o), ns.owner)
    assert seen(g) == [(WHO, receive_link(inv, "5000.00"))] and not g["closed"] and not g["complete"] and g["pack"] is None
    assert states(g) == {"Ordered": "done", "Confirmed": "done", "Packed": "done", "Billed": "done", "Paid": "now"}
    follow_links(ns, g)
    receive(ns, inv, "5000")
    g = order_guide(order_of(o), ns.owner)
    assert offered(g) == [] and g["closed"] and not g["complete"]


# ---------------- agreement, permissions, reading only ----------------

def test_the_order_the_packing_lists_and_the_bills_agree_on_every_shared_document(ns):
    o = confirmed_order(ns)
    p1 = pack(ns, o, [{"S": "10"}])
    inv1 = billed(ns, p1)
    p2 = pack(ns, o, [{"S": "5"}])
    inv2 = draft_bill(ns, p2)
    p3 = pack(ns, o, [{"M": "5"}])
    p4 = draft_pack(ns, o, [{"M": "5"}])
    note = draft_return(ns, inv1, "1")
    g = order_guide(order_of(o), ns.owner)
    assert [a["label"] for a in offered(g)] == ["Finish packing", "Make bill", "Post bill", "Post return", WHO]
    mine = {(a["label"], a["url"]) for a in offered(g)}
    parts = [packing_guide(packing_of(p), ns.owner) for p in (p1, p2, p3, p4)]
    parts += [invoice_guide(inv_of(i), ns.owner) for i in (inv1, inv2)] + [creditnote_guide(note_of(note), ns.owner)]
    theirs = {pair for part in parts for pair in seen(part)}
    assert theirs == mine                                # the same documents, the same words, the same links
    assert (g["pack"]["label"], "35 pieces" in g["pack"]["hint"]) == ("Pack goods", True)
    follow_links(ns, g)


def test_a_role_that_may_not_do_the_next_step_is_told_what_the_sale_waits_for(ns):
    o = confirmed_order(ns)
    seller = seeded("Salesperson", "seller", ns.factory)           # takes and confirms orders, packs nothing
    g = order_guide(order_of(o), seller)
    assert g["primary"] is None and g["others"] == [] and g["waiting"] == "Pack goods" and not g["blocked"]
    assert g["pack"] is None and order_next(order_of(o), seller) is None
    d = draft_order(ns)
    g = order_guide(order_of(d), seller)
    assert [a["label"] for a in offered(g)] == ["Confirm order"]
    follow_links(ns, g, seller)


def test_the_billing_clerk_packs_and_bills_and_waits_for_the_accountant_to_receive(ns, accountant):
    clerk = seeded("Billing Clerk", "clerk", ns.factory)
    o = confirmed_order(ns)
    g = order_guide(order_of(o), clerk)
    assert [a["label"] for a in offered(g)] == ["Pack goods"]
    follow_links(ns, g, clerk)
    p = pack(ns, o, ALL)
    g = packing_guide(packing_of(p), clerk)
    assert [a["label"] for a in offered(g)] == ["Make bill"]
    follow_links(ns, g, clerk)
    inv = billed(ns, p)
    g = invoice_guide(inv_of(inv), clerk)
    assert offered(g) == [] and g["waiting"] == WHO and not g["complete"]
    assert invoice_next(inv_of(inv), clerk) is None
    g = invoice_guide(inv_of(inv), accountant)
    assert [a["label"] for a in offered(g)] == [WHO] and g["waiting"] == ""
    follow_links(ns, g, accountant)


def stage(ns, name):
    """Build the state in which the guide offers one step; returns (guide function, document)."""
    if name == "draft_order":
        return order_guide, order_of(draft_order(ns))
    o = confirmed_order(ns)
    if name == "open_order":
        return order_guide, order_of(o)
    if name == "draft_packing":
        return packing_guide, packing_of(draft_pack(ns, o, ALL))
    p = pack(ns, o, ALL)
    if name == "packed":
        return packing_guide, packing_of(p)
    if name == "draft_bill":
        return invoice_guide, inv_of(draft_bill(ns, p))
    inv = billed(ns, p)
    if name == "posted_bill":
        return invoice_guide, inv_of(inv)
    receive(ns, inv, "30000")
    return creditnote_guide, note_of(draft_return(ns, inv))


@pytest.mark.parametrize("state, label, needs", [
    ("draft_order", "Confirm order", (("sales.order", "edit"), ("sales.order", "view"))),
    ("open_order", "Pack goods", (("sales.packing", "create"), ("sales.packing", "view"))),
    ("draft_packing", "Finish packing", (("sales.packing", "edit"), ("sales.packing", "view"))),
    ("packed", "Make bill", (("sales.invoice", "create"), ("sales.packing", "view"), ("sales.invoice", "view"))),
    ("draft_bill", "Post bill", (("sales.invoice", "edit"), ("sales.invoice", "view"))),
    ("posted_bill", WHO, (("ledger.voucher", "create"), ("ledger.voucher", "view"))),
    ("return", "Post return", (("sales.creditnote", "create"), ("sales.creditnote", "view"))),
])
def test_each_action_needs_every_right_its_step_and_the_screens_it_opens_ask_for(ns, state, label, needs):
    guide, doc = stage(ns, state)
    wanted = guide(doc, ns.owner)["primary"]
    assert wanted["label"] == label and wanted["perm"] == needs

    def grants(perms):
        out = {}
        for screen, action in perms:
            out.setdefault(screen, []).append(action)
        return out

    # any one of them missing: not offered, and the sale is said to wait for that step
    for n, missing in enumerate(needs):
        short = role_user(f"short{n}", grants([p for p in needs if p != missing]), ns.factory)
        g = guide(doc, short)
        assert offered(g) == [] and g["waiting"] == label and not g["blocked"], missing
    # all together: offered, the link opens, and the screen takes the step from this very role
    full = role_user("full", grants(needs), ns.factory)
    g = guide(doc, full)
    assert [a["label"] for a in offered(g)] == [label] and g["waiting"] == ""
    follow_links(ns, g, full)


@pytest.mark.parametrize("state, action, lands", [
    ("draft_order", "confirm", None), ("draft_packing", "finalize", None), ("packed", "invoice", "saleinvoice_detail"),
    ("draft_bill", "post", None), ("return", "post", None),
])
def test_the_screen_takes_the_step_from_a_role_holding_exactly_what_the_guide_asked_for(ns, state, action, lands):
    guide, doc = stage(ns, state)
    wanted = guide(doc, ns.owner)["primary"]
    grants = {}
    for screen, act in wanted["perm"]:
        grants.setdefault(screen, []).append(act)
    c = login(role_user("exact", grants, ns.factory))
    r = c.post(wanted["url"], {"action": action}, follow=True)
    assert r.status_code == 200 and [code for _, code in r.redirect_chain] == [302]
    fresh = type(doc).objects.get(pk=doc.pk)
    assert fresh.status != doc.status or lands
    if lands:
        assert r.redirect_chain[0][0] == reverse(lands, args=[SaleInvoice.objects.get().pk])


def test_a_custom_role_with_create_but_not_view_gets_no_link(ns):
    o = confirmed_order(ns)
    packer = role_user("pack_only", {"sales.packing": ["create"], "sales.order": ["view"]}, ns.factory)
    assert packer.has_screen_perm("sales.packing", "create") and not packer.has_screen_perm("sales.packing", "view")
    g = order_guide(order_of(o), packer)
    assert g["primary"] is None and g["others"] == [] and g["waiting"] == "Pack goods" and g["pack"] is None


def test_someone_who_may_do_a_later_step_gets_that_one_and_no_waiting_line(ns, accountant):
    o = confirmed_order(ns)
    p = pack(ns, o, [{"S": "10"}])
    # packing the rest is the dispatch desk's job; the accountant bills what is packed
    g = order_guide(order_of(o), accountant)
    assert seen(g) == [("Make bill", reverse("packing_detail", args=[p.pk]))] and g["waiting"] == "" and g["pack"] is None
    follow_links(ns, g, accountant)


class Counting:
    """The user, counting how often each permission is asked."""

    def __init__(self, user):
        self.user, self.asked = user, []

    def has_screen_perm(self, screen, action):
        self.asked.append((screen, action))
        return self.user.has_screen_perm(screen, action)

    def __getattr__(self, name):
        return getattr(self.user, name)


def test_one_call_asks_each_permission_once_and_callers_can_share_the_answers(ns):
    o = confirmed_order(ns)
    p = pack(ns, o, [{"S": "10"}])
    inv = billed(ns, p)
    who = Counting(ns.owner)
    g = order_guide(order_of(o), who)
    assert [a["label"] for a in offered(g)] == ["Pack goods", WHO]
    assert len(who.asked) == len(set(who.asked)) == 4      # packing create and view, voucher create and view
    shared, again = {}, Counting(ns.owner)
    assert order_guide(order_of(o), again, shared) == g
    assert packing_next(packing_of(p), again, shared)["label"] == WHO
    assert invoice_next(inv_of(inv), again, shared)["label"] == WHO
    assert len(again.asked) == 4                            # the packing list and the bill asked nothing new


def test_the_guide_reads_and_never_writes(ns):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    o = confirmed_order(ns)
    p = pack(ns, o, [{"S": "10"}])
    inv = billed(ns, p)
    note = draft_return(ns, inv)
    docs = [(order_guide, order_of(o)), (packing_guide, packing_of(p)), (invoice_guide, inv_of(inv)), (creditnote_guide, note_of(note))]
    before = [(d.history.count(), d.status) for _, d in docs]
    with CaptureQueriesContext(connection) as q:
        labels = [guide(doc, ns.owner)["primary"]["label"] for guide, doc in docs]
    assert labels == ["Pack goods", "Post return", "Post return", "Post return"]
    assert q.captured_queries and all(x["sql"].lstrip().upper().startswith("SELECT") for x in q.captured_queries)
    assert [(type(d).objects.get(pk=d.pk).history.count(), type(d).objects.get(pk=d.pk).status) for _, d in docs] == before


def test_another_factorys_user_never_reaches_the_documents_or_their_guides(ns, factory2):
    o = confirmed_order(ns)
    p = pack(ns, o, ALL)
    inv = billed(ns, p)
    note = draft_return(ns, inv)
    far = role_user("far", {"sales.order": ["view", "edit"], "sales.packing": ["view", "create", "edit"],
                            "sales.invoice": ["view", "create", "edit"], "sales.creditnote": ["view", "create"],
                            "ledger.voucher": ["view", "create"]}, factory2)
    for model, doc in ((SaleOrder, o), (PackingList, p), (SaleInvoice, inv), (SaleCreditNote, note)):
        assert not model.objects.for_user(far).filter(pk=doc.pk).exists()
    c = login(far)
    for name, doc in (("saleorder_detail", o), ("packing_detail", p), ("saleinvoice_detail", inv), ("salecn_detail", note)):
        assert c.get(reverse(name, args=[doc.pk])).status_code == 404
    # and the ledger figure is scoped to the factories of whoever asks
    assert due(inv_of(inv), far, {}) == D("0") and due(inv_of(inv), ns.owner, {}) == D("30000.00")


# ---------------- made to order ----------------

@pytest.fixture
def bare(company, factory, owner):
    """The same style and customers with nothing in stock."""
    return h.build(company, factory, owner, stock_qty=0)


def test_a_made_to_order_order_waits_for_production_until_its_goods_are_in_stock(bare):
    ns = bare
    o = orders.confirm_order(draft_order(ns, qty="40", order_type="mto", sizes=("M",)), user=ns.owner)
    assert o.production_order_id
    g = order_guide(order_of(o), ns.owner)
    assert g["primary"] is None and g["others"] == [] and g["waiting"] == "goods from production" and g["blocked"]
    assert not g["complete"] and not g["closed"] and order_next(order_of(o), ns.owner) is None
    assert states(g) == {"Ordered": "done", "Confirmed": "done", "Packed": "now", "Billed": "todo", "Paid": "todo"}
    # the packing screen itself still opens (a draft can be saved); only the guide stops pointing at it
    assert g["pack"]["url"] == reverse("packing_new", args=[o.pk])
    # someone who may not pack is told the same thing: it is production the sale waits for, not a colleague
    seller = seeded("Salesperson", "mto_seller", ns.factory)
    g = order_guide(order_of(o), seller)
    assert g["waiting"] == "goods from production" and g["blocked"] and g["pack"] is None
    # a draft packing list cannot be finished while nothing is in stock, and the screen says why
    p = draft_pack(ns, o, [{"M": "40"}])
    with pytest.raises(BusinessRuleError, match="only 0 available at LDH1 / Main Godown; 40 packed"):
        packing.finalize_packing(p, user=ns.owner)
    packing.cancel_packing(p, user=ns.owner)
    # another size of the style coming into stock changes nothing; the ordered one does
    post_opening_stock(company=ns.company, factory=ns.factory, location=ns.godown, user=ns.owner,
                       entries=[OpeningItem(ns.sku("Black", "S"), D("40"), D("300"))])
    assert order_guide(order_of(o), ns.owner)["blocked"]
    post_opening_stock(company=ns.company, factory=ns.factory, location=ns.godown, user=ns.owner,
                       entries=[OpeningItem(ns.sku("Black", "M"), D("15"), D("300"))])
    g = order_guide(order_of(o), ns.owner)
    assert seen(g) == [("Pack goods", reverse("packing_new", args=[o.pk]))] and not g["blocked"] and g["waiting"] == ""
    follow_links(ns, g)


def test_a_ready_stock_order_is_never_said_to_wait_for_production(bare):
    ns = bare
    o = orders.confirm_order(draft_order(ns, sizes=("M",)), user=ns.owner)
    g = order_guide(order_of(o), ns.owner)
    assert [a["label"] for a in offered(g)] == ["Pack goods"] and not g["blocked"]


def test_goods_still_in_production_do_not_count_and_production_never_sees_the_customer(company, factory, owner):
    from masters.models import SKU
    from masters.services import parties
    from production.services import bundles as bundle_service
    from production.services import orders as prod_orders
    from tests import prod_helpers as ph
    from tests.test_production import finish_route

    ns = ph.build(company, factory, owner)
    customer = parties.create_party(company=company, name="Dealer Dhillon", mobile="9877700000", is_customer=True, state_code="03")
    so = orders.create_order(
        company=company, factory=factory, customer=customer, date=DAY, user=owner, order_type="mto",
        lines=[orders.OrderLineSpec(SKU.objects.get(style=ns.style, colour=ns.black, size=ns.sizes[s]), D(q), D("400"), D("0"))
               for s, q in (("S", "17"), ("M", "33"), ("L", "33"), ("XL", "17"))])
    so = orders.confirm_order(so, user=owner)
    po = prod_orders.release_order(so.production_order, user=owner)
    ns.lot = po.lines.get().lot
    bundles = finish_route(ns)                           # cut, stitched, checked: at the packing step, not in stock
    g = order_guide(order_of(so), owner)
    assert g["blocked"] and g["waiting"] == "goods from production" and g["primary"] is None

    # nothing on any production screen of that lot names the customer or links to the sale order
    c, opened = login(owner), 0
    pages = [("order_list", [], {}), ("order_detail", [po.pk], {}), ("lot_detail", [ns.lot.pk], {}),
             ("lot_fabric", [ns.lot.pk], {}), ("lot_cutting", [ns.lot.pk], {}), ("lot_tags", [ns.lot.pk], {}),
             ("move_bundles", [], {}), ("production_dashboard", [], {}),
             ("production_track", [], {"q": so.number})]
    for name, args, query in pages:
        r = c.get(reverse(name, args=args), query)
        assert r.status_code in (200, 302), name
        if r.status_code == 200:
            opened += 1
            html = r.content.decode()
            assert customer.name not in html and customer.mobile not in html, name
            assert reverse("saleorder_detail", args=[so.pk]) not in html, name
    assert opened >= 6
    assert so.number in c.get(reverse("order_detail", args=[po.pk])).content.decode()     # traced by the number alone

    bundle_service.pack_bundles(bundles=bundles, user=owner, date=DAY)                  # into finished stock
    g = order_guide(order_of(so), owner)
    assert [a["label"] for a in offered(g)] == ["Pack goods"] and not g["blocked"]
    assert login(owner).get(g["primary"]["url"]).status_code == 200
