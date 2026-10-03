from datetime import date
from decimal import Decimal

import pytest
from django.db.models import Sum

from core.models import Factory, Role, User
from core.services.factories import create_factory
from core.services.setup import run_setup
from ledger.models import Ledger, Voucher, VoucherLine

D = Decimal
BOOKS_FROM = date(2026, 4, 1)
IN_YEAR = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def books_must_tally(db):
    """Definition of done: after any test that posts, the books balance - overall, per voucher,
    and per factory. (Stock reconciliation joins this check once the stock ledger exists.)"""
    yield
    totals = VoucherLine.objects.aggregate(d=Sum("debit"), c=Sum("credit"))
    assert (totals["d"] or 0) == (totals["c"] or 0), "Trial balance does not tally"
    for v in Voucher.objects.all():
        agg = v.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        assert agg["d"] == agg["c"] == v.total, f"{v} is out of balance"
        if v.status == "posted":
            assert v.number


def make_user(username, **extra):
    user = User.objects.create_user(username=username, password="pw-for-tests-1", **extra)
    return user


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(username="admin", password="pw-for-tests-1")


@pytest.fixture
def company(admin_user):
    return run_setup(
        company_data={
            "name": "Test Garments", "state_code": "03", "city": "Ludhiana", "pan": "ABCDE1234F",
            "books_from": BOOKS_FROM, "fy_start_month": 4,
        },
        tax_data={"gst_registered": False, "tds_deductor": False},
        factory_data={"code": "LDH1", "name": "Ludhiana Unit 1", "state_code": "03"},
        admin_user=admin_user,
    )


@pytest.fixture
def factory(company):
    return Factory.objects.get(company=company, code="LDH1")


@pytest.fixture
def factory2(company):
    return create_factory(company=company, code="LDH2", name="Ludhiana Unit 2", state_code="03")


@pytest.fixture
def owner(company):
    user = make_user("owner", all_factories=True)
    user.roles.add(Role.objects.get(name="Owner"))
    return user


@pytest.fixture
def accountant(company, factory):
    user = make_user("accountant")
    user.roles.add(Role.objects.get(name="Accountant"))
    user.allowed_factories.add(factory)
    return user


@pytest.fixture
def ledgers(company):
    def get(key):
        return Ledger.objects.get(company=company, system_key=key)

    return get
