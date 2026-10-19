"""The one rate list (owner, 19 Oct 2026; JOB-06). A rate is who (a fabricator, or In-house) + process + rate per
piece + from date. It is the only place a process cost is set; work looks its rate up on the day it is recorded,
so a change applies only to later work (BR-12)."""
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from core.exceptions import BusinessRuleError
from jobwork.models import LabourRate, PayBasis

ZERO = Decimal("0.00")
IN_HOUSE = "In-house"


class MissingRate(BusinessRuleError):
    """No rate on the Rates screen for this who + process on this date. The work is not saved."""


def _who_name(who) -> str:
    return who.name if who is not None else IN_HOUSE


def _day(d) -> str:
    return f"{d.day} {d:%b}"


def find_rate(who, process, on_date) -> LabourRate | None:
    """The rate in force on `on_date`. `who` is the fabricator, or None for In-house."""
    qs = LabourRate.objects.filter(process=process, is_active=True, effective_from__lte=on_date)
    qs = qs.filter(party=who) if who is not None else qs.filter(party__isnull=True)
    return qs.order_by("-effective_from").first()


def rate_for(who, process, on_date) -> LabourRate:
    rate = find_rate(who, process, on_date)
    if rate is None:
        raise MissingRate(f"No rate for {_who_name(who)} — {process.name} on {_day(on_date)}. Add one on Rates.")
    return rate


def source_text(rate: LabourRate) -> str:
    d = rate.effective_from
    return f"rate from {d.day} {d:%b %Y}"


@dataclass
class RateSpec:
    """What a challan freezes from a rate: the price per piece and the pay basis."""

    price: Decimal
    pay_basis: str
    source: LabourRate | None = None


def _check(who, process, effective_from, rate, pay_basis, exclude=None):
    if pay_basis not in PayBasis.values:
        raise BusinessRuleError("Choose whether to pay on pieces accepted or pieces received.")
    if who is not None and not who.is_fabricator and not who.is_vendor:
        raise BusinessRuleError(f"{who.name} is not a fabricator or supplier.")
    if rate is None or isinstance(rate, float):
        raise BusinessRuleError("Enter the rate per piece.")
    if rate < 0:
        raise BusinessRuleError("A rate cannot be negative.")
    if effective_from is None:
        raise BusinessRuleError("Enter the date the rate applies from.")
    clash = LabourRate.objects.filter(process=process, effective_from=effective_from)
    clash = clash.filter(party=who) if who is not None else clash.filter(party__isnull=True)
    if exclude is not None:
        clash = clash.exclude(pk=exclude.pk)
    if clash.exists():
        raise BusinessRuleError(f"There is already a rate for {_who_name(who)} on {process.name} from that date.")


@transaction.atomic
def save_rate(*, who, process, effective_from, rate, pay_basis=PayBasis.ACCEPTED) -> LabourRate:
    """Add a dated rate. `who` is the fabricator, or None for In-house (in-house work has no pay basis)."""
    rate = Decimal(rate) if isinstance(rate, (int, str)) else rate
    _check(who, process, effective_from, rate, pay_basis)
    return LabourRate.objects.create(party=who, process=process, rate=rate, effective_from=effective_from,
                                     pay_basis=pay_basis)


IN_USE = "Used on work already recorded. To change it, add a new rate from a later date."


def in_use(rate) -> bool:
    """Has recorded work been paid at this rate (a challan priced at it, or in-house labour costed at it)?"""
    from production.models import LotCostEntry

    return rate.challans.exists() or LotCostEntry.objects.filter(rate=rate).exists()


@transaction.atomic
def update_rate(rate, *, rate_value, effective_from, pay_basis) -> LabourRate:
    rate = LabourRate.objects.get(pk=rate.pk)
    if in_use(rate):
        raise BusinessRuleError(IN_USE)
    _check(rate.party, rate.process, effective_from, rate_value, pay_basis, exclude=rate)
    rate.rate, rate.effective_from, rate.pay_basis = rate_value, effective_from, pay_basis
    rate.save()
    return rate


@transaction.atomic
def delete_rate(rate) -> None:
    if in_use(rate):
        raise BusinessRuleError(IN_USE)
    LabourRate.objects.filter(pk=rate.pk).delete()


def resolve(party, step, on_date) -> RateSpec:
    """The price a challan freezes for a fabricator on a lot's step. Refused when there is no rate."""
    rate = rate_for(party, step.process, on_date)
    return RateSpec(rate.rate, rate.pay_basis, rate)
