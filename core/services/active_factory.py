"""The active factory: one choice per session that every screen follows, like a branch in a retail ERP.

The session holds a factory id, or "all" for a user with several factories (read-only views).
Whatever is stored is re-checked against the user's allowed factories on every request (BR-23).
"""
from core.exceptions import FactoryNotAllowed
from core.models import Factory

SESSION_KEY = "active_factory"
ALL = "all"


def allowed_factories(user):
    return Factory.objects.for_user(user).filter(is_active=True).order_by("code")


def resolve(request):
    """Work out the active factory for this request. Returns (factory, is_all, needs_choice)."""
    user = request.user
    allowed = list(allowed_factories(user))
    raw = request.session.get(SESSION_KEY)
    if raw == ALL and len(allowed) > 1:
        return None, True, False
    by_id = {str(f.pk): f for f in allowed}
    if raw in by_id:
        return by_id[raw], False, False
    # Nothing valid stored: a single factory is automatic, else fall back to the last one used.
    if len(allowed) == 1:
        choice = allowed[0]
    else:
        choice = by_id.get(str(user.last_factory_id)) if user.last_factory_id else None
    if choice:
        request.session[SESSION_KEY] = str(choice.pk)
        return choice, False, False
    return None, False, bool(allowed)


def switch(request, value):
    """Make `value` (a factory id or "all") the active factory. Raises FactoryNotAllowed if the user may not."""
    user = request.user
    allowed = {str(f.pk): f for f in allowed_factories(user)}
    if value == ALL:
        if len(allowed) < 2:
            raise FactoryNotAllowed("All factories is only for users with more than one factory.")
        request.session[SESSION_KEY] = ALL
        return
    if value not in allowed:
        raise FactoryNotAllowed("You do not have access to that factory.")
    request.session[SESSION_KEY] = value
    if user.last_factory_id != allowed[value].pk:
        user.last_factory = allowed[value]
        user.save(update_fields=["last_factory"])


def require_active_factory(request):
    """The factory a new document is entered in. Refuses in "All factories" mode (nothing posts without a factory)."""
    if request.factory is None:
        raise FactoryNotAllowed("Select a single factory (top bar) to enter documents.")
    return request.factory
