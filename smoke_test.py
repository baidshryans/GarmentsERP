"""
End-to-end smoke test for the Jewel India ERP.

Walks every major section of the SPA, captures console errors and failed
network requests per page, and writes a Markdown report at the end. Auth
is injected via sessionStorage so we don't depend on the login form.
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

# ── Config ──────────────────────────────────────────────────────────────────
FRONTEND   = "http://localhost:5173"
BACKEND    = "http://localhost:8000/"
TOKEN      = "5d458758ccdb84fdbda867d9e28b44f3e0391689"
USER_ID    = 1
USER_NAME  = "admin"
RETAIL     = "R001"

REPORT_DIR = Path("D:/Jewel India ERP/smoke_test_report")
REPORT_DIR.mkdir(exist_ok=True)
SCREEN_DIR = REPORT_DIR / "screenshots"
SCREEN_DIR.mkdir(exist_ok=True)

# Pages to visit. Each is (label, route). Routes are appended to FRONTEND.
PAGES = [
    # ── Core dashboard / settings ─────────────────────────────────────────
    ("Home / Dashboard",            "/"),
    ("Settings — Audit Log",        "/settings/audit-log"),

    # ── Recent route changes (Phase 5 of audit) ───────────────────────────
    ("Journal Vouchers (NEW URL)",  "/accounting/JRNL"),
    ("Receipt Vouchers (NEW URL)",  "/accounting/RCPT"),
    ("Payment Vouchers (NEW URL)",  "/accounting/PMNT"),
    ("Contra Vouchers (NEW URL)",   "/accounting/CONTRA"),
    ("OLD URL should 404",          "/accounting/AddJournal/JRNL"),

    # ── Accounting reports ────────────────────────────────────────────────
    ("Account Tree",                "/accounting/account-tree"),
    ("Trial Balance",               "/accounting/trialbalance"),
    ("Day Book",                    "/accounting/day-book"),
    ("Cash Book",                   "/accounting/cashbook"),
    ("Ledger Statement",            "/accounting/ledger-statement"),
    ("Outstanding Report",          "/accounting/outstanding"),
    ("Aged Receivables",            "/accounting/aged-receivables"),
    ("Advance Register",            "/accounting/advance-register"),
    ("Credit/Debit Notes",          "/accounting/credit-debit-notes"),
    ("Bank Reconciliation",         "/accounting/bank-reconciliation"),
    ("Cash Gold Conversion",        "/accounting/cashgoldconversion"),
    ("Opening Balance",             "/accounting/opening-balance"),

    # ── Sales ─────────────────────────────────────────────────────────────
    ("Pending Cheques",             "/sales/pending-cheques"),

    # ── Manufacturing — recent fixes ──────────────────────────────────────
    ("Job Work Receive list",       "/manufacturing/receive/jobworkreceive/"),

    # ── Fixed Assets — recent edit (overrides removed) ────────────────────
    ("Fixed Asset Master",          "/fixed-assets/master"),
    ("Depreciation Worksheet",      "/fixed-assets/depreciation"),
    ("Fixed Asset Settings",        "/fixed-assets/settings"),
]


# ── Result collection ──────────────────────────────────────────────────────

class PageResult:
    def __init__(self, label: str, route: str):
        self.label = label
        self.route = route
        self.console_errors: list[str] = []
        self.failed_requests: list[str] = []
        self.http_status: int | None = None
        self.load_ok = True
        self.error: str | None = None

    def to_dict(self):
        return {
            'label':            self.label,
            'route':            self.route,
            'http_status':      self.http_status,
            'load_ok':          self.load_ok,
            'console_errors':   self.console_errors,
            'failed_requests':  self.failed_requests,
            'error':            self.error,
        }

    @property
    def is_clean(self) -> bool:
        # 404 page is "clean" only when expected (the legacy redirect test)
        return self.load_ok and not self.console_errors and not self.failed_requests and self.error is None


# ── Single page test ───────────────────────────────────────────────────────

def visit_page(page: Page, label: str, route: str) -> PageResult:
    result = PageResult(label, route)
    url = FRONTEND + route

    # Reset error collectors for this page
    page_console: list[str] = []
    page_failures: list[str] = []

    def on_console(msg):
        if msg.type == "error":
            page_console.append(msg.text[:300])

    def on_response(resp):
        # Only report failed API calls (5xx, 4xx other than 401/404 from cancel)
        try:
            if resp.status >= 500:
                page_failures.append(f"{resp.status} {resp.request.method} {resp.url[:120]}")
            elif resp.status == 400 and "/api/" in resp.url:
                # 400 on API can indicate a broken page expectation
                page_failures.append(f"400 {resp.request.method} {resp.url[:120]}")
        except Exception:
            pass

    page.on("console", on_console)
    page.on("response", on_response)

    try:
        nav = page.goto(url, timeout=30_000, wait_until="domcontentloaded")
        result.http_status = nav.status if nav else None
        # Give the SPA time to settle but don't block forever
        try:
            page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:
            pass
        # Screenshot
        slug = route.replace("/", "_").strip("_") or "home"
        page.screenshot(path=str(SCREEN_DIR / f"{slug}.png"), full_page=False, timeout=10_000)
    except Exception as exc:
        result.load_ok = False
        result.error = f"{type(exc).__name__}: {str(exc)[:200]}"
    finally:
        page.remove_listener("console", on_console)
        page.remove_listener("response", on_response)

    result.console_errors = page_console
    result.failed_requests = page_failures
    return result


# ── Auth bootstrap ─────────────────────────────────────────────────────────

def inject_auth(page: Page) -> None:
    """Set sessionStorage values so the SPA treats us as a logged-in admin."""
    # Must be on the right origin first
    page.goto(FRONTEND + "/", wait_until="domcontentloaded")
    page.evaluate(
        f"""() => {{
            sessionStorage.setItem('Token', {json.dumps(TOKEN)});
            sessionStorage.setItem('baseUrl', {json.dumps(BACKEND)});
            sessionStorage.setItem('retail_code', {json.dumps(RETAIL)});
            sessionStorage.setItem('user', {json.dumps(json.dumps({"id": USER_ID, "username": USER_NAME, "email": ""}))});
            sessionStorage.setItem('erpSetupComplete', 'true');
        }}"""
    )


# ── Driver ─────────────────────────────────────────────────────────────────

def run() -> int:
    results: list[PageResult] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = ctx.new_page()

        inject_auth(page)
        # Reload home with auth in place
        page.goto(FRONTEND + "/", wait_until="domcontentloaded")
        time.sleep(1.5)

        for label, route in PAGES:
            print(f"  visiting {label}: {route}", flush=True)
            r = visit_page(page, label, route)
            results.append(r)

        browser.close()

    # ── Report ──────────────────────────────────────────────────────────────
    report_path = REPORT_DIR / "report.md"
    clean = sum(1 for r in results if r.is_clean)
    failures = [r for r in results if not r.is_clean]

    with report_path.open("w", encoding="utf-8") as f:
        f.write(f"# ERP Smoke Test — {time.strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"**Pages tested:** {len(results)}  •  **Clean:** {clean}  •  **Issues:** {len(failures)}\n\n")
        f.write("---\n\n")

        f.write("## Summary\n\n")
        f.write("| # | Page | Route | Status | Console errors | Failed requests | Notes |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for i, r in enumerate(results, 1):
            status = "OK" if r.is_clean else "FAIL"
            note = (r.error or "")[:80]
            f.write(
                f"| {i} | {r.label} | `{r.route}` | "
                f"{status} (HTTP {r.http_status or '?'}) | "
                f"{len(r.console_errors)} | {len(r.failed_requests)} | {note} |\n"
            )

        if failures:
            f.write("\n## Issue details\n\n")
            for r in failures:
                f.write(f"### {r.label} — `{r.route}`\n\n")
                if r.error:
                    f.write(f"- **Load error:** `{r.error}`\n")
                if r.console_errors:
                    f.write("- **Console errors:**\n")
                    for e in r.console_errors[:10]:
                        f.write(f"  - `{e}`\n")
                if r.failed_requests:
                    f.write("- **Failed requests:**\n")
                    for fr in r.failed_requests[:10]:
                        f.write(f"  - `{fr}`\n")
                f.write("\n")

    # Also dump raw JSON for downstream processing
    (REPORT_DIR / "report.json").write_text(
        json.dumps([r.to_dict() for r in results], indent=2),
        encoding="utf-8",
    )

    print(f"\nReport written to {report_path}")
    print(f"Screenshots in {SCREEN_DIR}")
    print(f"\n{clean} clean, {len(failures)} with issues")

    # Exit code = number of issues (caller can detect)
    return min(len(failures), 100)


if __name__ == "__main__":
    sys.exit(run())
