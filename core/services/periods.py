"""Period locks (BR-20 / E9.9). Locked periods block posting; unlock needs owner approval and is logged."""
from django.db import transaction
from django.db.models import Q

from core.exceptions import BusinessRuleError, PeriodLocked
from core.models import PeriodLock, PeriodLockLog

LOCK_SCREEN = "core.period_lock"


def locked_upto(company, factory=None):
    """Latest locked date that applies to this factory (a company-wide lock applies to all)."""
    qs = PeriodLock.objects.filter(company=company).filter(Q(factory__isnull=True) | Q(factory=factory))
    dates = list(qs.values_list("locked_upto", flat=True))
    return max(dates) if dates else None


def assert_period_open(company, factory, on_date):
    limit = locked_upto(company, factory)
    if limit is not None and on_date <= limit:
        raise PeriodLocked(f"The period up to {limit:%d-%b-%Y} is locked; {on_date:%d-%b-%Y} cannot be posted.")


@transaction.atomic
def lock_period(*, user, company, upto, factory=None, reason="Period locked after filing"):
    if not user.has_screen_perm(LOCK_SCREEN, "edit"):
        raise BusinessRuleError("You may not lock periods.")
    lock = PeriodLock.objects.filter(company=company, factory=factory).first()
    previous = lock.locked_upto if lock else None
    if previous and upto <= previous:
        raise BusinessRuleError("The period is already locked up to that date; use unlock to reopen.")
    PeriodLock.objects.update_or_create(company=company, factory=factory, defaults={"locked_upto": upto})
    PeriodLockLog.objects.create(
        company=company, factory=factory, action="lock", previous_upto=previous,
        new_upto=upto, user=user, reason=reason,
    )


@transaction.atomic
def unlock_period(*, user, company, new_upto, reason, factory=None):
    """Move the lock back to new_upto (None removes it). Owner approval permission required."""
    if not user.has_screen_perm(LOCK_SCREEN, "approve"):
        raise BusinessRuleError("Only the owner can unlock a period.")
    if not reason or not reason.strip():
        raise BusinessRuleError("A reason is required to unlock a period.")
    lock = PeriodLock.objects.filter(company=company, factory=factory).first()
    if lock is None:
        raise BusinessRuleError("There is no lock to remove.")
    previous = lock.locked_upto
    if new_upto is not None and new_upto >= previous:
        raise BusinessRuleError("Unlocking must move the lock to an earlier date.")
    if new_upto is None:
        lock.delete()
    else:
        lock.locked_upto = new_upto
        lock.save()
    PeriodLockLog.objects.create(
        company=company, factory=factory, action="unlock", previous_upto=previous,
        new_upto=new_upto, user=user, reason=reason.strip(),
    )
