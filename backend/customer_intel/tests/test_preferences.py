"""Buying-preference rollups."""

from datetime import date

from django.test import TestCase

from customer_intel.services import preferences
from customer_intel.tests.factories import (
    make_barcode,
    make_customer,
    make_item,
    make_item_group,
    make_purity,
    make_retail,
    make_sale,
    make_sale_line,
)


class CategoryPreferenceTests(TestCase):
    def setUp(self):
        self.retail = make_retail()
        self.customer = make_customer(self.retail, "Buyer")
        self.sale = make_sale(self.retail, self.customer, date(2026, 5, 1), mrp=300000)

    def test_shares_sum_to_one_and_are_ordered_by_value(self):
        rings = make_item("Ladies Ring", "LR")
        chains = make_item("Gold Chain", "GC")
        make_sale_line(self.sale, rings, amount=75000)
        make_sale_line(self.sale, chains, amount=25000)

        result = preferences.category_prefs(self.retail.id, [self.customer.id])
        entries = result[self.customer.id]

        self.assertEqual([e["label"] for e in entries], ["Ladies Ring", "Gold Chain"])
        self.assertAlmostEqual(entries[0]["share"], 0.75, places=4)
        self.assertAlmostEqual(entries[1]["share"], 0.25, places=4)
        self.assertAlmostEqual(sum(e["share"] for e in entries), 1.0, places=4)

    def test_falls_back_to_item_when_the_group_link_is_missing(self):
        """
        Every row in the live item_master has a null grp_id, so the item-level
        fallback is the normal path, not an edge case.
        """
        make_sale_line(self.sale, make_item("Lab Diamond Ear Tops", "LET"),
                       amount=50000)

        entries = preferences.category_prefs(
            self.retail.id, [self.customer.id],
        )[self.customer.id]

        self.assertEqual(entries[0]["level"], "item")
        self.assertEqual(entries[0]["label"], "Lab Diamond Ear Tops")

    def test_uses_the_group_when_one_exists(self):
        group = make_item_group("Earrings")
        make_sale_line(self.sale, make_item("Ear Tops", "ET", group=group),
                       amount=50000)

        entries = preferences.category_prefs(
            self.retail.id, [self.customer.id],
        )[self.customer.id]

        self.assertEqual(entries[0]["level"], "group")
        self.assertEqual(entries[0]["label"], "Earrings")

    def test_returned_lines_are_excluded(self):
        kept = make_item("Kept Ring", "KR")
        returned = make_item("Returned Ring", "RR")
        make_sale_line(self.sale, kept, amount=60000)
        make_sale_line(self.sale, returned, amount=90000, ret_status=True)

        entries = preferences.category_prefs(
            self.retail.id, [self.customer.id],
        )[self.customer.id]

        self.assertEqual([e["label"] for e in entries], ["Kept Ring"])

    def test_other_customers_do_not_leak_in(self):
        other = make_customer(self.retail, "Other")
        other_sale = make_sale(self.retail, other, date(2026, 5, 2), mrp=100000,
                               billno="OTHER1")
        make_sale_line(self.sale, make_item("Mine", "MN"), amount=10000)
        make_sale_line(other_sale, make_item("Theirs", "TH"), amount=99000)

        result = preferences.category_prefs(
            self.retail.id, [self.customer.id, other.id],
        )

        self.assertEqual([e["label"] for e in result[self.customer.id]], ["Mine"])
        self.assertEqual([e["label"] for e in result[other.id]], ["Theirs"])

    def test_other_retail_does_not_leak_in(self):
        elsewhere = make_retail(name="Elsewhere", code="EL")
        away_sale = make_sale(elsewhere, self.customer, date(2026, 5, 3),
                              mrp=100000, billno="AWAY1")
        make_sale_line(self.sale, make_item("Here", "HE"), amount=10000)
        make_sale_line(away_sale, make_item("Away", "AW"), amount=99000)

        entries = preferences.category_prefs(
            self.retail.id, [self.customer.id],
        )[self.customer.id]

        self.assertEqual([e["label"] for e in entries], ["Here"])


class PurityPreferenceTests(TestCase):
    def test_purity_comes_from_the_barcode_not_the_line(self):
        """
        SalesVouItem.purity is a bare integer, not a FK to PurityMaster —
        reading it as a purity id would yield garbage. The rollup must join
        through BarcodeMain.purity.
        """
        retail = make_retail()
        customer = make_customer(retail, "Purity Buyer")
        sale = make_sale(retail, customer, date(2026, 5, 1), mrp=100000)
        item = make_item()
        purity = make_purity("22")
        barcode = make_barcode(retail, item, purity=purity)

        # A deliberately misleading integer on the line itself.
        line = make_sale_line(sale, item, barcode=barcode, amount=50000)
        line.purity = 999
        line.save(update_fields=["purity"])

        entries = preferences.purity_prefs(retail.id, [customer.id])[customer.id]

        self.assertEqual(entries[0]["label"], "22")
        self.assertEqual(entries[0]["id"], purity.id)


class BuildAllTests(TestCase):
    def test_every_customer_gets_a_key_even_with_no_purchases(self):
        retail = make_retail()
        buyer = make_customer(retail, "Buyer")
        idle = make_customer(retail, "Idle")
        sale = make_sale(retail, buyer, date(2026, 5, 1), mrp=100000)
        make_sale_line(sale, make_item(), amount=50000)

        result = preferences.build_all(retail.id, [buyer.id, idle.id])

        self.assertEqual(set(result), {buyer.id, idle.id})
        self.assertTrue(result[buyer.id]["category"])
        self.assertEqual(result[idle.id]["category"], [])
        self.assertEqual(result[idle.id]["stone"], {})
