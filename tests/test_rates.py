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


# ---------------- in-house work looks its rate up on Rates (Task 2) ----------------

from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from production.models import CuttingEntry, LotCostEntry
from production.services import costing
from tests.prod_helpers import build, cut, go, set_inhouse_rate, step


def test_cutting_uses_inhouse_rate(company, factory, owner):
    ns = build(company, factory, owner)
    set_inhouse_rate("CUT", "1.50")
    cut(ns)                                                   # 100 pieces cut
    assert costing.cost_breakdown(ns.lot)["labour"] == D("150.00")


def test_cutting_refused_without_inhouse_rate(company, factory, owner):
    from jobwork.models import LabourRate

    ns = build(company, factory, owner)
    LabourRate.objects.filter(party__isnull=True, process__code="CUT").delete()
    with pytest.raises(rates.MissingRate, match="No rate for In-house — Cutting"):
        cut(ns)
    assert not CuttingEntry.objects.filter(lot=ns.lot).exists()


def test_rework_bundle_moving_on_accrues_nothing(company, factory, owner):
    ns = build(company, factory, owner)
    for s in ns.lot.steps.all():
        s.assignment, s.party, s.factory = "in_house", None, factory
        s.save()
    set_inhouse_rate("STITCH", "10")
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    go(ns, bundles, "IRON")                                   # stitching paid: 100 x 10
    go(ns, bundles[:1], "STITCH", reason="Redo")
    before = costing.cost_breakdown(ns.lot)["labour"]
    go(ns, bundles[:1], "IRON")                               # the redone stitching is not paid again
    assert costing.cost_breakdown(ns.lot)["labour"] == before


def test_route_and_lot_steps_carry_no_rate():
    from masters.models import RouteStep
    from production.models import LotStep

    names = {f.name for f in RouteStep._meta.get_fields()} | {f.name for f in LotStep._meta.get_fields()}
    assert not {"rate", "rework_rate"} & names


@pytest.mark.django_db(transaction=True)
def test_migration_creates_inhouse_and_zero_rates(company, factory, owner):
    from jobwork.models import LabourRate

    build(company, factory, owner)                            # a released lot to hang a subcontracted step on
    LabourRate.objects.all().delete()                         # the old schema has no In-house rates
    before = [("jobwork", "0006_held_for_rework"), ("production", "0010_lot_cost_step_backfill"), ("masters", "0005_bomline_process")]
    ex = MigrationExecutor(connection)
    ex.migrate(before)
    old = ex.loader.project_state(before).apps
    Route, RouteStep, Process = (old.get_model("masters", m) for m in ("RouteTemplate", "RouteStep", "Process"))
    Party, LotStep, Lot = old.get_model("masters", "Party"), old.get_model("production", "LotStep"), old.get_model("production", "Lot")
    proc = {p.code: p for p in Process.objects.all()}
    for name, rate in (("R1", "10"), ("R2", "10"), ("R3", "12")):
        r = Route.objects.create(name=name)
        RouteStep.objects.create(template=r, sequence=1, process=proc["STITCH"], rate=D(rate))
        RouteStep.objects.create(template=r, sequence=2, process=proc["PACK"], rate=D("0"))
    p = Party.objects.create(company_id=company.pk, name="P Ironing", is_fabricator=True)
    lot = Lot.objects.first()
    LotStep.objects.create(lot=lot, sequence=99, process=proc["IRON"], assignment="subcontract", party=p, rate=D("3"))
    ex = MigrationExecutor(connection)
    ex.loader.build_graph()
    ex.migrate(ex.loader.graph.leaf_nodes())

    def inhouse(code):
        return LabourRate.objects.get(party__isnull=True, process__code=code).rate

    assert inhouse("STITCH") == D("10") and inhouse("PACK") == D("0") and inhouse("CUT") == D("0")
    assert LabourRate.objects.get(party_id=p.pk, process__code="IRON").rate == D("3")
