"""
Shared user/retail-access helpers.

Single source of truth for granting a superuser access to every retail branch.
Previously this logic was duplicated (and had drifted) across:
  - mastersconfig/signals.py   (on RetailMaster creation)
  - contacts/views.py          (AllowedRetailView, lazy on GET)
  - userauth/setup_views.py    (sync_user_retails endpoint)

Keeping it in one place ensures a freshly-created superuser always sees all
branches on any new setup, no matter how the retails were imported (ORM save,
bulk_create, or loaddata — the latter two bypass model signals).
"""
from contacts.models import UserLocation


def sync_superuser_retail_access(user):
    """
    Ensure a superuser's UserLocation covers every RetailMaster.

    Idempotent and cheap: only writes when a branch is actually missing, so it
    won't fire M2M/audit signals (or create audit-log rows) on every call.
    No-op for non-superusers and when no retails exist yet.

    Returns the number of branches newly linked (0 if nothing changed).
    """
    if not (user and getattr(user, "is_authenticated", False) and user.is_superuser):
        return 0

    # Imported lazily to avoid a circular import at app-load time.
    from mastersconfig.models import RetailMaster

    all_retails = list(RetailMaster.objects.all())
    if not all_retails:
        return 0

    ul, _ = UserLocation.objects.get_or_create(user=user)
    existing_ids = set(ul.location.values_list("id", flat=True))
    missing = [r for r in all_retails if r.id not in existing_ids]
    if missing:
        ul.location.add(*missing)
    if ul.default_location is None:
        ul.default_location = all_retails[0]
        ul.save(update_fields=["default_location"])
    return len(missing)
