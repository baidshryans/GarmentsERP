"""The purge engine (owner, 19 Oct 2026): a posting and its reversal are removed together, leaving the books as if
neither had been made, and with no history row for anyone to find."""
from decimal import Decimal

import pytest

from core.services import purge
from core.services.factories import godown_location
from inventory.models import StockMovement
from inventory.services import stock
from ledger.models import Voucher
from ledger.services.posting import LineSpec, post_voucher, reverse_voucher
from tests.deletion_helpers import books
from tests.prod_helpers import DAY, build

D = Decimal


def _journal(company, factory, owner, ledgers, amount="100"):
    return post_voucher(company=company, factory=factory, voucher_type="journal", date=DAY, user=owner, narration="test",
                        lines=[LineSpec(ledger=ledgers("bank_charges"), debit=D(amount)),
                               LineSpec(ledger=ledgers("cash"), credit=D(amount))])


def test_purge_pair_leaves_balances_unchanged(company, factory, owner, ledgers):
    ns = build(company, factory, owner)
    before = books(company)
    v = _journal(company, factory, owner, ledgers)
    r = reverse_voucher(v, user=owner, reason="test")
    m = stock.post_movement(factory=factory, location=godown_location(factory), item=ns.zipper, qty=D("-5"),
                            movement_type="issue", date=DAY, user=owner)
    back = stock.reverse_movement(m, user=owner, date=DAY)
    purge.movements(StockMovement.objects.filter(pk__in=[m.pk, back.pk]))
    purge.vouchers(Voucher.objects.filter(pk__in=[v.pk, r.pk]))
    assert books(company) == before
    assert not Voucher.objects.filter(pk__in=[v.pk, r.pk]).exists()
    assert not StockMovement.objects.filter(pk__in=[m.pk, back.pk]).exists()


def test_purge_refuses_an_unbalanced_set(company, factory, owner, ledgers):
    ns = build(company, factory, owner)
    m = stock.post_movement(factory=factory, location=godown_location(factory), item=ns.zipper, qty=D("-5"),
                            movement_type="issue", date=DAY, user=owner)
    with pytest.raises(purge.PurgeError):
        purge.movements(StockMovement.objects.filter(pk=m.pk))
    v = _journal(company, factory, owner, ledgers)
    with pytest.raises(purge.PurgeError):
        purge.vouchers(Voucher.objects.filter(pk=v.pk))
    stock.reverse_movement(m, user=owner, date=DAY)             # leave the books whole for the tally check
    reverse_voucher(v, user=owner, reason="test")


def test_history_rows_are_gone_including_the_delete_marker(company, factory, owner, ledgers):
    v = _journal(company, factory, owner, ledgers)
    r = reverse_voucher(v, user=owner, reason="test")
    ids = [v.pk, r.pk]
    assert Voucher.history.filter(id__in=ids).exists()
    purge.vouchers(Voucher.objects.filter(pk__in=ids))
    assert not Voucher.history.filter(id__in=ids).exists()


def test_a_lone_posted_voucher_can_be_purged_when_asked(company, factory, owner, ledgers):
    """A hand-made entry has no reversal: deleting it purges it alone (Task 13)."""
    before = books(company)
    v = _journal(company, factory, owner, ledgers)
    purge.vouchers(Voucher.objects.filter(pk=v.pk), lone=True)
    assert not Voucher.objects.filter(pk=v.pk).exists() and not Voucher.history.filter(id=v.pk).exists()
    assert books(company) == before
