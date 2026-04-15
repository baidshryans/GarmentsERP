from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    p = b.new_page()
    p.goto("http://127.0.0.1:4321/login", wait_until="domcontentloaded", timeout=30000)
    p.wait_for_timeout(3000)
    p.screenshot(path=r"D:/Jewel India ERP/test-runs/screenshots/_recon_login.png", full_page=True)
    print("URL:", p.url)
    print("TITLE:", p.title())
    html = p.content()
    print("---HTML head---")
    print(html[:3000])
    b.close()
