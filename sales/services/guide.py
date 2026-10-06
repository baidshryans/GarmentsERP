"""Where a sale is on its way from order to paid, and what it needs next (read-only).

One journey, entered at whichever document exists: Ordered, Confirmed, Packed, Billed, Paid. A bill made by quick
billing has no order and starts at Billed. The sale order, packing list, bill and return pages and the three lists ask
the functions at the bottom; every action is built by one function here, so two pages that speak of the same document
name the same step with the same link. Callers fetch the document through `for_user`; everything reached from it (an
order's packing lists, their bills and returns) is in the same factory, so nothing here widens that. Nothing here
writes, and nothing here changes what is owed: the amount still to receive is read from the ledger's bill-wise records,
the same figure the bill page shows as Outstanding. A posted return is set against its bill by its own voucher, so that
figure already has it.

Customer names appear in what this module returns. It is for sales screens only (BR-15).
"""
from decimal import Decimal

from django.db.models import Sum
from django.urls import reverse

from inventory.models import StockBalance
from production.models import ProductionOrder
from ledger.selectors import outstanding_bills
from ledger.settlement import settle_url
from sales.models import CartonLine, PackingList, SaleCreditNote, SaleInvoice, SaleInvoiceLine, SaleOrder
from sales.services.packing import NOT_PACKED_FROM

ZERO = Decimal("0")
SO = SaleOrder.Status
P = PackingList.Status
INV = SaleInvoice.Status
CN = SaleCreditNote.Status
OPEN_ORDER = (SO.CONFIRMED, SO.PARTLY)
# what is furthest behind comes first
RANK = {"confirm": 1, "pack": 2, "production": 2, "finish_packing": 3, "bill": 4, "post_bill": 5, "post_return": 6,
        "receive": 7}
FROM_PRODUCTION = "goods from production"
NO_STOCK = "None of these pieces is in finished stock yet; the list can be saved but not finished."
LIST_GONE = "Its packing list was cancelled. Discard this draft bill."
BILL_GONE = "Its bill was cancelled. Discard this draft return."
# a production order that will still put pieces into finished stock
MAKING = (ProductionOrder.Status.DRAFT, ProductionOrder.Status.RELEASED, ProductionOrder.Status.IN_PRODUCTION,
          ProductionOrder.Status.PARTLY)


def checker(user, perms):
    """Ask each permission once. `perms` is the memo; a caller showing many rows to one user passes the same dict."""
    def can(screen, action):
        key = (screen, action)
        if key not in perms:
            perms[key] = user.has_screen_perm(screen, action)
        return perms[key]
    return can


def pcs(value):
    return f"{int(value)}"


# ---------------------------------------------------------------- one action each
# `perm` lists every permission the user needs: to do the thing, and to open every screen the step leads to.
# `pieces` is always 0: the shared strip reads it, and the hints here say the pieces themselves.

def _action(kind, label, hint, url, *perm):
    return {"kind": kind, "label": label, "hint": hint, "url": url, "perm": perm, "pieces": 0}


def confirm_action(order):
    hint = "The order is a draft. Confirming gives it a number"
    hint += " and raises the production requirement." if order.order_type == SaleOrder.Type.MTO else "."
    return _action("confirm", "Confirm order", hint, reverse("saleorder_detail", args=[order.pk]),
                   ("sales.order", "edit"), ("sales.order", "view"))


def pack_action(order, left, in_stock=True):
    """`in_stock` is False when none of the pieces still to pack can be had at any place goods are packed from: the
    packing list can be drafted, and the hint says it cannot be finished yet."""
    hint = f"{pcs(left)} pieces of {order.number} are still to be packed."
    return _action("pack", "Pack goods", hint if in_stock else f"{hint} {NO_STOCK}",
                   reverse("packing_new", args=[order.pk]), ("sales.packing", "create"), ("sales.packing", "view"))


def production_wait(order):
    """Not something anyone can press: the pieces of a made-to-order order are not in finished stock yet. It has no
    link, so it is never offered; it is what the sale is said to be waiting for."""
    return _action("production", FROM_PRODUCTION, "", None)


def finish_packing_action(packing):
    return _action("finish_packing", "Finish packing",
                   "The packing list is a draft. Finishing checks the pieces are in stock and gives it a number.",
                   reverse("packing_detail", args=[packing.pk]), ("sales.packing", "edit"), ("sales.packing", "view"))


def bill_action(packing):
    """The bill is made on the packing list's page, which then opens the draft bill: all three are needed."""
    return _action("bill", "Make bill", f"{packing.number} is packed and has no bill yet.",
                   reverse("packing_detail", args=[packing.pk]),
                   ("sales.invoice", "create"), ("sales.packing", "view"), ("sales.invoice", "view"))


def post_bill_action(inv):
    return _action("post_bill", "Post bill", "The bill is a draft. Check the GST and the total, then post it.",
                   reverse("saleinvoice_detail", args=[inv.pk]), ("sales.invoice", "edit"), ("sales.invoice", "view"))


def receive_action(inv, owed, credit=ZERO):
    """A posted bill with an amount still to receive: opens Money received with the customer, that amount and the
    bill reference filled in. Nothing is posted until the user posts that voucher. `credit` is what the customer
    already has on account (see `on_account`): the amount and the link stay the bill's, the hint mentions it."""
    hint = f"{owed:.2f} is still to be received on {inv.number}."
    if credit:
        hint += f" This customer also has {credit:.2f} on account from advances or returns."
    return _action("receive", f"Receive money from {inv.customer.name}", hint,
                   settle_url("receive", inv.customer.customer_ledger_id, owed, inv.number, f"Received against {inv.number}"),
                   ("ledger.voucher", "create"), ("ledger.voucher", "view"))


def post_return_action(note):
    return _action("post_return", "Post return",
                   "The return is a draft. Posting brings the pieces back into stock and credits the customer.",
                   reverse("salecn_detail", args=[note.pk]), ("sales.creditnote", "create"), ("sales.creditnote", "view"))


# ---------------------------------------------------------------- what the ledger and the documents say

def due(inv, user, memo):
    """What the customer still owes on a posted bill, from the ledger's bill-wise records: the figure the bill page
    shows as Outstanding. Receipts and posted returns set against the bill are already taken off it. Each customer's
    open bills are read once per memo."""
    if inv.status != INV.POSTED or not inv.customer.customer_ledger_id or not inv.number:
        return ZERO
    return max(_position(inv.customer, user, memo)["bills"].get(inv.number, ZERO), ZERO)


def _position(customer, user, memo):
    """The customer's bill-wise position in the factories the user may see, read once per memo: the same records
    the voucher screen shows beside a party (`ledger.selectors.ledger_position`)."""
    key = ("open bills", customer.customer_ledger_id)
    if key not in memo:
        memo[key] = outstanding_bills(customer.customer_ledger, user=user)
    return memo[key]


def on_account(customer, user, memo):
    """Money of the customer's that is set against no bill: advances received and on-account credits (a return posted
    after its bill was paid leaves one). Zero when there is none, or when the account is the other way round."""
    if not customer.customer_ledger_id:
        return ZERO
    position = _position(customer, user, memo)
    return max(-(position["advance"] + position["on_account"]), ZERO)


def held(inv, user, perms=None):
    """What sits on the customer's account while nothing is left to receive on this posted bill: the bill and return
    pages say it is there to be adjusted or refunded. Zero otherwise. No action comes of it."""
    memo = {} if perms is None else perms
    if inv.status != INV.POSTED or due(inv, user, memo):
        return ZERO
    return on_account(inv.customer, user, memo)


def _draft_returns(invoices):
    """{bill id: [its draft returns]} for the posted bills among `invoices`."""
    ids = [i.pk for i in invoices if i.status == INV.POSTED]
    found = {}
    if ids:
        for note in SaleCreditNote.objects.filter(invoice_id__in=ids, status=CN.DRAFT).order_by("id"):
            found.setdefault(note.invoice_id, []).append(note)
    return found


def stranded(inv):
    """A draft bill made from a packing list that is no longer a finished one (it was cancelled under the bill, which
    the packing service now refuses). Posting it would always fail, so it is never offered; the page says to discard it."""
    return inv.status == INV.DRAFT and inv.packing_id is not None and inv.packing.status != P.PACKED


def _bill_actions(inv, notes, user, memo):
    if inv.status == INV.DRAFT:
        return [] if stranded(inv) else [post_bill_action(inv)]
    if inv.status != INV.POSTED:
        return []
    found = [post_return_action(n) for n in notes.get(inv.pk, [])]
    owed = due(inv, user, memo)
    if owed:
        found.append(receive_action(inv, owed, on_account(inv.customer, user, memo)))
    return found


def _packing_actions(packing, inv, notes, user, memo):
    """`inv` is the packing list's bill that is not cancelled, if it has one."""
    if packing.status == P.DRAFT:
        return [finish_packing_action(packing)]
    if packing.status == P.CANCELLED:
        return []
    if inv is not None:
        return _bill_actions(inv, notes, user, memo)
    return [bill_action(packing)] if packing.status == P.PACKED else []


def _bill_of(packing):
    inv = packing.invoices.exclude(status=INV.CANCELLED).order_by("id").first()
    if inv is not None:
        inv.packing, inv.order, inv.customer = packing, packing.order, packing.order.customer
    return inv


def _in_stock(order, lines):
    """Is any piece still to pack to be had at a place of the factory goods are packed from? What a finished packing
    list that is not billed yet already holds there does not count, exactly as finishing a list judges it
    (`packing.available_at`). While this is False a packing list could be drafted but never finished."""
    skus = [l.sku_id for l in lines if min(l.to_pack, l.balance) > 0]
    have = {(b["location_id"], b["sku_id"]): b["qty"] for b in (
        StockBalance.objects.filter(factory_id=order.factory_id, sku_id__in=skus, qty__gt=0)
        .exclude(location__loc_type__in=NOT_PACKED_FROM).values("location_id", "sku_id", "qty"))}
    if not have:
        return False
    held = CartonLine.objects.filter(carton__packing__factory_id=order.factory_id, carton__packing__status=P.PACKED, sku_id__in=skus)
    for h in held.values("carton__packing__location_id", "sku_id").annotate(q=Sum("qty")):
        key = (h["carton__packing__location_id"], h["sku_id"])
        if key in have:
            have[key] -= h["q"]
    return any(q > 0 for q in have.values())


def _awaits_production(order):
    """A made-to-order order is packed from what production puts into finished stock. It waits for production only
    while its production order can still deliver; once that is completed or closed nothing more is coming, and the
    seller packs what there is or closes the balance."""
    if order.order_type != SaleOrder.Type.MTO or order.production_order_id is None:
        return False
    return order.production_order.status in MAKING


def _ranked(actions):
    """Furthest behind first; one document's step is named once."""
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
    """Several stages can be in progress at once; the earliest is where the sale is. A cancelled or closed sale shows
    the stages with nothing done."""
    first_now = None if closed else next((s for s in stages if s["state"] == "now"), None)
    for s in stages:
        if closed:
            s["state"], s["detail"] = "todo", ""
        s["current"] = s is first_now
    return stages


def _money_stages(*, billed, owed, any_posted, unbilled, all_packed):
    """Billed and Paid. `unbilled`: a finished packing list or a draft bill still waits. `all_packed` is False while
    more of the order is still to be packed: what went so far may be billed and paid, the sale is not."""
    if not (any_posted or unbilled):
        state = "todo"
    else:
        state = "done" if all_packed and not unbilled else "now"
    paid = "todo" if not any_posted else ("done" if state == "done" and not owed else "now")
    return [_stage("Billed", state, f"{billed:.2f}" if any_posted else ""),
            _stage("Paid", paid, f"{owed:.2f} to receive" if owed else "")]


def _result(journey, actions, user, memo, *, complete, closed, pack=None, idle=""):
    can = checker(user, memo)

    def may(a):
        return a["url"] is not None and all(can(*p) for p in a["perm"])

    allowed = [a for a in actions if may(a)]
    behind = actions[0] if actions and not allowed else None
    return {"journey": _strip(journey, closed), "primary": allowed[0] if allowed else None, "others": allowed[1:],
            "waiting": behind["label"] if behind else "", "blocked": bool(behind) and behind["kind"] == "production",
            "complete": complete and not actions and not idle, "closed": closed, "idle": idle,
            "pack": pack if pack is not None and may(pack) else None}


# ---------------------------------------------------------------- sale order

def _order_state(order, user, memo):
    """(actions, journey, pack) of an order: its own steps, then those of its packing lists, their bills and returns.
    `pack` is the Pack goods step whenever pieces of an open order are still to be packed, even while an earlier
    packing list is a draft or the goods are awaited from production: the guide then points elsewhere first, but a
    second packing list can be started before the first is finished, so the order page keeps a plain button for it."""
    status = order.status
    lines = list(order.lines.all())
    ordered = sum((l.qty for l in lines), ZERO)
    stages = [_stage("Ordered", "done", f"{pcs(ordered)} pieces")]
    if status == SO.DRAFT:
        rest = [_stage(name, "todo") for name in ("Packed", "Billed", "Paid")]
        return [confirm_action(order)], stages + [_stage("Confirmed", "now")] + rest, None
    stages.append(_stage("Confirmed", "done"))
    # `.all()` and not a new query: a list page prefetches the lines, packing lists and bills of its rows
    every_list = {p.pk: p for p in sorted(order.packing_lists.all(), key=lambda p: p.pk)}
    packings = [p for p in every_list.values() if p.status != P.CANCELLED]
    invoices = []
    for i in sorted(order.invoices.all(), key=lambda i: i.pk):
        i.order, i.customer = order, order.customer
        if i.packing_id:
            i.packing = every_list[i.packing_id]
        # a draft bill left behind by a cancelled packing list is nothing of this sale any more (see `stranded`)
        if i.status != INV.CANCELLED and not stranded(i):
            invoices.append(i)
    for p in packings:
        p.order = order
    notes = _draft_returns(invoices)
    bill_of = {i.packing_id: i for i in invoices if i.packing_id}
    drafts = [p for p in packings if p.status == P.DRAFT]
    left = sum((max(min(l.to_pack, l.balance), ZERO) for l in lines), ZERO) if status in OPEN_ORDER else ZERO

    pack = pack_action(order, left) if left else None
    actions = []
    if pack and not drafts:
        if _in_stock(order, lines):
            actions.append(pack)
        elif _awaits_production(order):
            actions.append(production_wait(order))
        else:
            pack = pack_action(order, left, in_stock=False)
            actions.append(pack)
    for p in packings:
        actions += _packing_actions(p, bill_of.get(p.pk), notes, user, memo)
    for i in invoices:
        if not i.packing_id:                      # billed against the order without a packing list
            actions += _bill_actions(i, notes, user, memo)

    finished = [p.pk for p in packings if p.status in (P.PACKED, P.INVOICED)]
    packed = ZERO
    if finished:
        packed += CartonLine.objects.filter(carton__packing_id__in=finished).aggregate(q=Sum("qty"))["q"] or ZERO
    loose = [i.pk for i in invoices if not i.packing_id and i.status == INV.POSTED]
    if loose:
        packed += SaleInvoiceLine.objects.filter(invoice_id__in=loose).aggregate(q=Sum("qty"))["q"] or ZERO
    packed_state = "now" if left or drafts else ("done" if packed else "todo")
    stages.append(_stage("Packed", packed_state, f"{pcs(packed)} of {pcs(ordered)}"))
    posted = [i for i in invoices if i.status == INV.POSTED]
    stages += _money_stages(
        billed=sum((i.total for i in posted), ZERO), owed=sum((due(i, user, memo) for i in posted), ZERO),
        any_posted=bool(posted), all_packed=packed_state == "done",
        unbilled=any(i.status == INV.DRAFT for i in invoices) or any(p.status == P.PACKED and p.pk not in bill_of for p in packings))
    return _ranked(actions), stages, pack


def order_guide(order, user, perms=None):
    """{'journey': [...], 'primary': action or None, 'others': [...], 'waiting': label, 'blocked': bool, 'complete': bool,
    'closed': bool, 'idle': '', 'pack': action or None}: the shape `templates/_journey.html` takes, plus `pack` for
    the order page's header button (see `_order_state`) and `blocked`, true when what the sale waits for is goods
    from production and not somebody's step. An action is offered only if the user's role may do it and may open the
    screens it leads to; `waiting` names the next step when it is not this user's to take. A short-closed order asks
    for no more packing, but what it did send is still billed and paid; it reads as closed once nothing is left.
    `perms` is an optional dict shared between calls for the SAME user (it also remembers each customer's open bills)."""
    memo = {} if perms is None else perms
    actions, journey, pack = _order_state(order, user, memo)
    return _result(journey, actions, user, memo, complete=order.status == SO.DISPATCHED,
                   closed=order.status in (SO.CANCELLED, SO.CLOSED) and not actions, pack=pack)


def order_next(order, user, perms=None):
    """The one thing this user can do next on an order, for a list row: an action or None."""
    return order_guide(order, user, perms)["primary"]


# ---------------------------------------------------------------- packing list

def packing_guide(packing, user, perms=None):
    """A packing list's own steps and those of its bill and that bill's returns."""
    memo = {} if perms is None else perms
    inv = _bill_of(packing) if packing.status in (P.PACKED, P.INVOICED) else None
    actions = _ranked(_packing_actions(packing, inv, _draft_returns([inv] if inv else []), user, memo))
    pieces = CartonLine.objects.filter(carton__packing=packing).aggregate(q=Sum("qty"))["q"] or ZERO
    draft, posted = packing.status == P.DRAFT, inv is not None and inv.status == INV.POSTED
    owed = due(inv, user, memo) if posted else ZERO
    stages = [_stage("Ordered", "done"), _stage("Confirmed", "done"),
              _stage("Packed", "now" if draft else "done", f"{pcs(pieces)} pieces")]
    stages += _money_stages(billed=inv.total if posted else ZERO, owed=owed, any_posted=posted, all_packed=True,
                            unbilled=not draft and not posted)
    return _result(stages, actions, user, memo, complete=posted, closed=packing.status == P.CANCELLED)


def packing_next(packing, user, perms=None):
    if packing.status == P.CANCELLED:
        return None
    return packing_guide(packing, user, perms)["primary"]


# ---------------------------------------------------------------- bill

def invoice_guide(inv, user, perms=None):
    """A bill's own steps: post it, then receive the money; and its draft returns. A bill made by quick billing has
    no order and starts at Billed."""
    memo = {} if perms is None else perms
    posted = inv.status == INV.POSTED
    actions = _ranked(_bill_actions(inv, _draft_returns([inv]), user, memo))
    lost = stranded(inv)
    owed = due(inv, user, memo)
    stages = []
    if inv.order_id:
        stages += [_stage("Ordered", "done"), _stage("Confirmed", "done")]
        if inv.packing_id:
            stages.append(_stage("Packed", "done"))
    stages += [_stage("Billed", "done" if posted else "now", f"{inv.total:.2f}"),
               _stage("Paid", "todo" if not posted else ("now" if owed else "done"), f"{owed:.2f} to receive" if owed else "")]
    return _result(stages, actions, user, memo, complete=posted, closed=inv.status == INV.CANCELLED,
                   idle=LIST_GONE if lost else "")


def invoice_next(inv, user, perms=None):
    if inv.status == INV.CANCELLED:
        return None
    return invoice_guide(inv, user, perms)["primary"]


# ---------------------------------------------------------------- return from customer

def creditnote_guide(note, user, perms=None):
    """A return's own step: post it. A draft whose bill was cancelled since can never be posted; it is not offered
    and the page says to discard it."""
    memo = {} if perms is None else perms
    draft, posted = note.status == CN.DRAFT, note.status == CN.POSTED
    lost = draft and note.invoice.status != INV.POSTED
    actions = [post_return_action(note)] if draft and not lost else []
    stages = [_stage("Return saved", "done"),
              _stage("Return posted", "done" if posted else ("todo" if lost else "now"), f"{note.total:.2f}" if posted else "")]
    return _result(stages, actions, user, memo, complete=posted, closed=note.status == CN.CANCELLED,
                   idle=BILL_GONE if lost else "")
