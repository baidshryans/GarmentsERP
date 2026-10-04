from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from core.exceptions import BusinessRuleError
from ledger.models import Ledger
from masters.models import SKU, BomVersion, Colour, Material, Party, PriceList, Process, Product, RouteStep, Size, Unit
from masters.services import boms, parties, pricing, routes, styles
from masters.services.codes import next_barcode
from tax.models import HSN
from tax.services import gst_rate_for

D = Decimal
SIZES5 = ["S", "M", "L", "XL", "XXL"]


@pytest.fixture
def basics(company):
    return {
        "colours": list(Colour.objects.filter(name__in=["Black", "Navy", "Grey Melange"])),
        "sizes": list(Size.objects.filter(code__in=SIZES5)),
        "product": Product.objects.get(code="JGR"),
    }


@pytest.fixture
def style(company, basics):
    return styles.create_style(
        company=company, style_no="jgr-104", product=basics["product"], name="Cuffed jogger",
        colours=basics["colours"], sizes=basics["sizes"],
    )


# ---------------- seeds ----------------

def test_wizard_seeds_default_masters_and_hsn(company):
    assert Unit.objects.filter(code__in=["PCS", "KG", "MTR", "GRS"]).count() == 4
    assert Size.objects.filter(code__in=SIZES5 + ["FREE", "4-6Y"]).count() == 7
    assert set(Product.objects.values_list("code", flat=True)) >= {"TRK", "JGR", "TSH", "SET"}
    assert Process.objects.filter(code__in=["CUT", "STITCH", "EMB", "PRINT", "WASH", "IRON", "PACK"]).count() == 7
    route = RouteStep.objects.filter(template__name="Standard track pant route")
    assert route.count() == 9 and route.get(process__code="STITCH").assignment == "subcontract"
    assert HSN.objects.filter(code="6103").exists()


def test_hsn_slabs_pick_rate_by_value_and_date(company):
    hsn = HSN.objects.get(code="6103")
    assert gst_rate_for(hsn, D("800"), date(2026, 6, 1)) == D("5.00")
    assert gst_rate_for(hsn, D("2500.00"), date(2026, 6, 1)) == D("5.00")
    assert gst_rate_for(hsn, D("2600"), date(2026, 6, 1)) == D("18.00")
    assert gst_rate_for(hsn, D("800"), date(2025, 1, 1)) is None  # before any slab existed
    from tax.models import HsnSlab

    HsnSlab.objects.create(hsn=hsn, value_from=D("0"), value_to=None, gst_rate=D("12"), effective_from=date(2027, 1, 1))
    assert gst_rate_for(hsn, D("800"), date(2026, 12, 31)) == D("5.00")  # old documents keep their rate
    assert gst_rate_for(hsn, D("800"), date(2027, 1, 1)) == D("12.00")


# ---------------- E2.1 style -> SKUs ----------------

def test_style_with_3_colours_and_5_sizes_makes_15_unique_barcoded_skus(style):
    skus = SKU.objects.filter(style=style)
    assert skus.count() == 15
    barcodes = list(skus.values_list("barcode", flat=True))
    assert len(set(barcodes)) == 15 and all(b.isdigit() and len(b) == 10 for b in barcodes)
    assert style.style_no == "JGR-104"


def test_adding_a_colour_creates_only_missing_skus(company, style, basics):
    before = set(SKU.objects.values_list("pk", "barcode"))
    styles.sync_variants(style, colours=basics["colours"] + [Colour.objects.get(name="Maroon")],
                         sizes=basics["sizes"], company=company)
    assert SKU.objects.filter(style=style).count() == 20
    assert before <= set(SKU.objects.values_list("pk", "barcode"))  # existing SKUs and barcodes untouched


def test_removing_a_size_deactivates_never_deletes_and_readding_reactivates(company, style, basics):
    styles.sync_variants(style, colours=basics["colours"], sizes=basics["sizes"][:4], company=company)
    assert SKU.objects.filter(style=style).count() == 15
    assert SKU.objects.filter(style=style, is_active=True).count() == 12
    styles.sync_variants(style, colours=basics["colours"], sizes=basics["sizes"], company=company)
    assert SKU.objects.filter(style=style, is_active=True).count() == 15


def test_style_needs_colour_and_size(company, basics):
    with pytest.raises(BusinessRuleError):
        styles.create_style(company=company, style_no="X1", product=basics["product"], name="x", colours=[], sizes=basics["sizes"])


def test_barcode_length_is_configurable(company):
    from masters.models import CodeCounter

    next_barcode(company)
    CodeCounter.objects.filter(company=company, key="barcode").update(padding=13)
    assert len(next_barcode(company)) == 13


def test_style_image_original_kept_and_thumbnail_made(company, basics, settings):
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (1600, 1200), "red").save(buf, "PNG")
    s = styles.create_style(
        company=company, style_no="IMG1", product=basics["product"], name="With photo", colours=basics["colours"][:1],
        sizes=basics["sizes"][:1], image=SimpleUploadedFile("p.png", buf.getvalue(), "image/png"),
    )
    with s.image.open("rb") as f:
        assert Image.open(f).size == (1600, 1200)
    with s.thumbnail.open("rb") as f:
        assert max(Image.open(f).size) <= 320
    assert s.thumbnail.size < s.image.size


# ---------------- E2.2 BOM versions ----------------

@pytest.fixture
def fabric(db):
    return Material.objects.create(code="FAB-1", name="Cotton fleece 280 GSM", kind="fabric", unit=Unit.objects.get(code="KG"), gsm=280)


@pytest.fixture
def zip_trim(db):
    return Material.objects.create(code="ZIP-1", name="Zipper 5in", kind="trim", unit=Unit.objects.get(code="PCS"))


def test_first_bom_is_version_1_and_edits_in_place_until_used(style, fabric, zip_trim):
    v1, new = boms.save_bom(style, lines=[boms.BomLineSpec(fabric, D("0.4500"))])
    assert v1.version_no == 1 and not new
    v1b, new = boms.save_bom(style, lines=[boms.BomLineSpec(fabric, D("0.4800")), boms.BomLineSpec(zip_trim, D("1"))])
    assert v1b.pk == v1.pk and not new and v1.lines.count() == 2


def test_changing_a_used_bom_creates_new_version_and_old_lots_keep_the_old(style, fabric, zip_trim, monkeypatch):
    v1, _ = boms.save_bom(style, lines=[boms.BomLineSpec(fabric, D("0.45"))])
    monkeypatch.setattr(boms, "_USAGE_CHECKS", [lambda v: v.pk == v1.pk])  # a lot now uses v1
    v2, new = boms.save_bom(style, lines=[boms.BomLineSpec(fabric, D("0.50"))], notes="Heavier fabric")
    assert new and v2.version_no == 2 and v2.is_current
    v1.refresh_from_db()
    assert not v1.is_current and v1.lines.get().qty_per_piece == D("0.45")  # unchanged for old lots
    assert BomVersion.objects.filter(style=style, is_current=True).count() == 1


def test_size_wise_consumption(style, fabric):
    xxl, s = Size.objects.get(code="XXL"), Size.objects.get(code="S")
    v, _ = boms.save_bom(style, lines=[boms.BomLineSpec(fabric, D("0.45"), D("3"), {xxl: D("0.55")})],
                         charges=[boms.BomChargeSpec("Embroidery", D("6.50"), Process.objects.get(code="EMB"))])
    assert boms.consumption_for(v, xxl)[0][1] == D("0.55")
    assert boms.consumption_for(v, s)[0][1] == D("0.45")
    assert v.charges.get().amount_per_piece == D("6.50")


def test_bom_rules(style, fabric):
    with pytest.raises(BusinessRuleError):
        boms.save_bom(style, lines=[])
    with pytest.raises(BusinessRuleError):
        boms.save_bom(style, lines=[boms.BomLineSpec(fabric, D("0"))])
    with pytest.raises(BusinessRuleError):
        boms.save_bom(style, lines=[boms.BomLineSpec(fabric, D("1")), boms.BomLineSpec(fabric, D("2"))])
    free = Size.objects.get(code="FREE")
    with pytest.raises(BusinessRuleError):
        boms.save_bom(style, lines=[boms.BomLineSpec(fabric, D("1"), size_qty={free: D("1")})])


# ---------------- E2.3 routes ----------------

def test_route_steps_keep_order_optional_flag_and_default_assignment(db, factory):
    p = {c: Process.objects.get(code=c) for c in ("CUT", "STITCH", "EMB", "IRON")}
    fab = parties.create_party(company=factory.company, name="Sharma Stitching", mobile="9811111111", is_fabricator=True)
    route = routes.save_route(name="Jogger route", steps=[
        routes.StepSpec(p["CUT"], default_factory=factory),
        routes.StepSpec(p["STITCH"], assignment="subcontract", default_party=fab, rate=D("25")),
        routes.StepSpec(p["EMB"], is_mandatory=False, assignment="subcontract"),
        routes.StepSpec(p["IRON"]),
    ])
    steps = list(route.steps.all())
    assert [s.process.code for s in steps] == ["CUT", "STITCH", "EMB", "IRON"]
    assert [s.sequence for s in steps] == [1, 2, 3, 4]
    assert steps[1].rate == D("25.00") and steps[1].default_party == fab and not steps[2].is_mandatory


def test_route_validation(db, factory):
    cut, stitch = Process.objects.get(code="CUT"), Process.objects.get(code="STITCH")
    cust = parties.create_party(company=factory.company, name="Dealer", mobile="9822222222", is_customer=True)
    with pytest.raises(BusinessRuleError):
        routes.save_route(name="empty", steps=[])
    with pytest.raises(BusinessRuleError):
        routes.save_route(name="bad", steps=[routes.StepSpec(stitch, assignment="subcontract", default_party=cust)])
    with pytest.raises(BusinessRuleError):
        routes.save_route(name="bad2", steps=[routes.StepSpec(cut, assignment="subcontract", default_factory=factory)])


# ---------------- E3.1 parties ----------------

def test_customer_gets_bill_wise_debtor_ledger_and_state_from_gstin(company):
    c = parties.create_party(company=company, name="Mehta Traders", mobile="+91 98765 43210",
                             gstin="27ABCDE1234F1Z5", is_customer=True, credit_limit=D("50000"))
    assert c.mobile == "9876543210" and c.state_code == "27" and c.pan == "ABCDE1234F"
    assert c.code == "P0001"
    assert c.customer_ledger.group.name == "Sundry Debtors" and c.customer_ledger.bill_wise
    assert c.payable_ledger is None


def test_duplicate_customer_mobile_rejected_naming_the_existing_customer(company):
    parties.create_party(company=company, name="Mehta Traders", mobile="9876543210", is_customer=True)
    with pytest.raises(BusinessRuleError, match="Mehta Traders"):
        parties.create_party(company=company, name="Other Firm", mobile="9876543210", is_customer=True)
    # the same mobile may still be a vendor
    parties.create_party(company=company, name="Other Firm", mobile="9876543210", is_vendor=True)


def test_database_also_enforces_one_mobile_per_customer(company):
    from django.db import IntegrityError, transaction

    parties.create_party(company=company, name="A", mobile="9876543210", is_customer=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        Party.objects.create(company=company, code="ZZ", name="B", mobile="9876543210", is_customer=True)


def test_fabricator_mobile_unique_among_fabricators(company):
    parties.create_party(company=company, name="F1", mobile="9811111111", is_fabricator=True)
    with pytest.raises(BusinessRuleError, match="fabricator F1"):
        parties.create_party(company=company, name="F2", mobile="9811111111", is_fabricator=True)


@pytest.mark.parametrize("mobile", ["12345", "5876543210", "abcdefghij", ""])
def test_bad_mobile_rejected(company, mobile):
    with pytest.raises(ValidationError):
        parties.create_party(company=company, name="X", mobile=mobile, is_customer=True)


def test_bad_gstin_and_missing_role_rejected(company):
    with pytest.raises(ValidationError):
        parties.create_party(company=company, name="X", mobile="9876543210", gstin="NOTAGSTIN", is_customer=True)
    with pytest.raises(ValidationError):
        parties.create_party(company=company, name="X", mobile="9876543210")


def test_party_with_both_roles_gets_two_ledgers_and_vendor_gets_creditor(company):
    both = parties.create_party(company=company, name="Dual Co", mobile="9876543210", is_customer=True, is_vendor=True)
    assert both.customer_ledger.group.name == "Sundry Debtors"
    assert both.payable_ledger.group.name == "Sundry Creditors" and both.payable_ledger.name == "Dual Co (Payable)"
    vendor = parties.create_party(company=company, name="Yarn House", mobile="9833333333", is_vendor=True)
    assert vendor.payable_ledger.name == "Yarn House"


def test_same_name_different_party_does_not_collide_on_ledger(company):
    a = parties.create_party(company=company, name="Same Name", mobile="9876543210", is_customer=True)
    b = parties.create_party(company=company, name="Same Name", mobile="9876543211", is_customer=True)
    assert a.customer_ledger.name != b.customer_ledger.name and b.customer_ledger.name.endswith("[P0002]")


def test_adding_a_role_later_creates_the_ledger_and_deactivation_follows(company):
    p = parties.create_party(company=company, name="Late Vendor", mobile="9876543210", is_customer=True)
    p = parties.update_party(p, is_vendor=True)
    assert p.payable_ledger is not None
    p = parties.update_party(p, is_active=False)
    assert not Ledger.objects.get(pk=p.customer_ledger_id).is_active and not Ledger.objects.get(pk=p.payable_ledger_id).is_active


def test_party_ledger_creation_posts_nothing(company):
    from ledger.selectors import trial_balance

    parties.create_party(company=company, name="Mehta", mobile="9876543210", is_customer=True)
    assert trial_balance(company)["rows"] == []


# ---------------- prices (PRC) ----------------

def test_price_list_slabs_and_future_only_changes(style):
    from masters.models import PriceListRate

    pl = PriceList.objects.create(name="Wholesale", kind="wholesale")
    m = Size.objects.get(code="M")
    PriceListRate.objects.create(price_list=pl, style=style, min_qty=1, rate=D("500"), effective_from=date(2026, 4, 1))
    PriceListRate.objects.create(price_list=pl, style=style, min_qty=100, rate=D("470"), effective_from=date(2026, 4, 1))
    PriceListRate.objects.create(price_list=pl, style=style, min_qty=1, rate=D("520"), effective_from=date(2026, 9, 1))
    PriceListRate.objects.create(price_list=pl, style=style, size=m, min_qty=1, rate=D("510"), effective_from=date(2026, 4, 1))
    S = Size.objects.get(code="S")
    assert pricing.price_list_rate(pl, style, S, 10, date(2026, 8, 1)) == D("500.00")
    assert pricing.price_list_rate(pl, style, S, 150, date(2026, 8, 1)) == D("470.00")  # quantity slab
    assert pricing.price_list_rate(pl, style, S, 10, date(2026, 9, 5)) == D("520.00")   # new price, new orders only
    assert pricing.price_list_rate(pl, style, S, 10, date(2026, 8, 1)) == D("500.00")   # old orders unchanged
    assert pricing.price_list_rate(pl, style, m, 10, date(2026, 8, 1)) == D("510.00")   # size-specific wins
    assert pricing.price_list_rate(pl, style, S, 10, date(2026, 3, 1)) is None


def test_customer_rate_style_beats_product_and_is_dated(company, style):
    from masters.models import CustomerRate

    c = parties.create_party(company=company, name="Mehta", mobile="9876543210", is_customer=True)
    CustomerRate.objects.create(party=c, product=style.product, rate=D("480"), effective_from=date(2026, 4, 1))
    assert pricing.customer_rate(c, style, date(2026, 5, 1)) == D("480.00")
    CustomerRate.objects.create(party=c, style=style, rate=D("455"), effective_from=date(2026, 6, 1))
    assert pricing.customer_rate(c, style, date(2026, 5, 1)) == D("480.00")
    assert pricing.customer_rate(c, style, date(2026, 6, 1)) == D("455.00")


def test_customer_rate_must_target_exactly_one_of_style_or_product(company, style):
    from django.db import IntegrityError, transaction

    from masters.models import CustomerRate

    c = parties.create_party(company=company, name="Mehta", mobile="9876543210", is_customer=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        CustomerRate.objects.create(party=c, rate=D("1"), effective_from=date(2026, 4, 1))
    with pytest.raises(IntegrityError), transaction.atomic():
        CustomerRate.objects.create(party=c, style=style, product=style.product, rate=D("1"), effective_from=date(2026, 4, 1))


def test_seeding_masters_is_idempotent_and_adds_only_missing(company):
    from core.seeding import seed_company

    Colour.objects.filter(name="Black").update(name="Jet Black")
    n = Colour.objects.count()
    seed_company(company)
    assert Colour.objects.filter(name="Jet Black").exists() and Colour.objects.filter(name="Black").exists()
    assert Colour.objects.count() == n + 1

