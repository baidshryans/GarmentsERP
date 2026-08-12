"""
Record what a shared catalog link's visitor looked at.

Every function here is best-effort and swallows its own exceptions. Tracking is
a reporting nicety; the public catalog is a customer-facing page that must keep
working even if this app is misconfigured, the table is locked, or a design id
is bogus. A tracking failure that breaks the catalog would be a far worse bug
than a missing analytics row.
"""

import hashlib
import logging
from datetime import timedelta

from django.conf import settings as django_settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Repeat opens within this window are treated as the same visit, so a customer
# refreshing the page does not inflate their engagement score.
DEDUPE_WINDOW = timedelta(minutes=30)


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def hash_ip(ip, retail_id):
    """
    Salted, per-retail hash. Never store the raw address.

    The salt is SECRET_KEY plus the retail id, so the same visitor is not
    correlatable across retails and the hash is not reversible with a rainbow
    table of the IPv4 space alone.
    """
    if not ip:
        return ""
    salt = f"{getattr(django_settings, 'SECRET_KEY', '')}:{retail_id}"
    return hashlib.sha256(f"{salt}:{ip}".encode("utf-8")).hexdigest()


def _session_key(request):
    """A stable id for this visit, without requiring a login."""
    key = request.COOKIES.get("catalog_sid")
    if key:
        return key[:40]
    if getattr(request, "session", None) is not None:
        try:
            if not request.session.session_key:
                request.session.save()
            return (request.session.session_key or "")[:40]
        except Exception:
            pass
    return ""


def track(request, share, kind, design_id=None, page=None):
    """
    Record one catalog interaction. Returns the event, or None if skipped.

    `ledger` is always taken from the share, never from the request — a public
    endpoint must not let a caller claim to be a particular customer.
    """
    try:
        from customer_intel.models import CatalogViewEvent

        if share is None or share.retail_id is None:
            return None

        session_key = _session_key(request)

        # Opens are deduped per session; design views are not, because looking
        # at the same design repeatedly is itself the signal.
        if kind == "open" and session_key:
            recent = CatalogViewEvent.objects.filter(
                share=share, kind="open", session_key=session_key,
                occurred_at__gte=timezone.now() - DEDUPE_WINDOW,
            ).exists()
            if recent:
                return None

        event = CatalogViewEvent.objects.create(
            share=share,
            ledger_id=share.ledger_id,
            retail_id=share.retail_id,
            kind=kind,
            design_id=design_id,
            page=page,
            session_key=session_key,
            ip_hash=hash_ip(_client_ip(request), share.retail_id),
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:300],
        )

        if kind == "open":
            _bump_share_counters(share)
            _log_timeline(share, event)
        return event
    except Exception:
        logger.warning("catalog tracking failed for share %s",
                       getattr(share, "id", None), exc_info=True)
        return None


def _bump_share_counters(share):
    from django.db.models import F

    from inventory.models import CatalogShare

    now = timezone.now()
    CatalogShare.objects.filter(id=share.id).update(
        open_count=F("open_count") + 1,
        last_opened_at=now,
        first_opened_at=share.first_opened_at or now,
    )


def _log_timeline(share, event):
    """Surface the open on the customer's timeline, when it is attributable."""
    if not share.ledger_id:
        return
    from customer_intel.models import EngagementEvent

    EngagementEvent.objects.create(
        retail_id=share.retail_id,
        ledger_id=share.ledger_id,
        channel="catalog",
        direction="in",
        event_type="catalog_open",
        subject=share.label or "Catalog",
        status="received",
        catalog_share=share,
        occurred_at=event.occurred_at or timezone.now(),
    )
