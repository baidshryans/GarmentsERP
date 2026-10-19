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


def test_inhouse_cost_entry_records_rate_and_qty(company, factory, owner):
    ns = build(company, factory, owner)
    set_inhouse_rate("CUT", "1.50")
    cut(ns)
    entry = LotCostEntry.objects.get(lot=ns.lot, kind="labour")
    assert (entry.qty, entry.rate.rate, entry.amount) == (100, D("1.50"), D("150.00"))


# ---------------- the Rates screen (Task 4) ----------------

from django.test import Client
from django.urls import reverse

from core.models import Role
from jobwork.models import LabourRate
from tests.conftest import make_user


def _client(user):
    c = Client()
    c.force_login(user)
    return c


def test_rates_screen_groups_by_process_with_in_house_first(company, factory, owner, fab, process):
    rates.save_rate(who=fab, process=process, effective_from=DAY, rate=D("12"))
    rates.save_rate(who=None, process=process, effective_from=DAY, rate=D("9"))
    page = _client(owner).get(reverse("rate_list")).content.decode()
    assert page.index("In-house") < page.index(fab.name)
    assert "<h1 class=\"page-title\">Rates</h1>" in page


def test_production_roles_do_not_see_rates(company, factory):
    sup = make_user("sup")
    sup.roles.add(Role.objects.get(name="Production Supervisor"))
    sup.allowed_factories.add(factory)
    assert _client(sup).get(reverse("rate_list")).status_code == 403


def test_an_unused_rate_can_be_edited_and_deleted(company, owner, fab, process):
    r = rates.save_rate(who=fab, process=process, effective_from=DAY, rate=D("12"))
    c = _client(owner)
    resp = c.post(reverse("rate_edit", args=[r.pk]), {"rate": "13", "effective_from": DAY.isoformat(), "pay_basis": "accepted"})
    assert resp.status_code == 302 and LabourRate.objects.get(pk=r.pk).rate == D("13")
    resp = c.post(reverse("rate_delete", args=[r.pk]))
    assert resp.status_code == 302 and not LabourRate.objects.filter(pk=r.pk).exists()


def test_edit_and_delete_refused_once_used(company, factory, owner):
    from tests.prod_helpers import build, cut, set_inhouse_rate

    ns = build(company, factory, owner)
    set_inhouse_rate("CUT", "1.50")
    cut(ns)                                                   # the cutting used the In-house cutting rate
    used = LabourRate.objects.get(party__isnull=True, process__code="CUT")
    assert rates.in_use(used)
    with pytest.raises(BusinessRuleError, match="Used on work already recorded"):
        rates.update_rate(used, rate_value=D("2"), effective_from=used.effective_from, pay_basis="accepted")
    with pytest.raises(BusinessRuleError, match="Used on work already recorded"):
        rates.delete_rate(used)
    page = _client(owner).get(reverse("rate_list")).content.decode()
    assert "Used on work already recorded. To change it, add a new rate from a later date." in page


def test_menu_says_rates(company, owner):
    page = _client(owner).get(reverse("home")).content.decode()
    assert ">Rates<" in page and "Labour rates" not in page


def test_bom_has_no_charges(company):
    from masters import models as m

    assert not hasattr(m, "BomCharge")
