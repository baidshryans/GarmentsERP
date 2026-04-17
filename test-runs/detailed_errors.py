"""Capture detailed console/page/network errors for the 23 failing routes."""
import json, sys, time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:4321"
USER = "admin"
PWD  = "admin123"

FAILING = [
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

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width":1440,"height":900})
    page = ctx.new_page()

    page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=60000)
    page.evaluate("sessionStorage.setItem('baseUrl', 'http://127.0.0.1:8000/')")

    page.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector('#username', timeout=30000)
    page.fill('#username', USER)
    page.fill('#password', PWD)
    page.click('button[type="submit"]')
    page.wait_for_url(lambda u: "/login" not in u, timeout=15000)
    print("Logged in.", file=sys.stderr)

    results = {}
    for i, path in enumerate(FAILING, 1):
        console_errors, page_errors, http_errors = [], [], []
        def on_console(msg, store=console_errors):
            if msg.type == "error":
                store.append(msg.text[:300])
        def on_pageerr(err, store=page_errors):
            store.append(str(err)[:300])
        def on_response(resp, store=http_errors):
            try:
                if resp.status >= 400:
                    body = ""
                    try: body = resp.text()[:200]
                    except: pass
                    store.append(f"{resp.status} {resp.url[:150]} | {body}")
            except: pass

        page.on("console", on_console)
        page.on("pageerror", on_pageerr)
        page.on("response", on_response)

        try:
            page.goto(f"{BASE}/{path}", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception as e:
            page_errors.append(f"Navigation: {str(e)[:200]}")

        time.sleep(1)

        page.remove_listener("console", on_console)
        page.remove_listener("pageerror", on_pageerr)
        page.remove_listener("response", on_response)

        results[path] = {
            "console_errors": console_errors,
            "page_errors": page_errors,
            "http_errors": http_errors,
        }
        status = "PASS" if not (console_errors or page_errors or http_errors) else "FAIL"
        print(f"[{i:3d}/{len(FAILING)}] {status} {path}  ce={len(console_errors)} pe={len(page_errors)} he={len(http_errors)}", file=sys.stderr)
        if console_errors:
            for e in console_errors[:2]:
                print(f"    CE: {e[:150]}", file=sys.stderr)
        if page_errors:
            for e in page_errors[:2]:
                print(f"    PE: {e[:150]}", file=sys.stderr)
        if http_errors:
            for e in http_errors[:2]:
                print(f"    HE: {e[:150]}", file=sys.stderr)

    browser.close()
    json.dump(results, open(r"D:/Jewel India ERP/test-runs/detailed_errors.json", "w"), indent=2)
    print("Done.", file=sys.stderr)
