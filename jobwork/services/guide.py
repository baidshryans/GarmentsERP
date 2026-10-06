"""Where a job work challan is on its way from draft to paid, and what it needs next (read-only).

The challan page, the receipt page and the two lists ask `challan_guide`; the lot guide
(`production.services.guide`) builds its challan and receipt actions from the same functions here, so a lot and
its challan always name the same step with the same link. Callers fetch the challan through `for_user`; nothing
here widens that. Only labels, piece counts and links come back, and the fabricator's is the only party name
used (BR-15). Nothing here changes what is paid: labour is still computed by the bill service on accepted pieces.
"""
from django.db.models import Sum
from django.urls import reverse

from jobwork.models import ChallanBundle, JobWorkBill, JobWorkBillLine, JobWorkChallan, QcResult, Receipt
from jobwork.services import receipts as receipt_service

S = JobWorkChallan.Status
# what is furthest behind comes first (the lot guide ranks its own send / move / rework actions around these)
RANK = {"issue": 1, "receive": 2, "approve": 3, "qc": 4, "rework": 5, "bill": 6, "post_bill": 7}
# making a challan needs `create`; the saved challan then opens on its own page, which needs `view`
CHALLAN_NEW = (("jobwork.challan", "create"), ("jobwork.challan", "view"))


def checker(user, perms):
    """Ask each permission once. `perms` is the memo; a caller showing many rows to one user passes the same dict."""
    def can(screen, action):
        key = (screen, action)
        if key not in perms:
            perms[key] = user.has_screen_perm(screen, action)
        return perms[key]
    return can


# ---------------------------------------------------------------- one action each, shared with the lot guide
# `perm` lists every permission the user needs: to do the thing, and to open the screen the link leads to.

def issue_action(challan, lines):
    """A draft challan: issue it. `lines` are its ChallanBundle rows with their bundle loaded."""
    return {"kind": "issue", "label": f"Issue challan to {challan.party.name}",
            "hint": "The challan is a draft. Issue it to hand the bundles over.",
            "url": reverse("challan_detail", args=[challan.pk]),
            "perm": (("jobwork.challan", "edit"), ("jobwork.challan", "view")),
            "pieces": sum(l.bundle.qty for l in lines)}


def receive_action(challan, lines, counted):
    """An issued challan with pieces still out. `counted` holds the lines already on an over-receipt that waits for
    approval: nothing has moved, but it is the owner's approval they wait for, not a recount. None if nothing is out."""
    out = sum(l.bundle.qty for l in lines if not (l.qty_received or l.qty_shortage) and l.pk not in counted)
    if not out:
        return None
    return {"kind": "receive", "label": f"Receive from {challan.party.name}",
            "hint": f"Count the pieces that came back from {challan.step.process.name}.",
            "url": reverse("receipt_new", args=[challan.pk]),
            "perm": (("jobwork.receipt", "create"), ("jobwork.receipt", "view")), "pieces": out}


def receipt_action(receipt):
    """A receipt that waits for the owner's approval or for QC. None once every line is checked."""
    url = reverse("receipt_detail", args=[receipt.pk])
    if receipt.status == Receipt.Status.PENDING_APPROVAL:
        return {"kind": "approve", "label": "Approve over-receipt",
                "hint": "More pieces were counted than were sent. The owner must approve.",
                "url": url, "perm": (("jobwork.receipt", "approve"), ("jobwork.receipt", "view")), "pieces": 0}
    if receipt.status == Receipt.Status.RECEIVED:
        return {"kind": "qc", "label": "Check received pieces",
                "hint": f"Accept, reject or send back what {receipt.challan.party.name} returned.",
                "url": url, "perm": (("jobwork.qc", "create"), ("jobwork.receipt", "view")), "pieces": 0}
    return None


def rework_action(lot_id, step_id, pieces):
    """Bundles QC sent back, waiting at `step_id`: the rework challan is for that step (the service refuses any other)."""
    at = f"&step={step_id}" if step_id else ""
    return {"kind": "rework", "label": "Send back for rework", "hint": "QC sent these pieces back to the fabricator.",
            "url": reverse("challan_new") + f"?lot={lot_id}&kind=rework{at}", "perm": CHALLAN_NEW, "pieces": pieces}


def bill_action(challan, pieces):
    """Accepted pieces of this challan that no labour bill has taken yet (the bill screen lists them by fabricator).
    `factory` and `challan` only let the bill screen say so when another factory is active; they choose nothing."""
    return {"kind": "bill", "label": f"Make labour bill for {challan.party.name}",
            "hint": "These pieces are checked and payable, and no labour bill has them yet.",
            "url": reverse("bill_new") + f"?party={challan.party_id}&factory={challan.factory_id}&challan={challan.pk}",
            "perm": (("jobwork.bill", "create"), ("jobwork.bill", "view")), "pieces": pieces}


def post_bill_action(bill_id, pieces):
    """Accepted pieces sitting on a draft labour bill: nothing is owed until it is posted (posting needs `edit`)."""
    return {"kind": "post_bill", "label": "Post labour bill",
            "hint": "These pieces are on a draft labour bill. Check it, then post it.",
            "url": reverse("bill_detail", args=[bill_id]),
            "perm": (("jobwork.bill", "edit"), ("jobwork.bill", "view")), "pieces": pieces}


def unbilled_pieces(challan):
    """Payable pieces of the challan not yet on a labour bill: the same test `bills.unbilled_qc` applies."""
    return QcResult.objects.filter(line__challan_bundle__challan=challan, bill_line__isnull=True, pay_qty__gt=0
                                   ).aggregate(n=Sum("pay_qty"))["n"] or 0


# ---------------------------------------------------------------- one challan

def _actions(challan, lines, receipts):
    if challan.status in (S.CANCELLED, S.BILLED):
        return []          # a challan is marked billed only once everything is in, checked and on a posted bill
    if challan.status == S.DRAFT:
        return [issue_action(challan, lines)]
    found = []
    if challan.is_open:
        pending = any(r.status == Receipt.Status.PENDING_APPROVAL for r in receipts)
        counted = receipt_service.awaiting_approval(challan) if pending else set()
        found.append(receive_action(challan, lines, counted))
    for r in sorted(receipts, key=lambda r: r.pk):
        r.challan = challan                      # already loaded: the hint names its fabricator
        found.append(receipt_action(r))
    back = [l.bundle for l in lines if _waits_for_rework(l.bundle) and l.bundle.current_step_id == challan.step_id]
    if back:
        # a bundle already on a draft rework challan asks for that draft to be issued, not for another challan
        drafted = set(ChallanBundle.objects.filter(bundle__in=back, challan__status=S.DRAFT).values_list("bundle_id", flat=True))
        pieces = sum(b.rework_qty or b.qty for b in back if b.pk not in drafted)
        if pieces:
            found.append(rework_action(challan.lot_id, challan.step_id, pieces))
    if any(l.qty_accepted for l in lines) or (challan.pay_basis == "received" and any(l.qty_received for l in lines)):
        pieces = unbilled_pieces(challan)
        if pieces:
            found.append(bill_action(challan, pieces))
        drafts = (JobWorkBillLine.objects.filter(challan=challan, bill__status=JobWorkBill.Status.DRAFT)
                  .values("bill_id").annotate(n=Sum("qty")).order_by("bill_id"))
        found.extend(post_bill_action(d["bill_id"], d["n"]) for d in drafts)
    return sorted((a for a in found if a), key=lambda a: RANK[a["kind"]])


def _waits_for_rework(bundle):
    return bundle.is_live and (bundle.status == bundle.Status.REWORK or bool(bundle.rework_qty))


def _finished(challan, lines, receipts, actions):
    """Nothing more will happen on this challan: billed or closed, or everything is back and checked with nothing
    left to send back, bill or post (all rejected, say, or reworked and paid on the rework challan)."""
    if actions:
        return False
    if challan.status in (S.BILLED, S.CLOSED):
        return True
    return (challan.status == S.RECEIVED and all(r.status == Receipt.Status.QC_DONE for r in receipts)
            and not any(_waits_for_rework(l.bundle) for l in lines))


def _journey(challan, lines, receipts, finished):
    def stage(label, state, pieces=None, detail=""):
        return {"label": label, "detail": detail, "state": state, "pieces": pieces or None, "optional": False}

    status = challan.status
    if status in (S.DRAFT, S.CANCELLED):
        first = "now" if status == S.DRAFT else "todo"
        stages = [stage("Draft", first)] + [stage(name, "todo") for name in ("Issued", "Received", "Checked", "Billed")]
    else:
        came = [l for l in lines if l.qty_received or l.qty_shortage]
        all_in, any_in = len(came) == len(lines), bool(came) or bool(receipts)
        checked = all_in and all(r.status == Receipt.Status.QC_DONE for r in receipts)
        accepted = sum(l.qty_accepted for l in lines)
        # what the fabricator is paid for: the accepted pieces, or every piece that came back
        payable = sum(l.qty_received for l in lines) if challan.pay_basis == "received" else accepted
        billed = status in (S.BILLED, S.CLOSED) or (finished and payable)   # every payable piece is paid
        stages = [
            stage("Draft", "done"),
            stage("Issued", "done" if all_in else "now", sum(l.qty_issued for l in lines)),
            stage("Received", "done" if all_in else ("now" if any_in else "todo"), sum(l.qty_received for l in lines)),
            stage("Checked", "done" if checked else ("now" if any_in else "todo"), accepted, "accepted" if accepted else ""),
            stage("Billed", "done" if billed else ("now" if payable and checked else ("now" if accepted else "todo"))),
        ]
    # several stages can be in progress at once; the earliest is where the challan is
    first_now = next((s for s in stages if s["state"] == "now"), None)
    for s in stages:
        s["current"] = s is first_now
    return stages


def challan_guide(challan, user, perms=None):
    """{'journey': [...], 'primary': action or None, 'others': [...], 'waiting': label, 'complete': bool, 'closed': bool},
    the same shape as the lot guide. An action is offered only if the user's role may do it and may open the screen
    it leads to; `waiting` names the next step when it is someone else's. `complete` is a challan with nothing left
    to do (see `_finished`); `closed` is a cancelled one. `perms` is an optional dict shared between calls for the SAME user."""
    can = checker(user, {} if perms is None else perms)
    lines = list(challan.bundles.select_related("bundle"))
    receipts = [] if challan.status in (S.DRAFT, S.CANCELLED) else list(challan.receipts.all())
    actions = _actions(challan, lines, receipts)
    allowed = [a for a in actions if all(can(*p) for p in a["perm"])]
    finished = _finished(challan, lines, receipts, actions)
    return {
        "journey": _journey(challan, lines, receipts, finished),
        "primary": allowed[0] if allowed else None, "others": allowed[1:],
        "waiting": actions[0]["label"] if actions and not allowed else "",
        "complete": finished, "closed": challan.status == S.CANCELLED,
    }


def challan_next(challan, user, perms=None):
    """The one thing this user can do next on a challan, for a list row: an action or None."""
    if challan.status in (S.CANCELLED, S.BILLED):
        return None                              # nothing to look up: see `_actions`
    return challan_guide(challan, user, perms)["primary"]
