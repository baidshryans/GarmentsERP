"""The lot page's "Step by step" view: for each route step, the pieces that went in and came out, what was lost
or held for rework, what it cost, and every recorded step behind those figures.

Pieces lost, rejected or short are counted at the step the pieces were leaving, as labour is: a move records
them as the bundles leave a stage, a receipt as they come back from the fabricator at that step. Cost comes from
the lot's cost entries, each linked to its route step when posted. Job work that QC has checked but no posted bill
pays yet is shown apart as "to bill" (payable pieces x the challan rate); it is not in the books.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from django.urls import reverse

from production.models import Bundle, LotCostEntry, LotStep, ProductionAction, ProductionActionItem, StageMovement
from production.services import actions as step_actions
from production.services import costing

ZERO = Decimal("0.00")
K = ProductionAction.Kind
INTO = (StageMovement.Kind.MOVE, StageMovement.Kind.FACTORY, StageMovement.Kind.ISSUE)   # moves that bring pieces to a step
OUT_OF = INTO + (StageMovement.Kind.PACK,)
LOT_LEVEL = {LotCostEntry.Kind.TRANSFER, LotCostEntry.Kind.RELIEF, LotCostEntry.Kind.WRITE_OFF}


@dataclass
class Event:
    date: object
    title: str
    detail: str = ""
    cost: Decimal | None = None
    url: str = ""
    action: object = None          # the ProductionAction, for Edit / Undo
    materials: list = field(default_factory=list)


@dataclass
class StepRow:
    step: object
    pieces_in: int = 0
    pieces_out: int = 0
    loss: int = 0
    rejected: int = 0
    short: int = 0
    held: int = 0
    here: int = 0
    rework_in: int = 0
    fabric: Decimal = ZERO
    materials: Decimal = ZERO
    labour: Decimal = ZERO
    jobwork: Decimal = ZERO
    to_bill: Decimal = ZERO
    first: object = None
    last: object = None
    events: list = field(default_factory=list)
    rate: object = None                   # the rate on Rates last used at this step

    @property
    def rate_text(self):
        if self.rate is None:
            return ""
        from jobwork.services.rates import source_text
        from ledger.services.narration import money

        return f"{money(self.rate.rate)} a piece · {source_text(self.rate)}"

    @property
    def lost(self):
        return self.loss + self.rejected + self.short

    @property
    def cost(self):
        """In the books for this step."""
        return self.fabric + self.materials + self.labour + self.jobwork

    @property
    def per_piece(self):
        """Cost of each good piece that came out of the step, counting job work still to be billed."""
        if not self.pieces_out or not (self.cost + self.to_bill):
            return None
        return costing.r2((self.cost + self.to_bill) / self.pieces_out)

    @property
    def touched(self):
        return bool(self.pieces_in or self.pieces_out or self.lost or self.here or self.held or self.cost or self.events)


@dataclass
class LotView:
    rows: list
    transfer: Decimal = ZERO
    relief: Decimal = ZERO
    write_off: Decimal = ZERO
    unlinked: Decimal = ZERO
    wip: Decimal = ZERO
    lot_events: list = field(default_factory=list)

    @property
    def spent(self):
        """Everything put into the lot so far: the steps' cost and cost not linked to a step."""
        return sum((r.cost for r in self.rows), ZERO) + self.unlinked

    @property
    def to_bill(self):
        return sum((r.to_bill for r in self.rows), ZERO)


def _cutting_head(steps):
    head = []
    for s in steps:
        if s.process.kind != "cutting":
            break
        head.append(s)
    return head


def _add_cost(row, kind, amount):
    if kind == LotCostEntry.Kind.FABRIC:
        row.fabric += amount
    elif kind in (LotCostEntry.Kind.TRIM, LotCostEntry.Kind.CHARGE):
        row.materials += amount
    elif kind == LotCostEntry.Kind.LABOUR:
        row.labour += amount
    elif kind == LotCostEntry.Kind.JOBWORK:
        row.jobwork += amount


def _pieces(lot, steps, by_pk, cut_step):
    """In, out, lost, held and still-here pieces of every step, from the stage movements and the bundles."""
    def row_for(step_id):
        return by_pk.get(step_id) if step_id else by_pk.get(cut_step.pk if cut_step else None)

    if cut_step is not None:
        row = by_pk[cut_step.pk]
        for c in lot.cuttings.prefetch_related("sizes"):
            sizes = list(c.sizes.all())
            row.pieces_in += sum(s.pieces for s in sizes)
            row.loss += sum(s.loss for s in sizes)
            row.first = min(filter(None, [row.first, c.date])) if row.first else c.date
            row.last = max(filter(None, [row.last, c.date]))
    for m in StageMovement.objects.filter(bundle__lot=lot).select_related("bundle"):
        same = m.from_step_id and m.from_step_id == m.to_step_id
        source = row_for(m.from_step_id)
        if source is not None:
            source.loss += m.loss
            source.rejected += m.rejection
            source.short += m.shortage
            if m.kind in OUT_OF and not same:
                source.pieces_out += m.qty_out - m.loss - m.rejection - m.shortage
        if m.kind in INTO and m.to_step_id in by_pk and not same:
            target = by_pk[m.to_step_id]
            if m.is_rework:
                target.rework_in += m.qty_in
            else:
                target.pieces_in += m.qty_in
    for b in Bundle.objects.filter(lot=lot, status__in=Bundle.LIVE):
        row = row_for(b.current_step_id)
        if row is None:
            continue
        if b.held_for_rework:
            row.held += b.qty
        else:
            row.here += b.qty


def _to_bill(lot, by_pk):
    """Job work checked at QC and payable, not yet on a posted labour bill: payable pieces x the challan rate."""
    from jobwork.models import QcResult
    from jobwork.services import bills

    results = (QcResult.objects.filter(line__challan_bundle__challan__lot=lot, pay_qty__gt=0)
               .exclude(bill_line__bill__status="posted")
               .select_related("line__challan_bundle__challan"))
    for r in results:
        row = by_pk.get(r.line.challan_bundle.challan.step_id)
        if row is not None:
            row.to_bill += bills.amount_for(r)[0]


def _main_step(action, items, docs, cut_step):
    """The route step an action is about."""
    if action.kind in (K.FABRIC, K.CUTTING, K.BUNDLES):
        return cut_step.pk if cut_step else None
    if action.kind in (K.CHALLAN, K.RECEIPT, K.APPROVAL, K.QC):
        return docs.get((action.doc_type, action.doc_id))
    moves = [i.after or {} for i in items if i.model == "production.stagemovement" and i.role == "created"]
    if action.kind == K.MOVE and moves:
        return moves[0].get("to_step_id")
    if action.kind in (K.COUNT, K.PACK) and moves:
        return moves[0].get("from_step_id") or (cut_step.pk if cut_step else None)
    if action.kind == K.SPLIT:
        made = [i.after or {} for i in items if i.model == "production.bundle" and i.role == "created"]
        if made:
            return made[0].get("current_step_id") or (cut_step.pk if cut_step else None)
    return None


def _url(action):
    if action.doc_type == "jobwork.jobworkchallan" and action.doc_id:
        return reverse("challan_detail", args=[action.doc_id])
    if action.doc_type == "jobwork.receipt" and action.doc_id:
        return reverse("receipt_detail", args=[action.doc_id])
    return ""


def build(lot, user) -> LotView:
    from jobwork.models import JobWorkChallan, Receipt
    from production.models import StepMaterialIssue

    steps = list(lot.steps.select_related("process", "factory", "party").order_by("sequence"))
    head = _cutting_head(steps)
    cut_step = head[0] if head else None
    rows = [StepRow(step=s) for s in steps]
    by_pk = {r.step.pk: r for r in rows}
    view = LotView(rows=rows)

    _pieces(lot, steps, by_pk, cut_step)
    _to_bill(lot, by_pk)

    entries = list(lot.cost_entries.select_related("rate"))
    for ch in JobWorkChallan.objects.filter(lot=lot, labour_rate__isnull=False).select_related("labour_rate").order_by("pk"):
        if ch.step_id in by_pk:
            by_pk[ch.step_id].rate = ch.labour_rate
    for e in entries:
        if e.kind == LotCostEntry.Kind.TRANSFER:
            view.transfer += e.amount
        elif e.kind == LotCostEntry.Kind.RELIEF:
            view.relief += e.amount
        elif e.kind == LotCostEntry.Kind.WRITE_OFF:
            view.write_off += e.amount
        elif e.step_id in by_pk:
            _add_cost(by_pk[e.step_id], e.kind, e.amount)
            if e.rate_id is not None:
                by_pk[e.step_id].rate = e.rate
        else:
            view.unlinked += e.amount
    view.wip = costing.lot_cost(lot)
    entry_by_pk = {e.pk: e for e in entries}

    # every recorded step of the lot, under the route step it is about, with the cost it posted there
    acts = step_actions.listed(user, limit=1000, lot=lot)
    items = {}
    for i in ProductionActionItem.objects.filter(action__in=acts).order_by("id"):
        items.setdefault(i.action_id, []).append(i)
    docs = {}
    for pk, step_id in JobWorkChallan.objects.filter(lot=lot).values_list("pk", "step_id"):
        docs[("jobwork.jobworkchallan", pk)] = step_id
    for pk, step_id in Receipt.objects.filter(challan__lot=lot).values_list("pk", "challan__step_id"):
        docs[("jobwork.receipt", pk)] = step_id
    issues = {i.pk: i for i in StepMaterialIssue.objects.filter(lot=lot).prefetch_related("lines__material__unit")}
    covered = set()          # cost entries shown with the step that posted them
    for a in sorted(acts, key=lambda a: (a.date, a.pk)):
        mine = items.get(a.pk, [])
        cost_by_step = {}
        for i in mine:
            if i.role == "cost" and i.object_id in entry_by_pk:
                e = entry_by_pk[i.object_id]
                covered.add(e.pk)
                if e.kind in LOT_LEVEL:
                    continue
                key = e.step_id if e.step_id in by_pk else None
                cost_by_step[key] = cost_by_step.get(key, ZERO) + e.amount
        materials = [l for i in mine if i.model == "production.stepmaterialissue" and i.role == "created"
                     for l in (issues[i.object_id].lines.all() if i.object_id in issues else [])]
        main = _main_step(a, mine, docs, cut_step)
        main = main if main in by_pk else None
        for step_id in {main, *cost_by_step}:
            cost = cost_by_step.get(step_id)
            if a.undone and cost is not None:
                cost = ZERO                              # its cost was reversed when it was undone
            elif cost is None and step_id != main:
                continue
            title = a.get_kind_display() if step_id == main else f"{a.get_kind_display()} (cost of this step)"
            ev = Event(date=a.date, title=title, detail=a.summary, cost=cost, url=_url(a), action=a,
                       materials=materials if step_id == main else [])
            if step_id is None:
                view.lot_events.append(ev)
            else:
                by_pk[step_id].events.append(ev)
    # cost posted outside a recorded step: labour bills and their cancellation
    for e in entries:
        if e.pk in covered or e.kind in LOT_LEVEL or e.source_type == "production.productionaction":
            continue
        url = reverse("bill_detail", args=[e.source_id]) if e.source_type == "jobwork.jobworkbill" and e.source_id else ""
        ev = Event(date=e.date, title=e.get_kind_display(), detail=e.note, cost=e.amount, url=url)
        (by_pk[e.step_id].events if e.step_id in by_pk else view.lot_events).append(ev)

    for r in rows:
        r.events.sort(key=lambda ev: (ev.date, ev.action.pk if ev.action else 0))
        dates = [ev.date for ev in r.events]
        if dates:
            r.first = min([d for d in [r.first, *dates] if d])
            r.last = max([d for d in [r.last, *dates] if d])
    view.lot_events.sort(key=lambda ev: (ev.date, ev.action.pk if ev.action else 0))
    return view
