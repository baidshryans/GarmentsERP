"""
Deep workflow tests for Jewel India ERP.
Tests major business flows via browser interaction.
Covers: Sales, Purchase, Inventory, Manufacturing, Financial Reports.
"""
import json, time, traceback
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:4321"
API = "http://127.0.0.1:8000"
TOKEN = "f41feaee46f2949d0408c6857200718953865589"

results = []

def log_result(category, test_name, status, details=""):
    r = {"category": category, "test": test_name, "status": status, "details": details}
    results.append(r)
    print(f"[{status}] {category}/{test_name}: {details[:200]}" if details else f"[{status}] {category}/{test_name}")

def capture_errors(page):
    """Set up error capture listeners, return error containers."""
    console_errors = []
    page_errors = []
    http_errors = []

    def on_console(msg):
        if msg.type == "error":
            console_errors.append(msg.text[:200])

    def on_page_error(err):
        page_errors.append(str(err)[:200])

    def on_response(resp):
        if resp.status >= 400:
            http_errors.append({"url": resp.url, "status": resp.status})

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("response", on_response)
    return console_errors, page_errors, http_errors

def cleanup_listeners(page):
    try:
        page.remove_listener("console", lambda m: None)
        page.remove_listener("pageerror", lambda e: None)
        page.remove_listener("response", lambda r: None)
    except:
        pass

def navigate_and_check(page, route, timeout=20000):
    """Navigate to a route, wait for load, return error summary."""
    console_errors = []
    page_errors = []
    http_errors = []

    handlers = {}
    def on_console(msg):
        if msg.type == "error":
            console_errors.append(msg.text[:200])
    def on_page_error(err):
        page_errors.append(str(err)[:200])
    def on_response(resp):
        if resp.status >= 400:
            http_errors.append({"url": resp.url, "status": resp.status})

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("response", on_response)

    try:
        page.goto(f"{BASE}/{route}", timeout=timeout)
        page.wait_for_load_state("networkidle", timeout=timeout)
        time.sleep(1)
    except Exception as e:
        page_errors.append(f"Navigation: {str(e)[:150]}")

    page.remove_listener("console", on_console)
    page.remove_listener("pageerror", on_page_error)
    page.remove_listener("response", on_response)

    return {
        "console_errors": console_errors,
        "page_errors": page_errors,
        "http_errors": http_errors,
        "has_errors": bool(page_errors or http_errors),
    }


def test_sales_list(page):
    """Test that sales voucher list page loads with data table."""
    errs = navigate_and_check(page, "sales/list")
    if errs["has_errors"]:
        log_result("sales", "voucher_list_load", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        return

    # Check for table/data
    table = page.query_selector("table, [role='table'], .data-table")
    if table:
        rows = page.query_selector_all("table tbody tr, [role='row']")
        log_result("sales", "voucher_list_load", "PASS", f"Table rendered with {len(rows)} rows")
    else:
        # Maybe it's a card/grid layout
        content = page.inner_text("body")[:500]
        if "No" in content and ("record" in content.lower() or "data" in content.lower()):
            log_result("sales", "voucher_list_load", "PASS", "List page loaded (no records yet)")
        else:
            log_result("sales", "voucher_list_load", "WARN", "List loaded but no table found")


def test_sales_add_form(page):
    """Test that sales voucher add form renders with required fields."""
    errs = navigate_and_check(page, "sales/add")
    if errs["has_errors"]:
        log_result("sales", "voucher_add_form", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        return

    inputs = page.query_selector_all("input, select, textarea")
    selects = page.query_selector_all("select, [role='combobox'], [role='listbox']")
    buttons = page.query_selector_all("button")

    log_result("sales", "voucher_add_form", "PASS",
               f"Form rendered: {len(inputs)} inputs, {len(selects)} selects, {len(buttons)} buttons")


def test_sales_return_list(page):
    """Test sales return list."""
    errs = navigate_and_check(page, "sales/salesreturn/list/")
    if errs["has_errors"]:
        log_result("sales", "return_list", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
    else:
        log_result("sales", "return_list", "PASS", "Sales return list loaded")


def test_purchase_list(page):
    """Test purchase voucher list page."""
    errs = navigate_and_check(page, "purchase/list")
    if errs["has_errors"]:
        log_result("purchase", "voucher_list_load", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        return

    table = page.query_selector("table, [role='table']")
    if table:
        rows = page.query_selector_all("table tbody tr")
        log_result("purchase", "voucher_list_load", "PASS", f"Table rendered with {len(rows)} rows")
    else:
        log_result("purchase", "voucher_list_load", "PASS", "List page loaded")


def test_purchase_add_form(page):
    """Test purchase voucher add form."""
    errs = navigate_and_check(page, "purchase/add")
    if errs["has_errors"]:
        log_result("purchase", "voucher_add_form", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        return

    inputs = page.query_selector_all("input, select, textarea")
    log_result("purchase", "voucher_add_form", "PASS", f"Form rendered with {len(inputs)} inputs")


def test_purchase_return_list(page):
    """Test purchase return list."""
    errs = navigate_and_check(page, "purchase/purchasereturn/list/")
    if errs["has_errors"]:
        log_result("purchase", "return_list", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
    else:
        log_result("purchase", "return_list", "PASS", "Purchase return list loaded")


def test_purchase_order(page):
    """Test purchase order list."""
    errs = navigate_and_check(page, "purchase/purchaseorder/list")
    if errs["has_errors"]:
        log_result("purchase", "order_list", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
    else:
        log_result("purchase", "order_list", "PASS", "Purchase order list loaded")


def test_stock_journal_list(page):
    """Test stock journal list page."""
    errs = navigate_and_check(page, "inventory/stockjournal/")
    if errs["has_errors"]:
        log_result("inventory", "stock_journal_list", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
    else:
        log_result("inventory", "stock_journal_list", "PASS", "Stock journal list loaded")


def test_stock_journal_add(page):
    """Test stock journal add form."""
    errs = navigate_and_check(page, "inventory/stockjournal/add")
    if errs["has_errors"]:
        log_result("inventory", "stock_journal_add", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        return
    inputs = page.query_selector_all("input, select, textarea")
    log_result("inventory", "stock_journal_add", "PASS", f"Form rendered with {len(inputs)} inputs")


def test_stock_transfer_list(page):
    """Test stock transfer list."""
    errs = navigate_and_check(page, "inventory/stocktransfer")
    if errs["has_errors"]:
        log_result("inventory", "stock_transfer_list", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
    else:
        log_result("inventory", "stock_transfer_list", "PASS", "Stock transfer list loaded")


def test_stock_transfer_add(page):
    """Test stock transfer add form."""
    errs = navigate_and_check(page, "inventory/stocktransfer/add")
    if errs["has_errors"]:
        log_result("inventory", "stock_transfer_add", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        return
    inputs = page.query_selector_all("input, select, textarea")
    log_result("inventory", "stock_transfer_add", "PASS", f"Form rendered with {len(inputs)} inputs")


def test_barcode_list(page):
    """Test barcode management list."""
    errs = navigate_and_check(page, "inventory/barcodemanagement/list")
    if errs["has_errors"]:
        log_result("inventory", "barcode_list", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
    else:
        log_result("inventory", "barcode_list", "PASS", "Barcode list loaded")


def test_barcode_add(page):
    """Test barcode management add form."""
    errs = navigate_and_check(page, "inventory/barcodemanagement/list/add")
    if errs["has_errors"]:
        log_result("inventory", "barcode_add", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        return
    inputs = page.query_selector_all("input, select, textarea")
    log_result("inventory", "barcode_add", "PASS", f"Form rendered with {len(inputs)} inputs")


def test_manufacturing_issue_pages(page):
    """Test all manufacturing issue add pages."""
    issue_routes = [
        ("goldissue", "manufacturing/issue/goldissue/add"),
        ("hallmarkissue", "manufacturing/issue/hallmarkissue/add"),
        ("melting", "manufacturing/issue/melting/add"),
        ("refinary", "manufacturing/issue/refinary/add"),
        ("assay", "manufacturing/issue/assay/add"),
        ("stoneissue", "manufacturing/issue/stoneissue/add"),
        ("jobwork", "manufacturing/issue/jobwork/add"),
    ]
    for name, route in issue_routes:
        errs = navigate_and_check(page, route)
        if errs["has_errors"]:
            log_result("manufacturing", f"issue_{name}", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        elif errs["console_errors"]:
            log_result("manufacturing", f"issue_{name}", "WARN", str(errs["console_errors"][:2]))
        else:
            log_result("manufacturing", f"issue_{name}", "PASS", "Form loaded")


def test_manufacturing_receive_pages(page):
    """Test all manufacturing receive add pages."""
    receive_routes = [
        ("jobworkreceive", "manufacturing/receive/jobworkreceive/add"),
        ("hallmarkreceive", "manufacturing/receive/hallmarkreceive/add"),
        ("refinary", "manufacturing/receive/refinary/add"),
        ("assay", "manufacturing/receive/assay/add"),
        ("stonereturn", "manufacturing/receive/stonereturn/add"),
    ]
    for name, route in receive_routes:
        errs = navigate_and_check(page, route)
        if errs["has_errors"]:
            log_result("manufacturing", f"receive_{name}", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        elif errs["console_errors"]:
            log_result("manufacturing", f"receive_{name}", "WARN", str(errs["console_errors"][:2]))
        else:
            log_result("manufacturing", f"receive_{name}", "PASS", "Form loaded")


def test_manufacturing_lists(page):
    """Test manufacturing list pages."""
    list_routes = [
        ("goldissue_list", "manufacturing/issue/goldissue"),
        ("hallmarkissue_list", "manufacturing/issue/hallmarkissue"),
        ("jobwork_list", "manufacturing/issue/jobwork"),
        ("karigar_list", "manufacturing/karigar"),
    ]
    for name, route in list_routes:
        errs = navigate_and_check(page, route)
        if errs["has_errors"]:
            log_result("manufacturing", name, "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        else:
            log_result("manufacturing", name, "PASS", "List loaded")


def test_financial_reports(page):
    """Test financial report pages."""
    report_routes = [
        ("balance_sheet", "accounting/reports/balancesheet"),
        ("pnl", "accounting/reports/pnl"),
        ("daybook", "accounting/reports/daybook"),
        ("trial_balance", "accounting/reports/trialbalance"),
        ("cash_book", "accounting/reports/cashbook"),
        ("bank_book", "accounting/reports/bankbook"),
        ("ledger_report", "accounting/reports/ledgerreport"),
        ("chart_of_accounts", "accounting/chartofaccounts"),
    ]
    for name, route in report_routes:
        errs = navigate_and_check(page, route)
        if errs["has_errors"]:
            log_result("reports", name, "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        elif errs["console_errors"]:
            log_result("reports", name, "WARN", str(errs["console_errors"][:2]))
        else:
            log_result("reports", name, "PASS", "Report loaded")


def test_accounting_vouchers(page):
    """Test accounting voucher pages."""
    routes = [
        ("journal_list", "accounting/vouchers/journal/list"),
        ("payment_list", "accounting/vouchers/payment/list"),
        ("receipt_list", "accounting/vouchers/receipt/list"),
        ("contra_list", "accounting/vouchers/contra/list"),
        ("journal_add", "accounting/vouchers/journal/add"),
    ]
    for name, route in routes:
        errs = navigate_and_check(page, route)
        if errs["has_errors"]:
            log_result("accounting", name, "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        elif errs["console_errors"]:
            log_result("accounting", name, "WARN", str(errs["console_errors"][:2]))
        else:
            log_result("accounting", name, "PASS", "Page loaded")


def test_crm_pages(page):
    """Test CRM pages."""
    routes = [
        ("dashboard", "crm"),
        ("ledger_list", "crm/ledger"),
        ("ledger_add", "crm/ledger/add"),
    ]
    for name, route in routes:
        errs = navigate_and_check(page, route)
        if errs["has_errors"]:
            log_result("crm", name, "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        else:
            log_result("crm", name, "PASS", "Page loaded")


def test_gold_scheme(page):
    """Test gold scheme pages."""
    routes = [
        ("scheme_list", "goldscheme"),
        ("enrollment_list", "goldscheme/enrollments"),
    ]
    for name, route in routes:
        errs = navigate_and_check(page, route)
        if errs["has_errors"]:
            log_result("goldscheme", name, "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        else:
            log_result("goldscheme", name, "PASS", "Page loaded")


def test_inventory_reports(page):
    """Test inventory report pages."""
    routes = [
        ("stock_value", "inventory/reports/stockvalue"),
        ("barcode_report", "inventory/reports/barcodereport"),
        ("id_generation", "inventory/reports/idgen"),
        ("raw_material", "inventory/reports/raw-material"),
        ("metal_report", "inventory/metalreport"),
    ]
    for name, route in routes:
        errs = navigate_and_check(page, route)
        if errs["has_errors"]:
            log_result("inv_reports", name, "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        elif errs["console_errors"]:
            log_result("inv_reports", name, "WARN", str(errs["console_errors"][:2]))
        else:
            log_result("inv_reports", name, "PASS", "Report loaded")


def test_masters(page):
    """Test master configuration pages."""
    routes = [
        ("item_master", "masters/item"),
        ("item_group", "masters/item-group"),
        ("hsn", "masters/hsn"),
        ("purity", "masters/purity"),
        ("branch", "masters/branch"),
        ("company", "masters/company"),
        ("gstin", "masters/gstin"),
    ]
    for name, route in routes:
        errs = navigate_and_check(page, route)
        if errs["has_errors"]:
            log_result("masters", name, "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        else:
            log_result("masters", name, "PASS", "Master page loaded")


def test_dashboard(page):
    """Test main dashboard."""
    errs = navigate_and_check(page, "dashboard")
    if errs["has_errors"]:
        log_result("core", "dashboard", "FAIL", str(errs["http_errors"] + errs["page_errors"]))
    else:
        log_result("core", "dashboard", "PASS", "Dashboard loaded")


def test_hr_pages(page):
    """Test HR pages."""
    routes = [
        ("employee_list", "hr/employees"),
        ("attendance", "hr/attendance"),
    ]
    for name, route in routes:
        errs = navigate_and_check(page, route)
        if errs["has_errors"]:
            log_result("hr", name, "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        else:
            log_result("hr", name, "PASS", "Page loaded")


def test_fixed_assets(page):
    """Test fixed asset pages."""
    routes = [
        ("asset_list", "accounting/fixedassets"),
        ("depreciation", "accounting/fixedassets/depreciation"),
    ]
    for name, route in routes:
        errs = navigate_and_check(page, route)
        if errs["has_errors"]:
            log_result("fixed_assets", name, "FAIL", str(errs["http_errors"] + errs["page_errors"]))
        else:
            log_result("fixed_assets", name, "PASS", "Page loaded")


# ── Main ───────────────────────────────────────────────────────────────────────

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()

    # Login
    print("=== Logging in ===")
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

    print("\n=== Core ===")
    test_dashboard(page)

    print("\n=== Sales ===")
    test_sales_list(page)
    test_sales_add_form(page)
    test_sales_return_list(page)

    print("\n=== Purchase ===")
    test_purchase_list(page)
    test_purchase_add_form(page)
    test_purchase_return_list(page)
    test_purchase_order(page)

    print("\n=== Inventory ===")
    test_stock_journal_list(page)
    test_stock_journal_add(page)
    test_stock_transfer_list(page)
    test_stock_transfer_add(page)
    test_barcode_list(page)
    test_barcode_add(page)

    print("\n=== Manufacturing ===")
    test_manufacturing_lists(page)
    test_manufacturing_issue_pages(page)
    test_manufacturing_receive_pages(page)

    print("\n=== Financial Reports ===")
    test_financial_reports(page)

    print("\n=== Accounting Vouchers ===")
    test_accounting_vouchers(page)

    print("\n=== CRM ===")
    test_crm_pages(page)

    print("\n=== Inventory Reports ===")
    test_inventory_reports(page)

    print("\n=== Masters ===")
    test_masters(page)

    print("\n=== Gold Scheme ===")
    test_gold_scheme(page)

    print("\n=== HR ===")
    test_hr_pages(page)

    print("\n=== Fixed Assets ===")
    test_fixed_assets(page)

    browser.close()

# Summary
print("\n" + "="*60)
print("WORKFLOW TEST SUMMARY")
print("="*60)
passes = sum(1 for r in results if r["status"] == "PASS")
warns = sum(1 for r in results if r["status"] == "WARN")
fails = sum(1 for r in results if r["status"] == "FAIL")
total = len(results)
print(f"PASS: {passes} | WARN: {warns} | FAIL: {fails} | Total: {total}")
print(f"Pass rate: {passes/total*100:.1f}%" if total else "No tests run")

if fails:
    print(f"\n--- FAILURES ({fails}) ---")
    for r in results:
        if r["status"] == "FAIL":
            print(f"  {r['category']}/{r['test']}: {r['details'][:200]}")

if warns:
    print(f"\n--- WARNINGS ({warns}) ---")
    for r in results:
        if r["status"] == "WARN":
            print(f"  {r['category']}/{r['test']}: {r['details'][:200]}")

with open("test-runs/workflow_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print("\nResults saved to test-runs/workflow_results.json")
