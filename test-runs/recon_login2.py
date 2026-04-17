"""Quick recon of the login page."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.goto("http://127.0.0.1:4321/login")
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    page.screenshot(path="test-runs/screenshots/login_recon.png")
    # Dump all input elements
    inputs = page.query_selector_all("input")
    for inp in inputs:
        print(f"input: type={inp.get_attribute('type')} name={inp.get_attribute('name')} id={inp.get_attribute('id')} placeholder={inp.get_attribute('placeholder')}")
    buttons = page.query_selector_all("button")
    for btn in buttons:
        print(f"button: type={btn.get_attribute('type')} text={btn.inner_text()}")
    browser.close()
