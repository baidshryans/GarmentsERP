from django.db import transaction

from core.models import FinancialYear, Location
from core.services.numbering import create_default_series

DEFAULT_LOCATIONS = [
    ("Main Godown", Location.Type.GODOWN),
    ("Cutting Floor", Location.Type.CUTTING),
    ("Process Area", Location.Type.PROCESS),
    ("Dispatch", Location.Type.DISPATCH),
]


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
