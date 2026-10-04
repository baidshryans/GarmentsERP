from datetime import date
from decimal import Decimal

import pytest
from django.db.models import Sum

from core.models import Factory, Role, User
from core.services.factories import create_factory
from core.services.setup import run_setup
from ledger.models import Ledger, Voucher, VoucherLine
from ledger.selectors import q2

D = Decimal
BOOKS_FROM = date(2026, 4, 1)
IN_YEAR = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def books_must_tally(db, request):
    """Definition of done: after any test that posts, the books balance - overall, per voucher,
    and per factory. (Stock reconciliation joins this check once the stock ledger exists.)"""
    yield
    totals = VoucherLine.objects.aggregate(d=Sum("debit"), c=Sum("credit"))
    assert q2(totals["d"]) == q2(totals["c"]), "Trial balance does not tally"
    for v in Voucher.objects.all():
        agg = v.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        assert q2(agg["d"]) == q2(agg["c"]) == v.total, f"{v} is out of balance"
        if v.status == "posted":
            assert v.number
    for f in Factory.objects.all():  # factory-wise books tally too (ACC-13)
        agg = VoucherLine.objects.filter(factory=f).aggregate(d=Sum("debit"), c=Sum("credit"))
        assert q2(agg["d"]) == q2(agg["c"]), f"Factory {f.code} does not tally"
    _stock_reconciles(check_gl=request.node.get_closest_marker("raw_stock") is None)


def _stock_reconciles(check_gl=True):
    """Definition of done: stock reconciles. Movements = balances, rolls = item balances, and stock value = GL."""
    from inventory.models import RollBalance, StockBalance, StockMovement

    for bal in StockBalance.objects.all():
        agg = StockMovement.objects.filter(location=bal.location, material=bal.material, sku=bal.sku).aggregate(
            q=Sum("qty"), v=Sum("value"))
        assert (q2(agg["q"]), q2(agg["v"])) == (bal.qty.quantize(Decimal("0.01")), bal.value), f"Balance drift at {bal.location}"
    for rb in RollBalance.objects.all():
        agg = StockMovement.objects.filter(roll=rb.roll, location=rb.location).aggregate(q=Sum("qty"), v=Sum("value"))
        assert (q2(agg["q"]), q2(agg["v"])) == (rb.qty.quantize(Decimal("0.01")), rb.value), f"Roll drift {rb.roll}"
    for bal in StockBalance.objects.filter(material__kind="fabric"):
        agg = RollBalance.objects.filter(location=bal.location, roll__material=bal.material).aggregate(q=Sum("qty"), v=Sum("value"))
        assert (q2(agg["q"]), q2(agg["v"])) == (bal.qty.quantize(Decimal("0.01")), bal.value), "Rolls do not add up to the item"
    _production_reconciles(check_gl)
    for f in Factory.objects.all() if check_gl else []:
        for key, field in (("stock_raw_material", "material"), ("stock_finished", "sku")):
            held = StockBalance.objects.filter(factory=f, **{f"{field}__isnull": False}).aggregate(v=Sum("value"))["v"]
            gl = VoucherLine.objects.filter(factory=f, voucher__status="posted", ledger__system_key=key).aggregate(
                d=Sum("debit"), c=Sum("credit"))
            assert q2(held) == q2(gl["d"]) - q2(gl["c"]), f"Stock value differs from the {key} ledger in {f.code}"


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


def _production_reconciles(check_gl):
    """Pieces in bundles equal the WIP stock quantities, and each factory's lot cost equals its WIP ledger."""
    from inventory.models import StockBalance
    from inventory.services.stock import QTY_ONLY_TYPES
    from production.models import Bundle
    from production.services.costing import check_wip_reconciles

    wip_types = [t for t in QTY_ONLY_TYPES if t != "rejects"]
    held = {}
    for b in Bundle.objects.filter(status__in=Bundle.LIVE):
        held[(b.location_id, b.sku_id)] = held.get((b.location_id, b.sku_id), 0) + b.qty
    for bal in StockBalance.objects.filter(sku__isnull=False, location__loc_type__in=wip_types):
        assert int(bal.qty) == held.pop((bal.location_id, bal.sku_id), 0), f"Bundles and WIP stock differ at {bal.location}"
    assert not held, f"Bundles with no WIP stock record: {held}"
    if check_gl:
        from core.models import Company

        for company in Company.objects.all():
            assert not check_wip_reconciles(company), "Lot cost differs from the WIP ledger"


@pytest.fixture(autouse=True)
def pick_first_factory_on_login(monkeypatch):
    """A logged-in test client starts in the user's first allowed factory, as if chosen at the picker.
    Tests of the picker itself (test_active_factory.py) clear it with `client.session` changes."""
    from django.test import Client
    from core.services.active_factory import SESSION_KEY, allowed_factories

    original = Client.force_login

    def force_login(self, user, backend=None):
        original(self, user, backend)
        first = allowed_factories(user).first()
        if first:
            session = self.session
            session[SESSION_KEY] = str(first.pk)
            session.save()

    monkeypatch.setattr(Client, "force_login", force_login)
