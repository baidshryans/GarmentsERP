"""For every /add route, capture: visible required inputs, all selects, all submit buttons.
Outputs a JSON manifest and a markdown summary."""
import json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:4321"
USER, PWD = "admin", "admin123"
OUT = Path(r"D:/Jewel India ERP/test-runs")
ROUTES = json.load(open(OUT/"routes.json"))
ADD_ROUTES = [r for r in ROUTES if r.endswith("/add") or r.endswith("/add/") or r.endswith("/new") or r.endswith("/create") or r.endswith("/account-create")]

def first_attr(el, attrs):
    for a in attrs:
        v = el.get_attribute(a)
        if v: return f"{a}={v}"
    return ""

manifest = []
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width":1440,"height":900})
    page = ctx.new_page()
    page.goto(f"{BASE}/", wait_until="domcontentloaded")
    page.evaluate("sessionStorage.setItem('baseUrl','http://127.0.0.1:8000/')")
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.wait_for_selector('#username'); page.fill('#username', USER); page.fill('#password', PWD); page.click('button[type="submit"]')
    page.wait_for_url(lambda u: '/login' not in u, timeout=15000)
    print(f"Discovering forms on {len(ADD_ROUTES)} /add routes...", file=sys.stderr)

    for i, path in enumerate(ADD_ROUTES, 1):
        url = f"{BASE}/{path}"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try: page.wait_for_load_state("networkidle", timeout=6000)
            except: pass
            page.wait_for_timeout(500)
        except Exception as e:
            manifest.append({"path":path,"error":str(e)[:200]}); continue

        try:
            inputs = page.locator("form input:not([type=hidden]), form textarea, form select").all()
            req_fields, opt_fields, selects = [], [], []
            for el in inputs[:80]:
                try:
                    tag = el.evaluate("e=>e.tagName.toLowerCase()")
                    name = el.get_attribute("name") or el.get_attribute("id") or el.get_attribute("placeholder") or ""
                    typ  = el.get_attribute("type") or tag
                    req  = el.get_attribute("required") is not None or el.get_attribute("aria-required")=="true"
                    label = ""
                    iden = el.get_attribute("id")
                    if iden:
                        try: label = page.locator(f'label[for="{iden}"]').first.inner_text(timeout=300)[:60]
                        except: pass
                    desc = f"{label or name} ({typ})"
                    if tag=="select": selects.append(desc)
                    elif req: req_fields.append(desc)
                    else: opt_fields.append(desc)
                except: pass
            # custom selects via radix-ui SelectTrigger
            try:
                radix_selects = [t.inner_text(timeout=200)[:60] for t in page.locator('[role="combobox"], button[aria-haspopup="listbox"]').all()[:20]]
            except: radix_selects = []
            buttons = []
            try:
                for bt in page.locator('button[type="submit"], button:has-text("Save"), button:has-text("Submit"), button:has-text("Create")').all()[:5]:
                    try: buttons.append(bt.inner_text(timeout=300)[:40])
                    except: pass
            except: pass
            manifest.append({
                "path": path,
                "required": req_fields,
                "optional": opt_fields[:15],
                "html_selects": selects,
                "radix_selects": radix_selects,
                "submit_buttons": buttons,
            })
            print(f"[{i:3}/{len(ADD_ROUTES)}] {path}  req={len(req_fields)} sel={len(selects)+len(radix_selects)}", file=sys.stderr)
        except Exception as e:
            manifest.append({"path":path,"error":str(e)[:200]})

    b.close()

json.dump(manifest, open(OUT/"forms_manifest.json","w"), indent=2)
# Markdown
lines = ["# Form requirements per `/add` route\n"]
for m in manifest:
    lines.append(f"## `/{m['path']}`")
    if "error" in m: lines.append(f"- ERROR: {m['error']}\n"); continue
    if m['required']: lines.append("**Required:**"); [lines.append(f"- {x}") for x in m['required']]
    if m['html_selects']+m['radix_selects']:
        lines.append("**Selects (need pre-existing data):**")
        [lines.append(f"- {x}") for x in m['html_selects']+m['radix_selects']]
    if m['submit_buttons']: lines.append(f"**Submit:** {', '.join(m['submit_buttons'])}")
    lines.append("")
open(OUT/"FORMS.md","w",encoding="utf-8").write("\n".join(lines))
print(f"Wrote {OUT/'forms_manifest.json'} and {OUT/'FORMS.md'}", file=sys.stderr)
