"""Journal entries read as plain sentences (owner, 19 Oct 2026): what, who, lot, pieces x rate = amount, and the
rate's date."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace as NS

from django.test import Client
from django.urls import reverse

from ledger.models import Voucher
from ledger.services import narration
from tests.prod_helpers import build, cut, set_inhouse_rate

D = Decimal
LOT = NS(lot_no="L-12")
RATE_150 = NS(rate=D("1.50"), effective_from=date(2026, 10, 1))
RATE_12 = NS(rate=D("12.00"), effective_from=date(2026, 10, 1))
CUTTING, STITCHING = NS(name="Cutting"), NS(name="Stitching")
FACTORY1, FACTORY2 = NS(name="Factory 1", code="F1"), NS(name="Factory 2", code="F2")
RAMESH = NS(name="Ramesh")


def test_money_uses_indian_grouping_and_drops_whole_paise():
    assert narration.money(D("360.00")) == "₹360"
    assert narration.money(D("2880")) == "₹2,880"
    assert narration.money(D("123456.5")) == "₹1,23,456.50"
    assert narration.money(D("1.5")) == "₹1.50"
    assert narration.money(D("96.40")) == "₹96.40"


def test_inhouse_labour():
    assert narration.inhouse_labour(CUTTING, FACTORY1, LOT, 240, RATE_150) == \
        "Cutting in-house at Factory 1, lot L-12: 240 pieces × ₹1.50 = ₹360 (rate from 1 Oct 2026)"


def test_labour_bill_one_lot():
    assert narration.labour_bill(RAMESH, [(LOT, STITCHING, 240, RATE_12)], tds=D("29")) == \
        "Stitching by Ramesh, lot L-12: 240 pieces × ₹12 = ₹2,880 (rate from 1 Oct 2026); TDS ₹29"


def test_labour_bill_two_lots_and_no_tds():
    other = NS(lot_no="L-13")
    assert narration.labour_bill(RAMESH, [(LOT, STITCHING, 240, RATE_12), (other, STITCHING, 10, RATE_12)], tds=D("0")) == \
        ("Stitching by Ramesh, lot L-12: 240 pieces × ₹12 = ₹2,880 (rate from 1 Oct 2026); "
         "Stitching by Ramesh, lot L-13: 10 pieces × ₹12 = ₹120 (rate from 1 Oct 2026)")


def test_packed():
    assert narration.packed(LOT, 230, D("96.40")) == "Lot L-12: 230 pieces packed into Ready Goods at ₹96.40 a piece"


def test_moved_between_factories():
    assert narration.moved_between_factories(LOT, FACTORY1, FACTORY2, 240, D("18200")) == \
        "Lot L-12 moved from Factory 1 to Factory 2: 240 pieces, ₹18,200 of work in progress"


def test_fabric_cut():
    assert narration.fabric_cut(LOT, 1, D("58.40"), "m", D("8760")) == "Fabric cut for lot L-12, Cutting 1: 58.40 m, ₹8,760"


def test_materials_used():
    zips, thread = NS(name="Zipper", unit=NS(code="PCS")), NS(name="Thread", unit=NS(code="CONE"))
    assert narration.materials_used(STITCHING, LOT, [(zips, D("240")), (thread, D("4.000"))], D("1120")) == \
        "Trims used at Stitching, lot L-12: Zipper 240 PCS, Thread 4 CONE, ₹1,120"


def test_a_cutting_voucher_reads_as_a_sentence(company, factory, owner):
    ns = build(company, factory, owner)
    set_inhouse_rate("CUT", "2")
    cut(ns)                                                   # 100 pieces; 43 kg of roll A burnt
    texts = list(Voucher.objects.filter(voucher_type="stock_journal").values_list("narration", flat=True))
    assert f"Cutting in-house at {factory.name}, lot {ns.lot.lot_no}: 100 pieces × ₹2 = ₹200 (rate from 1 Apr 2026)" in texts
    assert any(t.startswith(f"Fabric cut for lot {ns.lot.lot_no}, Cutting 1: 43 KG, ₹") for t in texts)


def test_a_production_voucher_links_back_to_its_lot(company, factory, owner):
    ns = build(company, factory, owner)
    set_inhouse_rate("CUT", "2")
    cut(ns)
    v = Voucher.objects.filter(narration__startswith="Cutting in-house").get()
    c = Client()
    c.force_login(owner)
    page = c.get(reverse("voucher_detail", args=[v.pk])).content.decode()
    assert reverse("lot_detail", args=[ns.lot.pk]) in page and ns.lot.lot_no in page
