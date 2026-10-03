from decimal import Decimal

import pytest

from core.exceptions import BusinessRuleError
from core.models import Location
from inventory.models import FabricRoll
from inventory.services import stock
from ledger.models import Voucher
from masters.models import Colour, Material, Product, Size, Unit
from masters.services import styles
from tests.test_imports import run, sheet

D = Decimal


def test_opening_stock_import_posts_rolls_items_and_skus(company, factory, owner):
    Material.objects.create(code="FAB-001", name="Fleece", kind="fabric", unit=Unit.objects.get(code="KG"))
    Material.objects.create(code="ZIP-1", name="Zipper", kind="trim", unit=Unit.objects.get(code="PCS"))
    s = styles.create_style(company=company, style_no="J1", product=Product.objects.get(code="JGR"), name="J",
                            colours=list(Colour.objects.filter(name="Black")), sizes=list(Size.objects.filter(code="M")))
    barcode = s.skus.get().barcode
    godown = Location.objects.get(factory=factory, name="Main Godown")
    data = sheet("opening_stock", ["fab-001", 100, 180, "OLD-1", "L1", 280, 180, ""], ["FAB-001", 50, 190, "OLD-2", "", "", "", ""],
                 ["ZIP-1", 500, "2.5", "", "", "", "", ""], [barcode, 40, 300, "", "", "", "", ""])
    r = run("opening_stock", data, company, owner, factory=factory, location=godown, commit=True)
    assert r.clean and r.committed
    fab = Material.objects.get(code="FAB-001")
    assert stock.on_hand(factory, fab) == (D("150.000"), D("27500.00")) and FabricRoll.objects.count() == 2
    assert stock.on_hand(factory, s.skus.get()) == (D("40.000"), D("12000.00"))


def test_opening_stock_import_errors_name_the_rows_and_post_nothing(company, factory, owner):
    Material.objects.create(code="FAB-001", name="Fleece", kind="fabric", unit=Unit.objects.get(code="KG"))
    godown = Location.objects.get(factory=factory, name="Main Godown")
    r = run("opening_stock", sheet("opening_stock", ["NOPE", 1, 1, "", "", "", "", ""], ["FAB-001", 5, 1, "", "", "", "", ""]),
            company, owner, factory=factory, location=godown, commit=True)
    assert r.errors[0][0] == 2 and "No material" in r.errors[0][1] and not r.committed
    r2 = run("opening_stock", sheet("opening_stock", ["FAB-001", 5, 1, "", "", "", "", ""]), company, owner,
             factory=factory, location=godown, commit=True)
    assert "roll" in r2.errors[0][1] and not Voucher.objects.exists()  # a fabric row without a roll number posts nothing
    with pytest.raises(BusinessRuleError):
        run("opening_stock", sheet("opening_stock"), company, owner, commit=True)
