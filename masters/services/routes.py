"""Route templates (E2.3). A route is an ordered list of processes, each mandatory or optional,
with a default in-house or subcontracted assignment and rate."""
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from core.exceptions import BusinessRuleError
from masters.models import RouteStep, RouteTemplate


@dataclass
class StepSpec:
    process: object
    is_mandatory: bool = True
    assignment: str = RouteStep.Assignment.IN_HOUSE
    default_factory: object | None = None
    default_party: object | None = None
    rate: Decimal = Decimal("0.00")


@transaction.atomic
def save_route(*, name, steps, template=None, is_active=True) -> RouteTemplate:
    steps = list(steps)
    if not steps:
        raise BusinessRuleError("A route needs at least one step.")
    for i, s in enumerate(steps, start=1):
        if s.rate < 0:
            raise BusinessRuleError(f"Step {i}: the rate cannot be negative.")
        if s.assignment == RouteStep.Assignment.IN_HOUSE and s.default_party:
            raise BusinessRuleError(f"Step {i}: an in-house step cannot have a default subcontractor.")
        if s.assignment == RouteStep.Assignment.SUBCONTRACT and s.default_factory:
            raise BusinessRuleError(f"Step {i}: a subcontracted step cannot have a default factory.")
        if s.default_party and not s.default_party.is_fabricator:
            raise BusinessRuleError(f"Step {i}: {s.default_party.name} is not marked as a fabricator.")
    if template is None:
        template = RouteTemplate(name=name)
    template.name = name
    template.is_active = is_active
    template.full_clean()
    template.save()
    template.steps.all().delete()
    for i, s in enumerate(steps, start=1):
        RouteStep.objects.create(
            template=template, sequence=i, process=s.process, is_mandatory=s.is_mandatory,
            assignment=s.assignment, default_factory=s.default_factory, default_party=s.default_party, rate=s.rate,
        )
    return template
