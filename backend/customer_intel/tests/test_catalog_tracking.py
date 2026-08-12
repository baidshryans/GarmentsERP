"""
Catalog intent tracking.

The resilience tests matter most: this hangs off a public, customer-facing page.
A tracking bug must degrade to "no analytics row", never to a broken catalog.
"""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from customer_intel.models import CatalogViewEvent, EngagementEvent
from customer_intel.services.catalog_tracking import hash_ip, track
from customer_intel.tests.factories import make_customer, make_retail


def make_share(retail, ledger=None, label="Diwali"):
    from inventory.models import CatalogShare

    return CatalogShare.objects.create(
        retail=retail, label=label, tier="retail", ledger=ledger,
        source="campaign" if ledger else "manual",
    )


class TrackingTests(TestCase):
    def setUp(self):
        self.retail = make_retail()
        self.customer = make_customer(self.retail, "Asha", mobile="9000000001")
        self.share = make_share(self.retail, self.customer)
        self.factory_request = self._request()

    def _request(self, session_id="sess-1"):
        from django.test import RequestFactory

        request = RequestFactory().get("/catalog/")
        request.COOKIES["catalog_sid"] = session_id
        request.META["REMOTE_ADDR"] = "203.0.113.5"
        request.META["HTTP_USER_AGENT"] = "Mozilla/5.0"
        return request

    def test_open_is_recorded_against_the_share_owner(self):
        track(self.factory_request, self.share, "open")

        event = CatalogViewEvent.objects.get()
        self.assertEqual(event.ledger_id, self.customer.id)
        self.assertEqual(event.kind, "open")

    def test_open_bumps_the_share_counters(self):
        track(self.factory_request, self.share, "open")
        self.share.refresh_from_db()

        self.assertEqual(self.share.open_count, 1)
        self.assertIsNotNone(self.share.first_opened_at)
        self.assertIsNotNone(self.share.last_opened_at)

    def test_open_appears_on_the_customer_timeline(self):
        track(self.factory_request, self.share, "open")

        event = EngagementEvent.objects.get(event_type="catalog_open")
        self.assertEqual(event.ledger_id, self.customer.id)
        self.assertEqual(event.channel, "catalog")

    def test_repeat_opens_in_the_same_session_are_deduped(self):
        """A page refresh must not inflate the engagement score."""
        track(self.factory_request, self.share, "open")
        track(self.factory_request, self.share, "open")

        self.assertEqual(CatalogViewEvent.objects.filter(kind="open").count(), 1)

    def test_an_open_after_the_dedupe_window_counts_again(self):
        track(self.factory_request, self.share, "open")
        CatalogViewEvent.objects.update(
            occurred_at=timezone.now() - timedelta(minutes=45),
        )

        track(self.factory_request, self.share, "open")

        self.assertEqual(CatalogViewEvent.objects.filter(kind="open").count(), 2)

    def test_a_different_session_is_a_different_visit(self):
        track(self.factory_request, self.share, "open")
        track(self._request(session_id="sess-2"), self.share, "open")

        self.assertEqual(CatalogViewEvent.objects.filter(kind="open").count(), 2)

    def test_design_views_are_not_deduped(self):
        """Looking at the same design repeatedly IS the signal."""
        track(self.factory_request, self.share, "design", design_id=None)
        track(self.factory_request, self.share, "design", design_id=None)

        self.assertEqual(CatalogViewEvent.objects.filter(kind="design").count(), 2)

    def test_an_anonymous_share_records_the_view_without_a_customer(self):
        anon_share = make_share(self.retail, ledger=None)

        track(self.factory_request, anon_share, "open")

        event = CatalogViewEvent.objects.get(share=anon_share)
        self.assertIsNone(event.ledger_id)
        self.assertFalse(
            EngagementEvent.objects.filter(catalog_share=anon_share).exists(),
            msg="an unattributable open has no customer timeline to appear on",
        )

    def test_raw_ip_is_never_stored(self):
        track(self.factory_request, self.share, "open")

        event = CatalogViewEvent.objects.get()
        self.assertNotIn("203.0.113.5", event.ip_hash)
        self.assertEqual(len(event.ip_hash), 64)

    def test_ip_hash_differs_between_retails(self):
        """Salted per retail, so the same visitor is not correlatable across them."""
        self.assertNotEqual(hash_ip("203.0.113.5", 1), hash_ip("203.0.113.5", 2))

    def test_tracking_failure_is_swallowed(self):
        """A broken tracker must never surface to the visitor."""
        with patch(
            "customer_intel.models.CatalogViewEvent.objects.create",
            side_effect=RuntimeError("db exploded"),
        ):
            result = track(self.factory_request, self.share, "open")

        self.assertIsNone(result)


@override_settings(ALLOWED_HOSTS=["*"])
class PublicEndpointTests(TestCase):
    """The public page must survive a failing tracker."""

    def setUp(self):
        self.retail = make_retail()
        self.customer = make_customer(self.retail, "Asha", mobile="9000000001")
        self.share = make_share(self.retail, self.customer)

    def test_track_endpoint_records_a_design_view(self):
        response = self.client.post(
            f"/inventory/api/catalog-share/{self.share.token}/track/",
            data={"kind": "design"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(CatalogViewEvent.objects.filter(kind="design").count(), 1)

    def test_track_endpoint_ignores_an_unknown_token(self):
        import uuid

        response = self.client.post(
            f"/inventory/api/catalog-share/{uuid.uuid4()}/track/",
            data={"kind": "design"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(CatalogViewEvent.objects.count(), 0)

    def test_track_endpoint_rejects_a_design_from_another_retail(self):
        """A public endpoint must not let a caller attach arbitrary design ids."""
        from customer_intel.tests.factories import make_item
        from inventory.models import DesignMain

        other_retail = make_retail(name="Other", code="OT")
        foreign = DesignMain.objects.create(
            design_no="X1", item=make_item(), retail=other_retail,
            pcs=1, gw=5, nw=5, making=0, making_type="per_gram", making_rate=0,
        )

        self.client.post(
            f"/inventory/api/catalog-share/{self.share.token}/track/",
            data={"kind": "design", "design_id": foreign.id},
            content_type="application/json",
        )

        event = CatalogViewEvent.objects.get()
        self.assertIsNone(event.design_id)

    def test_public_catalog_still_serves_when_tracking_raises(self):
        with patch(
            "customer_intel.services.catalog_tracking.track",
            side_effect=RuntimeError("tracker down"),
        ):
            response = self.client.get(
                f"/inventory/api/catalog-share/{self.share.token}/"
            )

        self.assertEqual(response.status_code, 200)
