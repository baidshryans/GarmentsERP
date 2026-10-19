"""Tags (owner, 19 Oct 2026): no bundle tags while a lot is being made; piece tags are printed once it is packed,
one per packed piece."""
import pytest
from django.test import Client
from django.urls import reverse

from production.services import bundles as bundle_service
from production.services import cutting, routes
from tests.prod_helpers import D, DAY, build, go, step


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
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=owner, date=DAY)
    return ns


def _cut(ns, c):
    S, M = ns.sizes["S"], ns.sizes["M"]
    rolls = {f"used_{ns.roll_a.pk}": "41", f"waste_{ns.roll_a.pk}": "2", f"remnant_{ns.roll_a.pk}": "17"}
    return c.post(reverse("lot_cutting", args=[ns.lot.pk]), {"date": "2026-06-15", f"bundles_{S.pk}": "9 8", f"bundles_{M.pk}": "20", **rolls})


def _pack(ns):
    bundles = list(ns.lot.bundles.all())
    for code in ("STITCH", "IRON", "FINISH", "QC", "PACK"):
        go(ns, bundles, code)
    bundle_service.pack_bundles(bundles=bundles, user=ns.owner, date=DAY)


def test_cutting_does_not_send_to_tags(ns):
    c = _login(ns.owner)
    r = _cut(ns, c)
    assert r.status_code == 302 and r.url != reverse("lot_tags", args=[ns.lot.pk])
    page = c.get(reverse("lot_cutting", args=[ns.lot.pk])).content.decode()
    assert "QR tags" not in page


def test_the_lot_page_offers_print_tags_only_after_packing(ns):
    c = _login(ns.owner)
    _cut(ns, c)
    page = c.get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    assert f'{reverse("tag_print")}?lot={ns.lot.pk}' not in page and reverse("lot_tags", args=[ns.lot.pk]) not in page
    _pack(ns)
    page = c.get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    assert f'{reverse("tag_print")}?lot={ns.lot.pk}' in page and "Print tags" in page


def test_print_tags_for_a_lot_prints_one_per_packed_piece(ns):
    c = _login(ns.owner)
    _cut(ns, c)
    _pack(ns)
    assert bundle_service.packed_counts(ns.lot) == {ns.style.skus.get(size=ns.sizes["S"], colour=ns.black): 17,
                                                     ns.style.skus.get(size=ns.sizes["M"], colour=ns.black): 20}
    page = c.get(reverse("tag_print"), {"lot": ns.lot.pk}).content.decode()
    assert page.count('class="tag') == 37


def test_bundle_tags_are_refused_before_packing(ns):
    c = _login(ns.owner)
    _cut(ns, c)
    r = c.get(reverse("lot_tags", args=[ns.lot.pk]), follow=True)
    assert "Tags are printed once the lot is packed." in r.content.decode()
