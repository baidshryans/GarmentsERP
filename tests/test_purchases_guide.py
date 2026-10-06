"""The buying guide: where a purchase is on its way from order to paid, and the one thing it needs next
(guided buying, piece 2c). One test per row of the spec's table, then agreement between the order, goods-received
and bill guides, permissions, and each offered link followed to the screen it opens."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.test import Client
from django.urls import reverse

from core.models import Location, Role, RolePermission
from ledger.models import Ledger
from ledger.selectors import bill_outstanding
from ledger.services.manual import Row, post_manual_voucher
from masters.models import Material, Unit
from masters.services import parties
from purchases.models import DebitNote, Grn, PurchaseInvoice, PurchaseOrder
from purchases.services import debit_notes, grn as grns, invoices, orders
from purchases.services.guide import (
    WAITS_FOR_BILL, debitnote_guide, grn_guide, grn_next, invoice_guide, invoice_next, po_guide, po_next,
)
from tests.conftest import make_user

D = Decimal
DAY = date(2026, 6, 15)


@pytest.fixture
def ns(company, factory, owner):
    return SimpleNamespace(
        company=company, factory=factory, owner=owner,
        vendor=parties.create_party(company=company, name="Yarn House", mobile="9833333333", is_vendor=True, credit_days=30),
        godown=Location.objects.get(factory=factory, name="Main Godown"),
        trim=Material.objects.create(code="ZIP-1", name="Zipper", kind="trim", unit=Unit.objects.get(code="PCS")),
        fabric=Material.objects.create(code="FAB-1", name="Fleece", kind="fabric", unit=Unit.objects.get(code="KG")))


def draft_po(ns, qty="100", rate="100"):
    return orders.create_po(company=ns.company, factory=ns.factory, vendor=ns.vendor, date=DAY, user=ns.owner,
                            lines=[orders.POLineSpec(ns.trim, D(qty), D(rate))])


def order(ns, qty="100", rate="100"):
    """A submitted order: approved at once up to 50,000, waiting for the owner above it."""
    return orders.submit_po(draft_po(ns, qty, rate), user=ns.owner)


def draft_grn(ns, po=None, qty="100", rejected="0", rate="100", remark=""):
    spec = grns.GrnLineSpec(item=ns.trim, rate=D(rate), qty_received=D(qty), qty_rejected=D(rejected),
                            remark=remark or ("damaged" if D(rejected) else ""), po_line=po.lines.get() if po else None)
    return grns.create_grn(company=ns.company, factory=ns.factory, location=ns.godown, vendor=ns.vendor, date=DAY,
                           lines=[spec], user=ns.owner, po=po)


def received(ns, po=None, **kw):
    """Goods received, checked and posted."""
    g = draft_grn(ns, po, **kw)
    grns.finish_qc(g, user=ns.owner)
    return grns.post_grn(g, user=ns.owner)


def draft_bill(ns, grn, qty=None, no="V-1", rate="100"):
    line = grn.lines.get()
    return invoices.save_invoice(
        company=ns.company, factory=ns.factory, vendor=ns.vendor, vendor_invoice_no=no, vendor_invoice_date=DAY, date=DAY,
        lines=[invoices.InvoiceLineSpec(line, D(qty) if qty else line.qty_accepted, D(rate))], user=ns.owner)


def billed(ns, grn, **kw):
    return invoices.post_invoice(draft_bill(ns, grn, **kw), user=ns.owner)


def direct_bill(ns, no="D-1", post=True):
    inv = invoices.save_invoice(
        company=ns.company, factory=ns.factory, vendor=ns.vendor, vendor_invoice_no=no, vendor_invoice_date=DAY, date=DAY,
        lines=[invoices.InvoiceLineSpec(None, D("10"), D("50"), item=ns.trim)], user=ns.owner, location=ns.godown)
    return invoices.post_invoice(inv, user=ns.owner) if post else inv


def pay(ns, inv, amount):
    cash = Ledger.objects.get(company=ns.company, system_key="cash")
    return post_manual_voucher(
        company=ns.company, factory=ns.factory, vtype="payment", on_date=DAY, narration="", header={"account": str(cash.pk)},
        rows=[Row(ledger=str(ns.vendor.payable_ledger_id), amount=str(amount), ref_type="against",
                  reference=inv.vendor_invoice_no)], user=ns.owner)


def po_of(po):
    return PurchaseOrder.objects.select_related("vendor", "factory", "company").get(pk=po.pk)


def grn_of(grn):
    return Grn.objects.select_related("vendor", "factory", "po").get(pk=grn.pk)


def inv_of(inv):
    return PurchaseInvoice.objects.select_related("vendor", "factory").get(pk=inv.pk)


def note_of(note):
    return DebitNote.objects.select_related("vendor", "factory", "grn").get(pk=note.pk)


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


def bill_url(ns, grn):
    return reverse("invoice_new") + f"?vendor={ns.vendor.pk}&factory={ns.factory.pk}&grn={grn.pk}"


def pay_link(ns, inv, due):
    return (reverse("voucher_payment") + f"?ledger={ns.vendor.payable_ledger_id}&amount={due}&ref={inv.vendor_invoice_no}"
            f"&narration=Paid+against+{inv.vendor_invoice_no}")


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
        if label == "Submit order":
            assert a["url"] == reverse("po_detail", args=[ctx["po"].pk])
            assert ctx["po"].status == "draft" and 'name="action" value="submit"' in html
        elif label == "Approve order":
            assert a["url"] == reverse("po_detail", args=[ctx["po"].pk])
            assert ctx["po"].status == "pending_approval" and 'name="action" value="approve"' in html
        elif label == "Receive goods":
            po = ctx["po"]
            assert a["url"] == reverse("grn_new") + f"?po={po.pk}" and f'name="po" value="{po.pk}"' in html
            lines = {str(l.pk) for l in po.lines.all()}
            assert {str(row["po_line"]) for row in ctx["rows"] if row} <= lines and any(ctx["rows"])
        elif label == "Check quality":
            assert a["url"] == reverse("grn_detail", args=[ctx["grn"].pk])
            assert ctx["grn"].status == "draft" and 'name="action" value="finish_qc"' in html
        elif label == "Post goods received":
            assert a["url"] == reverse("grn_detail", args=[ctx["grn"].pk])
            assert ctx["grn"].status == "qc_done" and 'name="action" value="post"' in html
        elif label == "Enter supplier bill":
            grn_id = int(a["url"].rsplit("grn=", 1)[1])
            assert ctx["vendor"] == ns.vendor and ctx["factory"] == ns.factory and not ctx["direct"]
            mine = [row for row in ctx["grn_lines"] if row["gl"].grn_id == grn_id]
            assert mine and all(row["use"] and row["left"] > 0 for row in mine), a
        elif label == "Post supplier bill":
            assert a["url"] == reverse("invoice_detail", args=[ctx["inv"].pk])
            assert ctx["inv"].status == "draft" and 'name="action" value="post"' in html
        elif label == f"Pay {ns.vendor.name}":
            row = ctx["rows"][0]
            assert ctx["vtype"] == "payment" and row["ledger"] == str(ns.vendor.payable_ledger_id) and row["ref_type"] == "against"
            assert D(row["amount"]) == -bill_outstanding(ns.vendor.payable_ledger, row["reference"]) > 0
            assert f"ref={row['reference']}&" in a["url"]
        elif label in ("Return rejected goods to supplier", "Post return"):
            note = ctx["note"]
            assert a["url"] == reverse("debitnote_detail", args=[note.pk])
            assert note.status == "draft" and 'name="action" value="post"' in html
            assert (note.kind == "rejection") == (label == "Return rejected goods to supplier")
        else:
            raise AssertionError(f"a link the guide should not offer: {a}")


# ---------------- one test per row of the table ----------------

def test_a_draft_order_is_submitted(ns):
    po = draft_po(ns)
    g = po_guide(po_of(po), ns.owner)
    assert seen(g) == [("Submit order", reverse("po_detail", args=[po.pk]))]
    assert states(g) == {"Ordered": "now", "Received": "todo", "Checked": "todo", "Billed": "todo", "Paid": "todo"}
    assert current(g) == ["Ordered"] and not g["complete"] and not g["closed"] and g["waiting"] == ""
    follow_links(ns, g)


def test_an_order_above_the_limit_waits_for_approval_and_shows_the_approved_stage(ns):
    po = draft_po(ns, "1000", "100")                       # 1,00,000 is above the 50,000 limit
    assert list(states(po_guide(po_of(po), ns.owner))) == ["Ordered", "Approved", "Received", "Checked", "Billed", "Paid"]
    po = orders.submit_po(po, user=ns.owner)
    assert po.status == "pending_approval"
    g = po_guide(po_of(po), ns.owner)
    assert seen(g) == [("Approve order", reverse("po_detail", args=[po.pk]))]
    assert states(g)["Ordered"] == "done" and states(g)["Approved"] == "now" and current(g) == ["Approved"]
    follow_links(ns, g)
    po = orders.approve_po(po, user=ns.owner)
    g = po_guide(po_of(po), ns.owner)
    assert states(g)["Approved"] == "done" and g["primary"]["label"] == "Receive goods"


def test_an_order_within_the_limit_has_no_approved_stage_and_asks_for_the_goods(ns):
    po = order(ns)
    assert po.status == "approved"
    g = po_guide(po_of(po), ns.owner)
    assert seen(g) == [("Receive goods", reverse("grn_new") + f"?po={po.pk}")]
    assert states(g) == {"Ordered": "done", "Received": "now", "Checked": "todo", "Billed": "todo", "Paid": "todo"}
    assert details(g) == {"Received": "0 of 100"} and current(g) == ["Received"]
    follow_links(ns, g)


def test_a_draft_goods_receipt_asks_for_the_quality_check_and_stops_the_order_asking_for_goods(ns):
    po = order(ns)
    g1 = draft_grn(ns, po, qty="60")
    for g in (po_guide(po_of(po), ns.owner), grn_guide(grn_of(g1), ns.owner)):
        assert seen(g) == [("Check quality", reverse("grn_detail", args=[g1.pk]))]
        assert states(g)["Checked"] == "now" and states(g)["Billed"] == "todo"
        follow_links(ns, g)
    assert current(grn_guide(grn_of(g1), ns.owner)) == ["Checked"] and states(grn_guide(grn_of(g1), ns.owner))["Received"] == "done"


def test_a_checked_goods_receipt_asks_to_be_posted(ns):
    po = order(ns)
    g1 = draft_grn(ns, po, qty="60")
    grns.finish_qc(g1, user=ns.owner)
    for g in (po_guide(po_of(po), ns.owner), grn_guide(grn_of(g1), ns.owner)):
        assert seen(g) == [("Post goods received", reverse("grn_detail", args=[g1.pk]))]
        follow_links(ns, g)


def test_a_partly_received_order_asks_for_the_rest_first_and_the_bill_beside_it(ns):
    po = order(ns)
    g1 = received(ns, po, qty="60")
    g = po_guide(po_of(po), ns.owner)
    assert po_of(po).status == "partly_received"
    assert seen(g) == [("Receive goods", reverse("grn_new") + f"?po={po.pk}"), ("Enter supplier bill", bill_url(ns, g1))]
    assert states(g) == {"Ordered": "done", "Received": "now", "Checked": "now", "Billed": "now", "Paid": "todo"}
    assert details(g) == {"Received": "60 of 100"} and current(g) == ["Received"]
    follow_links(ns, g)


def test_posted_goods_with_no_bill_ask_for_the_supplier_bill(ns):
    g1 = received(ns)                                      # no order: the journey starts at Received
    g = grn_guide(grn_of(g1), ns.owner)
    assert seen(g) == [("Enter supplier bill", bill_url(ns, g1))] and g1.number in g["primary"]["hint"]
    assert states(g) == {"Received": "done", "Checked": "done", "Billed": "now", "Paid": "todo"}
    assert details(g) == {"Received": "100", "Checked": "100 accepted"} and current(g) == ["Billed"]
    follow_links(ns, g)


def test_goods_on_a_draft_bill_are_not_offered_again_and_the_draft_asks_to_be_posted(ns):
    g1 = received(ns)
    inv = draft_bill(ns, g1, qty="40")
    g = grn_guide(grn_of(g1), ns.owner)                    # 60 accepted are on no bill yet
    assert seen(g) == [("Enter supplier bill", bill_url(ns, g1)), ("Post supplier bill", reverse("invoice_detail", args=[inv.pk]))]
    follow_links(ns, g)
    inv.delete()
    inv = draft_bill(ns, g1)                               # all 100 on the draft
    g = grn_guide(grn_of(g1), ns.owner)
    assert seen(g) == [("Post supplier bill", reverse("invoice_detail", args=[inv.pk]))] and states(g)["Billed"] == "now"
    mine = invoice_guide(inv_of(inv), ns.owner)
    assert seen(mine) == seen(g) and states(mine) == {"Received": "done", "Checked": "done", "Billed": "now", "Paid": "todo"}
    assert details(mine) == {"Billed": "10000.00"} and current(mine) == ["Billed"]
    follow_links(ns, mine)


def test_a_posted_bill_with_an_amount_unpaid_asks_to_pay_the_supplier_what_the_ledger_says(ns):
    po = order(ns)
    g1 = received(ns, po)
    inv = billed(ns, g1)
    for g in (po_guide(po_of(po), ns.owner), grn_guide(grn_of(g1), ns.owner), invoice_guide(inv_of(inv), ns.owner)):
        assert seen(g) == [("Pay Yarn House", pay_link(ns, inv, "10000.00"))]
        assert states(g)["Billed"] == "done" and states(g)["Paid"] == "now" and current(g) == ["Paid"]
        assert details(g)["Billed"] == "10000.00" and details(g)["Paid"] == "10000.00 unpaid"
        assert not g["complete"]
        follow_links(ns, g)
    pay(ns, inv, "4000")                                   # a part payment: the rest is what is asked for
    g = invoice_guide(inv_of(inv), ns.owner)
    assert seen(g) == [("Pay Yarn House", pay_link(ns, inv, "6000.00"))] and details(g)["Paid"] == "6000.00 unpaid"
    follow_links(ns, g)


def test_a_paid_purchase_is_complete_on_every_page(ns):
    po = order(ns)
    g1 = received(ns, po)
    inv = billed(ns, g1)
    pay(ns, inv, "10000")
    for g in (po_guide(po_of(po), ns.owner), grn_guide(grn_of(g1), ns.owner), invoice_guide(inv_of(inv), ns.owner)):
        assert offered(g) == [] and g["complete"] and not g["closed"] and g["waiting"] == ""
        assert set(states(g).values()) == {"done"} and current(g) == []
    assert details(po_guide(po_of(po), ns.owner)) == {"Received": "100 of 100", "Billed": "10000.00"}
    assert po_next(po_of(po), ns.owner) is None and grn_next(grn_of(g1), ns.owner) is None
    assert invoice_next(inv_of(inv), ns.owner) is None


def test_a_direct_bill_starts_at_billed(ns):
    inv = direct_bill(ns, post=False)
    g = invoice_guide(inv_of(inv), ns.owner)
    assert seen(g) == [("Post supplier bill", reverse("invoice_detail", args=[inv.pk]))]
    assert states(g) == {"Billed": "now", "Paid": "todo"}
    follow_links(ns, g)
    inv = invoices.post_invoice(inv, user=ns.owner)
    g = invoice_guide(inv_of(inv), ns.owner)
    assert seen(g) == [("Pay Yarn House", pay_link(ns, inv, "500.00"))] and states(g) == {"Billed": "done", "Paid": "now"}
    follow_links(ns, g)
    pay(ns, inv, "500")
    g = invoice_guide(inv_of(inv), ns.owner)
    assert g["complete"] and states(g) == {"Billed": "done", "Paid": "done"}


def test_rejected_goods_are_returned_once_the_supplier_has_billed_them(ns):
    """Posting goods received with a rejection raises the return itself, as a draft. It can be posted only when the
    supplier's bill includes the rejected goods, and that is when the guide offers it: before paying."""
    g1 = received(ns, qty="100", rejected="20")
    note = DebitNote.objects.get(grn=g1)
    assert note.status == "draft" and note.kind == "rejection"
    g = grn_guide(grn_of(g1), ns.owner)
    assert seen(g) == [("Enter supplier bill", bill_url(ns, g1))]          # nothing to post on the return yet
    mine = debitnote_guide(note_of(note), ns.owner)
    assert offered(mine) == [] and mine["waiting"] == "" and mine["idle"] == WAITS_FOR_BILL and not mine["complete"]
    assert states(mine) == {"Rejected": "done", "Billed by supplier": "now", "Return posted": "todo"}

    inv = billed(ns, g1, qty="100")                         # the supplier billed all 100, the 20 rejected included
    back = ("Return rejected goods to supplier", reverse("debitnote_detail", args=[note.pk]))
    money = ("Pay Yarn House", pay_link(ns, inv, "10000.00"))
    for g in (grn_guide(grn_of(g1), ns.owner), invoice_guide(inv_of(inv), ns.owner)):
        assert seen(g) == [back, money]
        follow_links(ns, g)
    mine = debitnote_guide(note_of(note), ns.owner)
    assert seen(mine) == [back] and mine["idle"] == ""
    assert states(mine) == {"Rejected": "done", "Billed by supplier": "done", "Return posted": "now"}
    follow_links(ns, mine)

    debit_notes.post_debit_note(note, user=ns.owner)
    assert seen(grn_guide(grn_of(g1), ns.owner)) == [money] == seen(invoice_guide(inv_of(inv), ns.owner))
    mine = debitnote_guide(note_of(note), ns.owner)
    assert mine["complete"] and offered(mine) == [] and details(mine) == {"Return posted": "2000.00"}


def test_a_bill_for_the_accepted_goods_only_leaves_the_return_waiting_and_the_purchase_can_finish(ns):
    g1 = received(ns, qty="100", rejected="20")
    inv = billed(ns, g1, qty="80")
    pay(ns, inv, "8000")
    g = grn_guide(grn_of(g1), ns.owner)
    assert offered(g) == [] and g["complete"] and details(g)["Checked"] == "80 accepted"
    assert debitnote_guide(note_of(DebitNote.objects.get(grn=g1)), ns.owner)["idle"] == WAITS_FOR_BILL


def test_a_draft_return_of_goods_in_stock_asks_to_be_posted(ns):
    received(ns)
    note = debit_notes.create_return_note(
        company=ns.company, factory=ns.factory, vendor=ns.vendor, date=DAY, user=ns.owner, reason="Wrong size",
        lines=[debit_notes.ReturnLineSpec(item=ns.trim, qty=D("10"), rate=D("100"), location=ns.godown)])
    g = debitnote_guide(note_of(note), ns.owner)
    assert seen(g) == [("Post return", reverse("debitnote_detail", args=[note.pk]))]
    assert states(g) == {"Return saved": "done", "Return posted": "now"} and current(g) == ["Return posted"]
    follow_links(ns, g)
    debit_notes.post_debit_note(note, user=ns.owner)
    g = debitnote_guide(note_of(note), ns.owner)
    assert g["complete"] and offered(g) == [] and states(g)["Return posted"] == "done"
    debit_notes.cancel_debit_note(note, user=ns.owner, reason="entered twice")
    g = debitnote_guide(note_of(note), ns.owner)
    assert g["closed"] and not g["complete"] and offered(g) == [] and set(states(g).values()) == {"todo"}


def test_cancelled_documents_ask_for_nothing(ns):
    g1 = received(ns)
    inv = billed(ns, g1)
    invoices.cancel_invoice(inv, user=ns.owner, reason="wrong rate")
    g = invoice_guide(inv_of(inv), ns.owner)
    assert offered(g) == [] and g["closed"] and not g["complete"] and set(states(g).values()) == {"todo"}
    assert invoice_next(inv_of(inv), ns.owner) is None
    # the goods are billable again
    assert seen(grn_guide(grn_of(g1), ns.owner)) == [("Enter supplier bill", bill_url(ns, g1))]
    grns.cancel_grn(g1, user=ns.owner, reason="wrong supplier")
    g = grn_guide(grn_of(g1), ns.owner)
    assert offered(g) == [] and g["closed"] and not g["complete"] and current(g) == []
    assert grn_next(grn_of(g1), ns.owner) is None


def test_a_short_closed_order_asks_for_no_more_goods_but_what_came_is_still_billed_and_paid(ns):
    po = order(ns)
    g1 = received(ns, po, qty="60")
    orders.short_close(po, user=ns.owner, reason="Supplier out of stock")
    g = po_guide(po_of(po), ns.owner)
    assert seen(g) == [("Enter supplier bill", bill_url(ns, g1))] and not g["closed"]
    assert states(g)["Received"] == "done" and details(g)["Received"] == "60 of 100"
    inv = billed(ns, g1)
    pay(ns, inv, "6000")
    g = po_guide(po_of(po), ns.owner)
    assert offered(g) == [] and g["closed"] and not g["complete"] and po_next(po_of(po), ns.owner) is None
    # closed with nothing received: closed at once
    other = order(ns)
    orders.short_close(other, user=ns.owner, reason="Not needed")
    g = po_guide(po_of(other), ns.owner)
    assert offered(g) == [] and g["closed"]


# ---------------- the guides agree ----------------

def test_the_order_the_goods_receipts_and_the_bills_agree_on_every_shared_document(ns):
    po = order(ns, qty="300")
    a = received(ns, po, qty="100")                         # billed and unpaid
    paid_for = billed(ns, a, no="V-A")
    b = received(ns, po, qty="100", rejected="10")          # on a draft bill
    drafted = draft_bill(ns, b, no="V-B")
    c = received(ns, po, qty="60")                          # no bill yet
    d = draft_grn(ns, po, qty="50")                         # still to be checked
    whole = {x["url"]: x for x in offered(po_guide(po_of(po), ns.owner))}
    parts = [x for g in (a, b, c, d) for x in offered(grn_guide(grn_of(g), ns.owner))]
    parts += [x for i in (paid_for, drafted) for x in offered(invoice_guide(inv_of(i), ns.owner))]
    assert sorted({x["label"] for x in parts}) == ["Check quality", "Enter supplier bill", "Pay Yarn House", "Post supplier bill"]
    for x in parts:
        assert whole[x["url"]] == x                         # same label, hint, link and permissions
    assert sorted(whole) == sorted({x["url"] for x in parts})
    # furthest behind first; and no more goods are asked for while a goods receipt is still open
    assert [x["label"] for x in whole.values()] == ["Check quality", "Enter supplier bill", "Post supplier bill", "Pay Yarn House"]
    follow_links(ns, po_guide(po_of(po), ns.owner))


def test_a_bill_that_covers_two_goods_receipts_is_named_once_on_the_order(ns):
    po = order(ns, qty="200")
    a, b = received(ns, po, qty="100"), received(ns, po, qty="100")
    inv = invoices.post_invoice(invoices.save_invoice(
        company=ns.company, factory=ns.factory, vendor=ns.vendor, vendor_invoice_no="V-9", vendor_invoice_date=DAY, date=DAY,
        lines=[invoices.InvoiceLineSpec(g.lines.get(), D("100"), D("100")) for g in (a, b)], user=ns.owner), user=ns.owner)
    g = po_guide(po_of(po), ns.owner)
    assert seen(g) == [("Pay Yarn House", pay_link(ns, inv, "20000.00"))]
    assert details(g) == {"Received": "200 of 200", "Billed": "20000.00", "Paid": "20000.00 unpaid"}
    assert seen(grn_guide(grn_of(a), ns.owner)) == seen(grn_guide(grn_of(b), ns.owner)) == seen(g)


# ---------------- permissions ----------------

def test_a_role_that_may_not_do_the_next_step_is_told_what_the_purchase_waits_for(ns):
    po = order(ns)
    looker = role_user("po_looker", {"purchases.po": ["view"]}, ns.factory)
    g = po_guide(po_of(po), looker)
    assert g["primary"] is None and g["others"] == [] and g["waiting"] == "Receive goods"
    assert po_next(po_of(po), looker) is None


def stage(ns, name):
    """Build the state in which the guide offers one step; returns (guide function, document)."""
    if name == "draft_po":
        return po_guide, po_of(draft_po(ns))
    if name == "pending_po":
        return po_guide, po_of(order(ns, "1000", "100"))
    if name == "open_po":
        return po_guide, po_of(order(ns))
    if name == "draft_grn":
        return grn_guide, grn_of(draft_grn(ns))
    if name == "checked_grn":
        g = draft_grn(ns)
        grns.finish_qc(g, user=ns.owner)
        return grn_guide, grn_of(g)
    if name == "posted_grn":
        return grn_guide, grn_of(received(ns))
    if name == "draft_bill":
        return invoice_guide, inv_of(draft_bill(ns, received(ns)))
    if name == "posted_bill":
        return invoice_guide, inv_of(billed(ns, received(ns)))
    if name == "rejection":
        g = received(ns, rejected="20")
        billed(ns, g, qty="100")
        pay(ns, PurchaseInvoice.objects.get(), "10000")
        return grn_guide, grn_of(g)
    note = debit_notes.create_return_note(
        company=ns.company, factory=ns.factory, vendor=ns.vendor, date=DAY, user=ns.owner, reason="Wrong size",
        lines=[debit_notes.ReturnLineSpec(item=ns.trim, qty=D("10"), rate=D("100"), location=ns.godown)])
    return debitnote_guide, note_of(note)


# `opens`: what the link itself answers to someone holding only the right to do the thing. A form that needs only
# `create` opens, but saving it lands on a page that needs `view`, so the guide asks for both either way.
@pytest.mark.parametrize("state, screen, action, target, label, opens", [
    ("draft_po", "purchases.po", "edit", "purchases.po", "Submit order", 403),
    ("pending_po", "purchases.po", "approve", "purchases.po", "Approve order", 403),
    ("open_po", "purchases.grn", "create", "purchases.grn", "Receive goods", 200),
    ("draft_grn", "purchases.grn", "edit", "purchases.grn", "Check quality", 403),
    ("checked_grn", "purchases.grn", "edit", "purchases.grn", "Post goods received", 403),
    ("posted_grn", "purchases.invoice", "create", "purchases.invoice", "Enter supplier bill", 200),
    ("draft_bill", "purchases.invoice", "edit", "purchases.invoice", "Post supplier bill", 403),
    ("posted_bill", "ledger.voucher", "create", "ledger.voucher", "Pay Yarn House", 200),
    ("rejection", "purchases.debitnote", "edit", "purchases.debitnote", "Return rejected goods to supplier", 403),
    ("return", "purchases.debitnote", "edit", "purchases.debitnote", "Post return", 403),
])
def test_each_action_needs_the_right_to_do_it_and_view_on_the_screen_it_opens(ns, state, screen, action, target, label, opens):
    guide, doc = stage(ns, state)
    wanted = guide(doc, ns.owner)["primary"]
    assert wanted["label"] == label and wanted["perm"] == ((screen, action), (target, "view"))
    # the right to do it alone is not enough: the link, or the page saving leads to, would refuse the role
    blind = role_user("blind", {screen: [action]}, ns.factory)
    g = guide(doc, blind)
    assert offered(g) == [] and g["waiting"] == label
    assert login(blind).get(wanted["url"]).status_code == opens
    # view alone is not enough either
    only_view = role_user("only_view", {target: ["view"]}, ns.factory)
    g = guide(doc, only_view)
    assert offered(g) == [] and g["waiting"] == label
    # both together: offered, and the link opens
    seeing = role_user("seeing", {screen: [action, "view"]}, ns.factory)
    g = guide(doc, seeing)
    assert [a["label"] for a in offered(g)] == [label] and g["waiting"] == ""
    assert login(seeing).get(wanted["url"]).status_code == 200


def test_a_custom_role_with_create_but_not_view_gets_no_link(ns):
    po = order(ns)
    clerk = role_user("receive_only", {"purchases.grn": ["create"], "purchases.po": ["view"]}, ns.factory)
    assert clerk.has_screen_perm("purchases.grn", "create") and not clerk.has_screen_perm("purchases.grn", "view")
    g = po_guide(po_of(po), clerk)
    assert g["primary"] is None and g["others"] == [] and g["waiting"] == "Receive goods"


def test_someone_who_may_do_a_later_step_gets_that_one_and_no_waiting_line(ns, accountant):
    po = order(ns)
    g1 = received(ns, po, qty="60")
    # receiving the rest is the store's job; entering the bill is the accountant's, so that is their button
    g = po_guide(po_of(po), accountant)
    assert seen(g) == [("Enter supplier bill", bill_url(ns, g1))] and g["waiting"] == ""
    follow_links(ns, g, accountant)
    keeper = make_user("keeper")
    keeper.roles.add(Role.objects.get(name="Store Keeper"))
    keeper.allowed_factories.add(ns.factory)
    g = po_guide(po_of(po), keeper)
    assert [a["label"] for a in offered(g)] == ["Receive goods"]
    follow_links(ns, g, keeper)


def test_paying_is_offered_only_to_a_role_that_may_enter_a_payment(ns):
    inv = billed(ns, received(ns))
    biller = role_user("biller", {"purchases.invoice": ["view", "create", "edit"]}, ns.factory)
    g = invoice_guide(inv_of(inv), biller)
    assert offered(g) == [] and g["waiting"] == "Pay Yarn House" and not g["complete"]
    assert invoice_next(inv_of(inv), biller) is None


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
    po = order(ns, qty="200")
    g1 = received(ns, po, qty="100")
    billed(ns, g1)
    who = Counting(ns.owner)
    g = po_guide(po_of(po), who)
    assert [a["label"] for a in offered(g)] == ["Receive goods", "Pay Yarn House"]
    assert len(who.asked) == len(set(who.asked)) == 4      # goods received create and view, voucher create and view
    shared, again = {}, Counting(ns.owner)
    assert po_guide(po_of(po), again, shared) == g
    assert grn_next(grn_of(g1), again, shared)["label"] == "Pay Yarn House"
    assert invoice_next(inv_of(PurchaseInvoice.objects.get()), again, shared)["label"] == "Pay Yarn House"
    assert len(again.asked) == 4                            # the goods receipt and the bill asked nothing new


def test_the_guide_reads_and_never_writes(ns):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    po = order(ns, qty="200")
    g1 = received(ns, po, qty="100", rejected="10")
    inv = billed(ns, g1, qty="100")
    note = DebitNote.objects.get(grn=g1)
    docs = [(po_guide, po_of(po)), (grn_guide, grn_of(g1)), (invoice_guide, inv_of(inv)), (debitnote_guide, note_of(note))]
    before = [(d.history.count(), d.status) for _, d in docs]
    with CaptureQueriesContext(connection) as q:
        labels = [guide(doc, ns.owner)["primary"]["label"] for guide, doc in docs]
    assert labels == ["Receive goods", "Return rejected goods to supplier", "Return rejected goods to supplier",
                      "Return rejected goods to supplier"]
    assert all(x["sql"].lstrip().upper().startswith("SELECT") for x in q.captured_queries)
    assert [(type(d).objects.get(pk=d.pk).history.count(), type(d).objects.get(pk=d.pk).status) for _, d in docs] == before


def test_the_unpaid_amount_is_the_ledgers_and_another_factorys_bills_are_never_reached(ns, factory2):
    inv = billed(ns, received(ns))
    assert -bill_outstanding(ns.vendor.payable_ledger, inv.vendor_invoice_no, user=ns.owner) == D("10000.00")
    # someone who works only in the other factory cannot fetch the bill at all: the guide is never asked
    far = role_user("far", {"purchases.invoice": ["view"], "ledger.voucher": ["view", "create"]}, factory2)
    assert not PurchaseInvoice.objects.for_user(far).filter(pk=inv.pk).exists()
    assert login(far).get(reverse("invoice_detail", args=[inv.pk])).status_code == 404
