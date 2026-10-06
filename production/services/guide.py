"""Where a lot is on its way from order to finished goods, and what it needs next (read-only).

The lot page, the order screens and Home all ask here, so every screen names the same next step. Callers fetch the
lot through `for_user`; nothing here widens that. Only labels, piece counts and links come back: a fabricator's name
is the only party name used (BR-15)."""
from django.urls import reverse

from core.models import Location
from jobwork.models import JobWorkChallan, Receipt, ReceiptLine
from jobwork.services import guide as jobwork_guide
from jobwork.services.guide import checker as _checker
from production.models import Bundle, LotStep
from production.services import bundles as bundle_service

B = Bundle.Status
AT_A_STAGE = (B.AT_STAGE, B.DONE, B.RECEIVED, B.REWORK)
# Within one stage, what is furthest behind comes first. An optional step sorts behind everything else aimed at the
# mandatory step it comes before, so it is never the main button while that step is open to the same user.
# Issue, receive, approve, QC and rework keep the order the challan guide gives them.
RANK = {"send": 0, "move": 0, **jobwork_guide.RANK, "optional": 6}
CHALLAN_NEW = jobwork_guide.CHALLAN_NEW
STATE = {LotStep.Status.DONE: "done", LotStep.Status.IN_PROGRESS: "now", LotStep.Status.PENDING: "todo"}


def _packing_step(steps):
    """The step bundles are packed from: the packing step, or the last step of a route that has none (the same
    rule as `bundles._packing_step`, which is what the pack service checks against)."""
    return next((s for s in reversed(steps) if s.process.kind == "packing"), steps[-1] if steps else None)


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
    # several stages can be in progress at once (an optional step that some bundles jumped over counts as in progress
    # too); one is marked as where the lot is: the earliest with pieces sitting at it, else the earliest in progress
    now = [s for s in stages if s["state"] == "now"] if lot.status != lot.Status.CLOSED else []
    first_now = next((s for s in now if s["pieces"]), now[0] if now else None)
    for s in stages:
        s["current"] = s is first_now
    return stages


def _actions(lot, steps, bundles, cuts, issued):
    found = {}

    def add(key, seq, label, hint, url, perm, pieces=0, tie=0):
        """`perm` lists every permission the user needs: to do the thing, and to open the screen the link leads to."""
        a = found.setdefault(key, {"label": label, "hint": hint, "url": url, "perm": perm, "pieces": 0,
                                   "order": (seq, RANK.get(key[0], 0), tie)})
        a["pieces"] += pieces

    def add_shared(a, pk, seq):
        """An action the challan guide builds: the same label and link here as on the challan's own page."""
        if a:
            add((a["kind"], pk), seq, a["label"], a["hint"], a["url"], a["perm"], a["pieces"])

    def onward(step, b, target=None):
        """Send or move bundles on to `step`. With `target`, `step` is an optional one on the way to that mandatory
        step (or, with nothing mandatory left, to itself): it is offered beside the main action, never ahead of it."""
        extra = "" if target is None else " (optional)"
        key = () if target is None else ("optional",)
        seq, tie = (step.sequence, 0) if target is None else (target.sequence, step.sequence)
        if step.assignment == LotStep.Assignment.SUBCONTRACT:
            if b.pk in on_challan:
                return        # the challan screen refuses a bundle until the challan it is on has been received in full
            who = step.party.name if step.party_id else "a fabricator"
            add(key + ("send", step.pk), seq, f"Send to {who} for {step.process.name}{extra}",
                "Make a challan and hand the bundles over.",
                reverse("challan_new") + f"?lot={lot.pk}&step={step.pk}", CHALLAN_NEW, b.qty, tie)
        else:
            add(key + ("move", step.pk), seq, f"Move to {step.process.name}{extra}", "Scan or tick the bundles that are ready.",
                reverse("move_bundles") + f"?lot={lot.pk}&back=1&step={step.pk}",
                (("production.move", "create"), ("production.move", "view")), b.qty, tie)

    cutting_perm = (("production.cutting", "create"), ("production.cutting", "view"))
    if not cuts and not issued:
        add(("fabric",), -3, "Issue fabric", "Send rolls from the store to the cutting floor.",
            reverse("lot_fabric", args=[lot.pk]), cutting_perm)
    elif not cuts:
        add(("cut",), -2, "Record cutting", "Enter the pieces cut in each size.", reverse("lot_cutting", args=[lot.pk]), cutting_perm)
    elif any(not c.bundled for c in cuts):
        add(("bundle",), -1, "Make bundles", "A lay is cut but not bundled yet.", reverse("lot_cutting", args=[lot.pk]), cutting_perm)

    if not bundles:
        return sorted(found.values(), key=lambda a: a["order"])   # nothing is bundled yet: no challan, receipt or move to look for

    # counted back above what was issued: nothing has moved, but it is the owner's approval they wait for, not a recount
    counted = set(ReceiptLine.objects.filter(receipt__challan__lot=lot, receipt__status=Receipt.Status.PENDING_APPROVAL)
                  .values_list("challan_bundle_id", flat=True))
    open_status = (JobWorkChallan.Status.DRAFT, JobWorkChallan.Status.ISSUED, JobWorkChallan.Status.PARTLY)
    on_draft, on_challan = set(), set()
    for ch in lot.challans.filter(status__in=open_status).select_related("party", "step__process").prefetch_related("bundles__bundle"):
        lines = list(ch.bundles.all())
        on_challan.update(l.bundle_id for l in lines)
        if ch.status == JobWorkChallan.Status.DRAFT:
            on_draft.update(l.bundle_id for l in lines)
            add_shared(jobwork_guide.issue_action(ch, lines), ch.pk, ch.step.sequence)
        else:
            add_shared(jobwork_guide.receive_action(ch, lines, counted), ch.pk, ch.step.sequence)

    waiting = (Receipt.Status.PENDING_APPROVAL, Receipt.Status.RECEIVED)
    for r in Receipt.objects.filter(challan__lot=lot, status__in=waiting).select_related("challan__party", "challan__step"):
        add_shared(jobwork_guide.receipt_action(r), r.pk, r.challan.step.sequence)

    for b in bundles:
        if not b.is_live or b.pk in on_draft:
            continue
        here = b.current_step.sequence if b.current_step_id else b.completed_seq
        if b.status == B.REWORK or b.rework_qty:
            # a bundle sent back keeps the step of the challan it came back on: the rework challan is for that step
            add_shared(jobwork_guide.rework_action(lot.pk, b.current_step_id, b.rework_qty or b.qty), b.current_step_id, here)
            continue
        if b.status not in (B.CUT, B.READY, B.AT_STAGE):
            continue
        if b.status == B.AT_STAGE and b.location.loc_type == Location.Type.FABRICATOR:
            continue                                         # out on a challan: the challan's own line covers it
        if pack_ready(b, steps):
            add(("pack",), 10_000, "Pack into finished goods", "These bundles have reached packing.",
                reverse("lot_detail", args=[lot.pk]) + "#pack", (("production.move", "create"), ("production.lot", "view")), b.qty)
            continue
        nxt, later = bundle_service.steps_ahead(b, steps)
        if nxt is not None:
            onward(nxt, b)
        for s in later:
            if nxt is not None and s.sequence > nxt.sequence:
                break
            if not s.is_mandatory:
                onward(s, b, target=nxt or s)
    return sorted(found.values(), key=lambda a: a["order"])


def lot_guide(lot, user, perms=None):
    """{'journey': [...], 'primary': action or None, 'others': [...], 'waiting': label, 'complete': bool, 'closed': bool}.
    An action is offered only if the user's role may do it and may open the screen it leads to; `waiting` names the
    next step when it is someone else's. `perms` is an optional dict shared between calls for the SAME user."""
    can = _checker(user, {} if perms is None else perms)
    steps = [s for s in lot.steps.select_related("process", "party").order_by("sequence") if s.status != LotStep.Status.SKIPPED]
    bundles = list(lot.bundles.select_related("location", "current_step"))
    cuts = list(lot.cuttings.all())
    issued = lot.fabric_issues.exists()
    closed, complete = lot.status == lot.Status.CLOSED, lot.status == lot.Status.COMPLETED
    actions = [] if closed or complete else _actions(lot, steps, bundles, cuts, issued)
    allowed = [a for a in actions if all(can(*p) for p in a["perm"])]
    return {
        "journey": _journey(lot, steps, bundles, cuts, issued),
        "primary": allowed[0] if allowed else None, "others": allowed[1:],
        "waiting": actions[0]["label"] if actions and not allowed else "",
        "complete": complete, "closed": closed,
    }


def order_next(order, user, perms=None):
    """The one thing to do next on an order, for the orders list: release it, act on its lot, or open it.
    `perms` as in `lot_guide`."""
    perms = {} if perms is None else perms
    if order.status == order.Status.DRAFT:
        return {"release": True} if _checker(user, perms)("production.order", "edit") else None
    if order.status in (order.Status.COMPLETED, order.Status.CLOSED):
        return None
    lots = [line.lot for line in order.lines.all() if hasattr(line, "lot")]
    if len(lots) == 1:
        return lot_guide(lots[0], user, perms)["primary"]
    return {"label": "Open", "hint": "", "url": reverse("order_detail", args=[order.pk])} if lots else None
