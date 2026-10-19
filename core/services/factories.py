from django.db import transaction

from core.models import FinancialYear, Location
from core.services.numbering import create_default_series

# Every factory has these. Godown, Ready Goods and Rejects are the places people see (owner, 19 Oct 2026); the
# others are bookkeeping for work in progress and are never shown or chosen.
DEFAULT_LOCATIONS = [
    ("Godown", Location.Type.GODOWN),
    ("Cutting Floor", Location.Type.CUTTING),
    ("Process Area", Location.Type.PROCESS),
    ("Ready Goods", Location.Type.DISPATCH),
    ("In Transit", Location.Type.TRANSIT),
    ("Rejects", Location.Type.REJECTS),
]
DEFAULT_NAME = {loc_type: name for name, loc_type in DEFAULT_LOCATIONS}


def location_of(factory, loc_type):
    """The factory's location of this kind: the first active one. Found by kind, never by name, so the owner can
    rename it. Made with its default name if the factory has none."""
    loc = Location.objects.filter(factory=factory, loc_type=loc_type, is_active=True).order_by("id").first()
    if loc is None:
        name = DEFAULT_NAME[loc_type]
        loc = Location.objects.filter(factory=factory, name=name).first() or \
            Location.objects.create(factory=factory, name=name, loc_type=loc_type)
    return loc


def transit_location(factory):
    """Stock on the way between factories."""
    return location_of(factory, Location.Type.TRANSIT)


def cutting_location(factory):
    return location_of(factory, Location.Type.CUTTING)


def process_location(factory):
    return location_of(factory, Location.Type.PROCESS)


def godown_location(factory):
    """Where everything received lands by default."""
    return location_of(factory, Location.Type.GODOWN)


def ready_goods_location(factory):
    """Packed, finished pieces only; sales and dispatch take from here."""
    return location_of(factory, Location.Type.DISPATCH)


dispatch_location = ready_goods_location


def rejects_location(factory):
    return location_of(factory, Location.Type.REJECTS)


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
