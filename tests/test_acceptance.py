"""BRD acceptance scenarios (section 11.1) for what exists so far. Each one is a story told end to end, and the
autouse fixture then checks that the books tally and stock reconciles.

A1, A2, A3, A10 are here. A11 is `test_one_lot_cut_in_house_stitched_by_a_subcontractor_ironed_at_factory_2_...`
in test_jobwork.py. A12 (every voucher type) arrives with the accounting screens; A4-A9 with sales and reports.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from core.models import Factory, Location, Role, User
from core.services.factories import create_factory
from core.services.setup import run_setup
from inventory.models import RollBalance
from jobwork.services import bills, challans, rates, receipts
from jobwork.services.challans import SecondFabricatorWarning
from jobwork.services.receipts import Counted
from ledger.models import AccountGroup, Ledger
from production.models import Bundle
from tax.models import TaxTemplate
from tests.conftest import make_user
from tests.prod_helpers import D, DAY, build, cut, fabricator, gl, step
from production.services import cutting, costing


def test_A1_order_fabric_issue_by_roll_cutting_and_variance_against_the_bom(company, factory, owner):
    ns = build(company, factory, owner)
    godown = Location.objects.get(factory=factory, name="Main Godown")
    before = RollBalance.objects.get(roll=ns.roll_a, location=godown).qty
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=owner, date=DAY)
    assert RollBalance.objects.get(roll=ns.roll_a, location=godown).qty == before - D("60")  # the roll balance reduces
    entry = cutting.record_cutting(
        lot=ns.lot, user=owner, date=DAY, pieces={ns.sizes["S"]: 17, ns.sizes["M"]: 33, ns.sizes["L"]: 33, ns.sizes["XL"]: 17},
        rolls=[cutting.RollUseSpec(ns.roll_a, used=D("41"), waste=D("2"), remnant=D("17"))])
    assert sum(s.pieces for s in entry.sizes.all()) == 100                       # pieces cut per size
    use = entry.rolls.get()
    assert (use.used_qty, use.waste_qty, use.remnant_qty) == (D("41"), D("2"), D("17"))  # consumption, waste, remnant
    assert RollBalance.objects.get(roll=ns.roll_a, location=godown).qty == before - D("43")  # remnant is back in the store
    assert entry.expected_fabric == D("40.000") and entry.variance_pct == D("7.50")  # variance against the BOM is shown
    assert costing.lot_cost(ns.lot) == D("9030.00")


def test_A2_issue_to_a_fabricator_partial_receipt_ledger_and_second_fabricator_warning(company, factory, owner):
    ns = build(company, factory, owner)
    bundles = cut(ns)
    fab, other = fabricator(company), fabricator(company, "Gupta Stitching", "9822222233")
    for f in (fab, other):
        rates.save_rate(party=f, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("25"), effective_from=date(2026, 4, 1))
    ch = challans.create_challan(company=company, factory=factory, party=fab, lot=ns.lot, step=step(ns, "STITCH"),
                                 bundles=bundles[:3], date=DAY, user=owner)
    ch = challans.issue_challan(ch, user=owner)
    page = Client()
    page.force_login(owner)
    printed = page.get(reverse("challan_print", args=[ch.pk])).content.decode()
    assert ch.number in printed and ns.order.number in printed  # the challan prints with the order reference
    receipts.create_receipt(challan=ch, user=owner, date=DAY, counts=[Counted(cb, cb.qty_issued) for cb in list(ch.bundles.all())[:2]])
    from jobwork import selectors

    row = selectors.fabricator_ledger(owner, fab)[0]
    assert (row["issued"], row["received"], row["in_process"]) == (50, 42, 8)  # issued, received, pending
    with pytest.raises(SecondFabricatorWarning):  # the lot is already open with the first fabricator
        challans.create_challan(company=company, factory=factory, party=other, lot=ns.lot, step=step(ns, "STITCH"),
                                bundles=bundles[3:4], date=DAY, user=owner)


def test_A3_qc_rejects_are_deducted_the_bill_has_tds_and_rework_goes_out_on_a_challan(company, factory, owner):
    ns = build(company, factory, owner)
    bundles = cut(ns)
    fab = fabricator(company)
    rates.save_rate(party=fab, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("25"), rework_rate=D("5"),
                    effective_from=date(2026, 4, 1))
    ch = challans.issue_challan(challans.create_challan(
        company=company, factory=factory, party=fab, lot=ns.lot, step=step(ns, "STITCH"), bundles=bundles[:3], date=DAY, user=owner), user=owner)
    lines = list(receipts.create_receipt(challan=ch, user=owner, date=DAY, counts=[Counted(cb, cb.qty_issued) for cb in ch.bundles.all()]).lines.order_by("id"))
    receipts.record_qc(receipt_line=lines[0], accepted=17, user=owner)
    receipts.record_qc(receipt_line=lines[1], accepted=22, rejected=3, reject_reason="Open seams", user=owner)  # rejected pieces
    receipts.record_qc(receipt_line=lines[2], accepted=0, rework=8, user=owner)                                  # rework
    rw = challans.create_challan(company=company, factory=factory, party=fab, lot=ns.lot, step=step(ns, "STITCH"),
                                 bundles=[Bundle.objects.get(pk=bundles[2].pk)], date=DAY, user=owner, kind="rework")
    assert rw.kind == "rework"                                                                                    # rework challan created
    bill = bills.create_bill(company=company, factory=factory, party=fab, date=DAY, user=owner,
                             tds_template=TaxTemplate.objects.get(name="TDS 194C - others (2%)"))
    assert bill.gross == D("975.00")        # only the 39 accepted pieces: the 3 rejected and 8 in rework are not paid
    assert bill.tds == D("19.50") and bill.net == D("955.50")                                                      # TDS applied
    bills.post_bill(bill, user=owner)
    assert gl(company, "tds_payable", factory) == D("-19.50")


def test_A10_fresh_install_two_factories_and_users_each_see_only_their_own(db):
    admin = User.objects.create_superuser(username="admin", password="pw-for-tests-1")
    company = run_setup(
        company_data={"name": "Fresh Co", "state_code": "03", "books_from": date(2026, 4, 1), "fy_start_month": 4},
        tax_data={}, factory_data={"code": "F1", "name": "Factory 1", "state_code": "03"}, admin_user=admin)
    f1 = Factory.objects.get(code="F1")
    f2 = create_factory(company=company, code="F2", name="Factory 2", state_code="03")
    # the wizard seeded groups, ledgers and default masters
    assert AccountGroup.objects.filter(company=company, name="Sundry Debtors").exists()
    assert Ledger.objects.filter(company=company, system_key="cash").exists()
    from masters.models import Process, Size, Unit

    assert Unit.objects.filter(code="PCS").exists() and Size.objects.filter(code="M").exists() and Process.objects.filter(code="STITCH").exists()
    u1, u2 = make_user("u1"), make_user("u2")
    for u, f in ((u1, f1), (u2, f2)):
        u.roles.add(Role.objects.get(name="Accountant"))
        u.allowed_factories.add(f)
    assert list(Factory.objects.for_user(u1)) == [f1] and list(Factory.objects.for_user(u2)) == [f2]
    c = Client()
    c.force_login(u1)
    assert c.get(reverse("factory_list")).status_code == 403  # an accountant has no factory screen, and
    assert [f["code"] for f in c.get("/api/v1/me/").json()["factories"]] == ["F1"]  # sees only Factory 1
