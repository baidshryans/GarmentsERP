from django.apps import apps
from django.test import Client
from django.urls import reverse

import pytest

from core.models import Factory, NumberSeries, User
from core.services import reset
from core.exceptions import BusinessRuleError
from inventory.models import StockMovement
from ledger.models import AccountGroup, Ledger, Voucher


@pytest.fixture
def posted(company, factory, admin_user, ledgers):
    from datetime import date
    from ledger.services.posting import post_voucher
    from tests.helpers import simple_lines

    return post_voucher(company=company, factory=factory, voucher_type="journal", date=date(2026, 6, 15),
                        user=admin_user, lines=simple_lines(ledgers))


def test_no_kept_model_points_at_a_cleared_one():
    cleared = set(reset.models_to_clear())
    for model in apps.get_models():
        if model in cleared or model._meta.app_label not in reset.OWN_APPS or model._meta.auto_created:
            continue
        for f in model._meta.concrete_fields:
            if f.is_relation and f.related_model in cleared and not hasattr(model, "instance_type"):
                pytest.fail(f"{model._meta.label} keeps a link to cleared {f.related_model._meta.label}")


def test_reset_clears_transactions_and_keeps_masters(company, factory, admin_user, posted):
    n_ledgers, n_groups, n_factories = Ledger.objects.count(), AccountGroup.objects.count(), Factory.objects.count()
    NumberSeries.objects.filter(factory=factory).update(next_number=7)
    assert Voucher.objects.count() == 1
    reset.reset_transactions(user=admin_user, backup=False)
    assert Voucher.objects.count() == 0 and StockMovement.objects.count() == 0
    assert Ledger.objects.count() == n_ledgers and AccountGroup.objects.count() == n_groups
    assert Factory.objects.count() == n_factories and User.objects.filter(pk=admin_user.pk).exists()
    assert not NumberSeries.objects.exclude(next_number=1).exists()


def test_only_a_superuser_may_reset(company, owner):
    with pytest.raises(BusinessRuleError):
        reset.reset_transactions(user=owner, backup=False)


def test_the_screen_needs_the_phrase_and_the_password(company, admin_user, posted):
    c = Client()
    c.force_login(admin_user)
    url = reverse("reset_database")
    assert c.get(url).status_code == 200
    c.post(url, {"phrase": "reset", "password": "pw-for-tests-1"})
    c.post(url, {"phrase": "RESET", "password": "wrong"})
    assert Voucher.objects.count() == 1
    r = c.post(url, {"phrase": "RESET", "password": "pw-for-tests-1"})
    assert r.status_code == 302 and Voucher.objects.count() == 0


def test_a_non_superuser_cannot_open_the_screen(company, owner):
    c = Client()
    c.force_login(owner)
    assert c.get(reverse("reset_database")).status_code == 403
