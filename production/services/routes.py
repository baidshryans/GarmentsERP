"""Changing a lot's route mid-way (E7.3, E7.2). Steps that have not started can be added, removed, skipped (if
optional), reordered or reassigned. Every change is logged with who and why."""
from decimal import Decimal

from django.db import transaction

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from production.models import Lot, LotRouteChange, LotStep


def _check(lot, user, reason):
    assert_factory_access(user, lot.factory)
    if lot.status in (Lot.Status.COMPLETED, Lot.Status.CLOSED):
        raise BusinessRuleError("This lot is finished; its route can no longer change.")
    if not reason or not reason.strip():
        raise BusinessRuleError("Give a reason for the route change.")


def _log(lot, action, detail, reason, user):
    LotRouteChange.objects.create(lot=lot, action=action, detail=detail[:255], reason=reason.strip()[:255], user=user)


def _renumber(lot, ordered):
    """Give steps the sequence 1..n in the given order without tripping the unique constraint."""
    for i, step in enumerate(ordered, start=1):
        LotStep.objects.filter(pk=step.pk).update(sequence=1000 + i)
    for i, step in enumerate(ordered, start=1):
        LotStep.objects.filter(pk=step.pk).update(sequence=i)


STARTED = (LotStep.Status.IN_PROGRESS, LotStep.Status.DONE)


def _movable(step):
    if step.status in STARTED:
        raise BusinessRuleError(f"{step.process.name} has already started and cannot be changed (E7.2).")


def _validate_assignment(assignment, factory, party):
    if assignment == LotStep.Assignment.IN_HOUSE:
        if party is not None:
            raise BusinessRuleError("An in-house step cannot have a fabricator.")
    else:
        if factory is not None:
            raise BusinessRuleError("A subcontracted step cannot have a factory.")
        if party is not None and not party.is_fabricator:
            raise BusinessRuleError(f"{party.name} is not marked as a fabricator.")


@transaction.atomic
def add_step(lot, *, process, after_sequence, user, reason, assignment="in_house", factory=None, party=None,
             rate=Decimal("0.00"), is_mandatory=True) -> LotStep:
    lot = Lot.objects.get(pk=lot.pk)
    _check(lot, user, reason)
    _validate_assignment(assignment, factory, party)
    steps = list(lot.steps.order_by("sequence"))
    if any(s.sequence > after_sequence and s.status in STARTED for s in steps):
        raise BusinessRuleError("A step cannot be inserted before one that has already started.")
    new = LotStep.objects.create(
        lot=lot, sequence=999, process=process, assignment=assignment, factory=factory or (lot.factory if assignment == "in_house" else None),
        party=party, rate=rate, is_mandatory=is_mandatory)
    ordered = [s for s in steps if s.sequence <= after_sequence] + [new] + [s for s in steps if s.sequence > after_sequence]
    _renumber(lot, ordered)
    _log(lot, "added", f"Added {process.name} after step {after_sequence}", reason, user)
    return LotStep.objects.get(pk=new.pk)


@transaction.atomic
def remove_step(step, *, user, reason):
    step = LotStep.objects.select_related("lot", "process").get(pk=step.pk)
    _check(step.lot, user, reason)
    _movable(step)
    lot, name = step.lot, step.process.name
    if step.challans.exists():
        raise BusinessRuleError("A job work challan exists for this step; it cannot be removed.")
    step.delete()
    _renumber(lot, list(lot.steps.order_by("sequence")))
    _log(lot, "removed", f"Removed {name}", reason, user)


@transaction.atomic
def skip_step(step, *, user, reason):
    step = LotStep.objects.select_related("lot", "process").get(pk=step.pk)
    _check(step.lot, user, reason)
    _movable(step)
    if step.is_mandatory:
        raise BusinessRuleError(f"{step.process.name} is mandatory; only optional steps can be skipped.")
    step.status = LotStep.Status.SKIPPED
    step.save(update_fields=["status"])
    _log(step.lot, "skipped", f"Skipped {step.process.name}", reason, user)


@transaction.atomic
def reorder_step(step, *, new_sequence, user, reason):
    step = LotStep.objects.select_related("lot", "process").get(pk=step.pk)
    lot = step.lot
    _check(lot, user, reason)
    steps = list(lot.steps.order_by("sequence"))
    if not 1 <= new_sequence <= len(steps):
        raise BusinessRuleError("That position does not exist on the route.")
    lo, hi = sorted((step.sequence, new_sequence))
    for s in steps:
        if lo <= s.sequence <= hi:
            _movable(s)
    steps.remove(next(s for s in steps if s.pk == step.pk))
    steps.insert(new_sequence - 1, step)
    _renumber(lot, steps)
    _log(lot, "reordered", f"Moved {step.process.name} to position {new_sequence}", reason, user)


@transaction.atomic
def reassign_step(step, *, user, reason, assignment, factory=None, party=None, rate=None, rework_rate=None):
    step = LotStep.objects.select_related("lot", "process").get(pk=step.pk)
    _check(step.lot, user, reason)
    _movable(step)
    _validate_assignment(assignment, factory, party)
    step.assignment = assignment
    step.factory = (factory or step.lot.factory) if assignment == "in_house" else None
    step.party = party if assignment == "subcontract" else None
    if rate is not None:
        step.rate = rate
    if rework_rate is not None:
        step.rework_rate = rework_rate
    step.save()
    where = step.factory.code if step.factory else (step.party.name if step.party else "subcontractor to be chosen")
    _log(step.lot, "reassigned", f"{step.process.name}: {step.get_assignment_display()} ({where}), rate {step.rate}", reason, user)
    return step
