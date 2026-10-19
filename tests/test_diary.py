"""The lot page reads as a diary (owner, 19 Oct 2026): every step recorded, oldest first, in plain words, the newest
with Change and Delete. Once cutting starts the processes are fixed; only who does a step is chosen, when the work
is sent."""
import pytest
from django.test import Client
from django.urls import reverse

from core.exceptions import BusinessRuleError
from core.models import Role
from masters.models import Process
from production.services import diary, routes
from tests.conftest import make_user
from tests.prod_helpers import D, DAY, build, cut, go, set_inhouse_rate, step


def _login(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def ns(company, factory, owner):
    ns = build(company, factory, owner)
    routes.reassign_step(step(ns, "STITCH"), user=owner, reason="Stitch in-house", assignment="in_house")
    for code in ("EMB", "PRINT", "WASH"):
        routes.skip_step(step(ns, code), user=owner, reason="Not needed")
    return ns


def test_the_diary_lists_every_step_oldest_first_with_who(ns):
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    entries = diary.entries(ns.lot, ns.owner)
    texts = [e.text for e in entries]
    assert texts[0].startswith("Fabric issued") and any(t.startswith("Bundles moved") for t in texts)
    assert [e.date for e in entries] == sorted(e.date for e in entries)
    assert all(e.who == ns.owner.username for e in entries)


def test_only_the_newest_diary_entry_can_be_deleted(ns):
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    entries = diary.entries(ns.lot, ns.owner)
    assert [e.can_delete for e in entries] == [False] * (len(entries) - 1) + [True]
    page = _login(ns.owner).get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    assert "Lot diary" in page and reverse("step_delete", args=[entries[-1].action.pk]) in page


def test_the_route_is_fixed_once_cutting_starts(ns):
    c = _login(ns.owner)
    assert "Change the route" in c.get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    cut(ns)
    assert "Change the route" not in c.get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    with pytest.raises(BusinessRuleError, match="The route is fixed once cutting has started. Choose who does a step when you send the work."):
        routes.add_step(ns.lot, process=Process.objects.get(code="DYE"), after_sequence=2, user=ns.owner, reason="x")
    with pytest.raises(BusinessRuleError, match="The route is fixed once cutting has started"):
        routes.remove_step(step(ns, "FINISH"), user=ns.owner, reason="x")
    page = c.get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    assert "Who does each step" in page and "Add a step" not in page and "Move a step" not in page
    routes.reassign_step(step(ns, "IRON"), user=ns.owner, reason="Iron outside", assignment="subcontract")   # who: still free


def test_the_lot_page_has_no_history_or_corrections(ns):
    cut(ns)
    page = _login(ns.owner).get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    assert "<summary>History</summary>" not in page and ">Corrections<" not in page


def test_the_step_table_shows_the_rate_and_its_date(ns):
    set_inhouse_rate("CUT", "2")
    cut(ns)
    page = _login(ns.owner).get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    assert "₹2 a piece · rate from 1 Apr 2026" in page


def test_the_lot_page_never_names_internal_places(ns, factory):
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    sup = make_user("sup")
    sup.roles.add(Role.objects.get(name="Production Supervisor"))
    sup.allowed_factories.add(factory)
    page = _login(sup).get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    for internal in ("Cutting Floor", "Process Area"):
        assert internal not in page
    assert "₹" not in page.split("Lot diary")[1] if "Lot diary" in page else True
