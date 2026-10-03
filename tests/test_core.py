from datetime import date
from decimal import Decimal

import pytest
from django.apps import apps
from django.test import Client
from django.utils import timezone

from core.exceptions import BusinessRuleError, PeriodLocked
from core.models import Company, Factory, FinancialYear, Location, NumberSeries, Role, User
from core.scoping import FactoryScopedModel
from core.services.factories import create_factory
from core.services.numbering import next_document_number
from core.services.periods import assert_period_open, lock_period, unlock_period
from ledger.models import Voucher
from ledger.services.posting import post_voucher
from tax.services import gst_enabled, set_tax_status, tds_enabled
from tests.conftest import BOOKS_FROM, IN_YEAR, make_user
from tests.helpers import simple_lines

D = Decimal


# ---------- numbering ----------

def test_numbers_are_sequential_per_factory_type_and_year(company, factory, factory2):
    assert next_document_number(factory=factory, doc_type="journal", on_date=IN_YEAR) == "JV/LDH1/26-27/0001"
    assert next_document_number(factory=factory, doc_type="journal", on_date=IN_YEAR) == "JV/LDH1/26-27/0002"
    assert next_document_number(factory=factory, doc_type="payment", on_date=IN_YEAR) == "PAY/LDH1/26-27/0001"
    assert next_document_number(factory=factory2, doc_type="journal", on_date=IN_YEAR) == "JV/LDH2/26-27/0001"


def test_numbering_restarts_in_a_new_financial_year(company, factory):
    FinancialYear.objects.get_or_create(
        company=company, label="27-28", defaults={"start_date": date(2027, 4, 1), "end_date": date(2028, 3, 31)}
    )
    next_document_number(factory=factory, doc_type="journal", on_date=IN_YEAR)
    assert next_document_number(factory=factory, doc_type="journal", on_date=date(2027, 5, 1)) == "JV/LDH1/27-28/0001"


def test_date_outside_any_financial_year_is_refused(company, factory):
    with pytest.raises(BusinessRuleError):
        next_document_number(factory=factory, doc_type="journal", on_date=date(2020, 1, 1))


def test_new_factory_gets_locations_and_series(company, factory2):
    assert Location.objects.filter(factory=factory2).count() == 6
    assert NumberSeries.objects.filter(factory=factory2, doc_type="journal").exists()


# ---------- period locks ----------

def test_locked_period_blocks_posting(company, factory, owner, ledgers):
    lock_period(user=owner, company=company, upto=date(2026, 6, 30))
    with pytest.raises(PeriodLocked):
        post_voucher(company=company, factory=factory, voucher_type="journal", date=IN_YEAR,
                     lines=simple_lines(ledgers), user=owner)
    assert not Voucher.objects.exists()
    post_voucher(company=company, factory=factory, voucher_type="journal", date=date(2026, 7, 1),
                 lines=simple_lines(ledgers), user=owner)


def test_factory_lock_only_affects_that_factory(company, factory, factory2, owner):
    lock_period(user=owner, company=company, factory=factory, upto=date(2026, 6, 30))
    with pytest.raises(PeriodLocked):
        assert_period_open(company, factory, IN_YEAR)
    assert_period_open(company, factory2, IN_YEAR)


def test_only_owner_can_unlock_and_it_is_logged(company, owner, accountant):
    from core.models import PeriodLockLog

    lock_period(user=accountant, company=company, upto=date(2026, 6, 30))
    with pytest.raises(BusinessRuleError):
        unlock_period(user=accountant, company=company, new_upto=None, reason="need to fix")
    with pytest.raises(BusinessRuleError):
        unlock_period(user=owner, company=company, new_upto=None, reason=" ")
    unlock_period(user=owner, company=company, new_upto=date(2026, 5, 31), reason="Audit adjustment")
    assert_period_open(company, None, date(2026, 6, 15))
    assert list(PeriodLockLog.objects.values_list("action", flat=True)) == ["unlock", "lock"]


# ---------- factory scoping (BR-23) ----------

def test_every_factory_scoped_model_uses_the_scoped_manager():
    scoped = [m for m in apps.get_models() if issubclass(m, FactoryScopedModel)]
    assert scoped, "expected at least Voucher and VoucherLine"
    for model in scoped:
        assert hasattr(model.objects, "for_user"), model


def test_user_sees_only_assigned_factories(company, factory, factory2, owner, accountant, ledgers):
    post_voucher(company=company, factory=factory, voucher_type="journal", date=IN_YEAR,
                 lines=simple_lines(ledgers), user=owner)
    post_voucher(company=company, factory=factory2, voucher_type="journal", date=IN_YEAR,
                 lines=simple_lines(ledgers), user=owner)
    assert list(Factory.objects.for_user(accountant)) == [factory]
    assert Voucher.objects.for_user(accountant).count() == 1
    assert Voucher.objects.for_user(accountant).get().factory == factory
    assert Voucher.objects.for_user(owner).count() == 2
    from django.contrib.auth.models import AnonymousUser

    assert Voucher.objects.for_user(AnonymousUser()).count() == 0


def test_superuser_and_all_factory_flag_see_future_factories(company, factory, owner, admin_user):
    new = create_factory(company=company, code="LDH9", name="New", state_code="03")
    assert new in Factory.objects.for_user(owner) and new in Factory.objects.for_user(admin_user)


# ---------- permissions ----------

def test_role_permissions_are_checked_against_the_database(company, accountant, factory):
    assert accountant.has_screen_perm("ledger.voucher", "create")
    assert not accountant.has_screen_perm("core.user", "view")
    role = Role.objects.get(name="Accountant")
    role.permissions.filter(screen="ledger.voucher", action="create").delete()
    assert not accountant.has_screen_perm("ledger.voucher", "create")  # effective at next check


def test_sensitive_fields_hidden_unless_granted(company, owner, accountant):
    clerk = make_user("clerk")
    clerk.roles.add(Role.objects.get(name="Production Supervisor"))  # production never sees MTO customer phone (BR-15)
    assert owner.can_view_field("cost") and accountant.can_view_field("margin")
    assert not clerk.can_view_field("cost") and not clerk.can_view_field("customer_phone")


def test_deactivated_user_cannot_log_in_but_history_stays(company, accountant):
    c = Client()
    assert c.login(username="accountant", password="pw-for-tests-1")
    c.logout()
    accountant.is_active = False
    accountant.save()
    assert not Client().login(username="accountant", password="pw-for-tests-1")
    assert User.objects.filter(pk=accountant.pk).exists() and accountant.history.count() >= 2


def test_lockout_after_repeated_failures_blocks_even_the_right_password(company, accountant, settings):
    c = Client()
    for _ in range(settings.LOGIN_MAX_FAILURES):
        assert not c.login(username="accountant", password="wrong")
    assert not c.login(username="accountant", password="pw-for-tests-1")
    accountant.refresh_from_db()
    assert accountant.is_locked()
    User.objects.filter(pk=accountant.pk).update(locked_until=timezone.now() - timezone.timedelta(minutes=1))
    assert c.login(username="accountant", password="pw-for-tests-1")


def test_login_activity_is_logged(company, accountant):
    from core.models import AuditEvent

    c = Client()
    c.login(username="accountant", password="bad")
    c.login(username="accountant", password="pw-for-tests-1")
    events = set(AuditEvent.objects.values_list("event", flat=True))
    assert {"failed", "login"} <= events


# ---------- tax switches (E1.9) ----------

def test_gst_and_tds_are_independent_and_effective_dated(company, factory):
    assert not gst_enabled(company, IN_YEAR) and not tds_enabled(company, IN_YEAR)
    set_tax_status(company=company, kind="gst", enabled=True, effective_from=date(2026, 7, 1),
                   registration_number="03ABCDE1234F1Z5")
    assert not gst_enabled(company, date(2026, 6, 30))  # earlier documents untouched
    assert gst_enabled(company, date(2026, 7, 1))
    assert not tds_enabled(company, date(2026, 8, 1))
    set_tax_status(company=company, kind="gst", enabled=False, effective_from=date(2026, 10, 1))
    assert gst_enabled(company, date(2026, 9, 30)) and not gst_enabled(company, date(2026, 10, 1))


def test_factory_setting_overrides_company_setting(company, factory, factory2):
    set_tax_status(company=company, kind="gst", enabled=True, effective_from=BOOKS_FROM,
                   registration_number="03ABCDE1234F1Z5")
    set_tax_status(company=company, kind="gst", enabled=False, effective_from=BOOKS_FROM, factory=factory2)
    assert gst_enabled(company, IN_YEAR, factory) and not gst_enabled(company, IN_YEAR, factory2)


def test_gst_on_requires_a_valid_gstin(company):
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        set_tax_status(company=company, kind="gst", enabled=True, effective_from=BOOKS_FROM)
    with pytest.raises(ValidationError):
        set_tax_status(company=company, kind="gst", enabled=True, effective_from=BOOKS_FROM,
                       registration_number="BADGSTIN")


def test_nothing_in_the_seed_posts_to_tax_ledgers(company):
    from ledger.models import VoucherLine

    assert not VoucherLine.objects.exists()
