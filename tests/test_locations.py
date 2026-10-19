"""Locations (owner, 19 Oct 2026): each factory shows Godown, Ready Goods and Rejects; the ERP finds them by kind,
never by name, so the owner can rename them."""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from core.models import Location
from core.services import factories
from core.services.factories import create_factory, godown_location, ready_goods_location, rejects_location


def test_new_factory_gets_godown_ready_goods_rejects(company):
    f = create_factory(company=company, code="LDH9", name="Unit 9", state_code="03")
    names = set(f.locations.values_list("name", flat=True))
    assert {"Godown", "Ready Goods", "Rejects"} <= names
    assert "Main Godown" not in names and "Dispatch" not in names


def test_renamed_godown_still_found(company, factory):
    g = godown_location(factory)
    g.name = "Store 1"
    g.save()
    assert godown_location(factory) == g
    assert Location.objects.filter(factory=factory, loc_type="godown").count() == 1


def test_renamed_ready_goods_still_found(company, factory):
    r = ready_goods_location(factory)
    r.name = "Packed stock"
    r.save()
    assert ready_goods_location(factory) == r == factories.dispatch_location(factory)
    assert r.loc_type == "dispatch"


def test_a_missing_kind_is_made_once(company, factory):
    Location.objects.filter(factory=factory, loc_type="rejects").delete()
    first = rejects_location(factory)
    assert rejects_location(factory) == first and first.name == "Rejects"


def test_ready_goods_is_the_label_of_the_dispatch_kind():
    assert Location.Type.DISPATCH.label == "Ready goods"


@pytest.mark.django_db(transaction=True)
def test_migration_renames_existing(company, factory):
    Location.objects.filter(factory=factory, loc_type="godown").update(name="Main Godown")
    Location.objects.filter(factory=factory, loc_type="dispatch").update(name="Dispatch")
    ex = MigrationExecutor(connection)
    ex.migrate([("core", "0007_cutting_variance_label")])
    ex = MigrationExecutor(connection)
    ex.loader.build_graph()
    ex.migrate(ex.loader.graph.leaf_nodes())
    names = set(Location.objects.filter(factory=factory).values_list("name", flat=True))
    assert {"Godown", "Ready Goods"} <= names and not {"Main Godown", "Dispatch"} & names


# ---------------- what people see (Task 7) ----------------

from django.test import Client
from django.urls import reverse

from core.models import Role
from tests.conftest import make_user

INTERNAL = ("Cutting Floor", "Process Area", "In Transit", "At ")


def _client(user):
    c = Client()
    c.force_login(user)
    return c


def _select(html, name):
    """The <select name=...> block of a page, or '' when there is none."""
    start = html.find(f'<select id="{name}" name="{name}"')
    if start < 0:
        start = html.find(f'name="{name}"><option')
    return html[start:html.find("</select>", start)] if start >= 0 else ""


def test_grn_form_has_no_location_select_with_one_godown(company, factory, owner):
    html = _client(owner).get(reverse("grn_new")).content.decode()
    assert _select(html, "location") == ""
    assert f'type="hidden" name="location" value="{godown_location(factory).pk}"' in html


def test_grn_form_offers_a_choice_with_two_godowns(company, factory, owner):
    Location.objects.create(factory=factory, name="Trims Rack", loc_type="godown")
    html = _client(owner).get(reverse("grn_new")).content.decode()
    sel = _select(html, "location")
    assert "Godown" in sel and "Trims Rack" in sel and "Ready Goods" not in sel


def test_location_selects_never_list_internal_kinds(company, factory, factory2, owner):
    c = _client(owner)
    for name in ("journal_new", "opening_stock", "transfer_new", "stock_enquiry", "grn_new"):
        html = c.get(reverse(name)).content.decode()
        for field in ("location", "from_location", "to_location"):
            sel = _select(html, field)
            for internal in INTERNAL:
                assert internal not in sel, (name, field, internal)


def test_where_is_my_stock_shows_lot_step_and_fabricator(company, factory, owner):
    from jobwork.services import challans, rates
    from tests.prod_helpers import D, DAY, build, cut, fabricator, step

    ns = build(company, factory, owner)
    bundles = cut(ns)
    fab = fabricator(company)
    rates.save_rate(who=fab, process=step(ns, "STITCH").process, rate=D("25"), effective_from=DAY)
    challans.create_and_issue(company=company, factory=factory, party=fab, lot=ns.lot, step=step(ns, "STITCH"),
                              bundles=bundles[:2], date=DAY, user=owner)
    html = _client(owner).get(reverse("where_stock")).content.decode()
    assert ns.lot.lot_no in html and "Stitching" in html and fab.name in html
    assert "Godown" in html and "Zipper" in html
    for internal in ("Cutting Floor", "Process Area"):
        assert internal not in html


def test_where_hides_values_from_production_role(company, factory, owner):
    from tests.prod_helpers import build

    build(company, factory, owner)
    sup = make_user("sup")
    sup.roles.add(Role.objects.get(name="Production Supervisor"))
    sup.allowed_factories.add(factory)
    owner_html = _client(owner).get(reverse("where_stock")).content.decode()
    html = _client(sup).get(reverse("where_stock")).content.decode()
    assert "Value" in owner_html and "Value" not in html and "Zipper" in html


def test_qc_offers_keep_as_rejects_or_scrap():
    from pathlib import Path

    text = "".join(p.read_text(encoding="utf-8") for p in Path("templates/jobwork").glob("*.html"))
    assert "Keep as rejects" in text and "Scrap" in text and "Seconds" not in text
