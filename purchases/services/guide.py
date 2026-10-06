"""Where a purchase is on its way from order to paid, and what it needs next (read-only).

One journey, entered at whichever document exists: Ordered, Approved, Received, Checked, Billed, Paid. The order,
goods-received, supplier-bill and return pages and the three lists ask the functions at the bottom; every action is
built by one function here, so two pages that speak of the same document name the same step with the same link.
Callers fetch the document through `for_user`; everything reached from it (an order's goods receipts, their bills
and returns) is in the same factory, so nothing here widens that. Nothing here writes, and nothing here changes
what is owed: the unpaid amount is read from the ledger's bill-wise records.
"""
from decimal import Decimal

from django.db.models import Sum
from django.urls import reverse

from ledger.selectors import outstanding_bills
from ledger.settlement import pay_url
from purchases.models import DebitNote, Grn, GrnLine, PurchaseInvoice, PurchaseInvoiceLine, PurchaseOrder
from purchases.services import debit_notes

ZERO = Decimal("0")
PO = PurchaseOrder.Status
G = Grn.Status
INV = PurchaseInvoice.Status
OPEN_GRN = (G.DRAFT, G.QC_DONE)
# what is furthest behind comes first
RANK = {"submit": 1, "approve": 2, "receive": 3, "check": 4, "post_grn": 5, "bill": 6, "post_bill": 7,
        "return_rejected": 8, "post_return": 8, "pay": 9}


def checker(user, perms):
    """Ask each permission once. `perms` is the memo; a caller showing many rows to one user passes the same dict."""
    def can(screen, action):
        key = (screen, action)
        if key not in perms:
            perms[key] = user.has_screen_perm(screen, action)
        return perms[key]
    return can


def qty(value):
    return f"{Decimal(value).normalize():f}"


# ---------------------------------------------------------------- one action each
# `perm` lists every permission the user needs: to do the thing, and to open the screen the link leads to.
# `pieces` is always 0 (purchases are in kilos, metres and pieces alike); the shared strip reads it.

def _action(kind, label, hint, url, *perm):
    return {"kind": kind, "label": label, "hint": hint, "url": url, "perm": perm, "pieces": 0}


def submit_action(po):
    return _action("submit", "Submit order", "The order is a draft. Submit it to give it a number.",
                   reverse("po_detail", args=[po.pk]), ("purchases.po", "edit"), ("purchases.po", "view"))


def approve_action(po):
    return _action("approve", "Approve order", "The order is above the approval limit and waits for the owner.",
                   reverse("po_detail", args=[po.pk]), ("purchases.po", "approve"), ("purchases.po", "view"))


def receive_action(po):
    return _action("receive", "Receive goods", f"Record what {po.vendor.name} delivered against {po.number}.",
                   reverse("grn_new") + f"?po={po.pk}", ("purchases.grn", "create"), ("purchases.grn", "view"))


def check_action(grn):
    return _action("check", "Check quality", "Accept everything in one step, or mark what was rejected and press Finish QC.",
                   reverse("grn_detail", args=[grn.pk]), ("purchases.grn", "edit"), ("purchases.grn", "view"))


def post_grn_action(grn):
    return _action("post_grn", "Post goods received", "Quality check is done. Posting brings the accepted goods into stock.",
                   reverse("grn_detail", args=[grn.pk]), ("purchases.grn", "edit"), ("purchases.grn", "view"))


def bill_action(grn):
    """Accepted goods of this receipt that no supplier bill has taken yet. The bill screen lists what is left to bill
    for the supplier in the active factory; `factory` and `grn` only let it tick this receipt's lines and say so
    when another factory is active. They choose nothing."""
    return _action("bill", "Enter supplier bill", f"{grn.number} has accepted goods with no supplier bill yet.",
                   reverse("invoice_new") + f"?vendor={grn.vendor_id}&factory={grn.factory_id}&grn={grn.pk}",
                   ("purchases.invoice", "create"), ("purchases.invoice", "view"))


def post_bill_action(inv):
    return _action("post_bill", "Post supplier bill", f"Bill {inv.vendor_invoice_no} is a draft. Check it, then post it.",
                   reverse("invoice_detail", args=[inv.pk]), ("purchases.invoice", "edit"), ("purchases.invoice", "view"))


def pay_action(inv, due):
    """A posted bill with an amount still open in the ledger's bill-wise records: opens Money paid with the supplier,
    the amount and the bill reference filled in. Nothing is posted until the user posts that voucher."""
    return _action("pay", f"Pay {inv.vendor.name}", f"{due:.2f} is still unpaid on bill {inv.vendor_invoice_no}.",
                   pay_url(inv.vendor.payable_ledger_id, due, inv.vendor_invoice_no, f"Paid against {inv.vendor_invoice_no}"),
                   ("ledger.voucher", "create"), ("ledger.voucher", "view"))


def return_action(note):
    """A draft return that can be posted now. One raised for goods rejected at the quality check can be posted only
    once the supplier has billed those goods (see `debit_notes.can_post`)."""
    url, perm = reverse("debitnote_detail", args=[note.pk]), (("purchases.debitnote", "edit"), ("purchases.debitnote", "view"))
    if note.kind == DebitNote.Kind.REJECTION:
        return _action("return_rejected", "Return rejected goods to supplier",
                       "The supplier billed goods you rejected. Post the return to claim their value back.", url, *perm)
    return _action("post_return", "Post return", "The return is a draft. Posting takes the goods out of stock.", url, *perm)


# ---------------------------------------------------------------- what the ledger and the documents say

def unpaid(inv, user, memo):
    """Amount still open on a posted bill, from the ledger's bill-wise records (the same figure the bill page shows).
    The open bills of one supplier are read once per memo."""
    ledger_id = inv.vendor.payable_ledger_id
    if inv.status != INV.POSTED or not ledger_id:
        return ZERO
    key = ("open bills", ledger_id)
    if key not in memo:
        memo[key] = outstanding_bills(inv.vendor.payable_ledger, user=user)["bills"]
    due = -memo[key].get(inv.vendor_invoice_no, ZERO)
    return due if due > 0 else ZERO


def _after_receipt(grns, user, memo):
    """What the posted goods receipts among `grns` still need. {grn id: {"accepted", "received", "items", "unbilled",
    "drafts": [bill], "posted": [(bill, unpaid)], "returns": [note]}} in four queries, plus one per supplier for
    the open bills and two per line of a rejection return."""
    facts = {g.pk: {"accepted": ZERO, "received": ZERO, "items": 0, "unbilled": False, "drafts": [], "posted": [], "returns": []}
             for g in grns if g.status == G.POSTED}
    if not facts:
        return facts
    left, owner = {}, {}
    for l in GrnLine.objects.filter(grn_id__in=facts).values("id", "grn_id", "qty_accepted", "qty_received"):
        left[l["id"]], owner[l["id"]] = l["qty_accepted"], l["grn_id"]
        f = facts[l["grn_id"]]
        f["accepted"] += l["qty_accepted"]
        f["received"] += l["qty_received"]
        f["items"] += 1
    seen = set()
    for il in (PurchaseInvoiceLine.objects.filter(grn_line_id__in=left, invoice__status__in=(INV.DRAFT, INV.POSTED))
               .select_related("invoice__vendor").order_by("invoice_id", "id")):
        inv, grn_id = il.invoice, owner[il.grn_line_id]
        # a draft bill has not split its quantity into accepted and rejected yet: posting takes the accepted first
        left[il.grn_line_id] -= il.qty_accepted_part if inv.status == INV.POSTED else il.qty
        if (grn_id, inv.pk) in seen:
            continue
        seen.add((grn_id, inv.pk))
        if inv.status == INV.DRAFT:
            facts[grn_id]["drafts"].append(inv)
        else:
            facts[grn_id]["posted"].append((inv, unpaid(inv, user, memo)))
    for line_id, qty_left in left.items():
        if qty_left > 0:
            facts[owner[line_id]]["unbilled"] = True
    for note in DebitNote.objects.filter(grn_id__in=facts, status=DebitNote.Status.DRAFT).order_by("id"):
        if debit_notes.can_post(note):
            facts[note.grn_id]["returns"].append(note)
    return facts


def _grn_actions(grn, facts):
    if grn.status == G.DRAFT:
        return [check_action(grn)]
    if grn.status == G.QC_DONE:
        return [post_grn_action(grn)]
    f = facts.get(grn.pk)
    if f is None:                                    # cancelled
        return []
    found = [bill_action(grn)] if f["unbilled"] else []
    found += [post_bill_action(inv) for inv in f["drafts"]]
    found += [return_action(note) for note in f["returns"]]
    found += [pay_action(inv, due) for inv, due in f["posted"] if due]
    return found


def _ranked(actions):
    """Furthest behind first; a bill that covers two goods receipts is named once."""
    out, seen = [], set()
    for a in sorted(actions, key=lambda a: RANK[a["kind"]]):
        if (a["kind"], a["url"]) not in seen:
            seen.add((a["kind"], a["url"]))
            out.append(a)
    return out


# ---------------------------------------------------------------- the strip

def _stage(label, state, detail=""):
    return {"label": label, "detail": detail, "state": state, "pieces": None, "optional": False}


def _strip(stages, closed=False):
    """Several stages can be in progress at once; the earliest is where the purchase is. A cancelled or closed
    purchase shows the stages with nothing done."""
    first_now = None if closed else next((s for s in stages if s["state"] == "now"), None)
    for s in stages:
        if closed:
            s["state"], s["detail"] = "todo", ""
        s["current"] = s is first_now
    return stages


def _money_stages(found, all_in=True):
    """Billed and Paid for the posted goods receipts in `found` (their facts). `all_in` is False while more goods
    are still to come on the order: what came so far may be billed and paid, the purchase is not."""
    drafts = {inv.pk: inv for f in found for inv in f["drafts"]}
    posted = {inv.pk: (inv, due) for f in found for inv, due in f["posted"]}
    return _bill_stages(
        billed=sum((inv.payable for inv, _ in posted.values()), ZERO), due=sum((due for _, due in posted.values()), ZERO),
        any_posted=bool(posted), open_work=bool(drafts) or any(f["unbilled"] for f in found) or not all_in,
        to_bill=any(f["accepted"] > 0 for f in found))


def _bill_stages(*, billed, due, any_posted, open_work, to_bill):
    if any_posted and not open_work:
        state = "done"
    else:
        state = "now" if any_posted or to_bill else "todo"
    paid = "todo" if not any_posted else ("done" if state == "done" and not due else "now")
    return [_stage("Billed", state, f"{billed:.2f}" if any_posted else ""),
            _stage("Paid", paid, f"{due:.2f} unpaid" if due else "")]


def _order_stages(po):
    """Ordered, and Approved when the order needed approval (it waits for it, was approved by someone, or is a
    draft above the limit)."""
    status = po.status
    stages = [_stage("Ordered", "now" if status == PO.DRAFT else "done")]
    needed = status == PO.PENDING or bool(po.approved_by_id) or (status == PO.DRAFT and po.total > po.company.po_approval_limit)
    if needed:
        stages.append(_stage("Approved", "now" if status == PO.PENDING else ("todo" if status == PO.DRAFT else "done")))
    return stages


def _result(journey, actions, user, memo, *, complete, closed, idle=""):
    can = checker(user, memo)
    allowed = [a for a in actions if all(can(*p) for p in a["perm"])]
    return {"journey": _strip(journey, closed), "primary": allowed[0] if allowed else None, "others": allowed[1:],
            "waiting": actions[0]["label"] if actions and not allowed else "",
            "complete": complete and not actions, "closed": closed, "idle": idle}


# ---------------------------------------------------------------- purchase order

def _po_state(po, user, memo):
    """(actions, journey) of an order: its own steps, then those of its goods receipts, their bills and returns."""
    status = po.status
    stages = _order_stages(po)
    if status in (PO.DRAFT, PO.PENDING):
        rest = [_stage(name, "todo") for name in ("Received", "Checked", "Billed", "Paid")]
        return [submit_action(po) if status == PO.DRAFT else approve_action(po)], stages + rest
    grns = [g for g in po.grns.select_related("vendor").order_by("id") if g.status != G.CANCELLED]
    for g in grns:
        g.po = po
    facts = _after_receipt(grns, user, memo)
    lines = list(po.lines.all())
    got = {r["po_line_id"]: r["q"] or ZERO for r in GrnLine.objects.filter(po_line__in=lines, grn__status=G.POSTED)
           .values("po_line_id").annotate(q=Sum("qty_accepted"))}
    waiting_on = any(got.get(l.pk, ZERO) < l.qty for l in lines)
    unposted = [g for g in grns if g.status in OPEN_GRN]
    actions = []
    if status in (PO.APPROVED, PO.PARTLY) and waiting_on and not unposted:
        actions.append(receive_action(po))
    for g in grns:
        actions += _grn_actions(g, facts)

    receiving = status in (PO.APPROVED, PO.PARTLY)
    if len(lines) == 1:
        detail = f"{qty(got.get(lines[0].pk, ZERO))} of {qty(lines[0].qty)}"
    else:
        detail = f"{sum(1 for l in lines if got.get(l.pk, ZERO) >= l.qty)} of {len(lines)} items in full"
    stages.append(_stage("Received", "now" if receiving else "done", detail))
    checked = "now" if unposted or (facts and receiving) else ("done" if facts else "todo")
    stages.append(_stage("Checked", checked))
    stages += _money_stages(list(facts.values()), all_in=not receiving)
    return _ranked(actions), stages


def po_guide(po, user, perms=None):
    """{'journey': [...], 'primary': action or None, 'others': [...], 'waiting': label, 'complete': bool, 'closed': bool,
    'idle': sentence}: the shape `templates/_journey.html` takes. An action is offered only if the user's role may do it
    and may open the screen it leads to; `waiting` names the next step when it is someone else's. A short-closed order
    asks for no more goods, but what it did receive is still billed and paid; it reads as closed once nothing is left.
    `perms` is an optional dict shared between calls for the SAME user (it also remembers each supplier's open bills)."""
    memo = {} if perms is None else perms
    actions, journey = _po_state(po, user, memo)
    return _result(journey, actions, user, memo, complete=po.status == PO.RECEIVED,
                   closed=po.status == PO.CLOSED and not actions)


def po_next(po, user, perms=None):
    """The one thing this user can do next on an order, for a list row: an action or None."""
    return po_guide(po, user, perms)["primary"]


# ---------------------------------------------------------------- goods received

def grn_guide(grn, user, perms=None):
    """A goods receipt's own steps and those of its bills and returns. It starts at Received when there is no order."""
    memo = {} if perms is None else perms
    facts = _after_receipt([grn], user, memo)
    actions = _ranked(_grn_actions(grn, facts))
    stages = []
    if grn.po_id:
        stages.append(_stage("Ordered", "done"))
        if grn.po.approved_by_id:
            stages.append(_stage("Approved", "done"))
    f = facts.get(grn.pk)
    if f is None:
        unposted = grn.status in OPEN_GRN
        stages += [_stage("Received", "done" if unposted else "todo"), _stage("Checked", "now" if unposted else "todo"),
                   _stage("Billed", "todo"), _stage("Paid", "todo")]
    else:
        one = f["items"] == 1
        stages += [_stage("Received", "done", qty(f["received"]) if one else f"{f['items']} items"),
                   _stage("Checked", "done", f"{qty(f['accepted'])} accepted" if one else "")]
        stages += _money_stages([f])
    return _result(stages, actions, user, memo, complete=grn.status == G.POSTED, closed=grn.status == G.CANCELLED)


def grn_next(grn, user, perms=None):
    if grn.status == G.CANCELLED:
        return None
    return grn_guide(grn, user, perms)["primary"]


# ---------------------------------------------------------------- supplier bill

def invoice_guide(inv, user, perms=None):
    """A supplier bill's own steps: post it, then pay it. Posting a bill that includes goods rejected at the quality
    check is what lets their return be posted, so that return is offered here too, before paying. A direct bill
    (no goods receipt) starts at Billed."""
    memo = {} if perms is None else perms
    status = inv.status
    actions, due = [], unpaid(inv, user, memo)
    if status == INV.DRAFT:
        actions.append(post_bill_action(inv))
    elif status == INV.POSTED:
        if not inv.is_direct:
            notes = DebitNote.objects.filter(status=DebitNote.Status.DRAFT, kind=DebitNote.Kind.REJECTION,
                                             lines__grn_line__invoice_lines__invoice=inv).distinct().order_by("id")
            actions += [return_action(n) for n in notes if debit_notes.can_post(n)]
        if due:
            actions.append(pay_action(inv, due))
    stages = []
    if not inv.is_direct:
        orders = list(Grn.objects.filter(lines__invoice_lines__invoice=inv).values_list("po_id", "po__approved_by_id").distinct())
        if orders and all(po_id for po_id, _ in orders):
            stages.append(_stage("Ordered", "done"))
            if any(by for _, by in orders):
                stages.append(_stage("Approved", "done"))
        stages += [_stage("Received", "done"), _stage("Checked", "done")]
    posted = status == INV.POSTED
    stages += [_stage("Billed", "done" if posted else "now", f"{inv.payable:.2f}"),
               _stage("Paid", "todo" if not posted else ("now" if due else "done"), f"{due:.2f} unpaid" if due else "")]
    return _result(stages, _ranked(actions), user, memo, complete=posted, closed=status == INV.CANCELLED)


def invoice_next(inv, user, perms=None):
    if inv.status == INV.CANCELLED:
        return None
    return invoice_guide(inv, user, perms)["primary"]


# ---------------------------------------------------------------- return to supplier

WAITS_FOR_BILL = "This return waits for the supplier's bill. It can be posted once the rejected goods are on a posted bill."


def debitnote_guide(note, user, perms=None):
    """A return's own step: post it. One raised for goods rejected at the quality check waits for the supplier's bill."""
    memo = {} if perms is None else perms
    N = DebitNote.Status
    draft, posted = note.status == N.DRAFT, note.status == N.POSTED
    ready = draft and debit_notes.can_post(note)
    actions = [return_action(note)] if ready else []
    last = _stage("Return posted", "done" if posted else ("now" if ready else "todo"), f"{note.total:.2f}" if posted else "")
    if note.kind == DebitNote.Kind.REJECTION:
        stages = [_stage("Rejected", "done"), _stage("Billed by supplier", "done" if ready or posted else "now"), last]
        idle = WAITS_FOR_BILL if draft and not ready else ""
    else:
        stages, idle = [_stage("Return saved", "done"), last], ""
    return _result(stages, actions, user, memo, complete=posted, closed=note.status == N.CANCELLED, idle=idle)
