import re
from decimal import Decimal
from pathlib import Path

import pytest
from django.test import Client
from django.urls import reverse

from core.models import Company, Factory, Role
from ledger.models import Ledger, Voucher
from ledger.services.posting import LineSpec, post_voucher
from tests.conftest import IN_YEAR, make_user
from tests.helpers import simple_lines

ROOT = Path(__file__).resolve().parent.parent
D = Decimal


# ---------------- design tokens ----------------

def _tokens(block_selector):
    css = (ROOT / "static/css/tokens.css").read_text()
    start = css.index(block_selector)
    body = css[css.index("{", start) + 1 : css.index("\n}", start)]
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;", body))


def _lum(hex_color):
    def channel(c):
        c = int(c, 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = hex_color[1:3], hex_color[3:5], hex_color[5:7]
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


PAIRS = [
    ("color-ink", "color-bg"), ("color-ink", "color-surface"), ("color-muted", "color-bg"),
    ("color-muted", "color-surface"), ("color-ink", "color-primary-soft"), ("color-ink", "color-primary-pale"),
    ("color-on-primary", "color-primary"), ("color-on-primary", "color-primary-darker"),
    ("color-on-primary", "color-primary-darkest"), ("color-primary", "color-bg"), ("color-primary", "color-surface"),
    ("color-success", "color-success-soft"), ("color-warning", "color-warning-soft"),
    ("color-danger", "color-danger-soft"), ("color-muted", "color-primary-soft"),
    ("color-ink", "color-sidebar"), ("color-muted", "color-sidebar"), ("color-primary", "color-sidebar"),
]


@pytest.mark.parametrize("theme,selector", [("light", ":root {"), ("dark", '[data-theme="dark"] {')])
def test_token_pairs_meet_wcag_aa(theme, selector):
    light = _tokens(":root {")
    tokens = {**light, **_tokens(selector)} if theme == "dark" else light
    for fg, bg in PAIRS:
        ratio = contrast(tokens[fg], tokens[bg])
        assert ratio >= 4.5, f"{theme}: {fg} on {bg} is {ratio:.2f}:1"


def test_dark_theme_overrides_every_light_colour_token():
    light, dark = _tokens(":root {"), _tokens('[data-theme="dark"] {')
    assert set(light) - set(dark) == set()


def test_no_raw_hex_outside_tokens_css():
    offenders = []
    for path in [*ROOT.glob("static/css/*.css"), *ROOT.glob("templates/**/*.html"), *ROOT.glob("static/js/*.js")]:
        if path.name == "tokens.css":
            continue
        if re.search(r"#[0-9a-fA-F]{3,8}\b(?![\w-])", re.sub(r"href=\"#[\w-]+\"|url\(#[\w-]+\)", "", path.read_text())):
            offenders.append(path.name)
    assert not offenders, offenders


def test_hand_font_not_used_in_tables_forms_or_print():
    """Owner's decision (Oct 2026): one professional typeface, Assistant, everywhere. No handwriting font."""
    for name in ("base.css", "print.css", "tokens.css"):
        text = (ROOT / "static/css" / name).read_text()
        assert "font-hand" not in text and "Caveat" not in text


# ---------------- login, theme, shell ----------------

def test_login_page_has_theme_toggle_and_no_flash_bootstrap(db):
    html = Client().get(reverse("login")).content.decode()
    assert "data-theme-toggle" in html and "prefers-color-scheme" not in html  # light by default
    assert "tokens.css" in html


def test_login_works_and_lands_on_home(company, accountant):
    c = Client()
    r = c.post(reverse("login"), {"username": "accountant", "password": "pw-for-tests-1"}, follow=True)
    assert r.redirect_chain[-1][0] == reverse("home") and b"Garment ERP" in r.content


def test_nav_rail_shows_only_screens_the_user_may_view(company, accountant):
    c = Client()
    c.force_login(accountant)
    html = c.get(reverse("home")).content.decode()
    assert "Chart of accounts" in html and "Trial balance" in html
    assert "Users" not in html and "Roles" not in html


def test_shell_has_resizable_menu_user_menu_and_skip_link(company, accountant):
    c = Client()
    c.force_login(accountant)
    html = c.get(reverse("home")).content.decode()
    assert 'class="rail-resizer"' in html and 'role="separator"' in html
    assert reverse("password_change") in html and "Sign out" in html
    assert 'class="skip-link"' in html and 'id="content"' in html


def test_user_can_change_own_password_and_stays_signed_in(company, accountant):
    c = Client()
    c.force_login(accountant)
    assert c.get(reverse("password_change")).status_code == 200
    r = c.post(reverse("password_change"), {
        "old_password": "pw-for-tests-1", "new_password1": "a-new-Passw0rd-42", "new_password2": "a-new-Passw0rd-42"})
    assert r.status_code == 302 and r["Location"] == reverse("home")
    assert c.get(reverse("home")).status_code == 200            # session survived
    accountant.refresh_from_db()
    assert accountant.check_password("a-new-Passw0rd-42")
    assert Client().login(username="accountant", password="a-new-Passw0rd-42")


def test_change_password_rejects_wrong_old_and_mismatch(company, accountant):
    c = Client()
    c.force_login(accountant)
    r = c.post(reverse("password_change"), {"old_password": "nope", "new_password1": "a-new-Passw0rd-42", "new_password2": "a-new-Passw0rd-42"})
    assert r.status_code == 200 and b"incorrect" in r.content
    r = c.post(reverse("password_change"), {"old_password": "pw-for-tests-1", "new_password1": "a-new-Passw0rd-42", "new_password2": "different-Passw0rd-1"})
    assert r.status_code == 200
    accountant.refresh_from_db()
    assert accountant.check_password("pw-for-tests-1")


def test_change_password_needs_login(company):
    r = Client().get(reverse("password_change"))
    assert r.status_code == 302 and "/accounts/login/" in r["Location"]


def test_as_on_dates_default_to_today(company, admin_user):
    from django.utils import timezone

    today = timezone.localdate().isoformat()
    c = Client()
    c.force_login(admin_user)
    for name in ("trial_balance", "opening_stock", "po_new", "transfer_new", "order_new", "grn_new"):
        html = c.get(reverse(name)).content.decode()
        assert f'type="date" value="{today}"' in html, name


def test_anonymous_user_is_sent_to_login(company):
    r = Client().get(reverse("voucher_list"))
    assert r.status_code == 302 and "/accounts/login/" in r["Location"]


def test_screen_without_permission_is_403(company, accountant):
    c = Client()
    c.force_login(accountant)
    assert c.get(reverse("user_list")).status_code == 403
    assert c.get(reverse("role_list")).status_code == 403


# ---------------- setup wizard (E1.1) ----------------

def test_nothing_is_reachable_before_setup(db, admin_user):
    c = Client()
    c.force_login(admin_user)
    r = c.get(reverse("home"))
    assert r.status_code == 302 and r["Location"] == reverse("setup")
    assert Client().get(reverse("login")).status_code == 200  # login stays open


def test_wizard_cannot_be_skipped_or_run_by_non_superuser(db, admin_user):
    c = Client()
    c.force_login(admin_user)
    r = c.get(reverse("setup_step", args=["review"]))
    assert r.status_code == 302 and r["Location"] == reverse("setup_step", args=["company"])
    other = make_user("plain")
    c2 = Client()
    c2.force_login(other)
    assert c2.get(reverse("setup")).status_code == 403


def test_full_wizard_flow_seeds_everything_and_lands_home(db, admin_user):
    c = Client()
    c.force_login(admin_user)
    c.post(reverse("setup_step", args=["company"]), {
        "name": "Baid Knitwear", "state_code": "03", "city": "Ludhiana", "pan": "abcde1234f"})
    c.post(reverse("setup_step", args=["tax"]), {})  # not registered, no TDS
    c.post(reverse("setup_step", args=["year"]), {"fy_start_month": "4", "books_from": "2026-04-01"})
    r = c.post(reverse("setup_step", args=["factory"]), {"code": "ldh1", "name": "Unit 1", "state_code": "03"})
    assert r.status_code == 302
    assert c.get(reverse("setup_step", args=["review"])).status_code == 200
    r = c.post(reverse("setup_step", args=["review"]), follow=True)
    assert r.redirect_chain[-1][0] == reverse("home")

    company = Company.objects.get()
    assert company.setup_complete and company.pan == "ABCDE1234F"
    from ledger.models import AccountGroup

    assert AccountGroup.objects.filter(company=company).count() == 22
    for name in ("Capital", "Sundry Debtors", "Stock-in-hand", "Bank Accounts", "Indirect Expenses"):
        assert AccountGroup.objects.filter(company=company, name=name).exists()
    for key in ("cash", "cgst_input", "igst_output", "tds_payable", "tcs_payable", "round_off", "job_work_charges",
                "wages", "salaries", "freight_inward", "depreciation", "opening_difference"):
        assert Ledger.objects.filter(company=company, system_key=key).exists(), key
    assert Role.objects.filter(name="Owner").exists() and Factory.objects.get().code == "LDH1"
    # wizard is closed afterwards
    assert c.get(reverse("setup")).status_code == 302


def test_wizard_validates_gstin_state_and_requires_it_when_registered(db, admin_user):
    c = Client()
    c.force_login(admin_user)
    c.post(reverse("setup_step", args=["company"]), {"name": "X", "state_code": "03"})
    r = c.post(reverse("setup_step", args=["tax"]), {"gst_registered": "on"})
    assert b"Enter the GSTIN" in r.content
    r = c.post(reverse("setup_step", args=["tax"]), {"gst_registered": "on", "gstin": "27ABCDE1234F1Z5"})
    assert b"state code does not match" in r.content
    r = c.post(reverse("setup_step", args=["tax"]), {"gst_registered": "on", "gstin": "03ABCDE1234F1Z5"})
    assert r.status_code == 302


def test_seeding_is_idempotent_and_keeps_admin_edits(company):
    from core.seeding import seed_company

    ledger = Ledger.objects.get(company=company, system_key="cash")
    ledger.name = "Petty Cash"
    ledger.save()
    count = Ledger.objects.count()
    seed_company(company)
    assert Ledger.objects.count() == count
    assert Ledger.objects.get(pk=ledger.pk).name == "Petty Cash"


# ---------------- factory scoping in screens and API ----------------

def test_voucher_screens_and_api_hide_other_factories(company, factory, factory2, owner, accountant, ledgers):
    mine = post_voucher(company=company, factory=factory, voucher_type="journal", date=IN_YEAR,
                        lines=simple_lines(ledgers), user=owner)
    theirs = post_voucher(company=company, factory=factory2, voucher_type="journal", date=IN_YEAR,
                          lines=simple_lines(ledgers), user=owner)
    c = Client()
    c.force_login(accountant)
    html = c.get(reverse("voucher_list")).content.decode()
    assert mine.number in html and theirs.number not in html
    assert c.get(reverse("voucher_detail", args=[theirs.pk])).status_code == 404
    api = c.get("/api/v1/vouchers/").json()
    assert [row["number"] for row in api] == [mine.number]
    assert [f["code"] for f in c.get("/api/v1/me/").json()["factories"]] == ["LDH1"]
    assert c.get(reverse("trial_balance"), {"factory": factory2.pk}).status_code == 404
    assert c.get(reverse("factory_list")).status_code == 403  # accountant has no factory screen


def test_api_requires_login(company):
    assert Client().get("/api/v1/me/").status_code in (401, 403)


def test_trial_balance_screen_tallies(company, factory, owner, ledgers):
    post_voucher(company=company, factory=factory, voucher_type="journal", date=IN_YEAR,
                 lines=simple_lines(ledgers, "2500.50"), user=owner)
    c = Client()
    c.force_login(owner)
    html = c.get(reverse("trial_balance")).content.decode()
    assert "Tallies" in html and "2500.50" in html


# ---------------- users and roles (E1.5 to E1.7) ----------------

def test_admin_creates_user_with_factory_and_role_and_can_deactivate(company, factory, factory2, owner):
    c = Client()
    c.force_login(owner)
    r = c.post(reverse("user_create"), {
        "username": "store1", "password": "Str0ng-pass-99", "mobile": "9876543210",
        "roles": [Role.objects.get(name="Store Keeper").pk], "allowed_factories": [factory.pk], "is_active": "on",
    })
    assert r.status_code == 302
    from core.models import User

    u = User.objects.get(username="store1")
    assert u.check_password("Str0ng-pass-99") and list(u.allowed_factories.all()) == [factory]
    assert u.allowed_factory_ids() == {factory.pk}
    c.post(reverse("user_edit", args=[u.pk]), {"username": "store1", "mobile": "9876543210"})
    u.refresh_from_db()
    assert not u.is_active
    assert not Client().login(username="store1", password="Str0ng-pass-99")


def test_duplicate_mobile_is_rejected(company, owner):
    make_user("a", mobile="9000000001")
    c = Client()
    c.force_login(owner)
    r = c.post(reverse("user_create"), {"username": "b", "password": "Str0ng-pass-99", "mobile": "9000000001", "is_active": "on"})
    assert r.status_code == 200 and b"already exists" in r.content


def test_custom_role_permissions_take_effect_on_next_action(company, factory, owner):
    c = Client()
    c.force_login(owner)
    r = c.post(reverse("role_create"), {
        "name": "Voucher Viewer", "perm__ledger.voucher__view": "on", "field__cost": "on",
    })
    assert r.status_code == 302
    role = Role.objects.get(name="Voucher Viewer")
    user = make_user("viewer", all_factories=True)
    user.roles.add(role)
    vc = Client()
    vc.force_login(user)
    assert vc.get(reverse("voucher_list")).status_code == 200
    assert vc.get(reverse("trial_balance")).status_code == 403
    assert user.can_view_field("cost") and not user.can_view_field("margin")
    c.post(reverse("role_edit", args=[role.pk]), {"name": "Voucher Viewer"})  # untick everything
    assert vc.get(reverse("voucher_list")).status_code == 403


def test_new_factory_appears_in_filters_immediately(company, owner):
    c = Client()
    c.force_login(owner)
    c.post(reverse("factory_create"), {"code": "ldh3", "name": "Third Unit", "state_code": "03"})
    assert b"LDH3" in c.get(reverse("voucher_list")).content


# ---------------- opening balances ----------------

def _opening_post(c, factory, rows):
    data = {"factory": factory.pk, "ledger": [], "debit": [], "credit": [], "reference": [], "due_date": []}
    for ledger, dr, cr, ref in rows:
        data["ledger"].append(ledger.pk if ledger else "")
        data["debit"].append(dr)
        data["credit"].append(cr)
        data["reference"].append(ref)
        data["due_date"].append("")
    return c.post(reverse("opening_balances"), data)


def test_opening_balances_post_with_difference_to_suspense(company, factory, owner, ledgers):
    from ledger.models import AccountGroup

    dealer = Ledger.objects.create(company=company, group=AccountGroup.objects.get(company=company, name="Sundry Debtors"),
                                   name="Dealer A", bill_wise=True)
    c = Client()
    c.force_login(owner)
    r = _opening_post(c, factory, [
        (ledgers("cash"), "5000", "", ""), (dealer, "20000", "", "OLD-INV-7"), (ledgers("wages"), "30000", "", ""),
        (ledgers("profit_loss"), "", "50000", ""),
    ])
    assert r.status_code == 302
    v = Voucher.objects.get(voucher_type="opening")
    assert v.number.startswith("OPN/LDH1/") and v.date == company.books_from
    from ledger.selectors import ledger_balance, outstanding_bills

    assert ledger_balance(ledgers("opening_difference")) == D("-5000.00")  # credit of 5,000 balances the entry
    assert outstanding_bills(dealer)["bills"] == {"OLD-INV-7": D("20000.00")}


def test_opening_screen_reports_bad_rows_without_saving(company, factory, owner, ledgers):
    c = Client()
    c.force_login(owner)
    r = _opening_post(c, factory, [(ledgers("cash"), "10", "10", "")])
    assert r.status_code == 200 and b"either a debit or a credit" in r.content
    r = _opening_post(c, factory, [(ledgers("cash"), "abc", "", "")])
    assert b"not a number" in r.content
    assert not Voucher.objects.exists()


def test_opening_cannot_be_posted_into_a_factory_the_user_lacks(company, factory, factory2, accountant, ledgers):
    c = Client()
    c.force_login(accountant)
    assert _opening_post(c, factory2, [(ledgers("cash"), "10", "", "")]).status_code == 404


def test_voucher_cancel_screen_reverses_and_needs_permission(company, factory, owner, accountant, ledgers):
    v = post_voucher(company=company, factory=factory, voucher_type="journal", date=IN_YEAR,
                     lines=simple_lines(ledgers), user=owner)
    c = Client()
    c.force_login(accountant)
    r = c.post(reverse("voucher_detail", args=[v.pk]), {"reason": "Wrong party"})
    assert r.status_code == 302 and Voucher.objects.get(pk=v.pk).is_reversed


# ---------------- collapsible menu, side or top ----------------

def test_menu_groups_are_collapsible_and_the_current_one_is_open(company, owner):
    c = Client()
    c.force_login(owner)
    html = c.get(reverse("voucher_list")).content.decode()
    assert html.count('<details class="nav-group') >= 6 and '<span class="nav-label">Accounts</span>' in html
    accounts = html[html.index('data-group="accounts"') - 60: html.index('data-group="accounts"') + 200]
    assert "active" in accounts and "open" in accounts            # the page being viewed sits in an open group
    admin_part = html[html.index('data-group="admin"') - 60: html.index('data-group="admin"') + 80]
    assert "open" not in admin_part                               # the others start collapsed
    assert 'aria-current="page"' in html and "data-nav-toggle" in html


def test_the_menu_can_move_to_the_top_and_the_choice_is_remembered_in_the_browser(db):
    boot = (ROOT / "templates/partials/theme_boot.html").read_text()
    js = (ROOT / "static/js/app.js").read_text()
    css = (ROOT / "static/css/base.css").read_text()
    assert 'getItem("nav") === "top"' in boot and 'setAttribute("data-nav", nav)' in boot
    assert 'store("nav", mode)' in js and "data-nav-toggle" in js
    assert '[data-nav="side"] .rail' in css and '[data-nav="top"] .nav-items' in css and "@media (max-width: 960px)" in css and "data-drawer" in css
    assert css.count("{") == css.count("}")  # the stylesheet is well formed


def test_side_menu_width_and_collapse_are_remembered_and_applied_before_first_paint(db):
    boot = (ROOT / "templates/partials/theme_boot.html").read_text()
    js = (ROOT / "static/js/app.js").read_text()
    css = (ROOT / "static/css/base.css").read_text()
    assert 'getItem("navWidth")' in boot and '"--rail-w-user"' in boot and "data-collapsed" in boot
    assert 'store("navWidth"' in js and "pointerdown" in js and "ArrowLeft" in js and "dblclick" in js
    assert "var(--sidebar-w)" in css and "col-resize" in css


def test_menu_groups_fold_into_sections_and_quick_jump_knows_every_screen(company, owner):
    from django.urls import reverse as rev

    c = Client()
    c.force_login(owner)
    html = c.get(rev("trial_balance")).content.decode()
    assert html.count('class="nav-sub') >= 6 and 'data-sub="accounts/books"' in html
    books = html[html.index('data-sub="accounts/books"') - 40: html.index('data-sub="accounts/books"') + 60]
    assert " open" in books                                       # the section holding the current page is open
    assert 'id="cmdk"' in html and "data-cmdk-open" in html and 'id="nav-index"' in html
    assert rev("voucher_payment") in html and "Trial balance" in html


def test_quick_jump_script_has_keyboard_support(db):
    js = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
    assert "ctrlKey || e.metaKey" in js and "ArrowDown" in js and "Escape" in js and "navRecent" in js
