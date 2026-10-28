"""Purchase approval: create / edit / return / buy-out / delete rules, through the real API."""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from contacts.models import Ledger
from mastersconfig.models import FiscalYearMaster, Item, RetailMaster, SystemSettings

from inventory.models import RawMaterialInventory, RawMaterialTransaction

from .models import PurchaseApproval, PurchaseApprovalItem, PurchaseVoucherItems

URL = "/purchase/api/purchase-approval/"


class _ApprovalBase(TestCase):
    def setUp(self):
        self.retail = RetailMaster.objects.create(
            retail_name="Appr Retail", retail_code="APPR", phone="0000000000", address_line1="Test")
        self.fy = FiscalYearMaster.objects.create(
            fy_code="25-26", fy_start=datetime.date(2025, 4, 1), fy_end=datetime.date(2026, 3, 31))
        SystemSettings.set_company_active_fy(self.fy)
        self.vendor = Ledger.objects.create(
            ac_name="Vendor A", display_name="Vendor A", b2b=False, tds_applicable=False, is_system=False)
        self.item = Item.objects.create(
            short_code="CHN", item_name="Chain", item_type="M", uom="GM", show_in_pcs_report=False)
        self.gold = Item.objects.create(
            short_code="GLD", item_name="Gold", item_type="R", uom="GM", show_in_pcs_report=False)
        self.stone = Item.objects.create(
            short_code="STN", item_name="Stone", item_type="S", uom="CT", show_in_pcs_report=False)
        self.user = get_user_model().objects.create_user(
            username="admin", password="pass12345", is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_X_RETAIL_ID=self.retail.retail_code)

    def _payload(self, lines=2, **extra):
        body = {
            "date1": "2025-06-01", "ldgr": self.vendor.id, "narration": "on approval",
            "items": [
                {"item": self.item.id, "pcs": 1, "gw": "10.000", "amount": "5000"}
                for _ in range(lines)
            ],
        }
        body.update(extra)
        return body

    def _create(self, **kw):
        r = self.client.post(URL, self._payload(**kw), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.data


class PurchaseApprovalApiTests(_ApprovalBase):
    def test_create_assigns_server_number_and_pending_lines(self):
        data = self._create()
        self.assertTrue(data["billno"].endswith("00001"), data["billno"])
        self.assertEqual(data["status"], "Open")
        self.assertEqual([i["status"] for i in data["items"]], ["pending", "pending"])
        self.assertEqual([i["sl_no"] for i in data["items"]], [1, 2])
        self.assertTrue(self._create()["billno"].endswith("00002"))

    def test_client_cannot_choose_the_bill_number(self):
        data = self._create(billno="HACK-1")
        self.assertNotEqual(data["billno"], "HACK-1")

    def test_requires_at_least_one_item(self):
        r = self.client.post(URL, self._payload(lines=0), format="json")
        self.assertEqual(r.status_code, 400)

    def test_sub_item_weight_must_match(self):
        body = self._payload(lines=1)
        body["items"][0]["details"] = [{"sub_item": self.item.id, "sub_gw": "3.000", "rate": "100"}]
        self.assertEqual(self.client.post(URL, body, format="json").status_code, 400)

    def test_edit_rebuilds_lines_while_all_pending(self):
        data = self._create()
        body = self._payload(lines=3, narration="changed")
        r = self.client.put(f"{URL}{data['id']}/", body, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data["items"]), 3)

    def test_return_then_status_closed_and_edit_blocked(self):
        data = self._create()
        ids = [i["id"] for i in data["items"]]
        r = self.client.post(f"{URL}{data['id']}/return-items/",
                             {"items": ids, "returned_on": "2025-06-10"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["status"], "Closed")
        self.assertEqual({i["status"] for i in r.data["items"]}, {"returned"})
        edit = self.client.put(f"{URL}{data['id']}/", self._payload(), format="json")
        self.assertEqual(edit.status_code, 400)
        self.assertEqual(self.client.delete(f"{URL}{data['id']}/").status_code, 400)

    def test_return_rejects_non_pending_lines_and_undo_restores(self):
        data = self._create()
        first = data["items"][0]["id"]
        self.client.post(f"{URL}{data['id']}/return-items/", {"items": [first]}, format="json")
        again = self.client.post(f"{URL}{data['id']}/return-items/", {"items": [first]}, format="json")
        self.assertEqual(again.status_code, 400)
        r = self.client.post(f"{URL}{data['id']}/undo-return/", {"items": [first]}, format="json")
        self.assertEqual(r.data["items"][0]["status"], "pending")

    def test_prefill_lists_only_pending_lines(self):
        data = self._create()
        first, second = [i["id"] for i in data["items"]]
        self.client.post(f"{URL}{data['id']}/return-items/", {"items": [first]}, format="json")
        r = self.client.get(f"{URL}{data['id']}/to-purchase-voucher/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([i["approval_item"] for i in r.data["items"]], [second])
        self.assertEqual(r.data["ldgr"], self.vendor.id)

    def test_line_linked_to_a_purchase_voucher_line_is_purchased(self):
        data = self._create()
        line = PurchaseApprovalItem.objects.get(pk=data["items"][0]["id"])
        PurchaseVoucherItems.objects.create(sl_no=1, item=self.item, approval_item=line)
        self.assertEqual(PurchaseApprovalItem.objects.get(pk=line.pk).status, "purchased")
        r = self.client.post(f"{URL}{data['id']}/return-items/", {"items": [line.id]}, format="json")
        self.assertEqual(r.status_code, 400)  # cannot return what was bought
        self.assertEqual(self.client.delete(f"{URL}{data['id']}/").status_code, 400)

    def test_delete_when_untouched_frees_the_number(self):
        data = self._create()
        self.assertEqual(self.client.delete(f"{URL}{data['id']}/").status_code, 204)
        self.assertTrue(self._create()["billno"].endswith("00001"))

    def test_closed_fiscal_year_blocks_changes(self):
        data = self._create()
        self.fy.is_closed = True
        self.fy.save()
        self.assertEqual(self.client.put(f"{URL}{data['id']}/", self._payload(), format="json").status_code, 400)
        self.assertEqual(self.client.delete(f"{URL}{data['id']}/").status_code, 400)

    def test_other_branch_cannot_see_it(self):
        data = self._create()
        other = RetailMaster.objects.create(
            retail_name="Other", retail_code="OTHR", phone="1", address_line1="x")
        self.client.credentials(HTTP_X_RETAIL_ID=other.retail_code)
        self.assertEqual(self.client.get(f"{URL}{data['id']}/").status_code, 404)


class PurchaseApprovalStockTests(_ApprovalBase):
    """An approval moves inventory like a purchase voucher, but posts no accounting entry."""

    def _with_subitems(self):
        body = {
            "date1": "2025-06-01", "ldgr": self.vendor.id, "narration": "x",
            "items": [{
                "item": self.item.id, "pcs": 1, "gw": "10.000", "making_type": "val", "making": "100",
                "making_value": "100",
                "details": [
                    {"sub_item": self.gold.id, "sub_pcs": 0, "sub_gw": "9.000", "rate": "6000"},
                    {"sub_item": self.stone.id, "sub_pcs": 5, "sub_gw": "1.000", "sub_ct": "5.000", "rate": "2000"},
                ],
            }],
        }
        r = self.client.post(URL, body, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.data

    def _stock(self, item):
        rows = RawMaterialInventory.objects.filter(item=item, retail=self.retail)
        return (sum(r.pcs for r in rows), sum(float(r.gw) for r in rows), sum(float(r.ct) for r in rows))

    def test_create_adds_main_and_sub_item_stock(self):
        self._with_subitems()
        self.assertEqual(self._stock(self.item), (1, 10.0, 0))
        self.assertEqual(self._stock(self.gold), (0, 9.0, 0))
        self.assertEqual(self._stock(self.stone), (5, 1.0, 5.0))

    def test_line_amount_is_sub_values_plus_making(self):
        data = self._with_subitems()
        # 9g * 6000 + 1g * 2000 + making 100
        self.assertEqual(float(data["items"][0]["amount"]), 9 * 6000 + 1 * 2000 + 100)

    def test_no_accounting_entry_is_created(self):
        from accounting.models import VoucherMain
        before = VoucherMain.objects.count()
        self._with_subitems()
        self.assertEqual(VoucherMain.objects.count(), before)

    def test_return_takes_stock_out_and_undo_puts_it_back(self):
        data = self._with_subitems()
        line = data["items"][0]["id"]
        self.client.post(f"{URL}{data['id']}/return-items/", {"items": [line]}, format="json")
        self.assertEqual(self._stock(self.item), (0, 0.0, 0))
        self.assertEqual(self._stock(self.stone), (0, 0.0, 0.0))
        self.client.post(f"{URL}{data['id']}/undo-return/", {"items": [line]}, format="json")
        self.assertEqual(self._stock(self.stone), (5, 1.0, 5.0))

    def test_edit_replaces_stock_instead_of_adding(self):
        data = self._with_subitems()
        body = {"date1": "2025-06-01", "ldgr": self.vendor.id, "narration": "x",
                "items": [{"item": self.item.id, "pcs": 2, "gw": "4.000"}]}
        r = self.client.put(f"{URL}{data['id']}/", body, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._stock(self.item), (2, 4.0, 0))
        self.assertEqual(self._stock(self.gold), (0, 0.0, 0))

    def test_delete_removes_the_stock(self):
        data = self._with_subitems()
        self.assertEqual(self.client.delete(f"{URL}{data['id']}/").status_code, 204)
        self.assertEqual(self._stock(self.item), (0, 0.0, 0))
        self.assertEqual(self._stock(self.stone), (0, 0.0, 0.0))

    def test_buying_a_line_nets_to_one_purchase_and_deleting_it_restores_the_approval(self):
        data = self._with_subitems()
        line = PurchaseApprovalItem.objects.get(pk=data["items"][0]["id"])
        pv_line = PurchaseVoucherItems.objects.create(
            sl_no=1, item=self.item, pcs=1, gw=Decimal("10.000"), approval_item=line, retail=self.retail)
        # approval gave its stock back; the voucher line holds the main item's stock now
        self.assertEqual(self._stock(self.item), (1, 10.0, 0))
        self.assertEqual(self._stock(self.stone), (0, 0.0, 0.0))
        pv_line.delete()
        self.assertEqual(self._stock(self.item), (1, 10.0, 0))
        self.assertEqual(self._stock(self.stone), (5, 1.0, 5.0))
        self.assertEqual(PurchaseApprovalItem.objects.get(pk=line.pk).status, "pending")

    def test_rows_created_before_stock_tracking_do_not_reverse_stock(self):
        data = self._with_subitems()
        PurchaseApprovalItem.objects.filter(pk=data["items"][0]["id"]).update(stock_applied=False)
        RawMaterialInventory.objects.all().delete()
        self.client.delete(f"{URL}{data['id']}/")
        self.assertEqual(self._stock(self.item), (0, 0.0, 0))
