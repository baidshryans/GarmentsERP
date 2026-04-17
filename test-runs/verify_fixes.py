"""Quick verify of the 3 routes we just fixed."""
import json, time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:4321"
ROUTES = [
    "inventory/stockjournal/add",
    "inventory/stocktransfer/add",
    "sales/quotation/add/",
]

results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 720})

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

    for route in ROUTES:
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

        try:
            page.goto(f"{BASE}/{route}", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=25000)
            time.sleep(1)
        except Exception as e:
            page_errors.append(f"Navigation: {e}")

        status_str = "FAIL" if (page_errors or http_errors) else ("WARN" if console_errors else "PASS")
        print(f"[{status_str}] {route} | console:{len(console_errors)} page:{len(page_errors)} http:{len(http_errors)}")
        if console_errors:
            for e in console_errors:
                print(f"  CONSOLE: {e[:150]}")
        if page_errors:
            for e in page_errors:
                print(f"  PAGE: {e[:150]}")
        if http_errors:
            for e in http_errors:
                print(f"  HTTP: {e}")

        page.remove_listener("console", on_console)
        page.remove_listener("pageerror", on_page_error)
        page.remove_listener("response", on_response)

    browser.close()
