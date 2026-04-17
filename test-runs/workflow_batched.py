"""
Deep workflow tests for Jewel India ERP — batched to avoid browser resource exhaustion.
Each batch gets a fresh browser context.
"""
import json, time, subprocess, sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:4321"

# All routes to test, grouped into batches
BATCHES = [
    {
        "name": "Core + Sales + Purchase",
        "routes": [
            ("core", "dashboard", "dashboard"),
            ("sales", "voucher_list", "sales/list"),
            ("sales", "voucher_add", "sales/add"),
            ("sales", "return_list", "sales/salesreturn/list/"),
            ("sales", "approval_list", "sales/salesapproval/list/"),
            ("purchase", "voucher_list", "purchase/list"),
            ("purchase", "voucher_add", "purchase/add"),
            ("purchase", "return_list", "purchase/purchasereturn/list/"),
            ("purchase", "order_list", "purchase/purchaseorder/list"),
        ],
    },
    {
        "name": "Inventory",
        "routes": [
            ("inventory", "stock_journal_list", "inventory/stockjournal/"),
            ("inventory", "stock_journal_add", "inventory/stockjournal/add"),
            ("inventory", "stock_transfer_list", "inventory/stocktransfer"),
            ("inventory", "stock_transfer_add", "inventory/stocktransfer/add"),
            ("inventory", "barcode_list", "inventory/barcodemanagement/list"),
            ("inventory", "barcode_add", "inventory/barcodemanagement/list/add"),
            ("inventory", "barcode_bulk", "inventory/barcode-bulk"),
            ("inventory", "barcode_merge", "inventory/barcodemanagement/merge/"),
        ],
    },
    {
        "name": "Manufacturing Issue",
        "routes": [
            ("mfg", "goldissue_add", "manufacturing/issue/goldissue/add"),
            ("mfg", "hallmark_add", "manufacturing/issue/hallmarkissue/add"),
            ("mfg", "melting_add", "manufacturing/issue/melting/add"),
            ("mfg", "refinary_add", "manufacturing/issue/refinary/add"),
            ("mfg", "assay_add", "manufacturing/issue/assay/add"),
            ("mfg", "stoneissue_add", "manufacturing/issue/stoneissue/add"),
            ("mfg", "jobwork_add", "manufacturing/issue/jobwork/add"),
        ],
    },
    {
        "name": "Manufacturing Receive + Lists",
        "routes": [
            ("mfg", "jobwork_recv", "manufacturing/receive/jobworkreceive/add"),
            ("mfg", "hallmark_recv", "manufacturing/receive/hallmarkreceive/add"),
            ("mfg", "refinary_recv", "manufacturing/receive/refinary/add"),
            ("mfg", "assay_recv", "manufacturing/receive/assay/add"),
            ("mfg", "stonereturn", "manufacturing/receive/stonereturn/add"),
            ("mfg", "goldissue_list", "manufacturing/issue/goldissue"),
            ("mfg", "karigar_list", "manufacturing/karigar"),
            ("mfg", "repair_new", "manufacturing/repair/new"),
        ],
    },
    {
        "name": "Financial Reports",
        "routes": [
            ("reports", "balance_sheet", "accounting/reports/balancesheet"),
            ("reports", "pnl", "accounting/reports/pnl"),
            ("reports", "daybook", "accounting/reports/daybook"),
            ("reports", "trial_balance", "accounting/reports/trialbalance"),
            ("reports", "cash_book", "accounting/reports/cashbook"),
            ("reports", "bank_book", "accounting/reports/bankbook"),
            ("reports", "ledger_report", "accounting/reports/ledgerreport"),
            ("reports", "chart_of_accounts", "accounting/chartofaccounts"),
        ],
    },
    {
        "name": "Accounting Vouchers + CRM",
        "routes": [
            ("accounting", "journal_list", "accounting/vouchers/journal/list"),
            ("accounting", "payment_list", "accounting/vouchers/payment/list"),
            ("accounting", "receipt_list", "accounting/vouchers/receipt/list"),
            ("accounting", "contra_list", "accounting/vouchers/contra/list"),
            ("accounting", "journal_add", "accounting/vouchers/journal/add"),
            ("crm", "dashboard", "crm"),
            ("crm", "ledger_list", "crm/ledger"),
            ("crm", "ledger_add", "crm/ledger/add"),
        ],
    },
    {
        "name": "Inv Reports + Masters",
        "routes": [
            ("inv_reports", "stock_value", "inventory/reports/stockvalue"),
            ("inv_reports", "barcode_report", "inventory/reports/barcodereport"),
            ("inv_reports", "id_generation", "inventory/reports/idgen"),
            ("inv_reports", "raw_material", "inventory/reports/raw-material"),
            ("inv_reports", "metal_report", "inventory/metalreport"),
            ("masters", "item_master", "masters/item"),
            ("masters", "item_group", "masters/item-group"),
            ("masters", "hsn", "masters/hsn"),
        ],
    },
    {
        "name": "Masters + GoldScheme + HR + FixedAssets",
        "routes": [
            ("masters", "purity", "masters/purity"),
            ("masters", "branch", "masters/branch"),
            ("masters", "company", "masters/company"),
            ("masters", "gstin", "masters/gstin"),
            ("goldscheme", "scheme_list", "goldscheme"),
            ("goldscheme", "enrollments", "goldscheme/enrollments"),
            ("hr", "employees", "hr/employees"),
            ("hr", "attendance", "hr/attendance"),
            ("fixed_assets", "asset_list", "accounting/fixedassets"),
            ("fixed_assets", "depreciation", "accounting/fixedassets/depreciation"),
            ("sales", "quotation_add", "sales/quotation/add/"),
        ],
    },
]

all_results = []


def login(page):
    page.goto(f"{BASE}/login")
    page.wait_for_load_state("networkidle")
    time.sleep(1)
    page.fill('#baseUrl', 'http://127.0.0.1:8000/')
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    time.sleep(1)
    page.fill('#username', 'admin')
    page.fill('#password', 'admin123')
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    time.sleep(2)


def test_route(page, category, test_name, route):
    console_errors = []
    page_errors = []
    http_errors = []

    def on_console(msg):
        if msg.type == "error":
            text = msg.text[:200] if hasattr(msg, 'text') else str(msg)[:200]
            console_errors.append(text)

    def on_page_error(err):
        page_errors.append(str(err)[:200])

    def on_response(resp):
        if resp.status >= 400:
            http_errors.append({"url": resp.url, "status": resp.status})

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("response", on_response)

    try:
        page.goto(f"{BASE}/{route}", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=25000)
        time.sleep(1)
    except Exception as e:
        page_errors.append(f"Navigation: {str(e)[:150]}")

    page.remove_listener("console", on_console)
    page.remove_listener("pageerror", on_page_error)
    page.remove_listener("response", on_response)

    # Determine status
    if page_errors or http_errors:
        status = "FAIL"
    elif console_errors:
        # Filter out React DOM warnings (cosmetic)
        real_errors = [e for e in console_errors if "validateDOMNesting" not in e and "unique \"key\"" not in e]
        if real_errors:
            status = "WARN"
        else:
            status = "PASS"
    else:
        status = "PASS"

    # Extra info
    details = ""
    if status == "FAIL":
        details = str(http_errors + page_errors)[:300]
    elif status == "WARN":
        details = str(console_errors[:2])[:300]

    result = {
        "category": category,
        "test": test_name,
        "route": route,
        "status": status,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "http_errors": http_errors,
        "details": details,
    }
    all_results.append(result)
    print(f"[{status}] {category}/{test_name}" + (f": {details[:150]}" if details else ""))
    return result


with sync_playwright() as p:
    for batch in BATCHES:
        print(f"\n{'='*50}")
        print(f"Batch: {batch['name']}")
        print(f"{'='*50}")

        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        login(page)

        for (cat, name, route) in batch["routes"]:
            test_route(page, cat, name, route)

        context.close()
        browser.close()
        time.sleep(1)  # let resources clean up

# Summary
print("\n" + "="*60)
print("WORKFLOW TEST SUMMARY")
print("="*60)
passes = sum(1 for r in all_results if r["status"] == "PASS")
warns = sum(1 for r in all_results if r["status"] == "WARN")
fails = sum(1 for r in all_results if r["status"] == "FAIL")
total = len(all_results)
print(f"PASS: {passes} | WARN: {warns} | FAIL: {fails} | Total: {total}")
print(f"Pass rate: {passes/total*100:.1f}%" if total else "No tests run")

if fails:
    print(f"\n--- FAILURES ({fails}) ---")
    for r in all_results:
        if r["status"] == "FAIL":
            print(f"  {r['category']}/{r['test']} ({r['route']}): {r['details'][:200]}")

if warns:
    print(f"\n--- WARNINGS ({warns}) ---")
    for r in all_results:
        if r["status"] == "WARN":
            print(f"  {r['category']}/{r['test']}: {r['details'][:200]}")

with open("test-runs/workflow_results.json", "w") as f:
    json.dump(all_results, f, indent=2, default=str)
print("\nResults saved to test-runs/workflow_results.json")
