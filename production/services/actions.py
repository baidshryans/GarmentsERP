"""Edit and undo of recorded steps (fabric issue, cutting, bundles, moves, challans, receipts, QC, packing).

A step's service is wrapped with `@recorded`. While it runs, every row it writes is noted: the stock movements,
vouchers and lot cost it posts, the rows it creates, and the rows it changes (as they were before). That list is
the step's ProductionAction.

Undoing a step never edits what was posted. It posts the opposite stock movements and reversing vouchers, puts
the changed rows back as they were and takes the created rows away, then marks the action as undone with the
reason. A step can be undone only while nothing later depends on it: if a row it left has changed since, the
later step is named and must be undone first. "Edit" is undo, then the same form again with the old figures.
"""
import contextvars
import datetime
import functools
import json

from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Max, ProtectedError
from django.db.models.signals import post_save, pre_save
from django.utils import timezone

from core import checks
from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.periods import assert_period_open
from production.models import Lot, LotCostEntry, ProductionAction, ProductionActionItem

Kind = ProductionAction.Kind
Role = ProductionActionItem.Role

# rows that are reversed by posting their opposite
POSTED = {"inventory.stockmovement": Role.MOVEMENT, "ledger.voucher": Role.VOUCHER, "production.lotcostentry": Role.COST}
# rows that are put back (changed) or taken away (created)
TRACKED = {
    "production.fabricissue", "production.fabricissueline", "production.cuttingentry", "production.cuttingsize",
    "production.cuttingrolluse", "production.bundle", "production.stagemovement", "production.packentry",
    "production.packentryline", "production.stepmaterialissue", "production.stepmaterialissueline",
    "jobwork.jobworkchallan", "jobwork.challanbundle", "jobwork.challantrim", "jobwork.receipt", "jobwork.receiptline",
    "jobwork.receipttrim", "jobwork.qcresult",
}
# worked out again after an undo, so a later step changing them does not hold an earlier one back
DERIVED = {"jobwork.jobworkchallan": {"status"}, "jobwork.receipt": {"status"}}
# a created row of these stays: the challan is cancelled and keeps its lines, a bundle is kept but voided
KEPT = {"jobwork.challanbundle", "jobwork.challantrim"}
# the screen whose "create" right lets a user undo a step: whoever may record it may undo it
SCREEN = {
    Kind.FABRIC: "production.cutting", Kind.CUTTING: "production.cutting", Kind.BUNDLES: "production.cutting",
    Kind.MOVE: "production.move", Kind.COUNT: "production.move", Kind.SPLIT: "production.move", Kind.PACK: "production.move",
    Kind.CHALLAN: "jobwork.challan", Kind.RECEIPT: "jobwork.receipt", Kind.APPROVAL: "jobwork.receipt", Kind.QC: "jobwork.qc",
}

_current = contextvars.ContextVar("production_action_recorder", default=None)


class _Exact(DjangoJSONEncoder):
    """Times in full. Django's encoder cuts them to milliseconds, so a row put back from a snapshot would differ
    from the snapshot taken before it (and a later undo would see a row "changed since")."""

    def default(self, o):
        if isinstance(o, (datetime.datetime, datetime.time)):
            return o.isoformat()
        return super().default(o)


def snapshot(obj) -> dict:
    """A row's stored fields as plain JSON values."""
    return json.loads(json.dumps({f.attname: getattr(obj, f.attname) for f in obj._meta.concrete_fields}, cls=_Exact))


class _Recorder:
    def __init__(self):
        self.items = []     # [role, model label, pk, text, before]
        self.seen = set()

    def note(self, role, obj, before=None):
        key = (obj._meta.label_lower, obj.pk)
        if key in self.seen:
            return
        self.seen.add(key)
        self.items.append([role, key[0], obj.pk, str(obj)[:80], before])


def _before_save(sender, instance, **kwargs):
    rec = _current.get()
    if rec is None or instance.pk is None or sender._meta.label_lower not in TRACKED:
        return
    if (sender._meta.label_lower, instance.pk) in rec.seen:
        return
    stored = sender._base_manager.filter(pk=instance.pk).first()
    if stored is not None:
        rec.note(Role.CHANGED, stored, snapshot(stored))


def _after_save(sender, instance, created, **kwargs):
    rec = _current.get()
    if rec is None or not created:
        return
    label = sender._meta.label_lower
    if label in POSTED:
        rec.note(POSTED[label], instance)
    elif label in TRACKED:
        rec.note(Role.CREATED, instance)


def connect():
    pre_save.connect(_before_save, dispatch_uid="production_action_before_save")
    post_save.connect(_after_save, dispatch_uid="production_action_after_save")


def recorded(kind, describe):
    """Wrap a step's service so that what it writes becomes a ProductionAction. `describe(result, args, kwargs)`
    returns {"lot", "date", "summary"} and optionally "doc", "factory" and "kind", or None to record nothing.
    A recorded service called from inside another is part of the outer step."""

    def decorate(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if _current.get() is not None:
                return fn(*args, **kwargs)
            rec = _Recorder()
            with transaction.atomic():
                token = _current.set(rec)
                try:
                    result = fn(*args, **kwargs)
                finally:
                    _current.reset(token)
                info = describe(result, args, kwargs)
                if info:
                    checks.not_future(info["date"], f"This step ({kind.label.lower()})")
                if info and rec.items:
                    _store(info.get("kind", kind), rec, info, kwargs.get("user"))
                return result
        return wrapper
    return decorate


def _store(kind, rec, info, user):
    lot, doc = info["lot"], info.get("doc")
    action = ProductionAction.objects.create(
        company=lot.company, factory=info.get("factory") or lot.factory, lot=lot, kind=kind, date=info["date"],
        summary=info["summary"][:255], created_by=user,
        doc_type=doc._meta.label_lower if doc is not None else "", doc_id=doc.pk if doc is not None else None)
    rows = []
    for role, label, pk, text, before in rec.items:
        after = None
        if role in (Role.CREATED, Role.CHANGED):
            now = apps.get_model(label)._base_manager.filter(pk=pk).first()
            if now is None:        # made and removed within the step
                continue
            after = snapshot(now)
        rows.append(ProductionActionItem(action=action, role=role, model=label, object_id=pk, label=text, before=before, after=after))
    ProductionActionItem.objects.bulk_create(rows)
    return action


# ---------------------------------------------------------------- what stands in the way

def _differs(label, now, after) -> bool:
    skip = DERIVED.get(label, ())
    return any(now.get(k) != v for k, v in after.items() if k not in skip)


def _why_changed(action, item, now):
    """Why a row is no longer as this step left it: the later step that touched it, or what else did."""
    later = ProductionAction.objects.filter(pk__in=ProductionActionItem.objects.filter(
        action__pk__gt=action.pk, action__undone=False, model=item.model, object_id=item.object_id,
        role__in=(Role.CREATED, Role.CHANGED)).values("action_id")).order_by("pk").last()
    if later is not None:
        return f"{later.get_kind_display()} ({later.summary}) came after this step. Undo that first."
    if item.model == "jobwork.qcresult" and now.get("bill_line_id"):
        return f"{item.label or 'The QC result'} is on a labour bill. Cancel the bill first."
    if item.model == "production.cuttingentry" and now.get("bundled"):
        return f"Bundles have been made from {item.label or 'this cutting'} and have moved on. Undo their later steps and the bundles first."
    if item.model == "production.bundle" and now.get("status") == "dispatched":
        return f"Bundle {item.label} has been dispatched."
    return f"{item.label or item.model} has been changed since this step was recorded."


def blockers(action) -> list:
    """Reasons this step cannot be undone now. Empty when it can."""
    from jobwork.models import ChallanBundle

    if action.undone:
        return ["This step has already been undone."]
    if action.lot.status == Lot.Status.CLOSED:
        return [f"Lot {action.lot.lot_no} is closed."]
    out = []
    for item in action.items.filter(role__in=(Role.CREATED, Role.CHANGED)):
        now = apps.get_model(item.model)._base_manager.filter(pk=item.object_id).first()
        if now is None:
            why = f"{item.label or item.model} no longer exists."
        elif _differs(item.model, snapshot(now), item.after or {}):
            why = _why_changed(action, item, snapshot(now))
        else:
            why = None
            if item.model == "production.bundle":
                draft = ChallanBundle.objects.filter(bundle_id=item.object_id, challan__status="draft").select_related("challan").first()
                if draft is not None:
                    why = f"Bundle {item.label} is on draft challan #{draft.challan_id}. Discard that draft first."
        if why and why not in out:
            out.append(why)
    return out


def may_undo(action, user) -> bool:
    """Whoever may record a step may undo it, in a factory they can work in."""
    if not user.has_screen_perm(SCREEN[action.kind], "create"):
        return False
    allowed = user.allowed_factory_ids()
    return allowed is None or action.factory_id in allowed


# ---------------------------------------------------------------- undo

def _challans_of(action) -> set:
    ids = set()
    for item in action.items.filter(model__in=("jobwork.jobworkchallan", "jobwork.challanbundle", "jobwork.receipt")):
        ids.add(item.object_id if item.model == "jobwork.jobworkchallan" else (item.after or item.before or {}).get("challan_id"))
    return ids - {None}


def _refresh_jobwork(challan_ids):
    """Statuses of challans and their receipts, worked out again from their lines."""
    from jobwork.models import JobWorkChallan, Receipt

    S = JobWorkChallan.Status
    for challan in JobWorkChallan.objects.filter(pk__in=challan_ids):
        for receipt in challan.receipts.exclude(status=Receipt.Status.PENDING_APPROVAL):
            lines = list(receipt.lines.all())
            status = Receipt.Status.QC_DONE if lines and all(l.qc_done for l in lines) else Receipt.Status.RECEIVED
            if receipt.status != status:
                receipt.status = status
                receipt.save(update_fields=["status"])
        if challan.status in (S.ISSUED, S.PARTLY, S.RECEIVED):
            lines = list(challan.bundles.all())
            done = [cb for cb in lines if cb.qty_received or cb.qty_shortage]
            status = S.RECEIVED if lines and len(done) == len(lines) else S.PARTLY if done else S.ISSUED
            if challan.status != status:
                challan.status = status
                challan.save(update_fields=["status"])


def refresh_lot(lot):
    """A lot's steps and status from what is recorded for it now."""
    from production.services import bundles as bundle_service
    from production.services import orders

    bundle_service.refresh_steps(lot)
    lot = Lot.objects.get(pk=lot.pk)
    if lot.status != Lot.Status.CLOSED and not lot.bundles.exists():
        lot.status = Lot.Status.CUTTING if (lot.cuttings.exists() or lot.fabric_issues.exists()) else Lot.Status.PLANNED
        lot.save(update_fields=["status"])
        orders.refresh_status(lot.order)


def _put_back(item):
    model = apps.get_model(item.model)
    obj = model._base_manager.get(pk=item.object_id)
    for f in model._meta.concrete_fields:
        if f.attname in item.before and not f.primary_key:
            setattr(obj, f.attname, f.to_python(item.before[f.attname]))
    obj.save()


def _take_away(item):
    from jobwork.models import JobWorkChallan

    model = apps.get_model(item.model)
    obj = model._base_manager.filter(pk=item.object_id).first()
    if obj is None:
        return
    if item.model in KEPT and not getattr(obj, "held_from_id", None):   # a line of held pieces goes with its receipt
        return
    if item.model == "production.bundle":
        obj.voided = True
        obj.bundle_no = f"{obj.bundle_no}~{obj.pk}"[:40]      # frees the number for the bundles made again
        obj.entry = None                                      # and lets the lay it came from be undone too
        obj.save(update_fields=["voided", "bundle_no", "entry"])
    elif item.model == "jobwork.jobworkchallan":
        obj.status = JobWorkChallan.Status.CANCELLED
        obj.save(update_fields=["status"])
    else:
        try:
            obj.delete()
        except ProtectedError:
            raise BusinessRuleError(f"{item.label or item.model} is still used elsewhere (a labour bill, a deduction or a waiver), so this step cannot be undone.")


@transaction.atomic
def undo(action, *, user, reason, date=None) -> ProductionAction:
    """Undo a recorded step. `date` is the date the reversing stock movements and vouchers carry: today unless
    given, and never before the step itself."""
    from inventory.exceptions import InsufficientStock
    from inventory.models import StockMovement
    from inventory.services import stock
    from ledger.models import Voucher
    from ledger.services.posting import reverse_voucher
    from production.services import costing

    action = ProductionAction.objects.select_related("lot", "lot__company", "factory", "company").get(pk=action.pk)
    reason = (reason or "").strip()
    if not reason:
        raise BusinessRuleError("Give the reason for undoing this step.")
    date = date or timezone.localdate()
    if date < action.date:
        raise BusinessRuleError(f"The reversal cannot be dated before the step itself ({action.date:%d %b %Y}).")
    if not user.has_screen_perm(SCREEN[action.kind], "create"):
        raise BusinessRuleError("You are not allowed to undo this step.")
    assert_factory_access(user, action.factory)
    stops = blockers(action)
    if stops:
        raise BusinessRuleError(" ".join(stops))
    assert_period_open(action.company, action.factory, date)
    lot, challan_ids = action.lot, _challans_of(action)
    note = f"Undone: {action.summary}"[:200]

    by_role = {}
    for item in action.items.order_by("-id"):               # last written, first undone
        by_role.setdefault(item.role, []).append(item)
    for item in by_role.get(Role.MOVEMENT, []):
        movement = StockMovement.objects.get(pk=item.object_id)
        try:
            stock.reverse_movement(movement, user=user, date=date, source=action, notes=note, enforce_scope=False)
        except InsufficientStock as exc:
            raise BusinessRuleError(f"{exc} What this step put there has been used since: undo the later step first.")
    reversals = {}
    for item in by_role.get(Role.VOUCHER, []):
        voucher = Voucher.objects.get(pk=item.object_id)
        if voucher.is_posted:
            reversals[voucher.pk] = reverse_voucher(voucher, user=user, reason=f"{note}. {reason}"[:250], date=date)
    for item in by_role.get(Role.COST, []):
        entry = LotCostEntry.objects.get(pk=item.object_id)
        costing.add_cost(lot=entry.lot, factory=entry.factory, kind=entry.kind, amount=-entry.amount, date=date,
                         note=f"Undone: {entry.note}", source=action, voucher=reversals.get(entry.voucher_id), step=entry.step)
    for item in action.items.filter(role__in=(Role.CREATED, Role.CHANGED)).order_by("-id"):
        if item.role == Role.CHANGED:
            _put_back(item)
        else:
            _take_away(item)

    _refresh_jobwork(challan_ids)
    refresh_lot(lot)
    action.undone, action.undo_reason, action.undo_date = True, reason[:255], date
    action.undone_by, action.undone_at = user, timezone.now()
    action.save()
    return action


# ---------------------------------------------------------------- delete (owner, 19 Oct 2026)

def later_steps(action):
    """Steps recorded on the same lot after this one and still standing, newest first."""
    return list(ProductionAction.objects.filter(lot_id=action.lot_id, undone=False, pk__gt=action.pk).order_by("-pk"))


def delete_blockers(action) -> list:
    """Reasons this step cannot be deleted now: steps are deleted newest first, then whatever undo would refuse."""
    later = later_steps(action)
    if later:
        names = ", then ".join(f"{a.get_kind_display()} ({a.summary})" for a in later)
        return [f"To delete this {action.get_kind_display().lower()}, first delete: {names}."]
    return blockers(action)


def consequences(action, user) -> list:
    """What deleting this step does, in plain sentences. Money only for those who may see cost."""
    from inventory.models import StockMovement
    from ledger.models import Voucher

    see_cost = user.can_view_field("cost")
    out = []
    moved = {}
    for item in action.items.filter(role=Role.MOVEMENT):
        m = StockMovement.objects.select_related("location", "material", "sku").filter(pk=item.object_id).first()
        if m is None:
            continue
        place = m.location.name if m.location.loc_type in ("godown", "dispatch", "rejects", "showroom") else "work in progress"
        key = (str(m.item), place)
        moved[key] = moved.get(key, 0) - m.qty
    for (item, place), qty in moved.items():
        if qty:
            out.append(f"{'put back' if qty > 0 else 'take out'} {abs(qty).normalize():f} {item} {'to' if qty > 0 else 'from'} {place}")
    for item in action.items.filter(role=Role.COST):
        entry = LotCostEntry.objects.filter(pk=item.object_id).first()
        if entry is not None and see_cost:
            out.append(f"remove ₹{entry.amount} of {entry.get_kind_display().lower()} cost from lot {action.lot.lot_no}")
    if not see_cost and action.items.filter(role=Role.COST).exists():
        out.append(f"remove this step's cost from lot {action.lot.lot_no}")
    for item in action.items.filter(role=Role.VOUCHER):
        v = Voucher.objects.filter(pk=item.object_id).first()
        if v is not None:
            out.append(f"delete journal entry {v.number}" + (f" (₹{v.total})" if see_cost else ""))
    created = {}
    for item in action.items.filter(role=Role.CREATED):
        label = apps.get_model(item.model)._meta.verbose_name
        created[label] = created.get(label, 0) + 1
    for label, n in created.items():
        out.append(f"remove {n} {label}{'s' if n > 1 and not label.endswith('s') else ''}")
    return out


@transaction.atomic
def delete_step(action, *, user) -> None:
    """Delete a recorded step entirely (owner, 19 Oct 2026). It is undone the usual way, which posts exact
    reversals and puts every other row back; then the step's postings and their reversals are purged together,
    with the rows it made and every history row, so nothing of it is left for anyone to find."""
    from inventory.models import StockMovement
    from jobwork.models import ChallanBundle, ChallanTrim, JobWorkChallan
    from ledger.models import Voucher

    from core.services import purge

    action = ProductionAction.objects.select_related("lot", "company", "factory").get(pk=action.pk)
    if action.undone:
        raise BusinessRuleError("This step has already been taken back.")
    if not user.has_screen_perm(SCREEN[action.kind], "create"):
        raise BusinessRuleError("You are not allowed to delete this step.")
    assert_factory_access(user, action.factory)
    assert_period_open(action.company, action.factory, action.date)
    stops = delete_blockers(action)
    if stops:
        raise BusinessRuleError(" ".join(stops))
    started = action.created_at
    undo(action, user=user, reason="Deleted", date=action.date)

    items = list(action.items.all())
    own = {role: [i.object_id for i in items if i.role == role] for role in (Role.MOVEMENT, Role.VOUCHER, Role.COST)}
    source = {"source_type": ProductionAction._meta.label_lower, "source_id": action.pk}
    vouchers = set(own[Role.VOUCHER]) | set(Voucher.objects.filter(reverses_id__in=own[Role.VOUCHER]).values_list("pk", flat=True))
    LotCostEntry.objects.filter(pk__in=own[Role.COST]).delete()
    LotCostEntry.objects.filter(**source).delete()
    purge.movements(StockMovement.objects.filter(pk__in=own[Role.MOVEMENT]) | StockMovement.objects.filter(**source))
    purge.vouchers(Voucher.objects.filter(pk__in=vouchers))

    created = [i for i in items if i.role == Role.CREATED]
    challan_ids = [i.object_id for i in created if i.model == "jobwork.jobworkchallan"]
    bundle_ids = [i.object_id for i in created if i.model == "production.bundle"]
    for model, ids in ((ChallanTrim, ChallanTrim.objects.filter(challan_id__in=challan_ids).values_list("pk", flat=True)),
                       (ChallanBundle, ChallanBundle.objects.filter(challan_id__in=challan_ids).values_list("pk", flat=True))):
        ids = list(ids)
        model._base_manager.filter(pk__in=ids).delete()
        purge.history(model, ids)
    for item in created:                            # rows the step made that undo kept (cancelled challans, voided bundles)
        if item.model in ("jobwork.challanbundle", "jobwork.challantrim"):
            continue
        model = apps.get_model(item.model)
        if item.model not in ("jobwork.jobworkchallan", "production.bundle"):
            model._base_manager.filter(pk=item.object_id).delete()
        purge.history(model, [item.object_id])
    JobWorkChallan._base_manager.filter(pk__in=challan_ids).delete()
    from production.models import Bundle

    Bundle._base_manager.filter(pk__in=bundle_ids).delete()
    purge.history(JobWorkChallan, challan_ids)
    purge.history(Bundle, bundle_ids)
    for item in items:
        if item.role == Role.CHANGED:
            purge.history_since(apps.get_model(item.model), item.object_id, started)
    ProductionActionItem.objects.filter(action=action).delete()
    ProductionAction._base_manager.filter(pk=action.pk).delete()


# ---------------------------------------------------------------- the form again, with the old figures

def _after(action, label):
    return [i.after for i in action.items.filter(model=label, role=Role.CREATED).order_by("id") if i.after]


def _bundles_typed(action) -> dict:
    """The bundles a step made, as they are typed: {"bundles_<size>": "25 25 22"}."""
    from masters.models import SKU

    made = _after(action, "production.bundle")
    size_of = dict(SKU.objects.filter(pk__in={b["sku_id"] for b in made}).values_list("pk", "size_id"))
    per_size = {}
    for b in made:
        per_size.setdefault(size_of.get(b["sku_id"]), []).append(str(b["original_qty"]))
    return {f"bundles_{size}": " ".join(counts) for size, counts in per_size.items()}


def form_values(action) -> dict:
    """What was entered for a step, under the names its form uses, so that "Edit" can show the form filled in."""
    vals = {}
    if action.kind == Kind.FABRIC:
        for issue in _after(action, "production.fabricissue"):
            vals.update(date=issue["date"], estimated_pieces=issue["expected_pieces"] or "")
        vals.update({f"qty_{l['roll_id']}": l["qty"] for l in _after(action, "production.fabricissueline")})
    elif action.kind == Kind.CUTTING:
        for entry in _after(action, "production.cuttingentry"):
            vals.update(date=entry["date"], notes=entry["notes"])
        vals.update({f"pieces_{s['size_id']}": s["pieces"] for s in _after(action, "production.cuttingsize")})
        for r in _after(action, "production.cuttingrolluse"):
            vals.update({f"used_{r['roll_id']}": r["used_qty"], f"waste_{r['roll_id']}": r["waste_qty"], f"remnant_{r['roll_id']}": r["remnant_qty"]})
        vals.update(_bundles_typed(action))               # a cutting recorded from its bundles
    elif action.kind == Kind.BUNDLES:
        vals.update(_bundles_typed(action))
        for i in action.items.filter(model="production.cuttingsize", role=Role.CHANGED):
            vals[f"loss_{i.after['size_id']}"] = i.after["loss"] or ""
        vals["entry"] = str(action.doc_id or "")
    return {k: "" if v is None else str(v) for k, v in vals.items()}


def listed(user, limit=60, **filters) -> list:
    """Recorded steps the user may see, newest first, each marked `can` when the user may delete it now: only the
    newest standing step of its lot can be deleted (owner, 19 Oct 2026)."""
    rows = list(ProductionAction.objects.for_user(user).filter(**filters).select_related("created_by", "undone_by")[:limit])
    newest = dict(ProductionAction.objects.filter(lot_id__in={a.lot_id for a in rows}, undone=False)
                  .values_list("lot_id").annotate(m=Max("pk")).values_list("lot_id", "m"))
    allowed = {}
    for a in rows:
        if a.kind not in allowed:
            allowed[a.kind] = user.has_screen_perm(SCREEN[a.kind], "create")
        a.can = not a.undone and allowed[a.kind] and newest.get(a.lot_id) == a.pk
    return rows


def for_docs(user, docs) -> list:
    """The steps that recorded these documents (a challan and its receipts, say), newest first."""
    out = []
    for doc in docs:
        out += listed(user, doc_type=doc._meta.label_lower, doc_id=doc.pk)
    return sorted(out, key=lambda a: -a.pk)


def edit_url(action) -> str:
    """Where a step is entered again after it has been undone."""
    from django.urls import reverse

    from jobwork.models import JobWorkChallan, Receipt

    lot = action.lot_id
    if action.kind == Kind.FABRIC:
        return reverse("lot_fabric", args=[lot])
    if action.kind in (Kind.CUTTING, Kind.BUNDLES):
        return reverse("lot_cutting", args=[lot])
    if action.kind in (Kind.MOVE, Kind.COUNT, Kind.SPLIT):
        return f"{reverse('move_bundles')}?lot={lot}&back=1"
    if action.kind == Kind.CHALLAN:
        if JobWorkChallan.objects.filter(pk=action.doc_id, status=JobWorkChallan.Status.DRAFT).exists():
            return reverse("challan_detail", args=[action.doc_id])
        return f"{reverse('challan_new')}?lot={lot}"
    if action.kind in (Kind.APPROVAL, Kind.QC) and Receipt.objects.filter(pk=action.doc_id).exists():
        return reverse("receipt_detail", args=[action.doc_id])
    if action.kind == Kind.RECEIPT:
        for item in action.items.filter(model="jobwork.receipt"):
            return reverse("receipt_new", args=[(item.after or {}).get("challan_id")])
    return reverse("lot_detail", args=[lot])
