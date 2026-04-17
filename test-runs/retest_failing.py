"""Re-test the 23 routes that had errors in the initial smoke test."""
import json, time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:4321"
FAILING_ROUTES = [
    "accounting/profitdemo",
    "inventory/barcode-bulk",
    "inventory/barcodemanagement/merge/",
    "inventory/reports/idgen",
    "inventory/reports/raw-material",
    "inventory/reports/stockvalue",
    "inventory/stockjournal/add",
    "inventory/stocktransfer/add",
    "manufacturing/issue/assay/add",
    "manufacturing/issue/goldissue/add",
    "manufacturing/issue/hallmarkissue/add",
    "manufacturing/issue/jobwork/add",
    "manufacturing/issue/melting/add",
    "manufacturing/issue/refinary/add",
    "manufacturing/issue/stoneissue/add",
    "manufacturing/receive/assay/add",
    "manufacturing/receive/hallmarkreceive/add",
    "manufacturing/receive/jobworkreceive/add",
    "manufacturing/receive/refinary/add",
    "manufacturing/receive/stonereturn/add",
    "manufacturing/repair/new",
    "purchase/purchaseorder/list/add",
    "sales/quotation/add/",
]

results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()

    # Login — Step 1: Base URL
    page.goto(f"{BASE}/login")
    page.wait_for_load_state("networkidle")
    time.sleep(1)
    page.fill('#baseUrl', 'http://127.0.0.1:8000/')
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    time.sleep(1)

    # Login — Step 2: Credentials
    page.fill('#username', 'admin')
    page.fill('#password', 'admin123')
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    # Set retail header via localStorage if needed
    page.evaluate("""() => {
        localStorage.setItem('retail_id', 'R001');
        localStorage.setItem('selectedRetail', JSON.stringify({code: 'R001', name: 'Retail 1'}));
    }""")

    for route in FAILING_ROUTES:
        console_errors = []
        page_errors = []
        http_errors = []

        def on_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)

        def on_page_error(err):
            page_errors.append(str(err))

        def on_response(resp):
            if resp.status >= 400:
                http_errors.append({"url": resp.url, "status": resp.status})

        page.on("console", on_console)
        page.on("pageerror", on_page_error)
        page.on("response", on_response)

        url = f"{BASE}/{route}"
        try:
            page.goto(url, timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(1)  # let async stuff settle
        except Exception as e:
            page_errors.append(f"Navigation error: {e}")

        # Take screenshot if errors
        slug = route.replace("/", "_").strip("_")
        if console_errors or page_errors or http_errors:
            try:
                page.screenshot(path=f"test-runs/screenshots/retest_{slug}.png")
            except Exception:
                pass  # screenshot may fail on some pages

        result = {
            "route": route,
            "console_errors": console_errors,
            "page_errors": page_errors,
            "http_errors": http_errors,
            "status": "FAIL" if (page_errors or http_errors) else ("WARN" if console_errors else "PASS"),
        }
        results.append(result)

        # Cleanup listeners
        page.remove_listener("console", on_console)
        page.remove_listener("pageerror", on_page_error)
        page.remove_listener("response", on_response)

        status_icon = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}[result["status"]]
        print(f"[{status_icon}] {route} | console:{len(console_errors)} page:{len(page_errors)} http:{len(http_errors)}")

    browser.close()

# Summary
passes = sum(1 for r in results if r["status"] == "PASS")
warns = sum(1 for r in results if r["status"] == "WARN")
fails = sum(1 for r in results if r["status"] == "FAIL")
print(f"\n--- RETEST SUMMARY ---")
print(f"PASS: {passes} | WARN: {warns} | FAIL: {fails} | Total: {len(results)}")

with open("test-runs/retest_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Results saved to test-runs/retest_results.json")
