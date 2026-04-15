"""Smoke test: log in, navigate every static route, capture console errors + screenshots on failure."""
import json, os, sys, time, traceback
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:4321"
USER = "admin"
PWD  = "admin123"
OUT  = Path(r"D:/Jewel India ERP/test-runs")
SCREENS = OUT / "screenshots"
SCREENS.mkdir(parents=True, exist_ok=True)
ROUTES = json.load(open(OUT/"routes.json"))

results = []  # {path, status, http_errors, console_errors, page_errors, duration_ms}

def safe_name(p): return p.replace("/", "_").replace(":", "_") or "root"

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width":1440,"height":900})
    page = ctx.new_page()

    # Seed baseUrl so the app skips /config redirect
    page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=60000)
    page.evaluate("sessionStorage.setItem('baseUrl', 'http://127.0.0.1:8000/')")

    # ── Login ────────────────────────────────────────────────────────────
    page.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector('#username', timeout=30000)
    page.fill('#username', USER)
    page.fill('#password', PWD)
    page.click('button[type="submit"]')
    try:
        page.wait_for_url(lambda u: "/login" not in u, timeout=15000)
    except Exception:
        page.screenshot(path=str(SCREENS/"LOGIN_FAILED.png"), full_page=True)
        print("LOGIN FAILED", file=sys.stderr)
        sys.exit(2)
    print(f"Logged in. Now testing {len(ROUTES)} routes...", file=sys.stderr)

    for i, path in enumerate(ROUTES, 1):
        url = f"{BASE}/{path}"
        console_errors, http_errors, page_errors = [], [], []
        def on_console(msg, store=console_errors):
            if msg.type == "error":
                store.append(msg.text[:500])
        def on_pageerr(err, store=page_errors):
            store.append(str(err)[:500])
        def on_response(resp, store=http_errors):
            try:
                if resp.status >= 400 and "/api/" in resp.url:
                    store.append(f"{resp.status} {resp.url[:200]}")
            except Exception: pass

        page.on("console", on_console)
        page.on("pageerror", on_pageerr)
        page.on("response", on_response)
        t0 = time.time()
        status = "ok"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception: pass
            page.wait_for_timeout(600)
        except Exception as e:
            status = f"nav_error: {str(e)[:200]}"
        dur = int((time.time()-t0)*1000)

        bad = bool(console_errors or page_errors or http_errors) or status != "ok"
        if bad:
            try:
                page.screenshot(path=str(SCREENS/f"{i:03d}_{safe_name(path)}.png"), full_page=False)
            except Exception: pass

        results.append({
            "i": i, "path": path, "status": status, "duration_ms": dur,
            "console_errors": console_errors[:8],
            "page_errors": page_errors[:8],
            "http_errors": http_errors[:8],
        })
        page.remove_listener("console", on_console)
        page.remove_listener("pageerror", on_pageerr)
        page.remove_listener("response", on_response)

        flag = "FAIL" if bad else "PASS"
        print(f"[{i:3}/{len(ROUTES)}] {flag} {path}  ({dur}ms)  ce={len(console_errors)} pe={len(page_errors)} he={len(http_errors)}", file=sys.stderr)

    json.dump(results, open(OUT/"smoke_results.json","w"), indent=2)
    browser.close()

# Summary
fails = [r for r in results if r["status"]!="ok" or r["console_errors"] or r["page_errors"] or r["http_errors"]]
print(f"\n=== DONE: {len(results)-len(fails)} pass, {len(fails)} fail ===", file=sys.stderr)
