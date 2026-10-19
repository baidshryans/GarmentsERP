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
