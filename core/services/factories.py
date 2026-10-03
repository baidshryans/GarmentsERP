from django.db import transaction

from core.models import FinancialYear, Location
from core.services.numbering import create_default_series

DEFAULT_LOCATIONS = [
    ("Main Godown", Location.Type.GODOWN),
    ("Cutting Floor", Location.Type.CUTTING),
    ("Process Area", Location.Type.PROCESS),
    ("Dispatch", Location.Type.DISPATCH),
    ("In Transit", Location.Type.TRANSIT),
    ("Rejects", Location.Type.REJECTS),
]


def transit_location(factory):
    """The factory's In Transit location (stock moving between factories). Created on first use for older factories."""
    loc, _ = Location.objects.get_or_create(
        factory=factory, name="In Transit", defaults={"loc_type": Location.Type.TRANSIT}
    )
    return loc


def _get(factory, name, loc_type, **extra):
    loc, _ = Location.objects.get_or_create(factory=factory, name=name, defaults={"loc_type": loc_type, **extra})
    return loc


def cutting_location(factory):
    return _get(factory, "Cutting Floor", Location.Type.CUTTING)


def process_location(factory):
    return _get(factory, "Process Area", Location.Type.PROCESS)


def godown_location(factory):
    return _get(factory, "Main Godown", Location.Type.GODOWN)


def dispatch_location(factory):
    return _get(factory, "Dispatch", Location.Type.DISPATCH)


def rejects_location(factory):
    return _get(factory, "Rejects", Location.Type.REJECTS)


def fabricator_location(factory, party):
    """Where a fabricator's work in progress sits, one per issuing factory (PRD section 4: a location can be a party's premises)."""
    loc, _ = Location.objects.get_or_create(
        factory=factory, party=party, loc_type=Location.Type.FABRICATOR,
        defaults={"name": f"At {party.name}"[:100]},
    )
    return loc


@transaction.atomic
def create_factory(*, company, code, name, state_code, address="", city="", gstin=""):
    """New factory with default locations and number series for every open financial year (E1.4)."""
    from core.models import Factory

    factory = Factory(
        company=company, code=code.strip().upper(), name=name, state_code=state_code,
        address=address, city=city, gstin=gstin.strip().upper(),
    )
    factory.full_clean()
    factory.save()
    for loc_name, loc_type in DEFAULT_LOCATIONS:
        Location.objects.create(factory=factory, name=loc_name, loc_type=loc_type)
    for fy in FinancialYear.objects.filter(company=company, is_closed=False):
        create_default_series(factory=factory, financial_year=fy)
    return factory
