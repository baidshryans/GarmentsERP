from decimal import Decimal

from django.test import TestCase
from accounting.utils import calculate_opening_stock
from inventory.models import Item, OpeningInventory


class CalculateOpeningStockTests(TestCase):
    """Opening stock value comes from OpeningInventory (the Opening Stock entry
    screen), valued as wtd_avg_rate x primary_qty: gw for metal (M/R), ct for
    stone (S)."""

    def _item(self, code, item_type):
        return Item.objects.create(
            short_code=code, item_name=f"Item {code}", item_type=item_type,
            uom="GM", show_in_pcs_report=False,
        )

    def test_values_metal_on_gw_and_stone_on_ct(self):
        metal = self._item("M1", "R")   # metal/raw -> gw * rate
        stone = self._item("S1", "S")   # stone -> ct * rate
        OpeningInventory.objects.create(
            item=metal, type="SH", gw=Decimal("10"), ct=Decimal("0"),
            wtd_avg_rate=Decimal("6000"),
        )
        OpeningInventory.objects.create(
            item=stone, type="SH", gw=Decimal("0"), ct=Decimal("5"),
            wtd_avg_rate=Decimal("40000"),
        )
        # metal: 10 * 6000 = 60000 ; stone: 5 * 40000 = 200000
        self.assertEqual(calculate_opening_stock(retail_ids=None), Decimal("260000"))

    def test_empty_opening_inventory_is_zero(self):
        self.assertEqual(calculate_opening_stock(retail_ids=None), Decimal("0"))
