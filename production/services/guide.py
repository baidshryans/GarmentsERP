"""Where a lot is on its way from order to finished goods, and what it needs next (read-only).

The lot page, the order screens and Home all ask here, so every screen names the same next step. Callers fetch the
lot through `for_user`; nothing here widens that. Only labels, piece counts and links come back: a fabricator's name
is the only party name used (BR-15)."""
from django.urls import reverse

from core.models import Location
from jobwork.models import ChallanBundle, JobWorkChallan, Receipt, ReceiptLine
from production.models import Bundle, LotStep

B = Bundle.Status
AT_A_STAGE = (B.AT_STAGE, B.DONE, B.RECEIVED, B.REWORK)
# Within one stage, what is furthest behind comes first. An optional step sorts behind everything else aimed at the
# mandatory step it comes before, so it is never the main button while that step is open to the same user.
RANK = {"send": 0, "move": 0, "issue": 1, "receive": 2, "approve": 3, "qc": 4, "rework": 5, "optional": 6}
STATE = {LotStep.Status.DONE: "done", LotStep.Status.IN_PROGRESS: "now", LotStep.Status.PENDING: "todo"}


def _packing_step(steps):
    return next((s for s in reversed(steps) if s.process.kind == "packing"), None)


def pack_ready(bundle, steps):
    """A bundle can be packed once it is at an in-house packing step, or has come back ready from one.
    `steps` is the lot's route in order, without the skipped ones."""
    ps = _packing_step(steps)
    if ps is None:
        return False
    return (bundle.status == B.AT_STAGE and bundle.current_step_id == ps.pk and ps.assignment == LotStep.Assignment.IN_HOUSE) or \
           (bundle.status == B.READY and bundle.completed_seq >= ps.sequence)


def _journey(lot, steps, bundles, cuts, issued):
    cut_pieces = sum(b.original_qty for b in bundles)
    bundled = bool(cuts) and all(c.bundled for c in cuts)
    at = {}
    for b in bundles:
        # a ready bundle keeps the step it finished as current_step, but it is no longer sitting there
        if b.status in AT_A_STAGE and b.current_step_id:
            at[b.current_step_id] = at.get(b.current_step_id, 0) + b.qty
    stages = [
        {"label": "Order", "detail": "", "state": "done", "pieces": None, "optional": False},
        {"label": "Fabric", "detail": "", "state": "done" if issued or cuts else "now", "pieces": None, "optional": False},
        {"label": "Cut", "detail": "", "state": "done" if bundled else ("now" if issued or cuts else "todo"),
         "pieces": cut_pieces or None, "optional": False},
    ]
    for s in steps:
        if s.process.kind == "cutting":
            continue
        outside = s.assignment == LotStep.Assignment.SUBCONTRACT and s.party_id
        stages.append({"label": s.process.name, "detail": s.party.name if outside else "",
                       "state": STATE[s.status], "pieces": at.get(s.pk) or None, "optional": not s.is_mandatory})
    packed = sum(b.qty for b in bundles if b.status in (B.PACKED, B.DISPATCHED))
    done = lot.status == lot.Status.COMPLETED
    stages.append({"label": "Finished goods", "detail": "", "state": "done" if done else ("now" if packed else "todo"),
                   "pieces": packed or None, "optional": False})
    return stages


def _actions(lot, steps, bundles, cuts, issued):
    found = {}

    def add(key, seq, label, hint, url, perm, pieces=0, tie=0):
        a = found.setdefault(key, {"label": label, "hint": hint, "url": url, "perm": perm, "pieces": 0,
                                   "order": (seq, RANK.get(key[0], 0), tie)})
        a["pieces"] += pieces

    def onward(step, pieces, target=None):
        """Send or move bundles on to `step`. With `target`, `step` is an optional one on the way to that mandatory
        step (or, with nothing mandatory left, to itself): it is offered beside the main action, never ahead of it."""
        extra = "" if target is None else " (optional)"
        key = () if target is None else ("optional",)
        seq, tie = (step.sequence, 0) if target is None else (target.sequence, step.sequence)
        if step.assignment == LotStep.Assignment.SUBCONTRACT:
            who = step.party.name if step.party_id else "a fabricator"
            add(key + ("send", step.pk), seq, f"Send to {who} for {step.process.name}{extra}",
                "Make a challan and hand the bundles over.",
                reverse("challan_new") + f"?lot={lot.pk}&step={step.pk}", ("jobwork.challan", "create"), pieces, tie)
        else:
            add(key + ("move", step.pk), seq, f"Move to {step.process.name}{extra}", "Scan or tick the bundles that are ready.",
                reverse("move_bundles") + f"?lot={lot.pk}&back=1", ("production.move", "create"), pieces, tie)

    cutting_perm = ("production.cutting", "create")
    if not cuts and not issued:
        add(("fabric",), -3, "Issue fabric", "Send rolls from the store to the cutting floor.",
            reverse("lot_fabric", args=[lot.pk]), cutting_perm)
    elif not cuts:
        add(("cut",), -2, "Record cutting", "Enter the pieces cut in each size.", reverse("lot_cutting", args=[lot.pk]), cutting_perm)
    elif any(not c.bundled for c in cuts):
        add(("bundle",), -1, "Make bundles", "A lay is cut but not bundled yet.", reverse("lot_cutting", args=[lot.pk]), cutting_perm)

    # counted back above what was issued: nothing has moved, but it is the owner's approval they wait for, not a recount
    counted = set(ReceiptLine.objects.filter(receipt__challan__lot=lot, receipt__status=Receipt.Status.PENDING_APPROVAL)
                  .values_list("challan_bundle_id", flat=True))
    open_status = (JobWorkChallan.Status.DRAFT, JobWorkChallan.Status.ISSUED, JobWorkChallan.Status.PARTLY)
    on_draft = set()
    for ch in lot.challans.filter(status__in=open_status).select_related("party", "step__process"):
        lines = list(ChallanBundle.objects.filter(challan=ch).select_related("bundle"))
        if ch.status == JobWorkChallan.Status.DRAFT:
            on_draft.update(l.bundle_id for l in lines)
            add(("issue", ch.pk), ch.step.sequence, f"Issue challan to {ch.party.name}",
                "The challan is a draft. Issue it to hand the bundles over.",
                reverse("challan_detail", args=[ch.pk]), ("jobwork.challan", "edit"), sum(l.bundle.qty for l in lines))
        else:
            out = sum(l.bundle.qty for l in lines if not (l.qty_received or l.qty_shortage) and l.pk not in counted)
            if out:
                add(("receive", ch.pk), ch.step.sequence, f"Receive from {ch.party.name}",
                    f"Count the pieces that came back from {ch.step.process.name}.",
                    reverse("receipt_new", args=[ch.pk]), ("jobwork.receipt", "create"), out)

    waiting = (Receipt.Status.PENDING_APPROVAL, Receipt.Status.RECEIVED)
    for r in Receipt.objects.filter(challan__lot=lot, status__in=waiting).select_related("challan__party", "challan__step"):
        url, seq = reverse("receipt_detail", args=[r.pk]), r.challan.step.sequence
        if r.status == Receipt.Status.PENDING_APPROVAL:
            add(("approve", r.pk), seq, "Approve over-receipt", "More pieces were counted than were sent. The owner must approve.",
                url, ("jobwork.receipt", "approve"))
        else:
            add(("qc", r.pk), seq, "Check received pieces", f"Accept, reject or send back what {r.challan.party.name} returned.",
                url, ("jobwork.qc", "create"))

    for b in bundles:
        if not b.is_live or b.pk in on_draft:
            continue
        here = b.current_step.sequence if b.current_step_id else b.completed_seq
        if b.status == B.REWORK or b.rework_qty:
            add(("rework",), here, "Send back for rework", "QC sent these pieces back to the fabricator.",
                reverse("challan_new") + f"?lot={lot.pk}&kind=rework", ("jobwork.challan", "create"), b.rework_qty or b.qty)
            continue
        if b.status not in (B.CUT, B.READY, B.AT_STAGE):
            continue
        if b.status == B.AT_STAGE and b.location.loc_type == Location.Type.FABRICATOR:
            continue                                         # out on a challan: the challan's own line covers it
        if pack_ready(b, steps):
            add(("pack",), 10_000, "Pack into finished goods", "These bundles have reached packing.",
                reverse("lot_detail", args=[lot.pk]) + "#pack", ("production.move", "create"), b.qty)
            continue
        done = here if b.status == B.AT_STAGE else b.completed_seq
        later = [s for s in steps if s.sequence > done]
        nxt = next((s for s in later if s.is_mandatory), None)   # optional steps may be jumped over (see check_entry)
        if nxt is not None:
            onward(nxt, b.qty)
        for s in later:
            if nxt is not None and s.sequence > nxt.sequence:
                break
            if not s.is_mandatory:
                onward(s, b.qty, target=nxt or s)
    return sorted(found.values(), key=lambda a: a["order"])


def lot_guide(lot, user):
    """{'journey': [...], 'primary': action or None, 'others': [...], 'waiting': label, 'complete': bool, 'closed': bool}.
    An action is offered only if the user's role may do it; `waiting` names the next step when it is someone else's."""
    steps = [s for s in lot.steps.select_related("process", "party").order_by("sequence") if s.status != LotStep.Status.SKIPPED]
    bundles = list(lot.bundles.select_related("location", "current_step"))
    cuts = list(lot.cuttings.all())
    issued = lot.fabric_issues.exists()
    closed, complete = lot.status == lot.Status.CLOSED, lot.status == lot.Status.COMPLETED
    actions = [] if closed or complete else _actions(lot, steps, bundles, cuts, issued)
    allowed = [a for a in actions if user.has_screen_perm(*a["perm"])]
    return {
        "journey": _journey(lot, steps, bundles, cuts, issued),
        "primary": allowed[0] if allowed else None, "others": allowed[1:],
        "waiting": actions[0]["label"] if actions and not allowed else "",
        "complete": complete, "closed": closed,
    }


def order_next(order, user):
    """The one thing to do next on an order, for the orders list: release it, act on its lot, or open it."""
    if order.status == order.Status.DRAFT:
        return {"release": True} if user.has_screen_perm("production.order", "edit") else None
    if order.status in (order.Status.COMPLETED, order.Status.CLOSED):
        return None
    lots = [line.lot for line in order.lines.all() if hasattr(line, "lot")]
    if len(lots) == 1:
        return lot_guide(lots[0], user)["primary"]
    return {"label": "Open", "hint": "", "url": reverse("order_detail", args=[order.pk])} if lots else None
