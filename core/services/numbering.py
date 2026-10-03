"""Document numbers from a counter table (database-neutral).

The increment is a single UPDATE ... SET next_number = next_number + 1 inside the caller's
transaction, so a failed posting rolls the number back too (gapless), and no row lock
(select_for_update, ignored by SQLite) is needed.
"""
from django.db import transaction
from django.db.models import F

from core.models import FinancialYear, NumberSeries

# doc_type -> default prefix. Apps add their document types here as they are built.
DEFAULT_PREFIXES = {
    "payment": "PAY",
    "receipt": "REC",
    "contra": "CNT",
    "journal": "JV",
    "sales": "SAL",
    "purchase": "PUR",
    "debit_note": "DN",
    "credit_note": "CN",
    "stock_journal": "SJ",
    "job_work_bill": "JWB",
    "payroll": "PRL",
    "opening": "OPN",
}


def register_doc_type(doc_type: str, prefix: str):
    DEFAULT_PREFIXES.setdefault(doc_type, prefix)


def get_or_create_series(*, factory, doc_type, financial_year) -> NumberSeries:
    series, _ = NumberSeries.objects.get_or_create(
        factory=factory,
        doc_type=doc_type,
        financial_year=financial_year,
        defaults={
            "company": factory.company,
            "prefix": DEFAULT_PREFIXES.get(doc_type, doc_type[:3].upper()),
        },
    )
    return series


def format_number(series: NumberSeries, number: int) -> str:
    return f"{series.prefix}/{series.factory.code}/{series.financial_year.label}/{number:0{series.padding}d}"


@transaction.atomic
def next_document_number(*, factory, doc_type: str, on_date) -> str:
    fy = FinancialYear.for_date(factory.company, on_date)
    series = get_or_create_series(factory=factory, doc_type=doc_type, financial_year=fy)
    NumberSeries.objects.filter(pk=series.pk).update(next_number=F("next_number") + 1)
    series.refresh_from_db()
    return format_number(series, series.next_number - 1)


def create_default_series(*, factory, financial_year):
    """Give a factory a series for every known document type in a financial year."""
    for doc_type in DEFAULT_PREFIXES:
        get_or_create_series(factory=factory, doc_type=doc_type, financial_year=financial_year)
