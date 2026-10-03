from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from core.exceptions import FactoryNotAllowed
from ledger.exceptions import (
    FactoryRequired, InvalidLine, NotReversible, PostedVoucherImmutable, PostingError, Unbalanced,
)
from ledger.models import BillAllocation, Voucher, VoucherLine
from ledger.selectors import outstanding_bills, trial_balance
from ledger.services.posting import (
    AllocationSpec, LineSpec, create_draft, post_draft, post_voucher, reverse_voucher, update_draft,
)
from tests.conftest import IN_YEAR
from tests.helpers import simple_lines

D = Decimal


def post(company, factory, user, lines, **kw):
    return post_voucher(
        company=company, factory=factory, voucher_type=kw.pop("voucher_type", "journal"),
        date=kw.pop("date", IN_YEAR), lines=lines, user=user, **kw,
    )


def test_posts_balanced_voucher_with_number(company, factory, owner, ledgers):
    v = post(company, factory, owner, simple_lines(ledgers))
    assert v.is_posted and v.number == "JV/LDH1/26-27/0001"
    assert v.total == D("1000.00") and v.lines.count() == 2
    assert trial_balance(company)["tallies"]


def test_unbalanced_voucher_rejected_and_nothing_saved(company, factory, owner, ledgers):
    lines = [LineSpec(ledger=ledgers("cash"), debit=D("100")), LineSpec(ledger=ledgers("sales_stock"), credit=D("90"))]
    with pytest.raises(Unbalanced):
        post(company, factory, owner, lines)
    assert not Voucher.objects.exists() and not VoucherLine.objects.exists()


def test_draft_must_also_balance(company, factory, owner, ledgers):
    lines = [LineSpec(ledger=ledgers("cash"), debit=D("100")), LineSpec(ledger=ledgers("sales_stock"), credit=D("90"))]
    with pytest.raises(Unbalanced):
        create_draft(company=company, factory=factory, voucher_type="journal", date=IN_YEAR, lines=lines, user=owner)
    assert not Voucher.objects.exists()


def test_factory_is_mandatory(company, owner, ledgers):
    with pytest.raises(FactoryRequired):
        post(company, None, owner, simple_lines(ledgers))
    assert not Voucher.objects.exists()


@pytest.mark.parametrize("bad", [100.0, "100", None])
def test_floats_and_non_numbers_refused(company, factory, owner, ledgers, bad):
    lines = [LineSpec(ledger=ledgers("cash"), debit=bad), LineSpec(ledger=ledgers("sales_stock"), credit=D("100"))]
    with pytest.raises(InvalidLine):
        post(company, factory, owner, lines)


def test_more_than_two_decimals_refused(company, factory, owner, ledgers):
    lines = [LineSpec(ledger=ledgers("cash"), debit=D("10.005")), LineSpec(ledger=ledgers("sales_stock"), credit=D("10.005"))]
    with pytest.raises(InvalidLine):
        post(company, factory, owner, lines)


def test_line_needs_exactly_one_side(company, factory, owner, ledgers):
    both = [LineSpec(ledger=ledgers("cash"), debit=D("5"), credit=D("5")), LineSpec(ledger=ledgers("sales_stock"), credit=D("0"))]
    with pytest.raises(InvalidLine):
        post(company, factory, owner, both)
    with pytest.raises(InvalidLine):
        post(company, factory, owner, [LineSpec(ledger=ledgers("cash"), debit=D("5"))])


def test_inactive_ledger_refused(company, factory, owner, ledgers):
    cash = ledgers("cash")
    cash.is_active = False
    cash.save()
    with pytest.raises(InvalidLine):
        post(company, factory, owner, simple_lines(ledgers))


def test_failure_mid_posting_rolls_everything_back(company, factory, owner, ledgers, monkeypatch):
    """One transaction: if the last step fails, no voucher, line, allocation or number survives."""
    from core.models import NumberSeries
    from ledger.services import posting

    def boom(*a, **kw):
        raise RuntimeError("disk full")

    monkeypatch.setattr(posting, "next_document_number", boom)
    with pytest.raises(RuntimeError):
        post(company, factory, owner, simple_lines(ledgers))
    assert not Voucher.objects.exists() and not VoucherLine.objects.exists()
    assert not NumberSeries.objects.filter(next_number__gt=1).exists()


def test_failed_post_does_not_consume_a_number(company, factory, owner, ledgers):
    post(company, factory, owner, simple_lines(ledgers))
    with pytest.raises(Unbalanced):
        post(company, factory, owner, [LineSpec(ledger=ledgers("cash"), debit=D("1")), LineSpec(ledger=ledgers("sales_stock"), credit=D("2"))])
    second = post(company, factory, owner, simple_lines(ledgers))
    assert second.number.endswith("/0002")


def test_user_without_factory_access_cannot_post(company, factory, factory2, accountant, ledgers):
    with pytest.raises(FactoryNotAllowed):
        post(company, factory2, accountant, simple_lines(ledgers))


def test_inactive_user_cannot_post(company, factory, accountant, ledgers):
    accountant.is_active = False
    accountant.save()
    with pytest.raises(FactoryNotAllowed):
        post(company, factory, accountant, simple_lines(ledgers))


def test_inter_factory_lines_need_access_to_both_factories(company, factory, factory2, accountant, ledgers):
    lines = [
        LineSpec(ledger=ledgers("cash"), debit=D("50")),
        LineSpec(ledger=ledgers("sales_stock"), credit=D("50"), factory=factory2),
    ]
    with pytest.raises(FactoryNotAllowed):
        post(company, factory, accountant, lines)


# ---------- drafts ----------

def test_draft_has_no_number_until_posted_and_can_be_edited(company, factory, owner, ledgers):
    draft = create_draft(company=company, factory=factory, voucher_type="journal", date=IN_YEAR,
                         lines=simple_lines(ledgers, "10"), user=owner)
    assert draft.status == "draft" and draft.number is None
    update_draft(draft, lines=simple_lines(ledgers, "25"), user=owner, narration="edited")
    draft.refresh_from_db()
    assert draft.total == D("25.00") and draft.narration == "edited"
    posted = post_draft(draft, user=owner)
    assert posted.is_posted and posted.number


def test_posted_voucher_cannot_be_edited_or_deleted(company, factory, owner, ledgers):
    v = post(company, factory, owner, simple_lines(ledgers))
    with pytest.raises(PostedVoucherImmutable):
        update_draft(v, lines=simple_lines(ledgers, "5"), user=owner)
    v = Voucher.objects.get(pk=v.pk)
    v.narration = "tamper"
    with pytest.raises(PostedVoucherImmutable):
        v.save()
    with pytest.raises(PostedVoucherImmutable):
        v.delete()
    with pytest.raises(PostedVoucherImmutable):
        Voucher.objects.filter(pk=v.pk).update(narration="tamper")
    with pytest.raises(PostedVoucherImmutable):
        Voucher.objects.filter(pk=v.pk).delete()
    line = v.lines.first()
    line.debit = D("9999")
    with pytest.raises(PostedVoucherImmutable):
        line.save()
    with pytest.raises(PostedVoucherImmutable):
        line.delete()
    with pytest.raises(PostedVoucherImmutable):
        VoucherLine.objects.filter(voucher=v).update(debit=D("1"))
    with pytest.raises(PostedVoucherImmutable):
        VoucherLine.objects.filter(voucher=v).delete()
    with pytest.raises(PostedVoucherImmutable):
        VoucherLine.objects.bulk_create([VoucherLine(voucher=v, ledger=line.ledger, debit=D("1"), factory=factory)])
    with pytest.raises(PostedVoucherImmutable):
        post_draft(v, user=owner)


def test_database_refuses_a_line_with_both_sides(company, factory, owner, ledgers):
    draft = create_draft(company=company, factory=factory, voucher_type="journal", date=IN_YEAR,
                         lines=simple_lines(ledgers), user=owner)
    with pytest.raises(IntegrityError), transaction.atomic():
        VoucherLine.objects.create(voucher=draft, ledger=ledgers("cash"), debit=D("5"), credit=D("5"), factory=factory)


# ---------- reversal ----------

def test_reversal_posts_mirror_and_leaves_original_untouched(company, factory, owner, ledgers):
    v = post(company, factory, owner, simple_lines(ledgers))
    r = reverse_voucher(v, user=owner, reason="Entered twice", date=date(2026, 6, 20))
    assert r.reverses_id == v.pk and r.is_posted and r.number != v.number
    assert v.pk == Voucher.objects.get(pk=v.pk).pk and Voucher.objects.get(pk=v.pk).is_reversed
    tb = trial_balance(company)
    assert all(row["closing_debit"] == 0 and row["closing_credit"] == 0 for row in tb["rows"])


def test_cannot_reverse_twice_or_reverse_a_reversal_or_a_draft(company, factory, owner, ledgers):
    v = post(company, factory, owner, simple_lines(ledgers))
    r = reverse_voucher(v, user=owner, reason="x")
    with pytest.raises(NotReversible):
        reverse_voucher(v, user=owner, reason="again")
    with pytest.raises(NotReversible):
        reverse_voucher(r, user=owner, reason="undo undo")
    draft = create_draft(company=company, factory=factory, voucher_type="journal", date=IN_YEAR,
                         lines=simple_lines(ledgers), user=owner)
    with pytest.raises(NotReversible):
        reverse_voucher(draft, user=owner, reason="x")


def test_reversal_needs_a_reason(company, factory, owner, ledgers):
    v = post(company, factory, owner, simple_lines(ledgers))
    with pytest.raises(PostingError):
        reverse_voucher(v, user=owner, reason="  ")


# ---------- source link and bill-wise ----------

def test_voucher_links_back_to_source_document(company, factory, owner, ledgers):
    v = post(company, factory, owner, simple_lines(ledgers), source=factory)
    assert (v.source_type, v.source_id) == ("core.factory", factory.pk)


def _debtor(company):
    from ledger.models import AccountGroup, Ledger

    group = AccountGroup.objects.get(company=company, name="Sundry Debtors")
    return Ledger.objects.create(company=company, group=group, name="Dealer A", bill_wise=True)


def test_bill_wise_new_against_and_outstanding(company, factory, owner, ledgers):
    dealer = _debtor(company)
    post(company, factory, owner, [
        LineSpec(ledger=dealer, debit=D("1000"), allocations=(AllocationSpec("new", D("1000"), "INV-1"),)),
        LineSpec(ledger=ledgers("sales_stock"), credit=D("1000")),
    ], voucher_type="sales")
    assert outstanding_bills(dealer)["bills"] == {"INV-1": D("1000.00")}
    post(company, factory, owner, [
        LineSpec(ledger=ledgers("cash"), debit=D("400")),
        LineSpec(ledger=dealer, credit=D("400"), allocations=(AllocationSpec("against", D("400"), "INV-1"),)),
    ], voucher_type="receipt")
    assert outstanding_bills(dealer)["bills"] == {"INV-1": D("600.00")}


def test_bill_wise_ledger_defaults_to_on_account_and_allocation_must_sum(company, factory, owner, ledgers):
    dealer = _debtor(company)
    v = post(company, factory, owner, [
        LineSpec(ledger=ledgers("cash"), debit=D("50")), LineSpec(ledger=dealer, credit=D("50")),
    ], voucher_type="receipt")
    assert BillAllocation.objects.get(line__voucher=v).ref_type == "on_account"
    with pytest.raises(InvalidLine):
        post(company, factory, owner, [
            LineSpec(ledger=dealer, debit=D("100"), allocations=(AllocationSpec("new", D("60"), "X"),)),
            LineSpec(ledger=ledgers("sales_stock"), credit=D("100")),
        ])


def test_non_bill_wise_ledger_rejects_allocations(company, factory, owner, ledgers):
    with pytest.raises(InvalidLine):
        post(company, factory, owner, [
            LineSpec(ledger=ledgers("cash"), debit=D("10"), allocations=(AllocationSpec("new", D("10"), "X"),)),
            LineSpec(ledger=ledgers("sales_stock"), credit=D("10")),
        ])


def test_reversing_a_bill_reopens_nothing_and_nets_to_zero(company, factory, owner, ledgers):
    dealer = _debtor(company)
    v = post(company, factory, owner, [
        LineSpec(ledger=dealer, debit=D("700"), allocations=(AllocationSpec("new", D("700"), "INV-9"),)),
        LineSpec(ledger=ledgers("sales_stock"), credit=D("700")),
    ], voucher_type="sales")
    reverse_voucher(v, user=owner, reason="Cancelled invoice")
    assert outstanding_bills(dealer)["bills"] == {}
