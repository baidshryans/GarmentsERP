"""First-install setup (E1.1). One atomic call creates the company, years, tax status,
first factory and every seeded group, ledger, role and default."""
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from core.models import Company, FinancialYear, Role
from core.seeding import seed_company
from core.services.factories import create_factory
from core.services.numbering import create_default_series
from tax.models import TaxSetting
from tax.services import set_tax_status


def financial_year_bounds(books_from: date, start_month: int):
    start = date(books_from.year, start_month, 1)
    if start > books_from:
        start = date(books_from.year - 1, start_month, 1)
    end = date(start.year + 1, start_month, 1) - timedelta(days=1)
    return start, end


@transaction.atomic
def ensure_financial_years(company, through: date | None = None):
    """Create every financial year from books-from up to the one containing `through` (default today)."""
    through = max(through or timezone.localdate(), company.books_from)
    start, end = financial_year_bounds(company.books_from, company.fy_start_month)
    years = []
    while start <= through:
        fy, _ = FinancialYear.objects.get_or_create(
            company=company, label=FinancialYear.label_for(start),
            defaults={"start_date": start, "end_date": end},
        )
        years.append(fy)
        start = end + timedelta(days=1)
        end = date(start.year + 1, start.month, 1) - timedelta(days=1)
    return years


@transaction.atomic
def run_setup(*, company_data, tax_data, factory_data, admin_user) -> Company:
    if Company.objects.filter(setup_complete=True).exists():
        raise RuntimeError("Setup has already been completed.")
    Company.objects.filter(setup_complete=False).delete()  # discard an abandoned attempt

    company = Company(**company_data)
    company.full_clean()
    company.save()
    years = ensure_financial_years(company)

    if tax_data.get("gst_registered"):
        set_tax_status(
            company=company, kind=TaxSetting.Kind.GST, enabled=True,
            effective_from=tax_data["gst_from"], registration_number=tax_data["gstin"],
        )
    if tax_data.get("tds_deductor"):
        set_tax_status(
            company=company, kind=TaxSetting.Kind.TDS, enabled=True,
            effective_from=tax_data["tds_from"], registration_number=tax_data.get("tan", ""),
        )

    factory = create_factory(company=company, **factory_data)
    for fy in years:
        create_default_series(factory=factory, financial_year=fy)

    seed_company(company)

    admin_user.all_factories = True
    admin_user.save(update_fields=["all_factories"])
    admin_user.roles.add(Role.objects.get(name="Owner"))

    company.setup_complete = True
    company.save(update_fields=["setup_complete"])
    return company
