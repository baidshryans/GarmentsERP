import pytest
from django.test import Client
from django.urls import reverse

from core.models import Role, User
from core.services.active_factory import SESSION_KEY
from tests.conftest import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_factories(company):
    from core.services.factories import create_factory
    f2 = create_factory(company=company, code="LDH2", name="Ludhiana Unit 2", state_code="03")
    from core.models import Factory
    return Factory.objects.get(code="LDH1"), f2


def fresh_client(user):
    """A client that has logged in but not yet chosen a factory."""
    c = Client()
    c.force_login(user)
    s = c.session
    s.pop(SESSION_KEY, None)
    s.save()
    return c


def test_several_factories_and_no_choice_goes_to_the_picker(two_factories, admin_user):
    c = fresh_client(admin_user)
    r = c.get(reverse("home"))
    assert r.status_code == 302 and r.url.startswith(reverse("factory_select"))
    r = c.post(reverse("factory_select"), {"factory": two_factories[1].pk, "next": reverse("home")})
    assert r.status_code == 302 and r.url == reverse("home")
    assert c.get(reverse("home")).wsgi_request.factory == two_factories[1]
    admin_user.refresh_from_db()
    assert admin_user.last_factory == two_factories[1]       # remembered for the next login


def test_next_login_returns_to_last_factory(two_factories, admin_user):
    admin_user.last_factory = two_factories[0]
    admin_user.save()
    r = fresh_client(admin_user).get(reverse("home"))
    assert r.status_code == 200 and r.wsgi_request.factory == two_factories[0]


def test_a_single_factory_is_automatic(company, admin_user):
    r = fresh_client(admin_user).get(reverse("home"))
    assert r.status_code == 200 and r.wsgi_request.factory.code == "LDH1"


def test_all_mode_is_view_only_and_needs_several_factories(two_factories, admin_user):
    c = fresh_client(admin_user)
    c.post(reverse("factory_switch"), {"factory": "all"})
    req = c.get(reverse("home")).wsgi_request
    assert req.factory is None and req.factory_all and len(req.active_factories) == 2


def test_all_mode_refused_with_one_factory(company, admin_user):
    c = fresh_client(admin_user)
    c.post(reverse("factory_switch"), {"factory": "all"})
    assert c.get(reverse("home")).wsgi_request.factory_all is False


def test_a_factory_the_user_cannot_access_is_dropped(two_factories, company):
    user = make_user("clerk1")
    user.allowed_factories.add(two_factories[0])
    c = Client()
    c.force_login(user)
    s = c.session
    s[SESSION_KEY] = str(two_factories[1].pk)                # tampered session
    s.save()
    assert c.get(reverse("home")).wsgi_request.factory == two_factories[0]
    c.post(reverse("factory_switch"), {"factory": two_factories[1].pk})
    assert c.get(reverse("home")).wsgi_request.factory == two_factories[0]
