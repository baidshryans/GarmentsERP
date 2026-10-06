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


# ================================================================ the guide on the screens

def page(user, name, *args, **query):
    r = login(user).get(reverse(name, args=args), query)
    assert r.status_code == 200
    return r.content.decode()


def guide_of(html):
    """The guide island alone: from its opening tag to the next island."""
    start = html.index('class="island guide"')
    return html[start:html.index('class="island"', start)]


def head_of(html):
    return html[html.index('class="page-head"'):html.index('class="island guide"')]


def row_with(html, text):
    return next(r for r in re.findall(r"<tr>.*?</tr>", html, re.S) if text in r)


def button(url, label):
    return f'<a class="btn primary" href="{escape(url)}">{label}</a>'


def plain(url, label):
    return f'<a class="btn" href="{escape(url)}">{label}</a>'


def header_button(url):
    """The bill page's own plain button for the money step (it carries a tooltip)."""
    return (f'<a class="btn" href="{escape(url)}" title="Opens the voucher with this bill filled in; nothing is posted '
            'until you press Post">Receive money</a>')


def test_the_order_page_leads_from_confirming_to_packing(ns):
    o = draft_order(ns)
    html = page(ns.owner, "saleorder_detail", o.pk)
    g = guide_of(html)
    assert 'aria-label="Where this sale is"' in g and button("#do-next", "Confirm order") in g
    assert re.search(r'<form method="post" id="do-next">.*?name="action" value="confirm">Confirm order</button>', html, re.S)
    assert "Pack goods" not in html
    c = login(ns.owner)
    r = c.post(reverse("saleorder_detail", args=[o.pk]), {"action": "confirm"}, follow=True)
    html = r.content.decode()
    pack_url = reverse("packing_new", args=[o.pk])
    assert button(pack_url, "Pack goods") in guide_of(html)
    # the header's own button for the same step is a plain one: one violet button says what is next
    assert plain(pack_url, "Pack goods") in head_of(html) and "btn primary" not in head_of(html)


def test_the_order_page_keeps_a_way_to_a_second_packing_list_while_one_is_a_draft(ns):
    o = confirmed_order(ns)
    p = draft_pack(ns, o, [{"S": "10"}])
    html = page(ns.owner, "saleorder_detail", o.pk)
    assert button(reverse("packing_detail", args=[p.pk]), "Finish packing") in guide_of(html)
    assert plain(reverse("packing_new", args=[o.pk]), "Pack goods") in head_of(html)
    # the route works: a second draft is saved beside the first
    s_id, m_id = ns.sku("Black", "S").pk, ns.sku("Black", "M").pk
    r = login(ns.owner).post(reverse("packing_new", args=[o.pk]), {
        "n": "1", "location": ns.godown.pk, "date": "2026-06-15", "transporter": "", "lr_no": "", "lr_date": "",
        "vehicle_no": "", "remarks": "", f"c1_{s_id}": "5", f"c1_{m_id}": ""})
    assert r.status_code == 302 and PackingList.objects.filter(order=o, status="draft").count() == 2
    # with everything on packing lists there is nothing more to start
    packing.cancel_packing(PackingList.objects.exclude(pk=p.pk).get(), user=ns.owner)
    packing.cancel_packing(p, user=ns.owner)
    draft_pack(ns, o, ALL)
    assert "Pack goods" not in page(ns.owner, "saleorder_detail", o.pk)


def test_the_order_page_tells_a_seller_what_it_waits_for_and_links_nowhere_they_cannot_go(ns):
    o = confirmed_order(ns)
    p = pack(ns, o, [{"S": "10"}])
    inv = billed(ns, p)
    seller = seeded("Salesperson", "page_seller", ns.factory)
    html = page(seller, "saleorder_detail", o.pk)
    g = guide_of(html)
    assert "Waiting for: Pack goods" in g and "<a " not in g and "Pack goods" not in head_of(html)
    # the packing list and the bill are named, as plain text: the seller cannot open either
    assert p.number in html and inv.number in html
    for name, doc in (("packing_detail", p), ("saleinvoice_detail", inv), ("packing_new", o)):
        url = reverse(name, args=[doc.pk])
        assert url not in html and login(seller).get(url).status_code == 403
    # the owner gets both as links
    html = page(ns.owner, "saleorder_detail", o.pk)
    assert f'<a href="{reverse("packing_detail", args=[p.pk])}">{p.number}</a>' in html
    assert f'<a href="{reverse("saleinvoice_detail", args=[inv.pk])}">{inv.number}</a>' in html


def test_a_made_to_order_page_says_it_waits_for_production_and_gives_no_link(bare):
    ns = bare
    o = orders.confirm_order(draft_order(ns, qty="40", order_type="mto", sizes=("M",)), user=ns.owner)
    html = page(ns.owner, "saleorder_detail", o.pk)
    g = guide_of(html)
    assert "Waiting for: goods from production" in g and "<a " not in g
    row = row_with(page(ns.owner, "saleorder_list"), o.number)
    assert '<span class="muted">Waiting for: goods from production</span>' in row and 'class="btn"' not in row
    post_opening_stock(company=ns.company, factory=ns.factory, location=ns.godown, user=ns.owner,
                       entries=[OpeningItem(ns.sku("Black", "M"), D("40"), D("300"))])
    assert button(reverse("packing_new", args=[o.pk]), "Pack goods") in guide_of(page(ns.owner, "saleorder_detail", o.pk))
    assert plain(reverse("packing_new", args=[o.pk]), "Pack goods") in row_with(page(ns.owner, "saleorder_list"), o.number)


def test_a_finished_sale_and_a_cancelled_one_say_so(ns):
    o = confirmed_order(ns)
    inv = billed(ns, pack(ns, o, ALL))
    receive(ns, inv, "30000")
    g = guide_of(page(ns.owner, "saleorder_detail", o.pk))
    assert "This sale is complete." in g and "<a " not in g
    assert "This bill is settled." in guide_of(page(ns.owner, "saleinvoice_detail", inv.pk))
    c = orders.cancel_order(confirmed_order(ns), user=ns.owner, reason="customer left")
    g = guide_of(page(ns.owner, "saleorder_detail", c.pk))
    assert "This sale was cancelled or closed." in g and "<a " not in g


def test_the_packing_page_leads_from_finishing_to_the_bill(ns):
    o = confirmed_order(ns)
    p = draft_pack(ns, o, ALL)
    c = login(ns.owner)
    url = reverse("packing_detail", args=[p.pk])
    html = c.get(url).content.decode()
    assert button("#do-next", "Finish packing") in guide_of(html)
    assert re.search(r'<form method="post" id="do-next">.*?name="action" value="finalize">Finish packing</button>', html, re.S)
    assert f'<a href="{reverse("saleorder_detail", args=[o.pk])}">{o.number}</a>' in html
    html = c.post(url, {"action": "finalize"}, follow=True).content.decode()
    assert "Packing finished." in html and button("#do-next", "Make bill") in guide_of(html)
    assert re.search(r'<form method="post" id="do-next">.*?name="action" value="invoice">Make bill</button>', html, re.S)
    r = c.post(url, {"action": "invoice"}, follow=True)
    inv = SaleInvoice.objects.get()
    bill_url = reverse("saleinvoice_detail", args=[inv.pk])
    assert r.redirect_chain == [(bill_url, 302)]
    # back on the packing list, the next step is on the bill, and no second bill can be made
    html = c.get(url).content.decode()
    assert button(bill_url, "Post bill") in guide_of(html) and 'value="invoice"' not in html
    assert f'<a href="{bill_url}">Draft bill</a>' in html
    # a packer who has no right on bills gets no bill button and no link to the bill
    packer = role_user("packer", {"sales.packing": ["view", "create", "edit"]}, ns.factory)
    html = page(packer, "packing_detail", p.pk)
    assert "Waiting for: Post bill" in guide_of(html) and bill_url not in html and "Draft bill" in html
    assert reverse("saleorder_detail", args=[o.pk]) not in html and o.number in html


def test_the_bill_page_leads_from_posting_to_receiving_the_money(ns, company):
    h.gst_on(company)
    o = confirmed_order(ns)
    inv = draft_bill(ns, pack(ns, o, ALL))
    c = login(ns.owner)
    url = reverse("saleinvoice_detail", args=[inv.pk])
    html = c.get(url).content.decode()
    assert button("#do-next", "Post bill") in guide_of(html)
    assert re.search(r'<form method="post" id="do-next">.*?name="action" value="post">Post bill</button>', html, re.S)
    # GST can still be chosen or waived on the draft before it is posted
    assert 'name="tax_mode"' in html and "No GST on this bill" in html and 'name="tax_note"' in html
    assert inv.gst_total == D("1500.00")
    c.post(url, {"action": "tax", "tax_mode": "none", "gst_template": "", "tax_note": "Export under bond"})
    inv.refresh_from_db()
    assert inv.gst_total == D("0.00") and inv.total == D("30000.00") and inv.status == "draft"
    html = c.post(url, {"action": "post"}, follow=True).content.decode()
    inv.refresh_from_db()
    link = receive_link(inv, "30000.00")
    assert "Bill posted." in html and button(link, WHO) in guide_of(html)
    head = head_of(html)
    assert "Outstanding 30000.00" in head and header_button(link) in head and "btn primary" not in head
    receive(ns, inv, "10000")
    html = c.get(url).content.decode()
    link = receive_link(inv, "20000.00")
    assert "Outstanding 20000.00" in head_of(html) and header_button(link) in head_of(html)
    assert button(link, WHO) in guide_of(html) and "20000.00 to receive" in guide_of(html)


def test_the_bill_page_shows_a_clerk_what_is_owed_and_no_way_into_the_books(ns):
    inv = billed(ns, pack(ns, confirmed_order(ns), ALL))
    clerk = seeded("Billing Clerk", "page_clerk", ns.factory)
    html = page(clerk, "saleinvoice_detail", inv.pk)
    assert f"Waiting for: {WHO}" in guide_of(html) and "<a " not in guide_of(html)
    assert "Outstanding 30000.00" in head_of(html) and reverse("voucher_receipt") not in html
    voucher_url = reverse("voucher_detail", args=[inv.voucher_id])
    assert inv.voucher.number in html and voucher_url not in html and login(clerk).get(voucher_url).status_code == 403
    assert f'<a href="{voucher_url}">' in page(ns.owner, "saleinvoice_detail", inv.pk)


def test_the_return_page_offers_posting_to_those_who_may_post(ns):
    inv = quick_invoice(ns)
    note = draft_return(ns, inv)
    c = login(ns.owner)
    url = reverse("salecn_detail", args=[note.pk])
    html = c.get(url).content.decode()
    g = guide_of(html)
    assert 'aria-label="Where this return is"' in g and button("#do-next", "Post return") in g
    assert re.search(r'<form method="post" id="do-next">.*?name="action" value="post">Post return</button>', html, re.S)
    # the bill names the draft return as its next step, with the money after it
    bill = guide_of(page(ns.owner, "saleinvoice_detail", inv.pk))
    assert button(url, "Post return") in bill and "Also waiting" in bill and WHO in bill
    looker = role_user("cn_looker", {"sales.creditnote": ["view"]}, ns.factory)
    html = page(looker, "salecn_detail", note.pk)
    assert "Waiting for: Post return" in guide_of(html) and 'value="post"' not in html
    assert reverse("saleinvoice_detail", args=[inv.pk]) not in html and inv.number in html
    assert login(looker).post(url, {"action": "post"}).status_code == 403
    html = c.post(url, {"action": "post"}, follow=True).content.decode()
    assert "Return posted." in html and "This return is posted." in guide_of(html)


def test_quick_billing_still_posts_in_one_step_and_its_bill_starts_at_billed(ns):
    c = login(ns.owner)
    form = c.get(reverse("billing")).content.decode()
    assert "Quick billing" in form and "Post bill" in form and "Save as draft" in form
    sku = ns.sku("Black", "M")
    r = c.post(reverse("billing"), {"customer": ns.local.pk, "location": ns.godown.pk, "date": "2026-06-15", "action": "post",
                                    "notes": "", "sku": [sku.pk], "qty": ["4"], "rate": ["500"], "disc": [""]}, follow=True)
    inv = SaleInvoice.objects.get()
    assert inv.status == "posted" and inv.order_id is None and inv.total == D("2000.00")
    html = r.content.decode()
    g = guide_of(html)
    assert f"Bill {inv.number} posted." in html and button(receive_link(inv, "2000.00"), WHO) in g
    assert "Billed" in g and "Paid" in g and "Ordered" not in g and "Packed" not in g


# ---------------- the lists ----------------

def test_each_list_names_the_next_step_of_every_row(ns):
    o1 = confirmed_order(ns)
    p1 = pack(ns, o1, [{"S": "10"}])
    inv1 = billed(ns, p1)
    p2 = draft_pack(ns, o1, [{"M": "10"}])
    drafted = draft_order(ns)
    o2 = confirmed_order(ns)
    p3 = pack(ns, o2, ALL)
    inv3 = draft_bill(ns, p3)
    money = receive_link(inv1, "5000.00")

    html = page(ns.owner, "saleorder_list")
    assert '<th scope="col">Next step</th>' in html
    assert plain(reverse("packing_detail", args=[p2.pk]), "Finish packing") in row_with(html, o1.number)
    assert plain(reverse("saleinvoice_detail", args=[inv3.pk]), "Post bill") in row_with(html, o2.number)
    assert plain(reverse("saleorder_detail", args=[drafted.pk]), "Confirm order") in html

    html = page(ns.owner, "packing_list")
    assert '<th scope="col">Next step</th>' in html
    assert plain(money, WHO) in row_with(html, p1.number)
    assert plain(reverse("saleinvoice_detail", args=[inv3.pk]), "Post bill") in row_with(html, p3.number)
    assert plain(reverse("packing_detail", args=[p2.pk]), "Finish packing") in html

    html = page(ns.owner, "saleinvoice_list")
    assert '<th scope="col">Next step</th>' in html
    assert plain(money, WHO) in row_with(html, inv1.number)
    assert plain(reverse("saleinvoice_detail", args=[inv3.pk]), "Post bill") in html
    receive(ns, inv1, "5000")
    assert WHO not in page(ns.owner, "saleinvoice_list") and WHO not in page(ns.owner, "packing_list")

    # a role that may only look gets no button on any row, and no Pack button beside the open orders
    looker = role_user("list_looker", {"sales.order": ["view"], "sales.packing": ["view"], "sales.invoice": ["view"]}, ns.factory)
    for name in ("saleorder_list", "packing_list", "saleinvoice_list"):
        html = page(looker, name)
        assert "Next step" in html and 'class="btn" href' not in html[html.index("<tbody>"):], name
    assert plain(reverse("packing_new", args=[o1.pk]), "Pack") in page(ns.owner, "packing_list")


def test_the_lists_never_show_another_factorys_documents_or_their_steps(ns, factory2):
    o = confirmed_order(ns)
    p = pack(ns, o, ALL)
    inv = billed(ns, p)
    far = role_user("far_seller", {"sales.order": ["view", "edit"], "sales.packing": ["view", "create", "edit"],
                                   "sales.invoice": ["view", "create", "edit"], "ledger.voucher": ["view", "create"]}, factory2)
    for name, number in (("saleorder_list", o.number), ("packing_list", p.number), ("saleinvoice_list", inv.number)):
        html = page(far, name)
        assert number not in html and WHO not in html and "<tbody>" not in html, name


def test_the_lists_ask_each_permission_once_however_many_rows_they_show(ns):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def asked(name):
        c = login(ns.owner)
        with CaptureQueriesContext(connection) as q:
            assert c.get(reverse(name)).status_code == 200
        return (len([x for x in q.captured_queries if "core_rolepermission" in x["sql"]]),
                len([x for x in q.captured_queries if "ledger_billallocation" in x["sql"]]), len(q))

    def sale():
        billed(ns, pack(ns, confirmed_order(ns, qty="5"), [{"S": "5", "M": "5"}]))

    names = ("saleorder_list", "packing_list", "saleinvoice_list")
    sale()
    one = {name: asked(name) for name in names}
    for _ in range(3):
        sale()
    four = {name: asked(name) for name in names}
    for name in names:
        assert four[name][0] == one[name][0], name              # three more rows, no permission asked again
        assert four[name][1] == one[name][1] == 1, name         # one customer: its open bills are read once for the page
        assert four[name][2] - one[name][2] <= 3 * 14, name     # a bounded number of reads per row


# ================================================================ fewer steps

# ---------------- Save and confirm a new order ----------------

def order_form(ns, cells=None, **extra):
    """Every field the browser sends from the new-order form with one style's grid loaded."""
    sid = ns.style.pk
    cells = {("Black", "M"): "20", ("Navy", "S"): "5"} if cells is None else cells
    grid = {f"q_{sid}_{ns.colours[c].pk}_{ns.sizes[s].pk}": cells.get((c, s), "") for c in ns.colours for s in ns.sizes}
    return {"customer": ns.local.pk, "date": "2026-06-15", "due_date": "2026-06-30", "order_type": "stock",
            "remarks": "Urgent", "style_pick": "", "style": sid, f"rate_{sid}": "500", f"disc_{sid}": "0", **grid, **extra}


CONFIRM = '<button class="btn primary" name="then" value="confirm">Save and confirm</button>'
DRAFT = '<button class="btn" name="then" value="draft">Save draft</button>'


def test_save_and_confirm_takes_the_order_and_confirms_it_in_one_step(ns):
    html = page(ns.owner, "saleorder_new")
    # Save draft comes first, so Enter in a field saves a draft and never confirms; Save and confirm is the violet one
    assert html.index(DRAFT) < html.index(CONFIRM)
    r = login(ns.owner).post(reverse("saleorder_new"), order_form(ns, then="confirm"), follow=True)
    o = SaleOrder.objects.get()
    assert r.redirect_chain == [(reverse("saleorder_detail", args=[o.pk]), 302)]
    assert o.status == "confirmed" and o.number == "SO/LDH1/26-27/0001" and o.total_qty == D("25") and o.remarks == "Urgent"
    assert o.production_order_id is None
    done = r.content.decode()
    assert f"Order {o.number} confirmed." in done and "saved as a draft" not in done
    assert button(reverse("packing_new", args=[o.pk]), "Pack goods") in guide_of(done)


def test_save_and_confirm_of_a_made_to_order_order_raises_the_production_requirement(bare):
    from production.models import ProductionOrder

    ns = bare
    r = login(ns.owner).post(reverse("saleorder_new"), order_form(ns, then="confirm", order_type="mto"), follow=True)
    o = SaleOrder.objects.get()
    po = ProductionOrder.objects.get()
    assert o.status == "confirmed" and o.production_order_id == po.pk and po.order_reference == o.number
    done = r.content.decode()
    assert f"Order {o.number} confirmed. Production requirement" in done
    assert "Waiting for: goods from production" in guide_of(done)


def test_the_draft_button_still_saves_a_draft(ns):
    c = login(ns.owner)
    for n, extra in enumerate(({"then": "draft"}, {}), start=1):
        r = c.post(reverse("saleorder_new"), order_form(ns, **extra), follow=True)
        assert SaleOrder.objects.count() == n
        o = SaleOrder.objects.order_by("-id").first()
        assert o.status == "draft" and o.number is None and "Order saved as a draft." in r.content.decode()


def test_without_edit_only_the_draft_button_shows_and_a_forged_confirm_is_refused(ns):
    taker = role_user("draft_only", {"sales.order": ["view", "create"]}, ns.factory)
    html = page(taker, "saleorder_new")
    assert "Save and confirm" not in html and '<button class="btn primary">Save draft</button>' in html
    r = login(taker).post(reverse("saleorder_new"), order_form(ns, then="confirm"))
    assert r.status_code == 403 and not SaleOrder.objects.exists()
    assert login(taker).post(reverse("saleorder_new"), order_form(ns)).status_code == 302
    assert SaleOrder.objects.get().status == "draft"


def test_editing_a_draft_order_offers_no_save_and_confirm_and_never_confirms(ns):
    o = draft_order(ns)
    html = page(ns.owner, "saleorder_edit", o.pk)
    assert "Save and confirm" not in html and '<button class="btn primary">Save draft</button>' in html
    login(ns.owner).post(reverse("saleorder_edit", args=[o.pk]), order_form(ns, {("Black", "M"): "7"}, then="confirm"))
    o = order_of(o)
    assert o.status == "draft" and o.number is None and o.total_qty == D("7")


def test_if_confirming_fails_nothing_is_saved_and_the_form_comes_back(bare, monkeypatch):
    from production.models import ProductionOrder

    ns = bare

    def fails(**kwargs):
        # the last thing confirming a made-to-order order does, after the lines were written and the number was drawn
        assert kwargs["order_reference"] == "SO/LDH1/26-27/0001"
        raise BusinessRuleError("The production requirement could not be raised.")

    monkeypatch.setattr(orders.production_orders, "create_order", fails)
    moves, vouchers = StockMovement.objects.count(), Voucher.objects.count()
    c = login(ns.owner)
    r = c.post(reverse("saleorder_new"), order_form(ns, then="confirm", order_type="mto"))
    html = r.content.decode()
    assert r.status_code == 200 and "The production requirement could not be raised." in html
    assert not SaleOrder.objects.exists() and not SaleOrder.history.exists()          # no draft left behind
    assert not ProductionOrder.objects.exists()
    assert (StockMovement.objects.count(), Voucher.objects.count()) == (moves, vouchers)
    # the form comes back with both buttons and what was typed
    assert CONFIRM in html and DRAFT in html and 'value="Urgent"' in html and 'value="20"' in html
    assert '<option value="mto" selected>' in html
    # the number drawn by the failed attempt was given back: the next order is the first of the series
    monkeypatch.undo()
    assert c.post(reverse("saleorder_new"), order_form(ns, then="confirm", order_type="mto")).status_code == 302
    assert SaleOrder.objects.get().number == "SO/LDH1/26-27/0001" and ProductionOrder.objects.count() == 1


def test_a_validation_error_shows_for_both_buttons_and_saves_nothing(ns):
    c = login(ns.owner)
    for then in ("confirm", "draft"):
        r = c.post(reverse("saleorder_new"), order_form(ns, {("Black", "M"): "2.5"}, then=then))
        html = r.content.decode()
        assert r.status_code == 200 and "whole pieces" in html and CONFIRM in html and 'value="2.5"' in html
        assert not SaleOrder.objects.exists()


def test_save_and_confirm_in_a_locked_period_does_exactly_what_confirming_a_draft_does(ns):
    """An order posts nothing to the books or to stock, so the period lock has never applied to it: the one-step
    button must not differ from Save draft followed by Confirm order."""
    from core.services.periods import lock_period

    lock_period(user=ns.owner, company=ns.company, upto=date(2026, 6, 30))
    two_steps = orders.confirm_order(draft_order(ns), user=ns.owner)
    r = login(ns.owner).post(reverse("saleorder_new"), order_form(ns, then="confirm"), follow=True)
    one_step = SaleOrder.objects.exclude(pk=two_steps.pk).get()
    assert (one_step.status, one_step.number) == ("confirmed", "SO/LDH1/26-27/0002") and two_steps.status == "confirmed"
    assert "is locked" not in r.content.decode()


# ---------------- Finish packing and make the bill ----------------

BOTH = '<button class="btn primary" name="action" value="finish_and_bill">Finish packing and make bill</button>'
FINISH = '<button class="btn" name="action" value="finalize">Finish packing</button>'
FINISH_ONLY = '<button class="btn primary" name="action" value="finalize">Finish packing</button>'


def test_finish_packing_and_make_bill_does_both_and_opens_the_draft_bill(ns, company):
    h.gst_on(company)
    o = confirmed_order(ns)
    p = draft_pack(ns, o, [{"S": "10", "M": "5"}, {"S": "5"}])
    c = login(ns.owner)
    url = reverse("packing_detail", args=[p.pk])
    html = c.get(url).content.decode()
    assert html.index(FINISH) < html.index(BOTH)                    # the smaller step first; the violet one does both
    moves, vouchers = StockMovement.objects.count(), Voucher.objects.count()
    r = c.post(url, {"action": "finish_and_bill"}, follow=True)
    p, inv = packing_of(p), SaleInvoice.objects.get()
    assert r.redirect_chain == [(reverse("saleinvoice_detail", args=[inv.pk]), 302)]
    assert p.status == "packed" and p.number == "PKL/LDH1/26-27/0001"
    assert inv.status == "draft" and inv.number is None and inv.packing_id == p.pk and inv.order_id == o.pk
    assert {l.sku.size.code: l.qty for l in inv.lines.all()} == {"S": D("15"), "M": D("5")}
    assert inv.subtotal == D("10000.00") and inv.gst_total == D("500.00")       # the slab's GST, as Make bill suggests it
    # nothing left stock and nothing reached the books: posting is still its own step
    assert (StockMovement.objects.count(), Voucher.objects.count()) == (moves, vouchers)
    assert order_of(o).status == "confirmed"
    done = r.content.decode()
    assert "Packing finished and the bill drafted." in done and button("#do-next", "Post bill") in guide_of(done)
    assert 'name="tax_mode"' in done and "No GST on this bill" in done           # GST can be chosen or waived first
    c.post(reverse("saleinvoice_detail", args=[inv.pk]), {"action": "tax", "tax_mode": "none", "gst_template": "",
                                                          "tax_note": "Sold under a bond"})
    r = c.post(reverse("saleinvoice_detail", args=[inv.pk]), {"action": "post"}, follow=True)
    inv = inv_of(inv)
    assert inv.status == "posted" and inv.gst_total == D("0.00") and packing_of(p).status == "invoiced"
    assert button(receive_link(inv, "10000.00"), WHO) in guide_of(r.content.decode())


def test_finish_and_bill_needs_every_right_of_both_steps_and_the_packing_lists_factory(ns, factory2):
    o = confirmed_order(ns)
    p = draft_pack(ns, o, ALL)
    url = reverse("packing_detail", args=[p.pk])

    def untouched():
        fresh = packing_of(p)
        return fresh.status == "draft" and fresh.number is None and not SaleInvoice.objects.exists()

    # a packer finishes the list and no more
    packer = role_user("fb_packer", {"sales.packing": ["view", "edit"]}, ns.factory)
    html = page(packer, "packing_detail", p.pk)
    assert FINISH_ONLY in html and "Finish packing and make bill" not in html
    assert login(packer).post(url, {"action": "finish_and_bill"}).status_code == 403 and untouched()
    # the right to make bills without the right to open them, or without the right to finish the list: refused
    for n, grants in enumerate(({"sales.packing": ["view", "edit"], "sales.invoice": ["create"]},
                                {"sales.packing": ["view"], "sales.invoice": ["view", "create"]})):
        who = role_user(f"fb_short{n}", grants, ns.factory)
        assert "Finish packing and make bill" not in page(who, "packing_detail", p.pk)
        assert login(who).post(url, {"action": "finish_and_bill"}).status_code == 403 and untouched()
    # every right, in another factory: the packing list is not theirs to find
    far = role_user("fb_far", {"sales.packing": ["view", "edit"], "sales.invoice": ["view", "create"]}, factory2)
    assert login(far).post(url, {"action": "finish_and_bill"}).status_code == 404 and untouched()
    # every right, here: both steps happen
    both = role_user("fb_both", {"sales.packing": ["view", "edit"], "sales.invoice": ["view", "create"]}, ns.factory)
    assert BOTH in page(both, "packing_detail", p.pk)
    r = login(both).post(url, {"action": "finish_and_bill"}, follow=True)
    assert r.status_code == 200 and packing_of(p).status == "packed" and SaleInvoice.objects.get().packing_id == p.pk
    # once finished the one-step button is gone
    assert "finish_and_bill" not in page(both, "packing_detail", p.pk)


def test_if_the_bill_cannot_be_drafted_the_packing_list_stays_a_draft(ns, monkeypatch):
    from sales.models import Carton, SaleInvoiceLine

    o = confirmed_order(ns)
    p = draft_pack(ns, o, [{"S": "10", "M": "5"}])
    real = SaleInvoice.save

    def fails(self, *args, **kwargs):
        # the very last thing drafting the bill does, after the list was numbered and the bill's lines were written
        if self.total:
            raise BusinessRuleError("The bill could not be drafted.")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(SaleInvoice, "save", fails)
    moves, vouchers, history = StockMovement.objects.count(), Voucher.objects.count(), PackingList.history.count()
    packed = {l.sku.size.code: l.qty_packed for l in o.lines.all()}
    c = login(ns.owner)
    url = reverse("packing_detail", args=[p.pk])
    r = c.post(url, {"action": "finish_and_bill"}, follow=True)
    html = r.content.decode()
    assert r.redirect_chain == [(url, 302)] and "The bill could not be drafted." in html and BOTH in html
    fresh = packing_of(p)
    assert fresh.status == "draft" and fresh.number is None and PackingList.history.count() == history
    assert not SaleInvoice.objects.exists() and not SaleInvoice.history.exists() and not SaleInvoiceLine.objects.exists()
    assert (StockMovement.objects.count(), Voucher.objects.count()) == (moves, vouchers)
    assert {l.sku.size.code: l.qty_packed for l in o.lines.all()} == packed and Carton.objects.filter(packing=p).count() == 1
    assert order_of(o).status == "confirmed"
    # the number drawn by the failed attempt was given back: the list is the first of its series when it does go through
    monkeypatch.undo()
    r = c.post(url, {"action": "finish_and_bill"}, follow=True)
    assert packing_of(p).number == "PKL/LDH1/26-27/0001" and SaleInvoice.objects.get().status == "draft"


def test_if_the_goods_are_not_in_stock_nothing_is_finished_or_billed(bare):
    ns = bare
    o = orders.confirm_order(draft_order(ns), user=ns.owner)
    p = draft_pack(ns, o, ALL)
    url = reverse("packing_detail", args=[p.pk])
    r = login(ns.owner).post(url, {"action": "finish_and_bill"}, follow=True)
    assert r.redirect_chain == [(url, 302)] and "only 0 available at LDH1 / Main Godown" in r.content.decode()
    assert packing_of(p).status == "draft" and packing_of(p).number is None and not SaleInvoice.objects.exists()


def test_finish_and_bill_in_a_locked_period_drafts_as_the_two_steps_do_and_posting_is_still_refused(ns):
    """Finishing a packing list and drafting a bill post nothing to the books or to stock, so the period lock does not
    stop them, one step or two. Posting the bill is where the lock applies, and that step is untouched."""
    from core.services.periods import lock_period

    o = confirmed_order(ns)
    two = draft_bill(ns, pack(ns, o, [{"S": "5"}]))
    p = draft_pack(ns, o, [{"M": "5"}])
    lock_period(user=ns.owner, company=ns.company, upto=date(2030, 12, 31))
    c = login(ns.owner)
    r = c.post(reverse("packing_detail", args=[p.pk]), {"action": "finish_and_bill"}, follow=True)
    one = SaleInvoice.objects.exclude(pk=two.pk).get()
    assert "is locked" not in r.content.decode() and packing_of(p).status == "packed" and one.status == "draft"
    moves, vouchers = StockMovement.objects.count(), Voucher.objects.count()
    for inv in (one, two):
        r = c.post(reverse("saleinvoice_detail", args=[inv.pk]), {"action": "post"}, follow=True)
        fresh = inv_of(inv)
        assert "is locked" in r.content.decode() and fresh.status == "draft" and fresh.number is None
    assert (StockMovement.objects.count(), Voucher.objects.count()) == (moves, vouchers)
    assert packing_of(p).status == "packed" and order_of(o).status == "confirmed"


# ================================================================ review fixes: no step that must fail

BILL_GONE = "Its bill was cancelled. Discard this draft return."
LIST_GONE = "Its packing list was cancelled. Discard this draft bill."
NO_STOCK = "None of these pieces is in finished stock yet; the list can be saved but not finished."


def test_a_packing_list_with_a_bill_cannot_be_cancelled(ns):
    o = confirmed_order(ns)
    p = pack(ns, o, [{"S": "10"}])
    inv = draft_bill(ns, p)
    with pytest.raises(BusinessRuleError, match=f"{p.number} has a draft bill. Discard or cancel that bill first."):
        packing.cancel_packing(p, user=ns.owner, reason="wrong goods")
    assert packing_of(p).status == "packed" and order_of(o).lines.get(sku=ns.sku("Black", "S")).qty_packed == D("10")
    # the page does not offer what would be refused, and says why
    c = login(ns.owner)
    url = reverse("packing_detail", args=[p.pk])
    html = c.get(url).content.decode()
    assert "Cancel packing list" not in html and "Discard or cancel its bill before cancelling this packing list." in html
    r = c.post(url, {"action": "cancel", "reason": "wrong goods"}, follow=True)
    assert "has a draft bill. Discard or cancel that bill first." in r.content.decode() and packing_of(p).status == "packed"
    # with the draft discarded the list can be cancelled as before
    invoices.discard_draft(inv, user=ns.owner)
    assert "Cancel packing list" in c.get(url).content.decode()
    # a cancelled bill does not hold the list either
    inv = billed(ns, p)
    with pytest.raises(BusinessRuleError, match="has been invoiced"):
        packing.cancel_packing(p, user=ns.owner, reason="wrong goods")
    invoices.cancel_invoice(inv, user=ns.owner, reason="wrong")
    assert packing.cancel_packing(p, user=ns.owner, reason="wrong goods").status == "cancelled"


def stranded_bill(ns):
    """A draft bill whose packing list was cancelled under it: no screen can make this any more, but books that
    were kept before the guard may hold one. Built here by lifting the guard, as the old service behaved."""
    o = confirmed_order(ns)
    p = pack(ns, o, [{"S": "10"}])
    inv = draft_bill(ns, p)
    PackingList.objects.filter(pk=p.pk).update(status="cancelled")
    packing.refresh_packed(o)
    return o, p, inv


def test_a_draft_bill_of_a_cancelled_packing_list_is_never_offered_for_posting(ns):
    o, p, inv = stranded_bill(ns)
    with pytest.raises(BusinessRuleError, match="no longer a finalised packing list"):
        invoices.post_invoice(inv, user=ns.owner)
    g = invoice_guide(inv_of(inv), ns.owner)
    assert offered(g) == [] and g["waiting"] == "" and g["idle"] == LIST_GONE and not g["complete"] and not g["closed"]
    assert invoice_next(inv_of(inv), ns.owner) is None
    html = page(ns.owner, "saleinvoice_detail", inv.pk)
    assert LIST_GONE in guide_of(html) and "<a " not in guide_of(html) and "Discard draft" in html
    assert 'value="post"' not in html
    assert "Post bill" not in row_with(page(ns.owner, "saleinvoice_list"), "Draft")
    # the order does not count it: nothing is billed, the pieces are to be packed again
    g = order_guide(order_of(o), ns.owner)
    assert [a["label"] for a in offered(g)] == ["Pack goods"] and "60 pieces" in g["primary"]["hint"]
    assert states(g) == {"Ordered": "done", "Confirmed": "done", "Packed": "now", "Billed": "todo", "Paid": "todo"}
    follow_links(ns, g)
    pg = packing_guide(packing_of(p), ns.owner)
    assert offered(pg) == [] and pg["closed"]


def test_a_draft_return_of_a_cancelled_bill_is_never_offered_for_posting(ns):
    inv = quick_invoice(ns)
    note = draft_return(ns, inv)
    invoices.cancel_invoice(inv, user=ns.owner, reason="wrong customer")        # a draft return does not stop this
    with pytest.raises(BusinessRuleError, match="no longer posted"):
        credit_notes.post_credit_note(note, user=ns.owner)
    g = creditnote_guide(note_of(note), ns.owner)
    assert offered(g) == [] and g["waiting"] == "" and g["idle"] == BILL_GONE and not g["complete"] and not g["closed"]
    assert states(g) == {"Return saved": "done", "Return posted": "todo"}
    html = page(ns.owner, "salecn_detail", note.pk)
    assert BILL_GONE in guide_of(html) and 'value="post"' not in html and "Discard draft" in html
    assert offered(invoice_guide(inv_of(inv), ns.owner)) == []


def test_pieces_promised_to_a_packed_list_do_not_count_as_stock_for_the_next_one(bare):
    ns = bare
    post_opening_stock(company=ns.company, factory=ns.factory, location=ns.godown, user=ns.owner,
                       entries=[OpeningItem(ns.sku("Black", "M"), D("10"), D("300"))])
    first = orders.confirm_order(draft_order(ns, qty="10", sizes=("M",)), user=ns.owner)
    second = orders.confirm_order(draft_order(ns, qty="10", order_type="mto", sizes=("M",)), user=ns.owner)
    assert not order_guide(order_of(second), ns.owner)["blocked"]             # ten in stock, promised to nobody
    p = packing.finalize_packing(draft_pack(ns, first, [{"M": "10"}]), user=ns.owner)
    # all ten are now held for the first order's list: a list for the second could be saved but never finished
    assert packing.available_at(ns.godown, ns.sku("Black", "M")) == D("0")
    g = order_guide(order_of(second), ns.owner)
    assert g["blocked"] and g["waiting"] == "goods from production" and g["primary"] is None
    packing.cancel_packing(p, user=ns.owner, reason="held back")
    assert [a["label"] for a in offered(order_guide(order_of(second), ns.owner))] == ["Pack goods"]


def test_a_ready_stock_order_with_nothing_in_stock_still_packs_and_is_told_so(bare):
    ns = bare
    o = orders.confirm_order(draft_order(ns, sizes=("M",)), user=ns.owner)
    g = order_guide(order_of(o), ns.owner)
    assert [a["label"] for a in offered(g)] == ["Pack goods"] and not g["blocked"]
    assert g["primary"]["hint"] == f"30 pieces of {o.number} are still to be packed. {NO_STOCK}"
    follow_links(ns, g)
    assert NO_STOCK in guide_of(page(ns.owner, "saleorder_detail", o.pk))
    post_opening_stock(company=ns.company, factory=ns.factory, location=ns.godown, user=ns.owner,
                       entries=[OpeningItem(ns.sku("Black", "M"), D("1"), D("300"))])
    g = order_guide(order_of(o), ns.owner)
    assert g["primary"]["hint"] == f"30 pieces of {o.number} are still to be packed."


def test_a_made_to_order_order_stops_waiting_once_its_production_order_is_closed(company, factory, owner):
    from masters.models import SKU
    from production.services import orders as prod_orders
    from tests import prod_helpers as ph

    ns = ph.build(company, factory, owner)
    customer = h.parties.create_party(company=company, name="Dealer Dhillon", mobile="9877700000", is_customer=True, state_code="03")
    so = orders.create_order(
        company=company, factory=factory, customer=customer, date=DAY, user=owner, order_type="mto",
        lines=[orders.OrderLineSpec(SKU.objects.get(style=ns.style, colour=ns.black, size=ns.sizes["M"]), D("40"), D("400"), D("0"))])
    so = orders.confirm_order(so, user=owner)
    assert order_guide(order_of(so), owner)["blocked"]                         # a draft requirement: still to be made
    po = prod_orders.release_order(so.production_order, user=owner)
    assert order_guide(order_of(so), owner)["blocked"]
    prod_orders.close_order(po, user=owner, reason="Fabric not available")
    # nothing more will come from production: the seller is not left waiting for ever
    g = order_guide(order_of(so), owner)
    assert [a["label"] for a in offered(g)] == ["Pack goods"] and not g["blocked"] and g["waiting"] == ""
    assert g["primary"]["hint"] == f"40 pieces of {so.number} are still to be packed. {NO_STOCK}"
    assert login(owner).get(g["primary"]["url"]).status_code == 200
    html = page(owner, "saleorder_detail", so.pk)
    assert NO_STOCK in guide_of(html) and "Close the balance" in html
