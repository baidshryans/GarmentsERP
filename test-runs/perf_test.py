"""
Performance test: ensure all form and list pages load within 1.5 seconds.
Measures time from navigation start to networkidle.
"""
import json, time, sys
sys.stdout = open('D:/tmp/perf_browser.txt', 'w', encoding='utf-8')
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:4321"
THRESHOLD = 1.5  # seconds

ROUTES = [
    # Core
    ("core", "dashboard", "dashboard"),
    # Sales
    ("sales", "voucher_list", "sales/list"),
    ("sales", "voucher_add", "sales/add"),
    ("sales", "return_list", "sales/salesreturn/list/"),
    ("sales", "quotation_add", "sales/quotation/add/"),
    # Purchase
    ("purchase", "voucher_list", "purchase/list"),
    ("purchase", "voucher_add", "purchase/add"),
    ("purchase", "order_list", "purchase/purchaseorder/list"),
    # Inventory
    ("inventory", "stock_journal_list", "inventory/stockjournal/"),
    ("inventory", "stock_journal_add", "inventory/stockjournal/add"),
    ("inventory", "stock_transfer_add", "inventory/stocktransfer/add"),
    ("inventory", "barcode_list", "inventory/barcodemanagement/list"),
    ("inventory", "barcode_add", "inventory/barcodemanagement/list/add"),
    # Manufacturing
    ("mfg", "goldissue_add", "manufacturing/issue/goldissue/add"),
    ("mfg", "jobwork_add", "manufacturing/issue/jobwork/add"),
    ("mfg", "jobwork_recv", "manufacturing/receive/jobworkreceive/add"),
    ("mfg", "stonereturn", "manufacturing/receive/stonereturn/add"),
    ("mfg", "karigar_list", "manufacturing/karigar"),
    # Reports
    ("reports", "balance_sheet", "accounting/reports/balancesheet"),
    ("reports", "pnl", "accounting/reports/pnl"),
    ("reports", "daybook", "accounting/reports/daybook"),
    ("reports", "trial_balance", "accounting/reports/trialbalance"),
    ("reports", "chart_of_accounts", "accounting/chartofaccounts"),
    # Accounting
    ("accounting", "journal_list", "accounting/vouchers/journal/list"),
    ("accounting", "journal_add", "accounting/vouchers/journal/add"),
    # CRM
    ("crm", "ledger_list", "crm/ledger"),
    ("crm", "ledger_add", "crm/ledger/add"),
    # Inv Reports
    ("inv_reports", "stock_value", "inventory/reports/stockvalue"),
    ("inv_reports", "barcode_report", "inventory/reports/barcodereport"),
    # Masters
    ("masters", "item_master", "masters/item"),
    ("masters", "hsn", "masters/hsn"),
    ("masters", "purity", "masters/purity"),
    # Other
    ("goldscheme", "scheme_list", "goldscheme"),
    ("hr", "employees", "hr/employees"),
    ("fixed_assets", "asset_list", "accounting/fixedassets"),
]

# Split into batches of 12 to avoid resource exhaustion
BATCH_SIZE = 12
all_results = []

with sync_playwright() as p:
    batches = [ROUTES[i:i+BATCH_SIZE] for i in range(0, len(ROUTES), BATCH_SIZE)]

    for batch_idx, batch in enumerate(batches):
        sys.stdout.write(f"\n=== Batch {batch_idx+1}/{len(batches)} ===\n")
        sys.stdout.flush()

        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        # Login
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

        for (cat, name, route) in batch:
            start = time.time()
            had_error = False
            try:
                page.goto(f"{BASE}/{route}", timeout=15000)
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception as e:
                had_error = True
            elapsed = time.time() - start

            if had_error:
                status = "ERROR"
            elif elapsed > THRESHOLD:
                status = "SLOW"
            else:
                status = "PASS"

            result = {
                "category": cat,
                "test": name,
                "route": route,
                "time_s": round(elapsed, 3),
                "status": status,
            }
            all_results.append(result)
            sys.stdout.write(f"[{status}] {cat}/{name}: {elapsed:.3f}s ({route})\n")
            sys.stdout.flush()

        context.close()
        browser.close()
        time.sleep(1)

# Summary
sys.stdout.write(f"\n{'='*60}\n")
sys.stdout.write("PERFORMANCE TEST SUMMARY\n")
sys.stdout.write(f"{'='*60}\n")
passes = sum(1 for r in all_results if r["status"] == "PASS")
slow = sum(1 for r in all_results if r["status"] == "SLOW")
errors = sum(1 for r in all_results if r["status"] == "ERROR")
total = len(all_results)
avg_time = sum(r["time_s"] for r in all_results) / total if total else 0
max_result = max(all_results, key=lambda r: r["time_s"]) if all_results else None

sys.stdout.write(f"PASS (<1.5s): {passes} | SLOW (>=1.5s): {slow} | ERROR: {errors} | Total: {total}\n")
sys.stdout.write(f"Average load time: {avg_time:.3f}s\n")
if max_result:
    sys.stdout.write(f"Slowest: {max_result['category']}/{max_result['test']} at {max_result['time_s']:.3f}s\n")

if slow:
    sys.stdout.write(f"\n--- SLOW PAGES ({slow}) ---\n")
    for r in sorted(all_results, key=lambda x: -x["time_s"]):
        if r["status"] == "SLOW":
            sys.stdout.write(f"  {r['category']}/{r['test']}: {r['time_s']:.3f}s ({r['route']})\n")

with open("D:/tmp/perf_results.json", "w") as f:
    json.dump(all_results, f, indent=2)

sys.stdout.write("\nResults saved to D:/tmp/perf_results.json\n")
sys.stdout.close()
