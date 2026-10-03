"""Labour rates (JOB-06). A rate is looked up by date, so a change applies only to challans issued after it (BR-12)."""
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from core.exceptions import BusinessRuleError
from jobwork.models import LabourRate, LabourRateAddon, LabourRateSize

ZERO = Decimal("0.00")


@dataclass
class RateSpec:
    """What a challan needs from a rate: the type, a per-size (or flat) amount, and the rework charge."""

    rate_type: str
    per_piece: dict  # {size_id: rate}; key None = every size
    flat: Decimal
    rework: Decimal
    source: object | None = None

    def for_size(self, size):
        return self.per_piece.get(size.pk, self.per_piece.get(None, ZERO))


def find_rate(party, process, on_date):
    return (LabourRate.objects.filter(party=party, process=process, is_active=True, effective_from__lte=on_date)
            .order_by("-effective_from").first())


def resolve(party, step, on_date) -> RateSpec:
    """The rate for a fabricator on a lot's step: their labour rate if they have one, else the step's own rate."""
    rate = find_rate(party, step.process, on_date)
    if rate is None:
        return RateSpec("A", {None: step.rate}, ZERO, step.rework_rate)
    if rate.rate_type == LabourRate.Type.PER_PIECE:
        return RateSpec("A", {None: rate.base_rate}, ZERO, rate.rework_rate, rate)
    if rate.rate_type == LabourRate.Type.ADDONS:
        total = rate.base_rate + sum((a.amount for a in rate.addons.all()), ZERO)
        return RateSpec("B", {None: total}, ZERO, rate.rework_rate, rate)
    if rate.rate_type == LabourRate.Type.SIZE_WISE:
        return RateSpec("C", {s.size_id: s.amount for s in rate.sizes.all()}, ZERO, rate.rework_rate, rate)
    return RateSpec("D", {None: ZERO}, rate.flat_amount, rate.rework_rate, rate)


@transaction.atomic
def save_rate(*, party, process, rate_type, effective_from, base_rate=ZERO, flat_amount=ZERO, rework_rate=ZERO,
              addons=(), size_rates=None) -> LabourRate:
    """Add a dated rate. addons = [(name, amount)] for type B; size_rates = {Size: amount} for type C."""
    if not party.is_fabricator and not party.is_vendor:
        raise BusinessRuleError(f"{party.name} is not a fabricator or vendor.")
    if rate_type == LabourRate.Type.PER_PIECE and base_rate <= 0:
        raise BusinessRuleError("Enter the rate per piece.")
    if rate_type == LabourRate.Type.ADDONS and (base_rate <= 0 or not addons):
        raise BusinessRuleError("Type B needs a base rate and at least one add-on.")
    if rate_type == LabourRate.Type.SIZE_WISE and not size_rates:
        raise BusinessRuleError("Type C needs a rate for each size.")
    if rate_type == LabourRate.Type.FLAT and flat_amount <= 0:
        raise BusinessRuleError("Enter the flat amount per lot.")
    if LabourRate.objects.filter(party=party, process=process, effective_from=effective_from).exists():
        raise BusinessRuleError("There is already a rate for this fabricator and process from that date.")
    rate = LabourRate.objects.create(party=party, process=process, rate_type=rate_type, base_rate=base_rate,
                                     flat_amount=flat_amount, rework_rate=rework_rate, effective_from=effective_from)
    for name, amount in addons:
        LabourRateAddon.objects.create(rate=rate, name=name, amount=amount)
    for size, amount in (size_rates or {}).items():
        LabourRateSize.objects.create(rate=rate, size=size, amount=amount)
    return rate
