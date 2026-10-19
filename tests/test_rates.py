"""The one rate list (19 Oct 2026): a rate is who (a fabricator, or In-house) + process + rate per piece + from date."""
from datetime import date, timedelta

import pytest

from core.exceptions import BusinessRuleError
from jobwork.services import rates
from masters.models import Process
from tests.prod_helpers import D, fabricator

DAY = date(2026, 6, 15)


@pytest.fixture
def process(company):
    return Process.objects.get(code="STITCH")


@pytest.fixture
def fab(company):
    return fabricator(company)


def test_inhouse_rate_found_with_who_none(process):
    r = rates.save_rate(who=None, process=process, effective_from=DAY, rate=D("1.50"))
    assert rates.rate_for(None, process, DAY) == r


def test_missing_rate_names_who_process_and_date(fab, process):
    with pytest.raises(rates.MissingRate) as exc:
        rates.rate_for(fab, process, DAY)
    assert str(exc.value) == f"No rate for {fab.name} — {process.name} on 15 Jun. Add one on Rates."


def test_inhouse_missing_rate_message(process):
    with pytest.raises(rates.MissingRate) as exc:
        rates.rate_for(None, process, DAY)
    assert str(exc.value).startswith(f"No rate for In-house — {process.name}")


def test_missing_rate_is_a_business_rule_error():
    assert issubclass(rates.MissingRate, BusinessRuleError)


def test_later_rate_does_not_apply_before_its_date(fab, process):
    rates.save_rate(who=fab, process=process, effective_from=DAY, rate=D("12"))
    rates.save_rate(who=fab, process=process, effective_from=DAY + timedelta(days=5), rate=D("13"))
    assert rates.rate_for(fab, process, DAY + timedelta(days=4)).rate == D("12")
    assert rates.rate_for(fab, process, DAY + timedelta(days=5)).rate == D("13")


def test_inhouse_and_fabricator_rates_are_kept_apart(fab, process):
    rates.save_rate(who=None, process=process, effective_from=DAY, rate=D("9"))
    rates.save_rate(who=fab, process=process, effective_from=DAY, rate=D("12"))
    assert rates.rate_for(None, process, DAY).rate == D("9")
    assert rates.rate_for(fab, process, DAY).rate == D("12")


def test_zero_rate_allowed_negative_refused(process):
    rates.save_rate(who=None, process=process, effective_from=DAY, rate=D("0"))
    with pytest.raises(BusinessRuleError):
        rates.save_rate(who=None, process=process, effective_from=DAY + timedelta(days=1), rate=D("-1"))


def test_two_inhouse_rates_on_the_same_date_refused(process):
    rates.save_rate(who=None, process=process, effective_from=DAY, rate=D("1"))
    with pytest.raises(BusinessRuleError):
        rates.save_rate(who=None, process=process, effective_from=DAY, rate=D("2"))


def test_source_text(process):
    r = rates.save_rate(who=None, process=process, effective_from=date(2026, 10, 1), rate=D("1.50"))
    assert rates.source_text(r) == "rate from 1 Oct 2026"
