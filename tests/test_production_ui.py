from datetime import date
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from core.models import Role
from jobwork.models import JobWorkBill, JobWorkChallan, QcResult, Receipt
from jobwork.services import rates
from masters.models import Colour, Product, Size
from production import labels
from production.models import Bundle, Lot, ProductionOrder
from production.services import routes
from tests.conftest import make_user
from tests.prod_helpers import D, DAY, build, cut, fabricator, step


def login(user):
    c = Client()
    c.force_login(user)
    return c


def user_with(name, role, factory):
    u = make_user(name)
    u.roles.add(Role.objects.get(name=role))
    u.allowed_factories.add(factory)
    return u


@pytest.fixture
def ns(company, factory, owner):
    return build(company, factory, owner, with_stock=True)


# ---------------- order to bundles through the screens ----------------

def test_order_cutting_and_qr_tags_through_the_screens(company, factory, owner):
    ns = build(company, factory, owner)
    c = login(owner)
    r = c.post(reverse("order_new"), {
        "factory": factory.pk, "date": "2026-06-15", "due_date": "2026-07-15", "purpose": "mto", "order_reference": "SO-77",
        "style": [ns.style.pk, ""], "colour": [ns.black.pk, ns.black.pk], "qty": ["60", ""], "ratios": ["S:1, M:2, L:2, XL:1", ""]})
    order = ProductionOrder.objects.exclude(pk=ns.order.pk).get()
    assert r.status_code == 302 and order.status == "draft" and order.order_reference == "SO-77"
    c.post(reverse("order_detail", args=[order.pk]), {"action": "release"})
    order.refresh_from_db()
    assert order.status == "released"
    lot = order.lines.get().lot
    page = c.get(reverse("lot_detail", args=[lot.pk])).content.decode()
    assert lot.lot_no in page and "Standard track pant route" not in page and "Stitching" in page

    r = c.post(reverse("lot_fabric", args=[lot.pk]), {"date": "2026-06-16", f"qty_{ns.roll_a.pk}": "30", "estimated_pieces": "75"})
    assert r.status_code == 302 and lot.fabric_issues.get().expected_pieces == 75
    r = c.post(reverse("lot_cutting", args=[lot.pk]), {
        "date": "2026-06-16", f"pieces_{ns.sizes['S'].pk}": "10", f"pieces_{ns.sizes['M'].pk}": "20", f"pieces_{ns.sizes['L'].pk}": "20",
        f"pieces_{ns.sizes['XL'].pk}": "10", f"used_{ns.roll_a.pk}": "24", f"waste_{ns.roll_a.pk}": "1", f"remnant_{ns.roll_a.pk}": "5"})
    assert r.status_code == 302
    entry = lot.cuttings.get()
    assert entry.expected_pieces == 62 and entry.variance_pct == D("-3.23") and not entry.over_tolerance   # 25 kg burnt, 60 cut
    # bundles come off the floor uneven: the pieces of each are typed per size, and must add up to the pieces cut
    sz = {code: f"bundles_{ns.sizes[code].pk}" for code in ("S", "M", "L", "XL")}
    assert "Pieces in each bundle" in c.get(reverse("lot_cutting", args=[lot.pk])).content.decode()
    r = c.post(reverse("lot_cutting", args=[lot.pk]), {
        "action": "bundles", "entry": entry.pk, sz["S"]: "10", sz["M"]: "12 5", sz["L"]: "9, 11", sz["XL"]: "10"})
    page = r.content.decode()
    assert r.status_code == 200 and "Size M: the bundles add up to 17 pieces but 20 are to be bundled (3 short)" in page
    assert not lot.bundles.exists() and 'value="12 5"' in page and 'value="9, 11"' in page    # what was typed comes back
    r = c.post(reverse("lot_cutting", args=[lot.pk]), {
        "action": "bundles", "entry": entry.pk, sz["S"]: "10", sz["M"]: "12 x", sz["L"]: "9 11", sz["XL"]: "10"})
    assert r.status_code == 200 and not lot.bundles.exists()
    r = c.post(reverse("lot_cutting", args=[lot.pk]), {
        "action": "bundles", "entry": entry.pk, sz["S"]: "10", sz["M"]: "12 5 3", sz["L"]: "9, 11", sz["XL"]: "4 6"})
    assert r.status_code == 302 and [b.qty for b in lot.bundles.order_by("bundle_no")] == [10, 12, 5, 3, 9, 11, 4, 6]
    tags = c.get(reverse("lot_tags", args=[lot.pk]))
    html = tags.content.decode()
    first = lot.bundles.first()
    assert "<svg" in html and first.bundle_no in html and html.count('class="tag"') == lot.bundles.count()
    zpl = c.get(reverse("lot_zpl", args=[lot.pk]))
    assert zpl["Content-Type"].startswith("text/plain") and zpl.content.decode().count("^XA") == lot.bundles.count()
    assert f"GE1:{first.qr_token}" in zpl.content.decode()


def test_qr_helpers_round_trip_and_zpl_is_clean(company, factory, owner):
    ns = build(company, factory, owner)
    b = cut(ns)[0]
    assert labels.parse_scan(labels.scan_text(b)) == b.qr_token == labels.parse_scan(" " + b.qr_token + "\n")
    assert labels.qr_svg(b).startswith("<svg")
    z = labels.zpl_label(b)
    assert z.startswith("^XA") and z.rstrip().endswith("^XZ") and "^BQN" in z and ns.lot.style.style_no in z
    b.lot.style.style_no = "A^B~C"
    assert "^B~C" not in labels.zpl_label(b).replace("^BQN", "").replace("^FD", "").replace("^FS", "")


def test_variance_beyond_tolerance_is_shown_to_the_cutting_master(company, factory, owner):
    ns = build(company, factory, owner)
    master = user_with("cutter", "Cutting Master", factory)
    c = login(master)
    c.post(reverse("lot_fabric", args=[ns.lot.pk]), {f"qty_{ns.roll_a.pk}": "60", "estimated_pieces": "150"})
    r = c.post(reverse("lot_cutting", args=[ns.lot.pk]), {
        f"pieces_{ns.sizes['M'].pk}": "100", f"used_{ns.roll_a.pk}": "50", f"waste_{ns.roll_a.pk}": "5", f"remnant_{ns.roll_a.pk}": "5"}, follow=True)
    assert b"beyond the 5" in r.content and ns.lot.cuttings.get().over_tolerance


# ---------------- moving bundles ----------------

def test_move_screen_lists_bundles_and_moves_them_with_counts(company, factory, owner):
    ns = build(company, factory, owner)
    routes.reassign_step(step(ns, "STITCH"), user=owner, reason="in-house", assignment="in_house", rate=D("10"))
    for code in ("EMB", "PRINT", "WASH"):
        routes.skip_step(step(ns, code), user=owner, reason="n/a")
    bundles = cut(ns)
    sup = user_with("sup", "Production Supervisor", factory)
    c = login(sup)
    page = c.get(reverse("move_bundles"), {"lot": ns.lot.pk}).content.decode()
    assert bundles[0].qr_token in page and "Scan a bundle QR" in page
    move = {"lot": ns.lot.pk, "bundle": [bundles[0].pk, bundles[1].pk], "to_step": step(ns, "STITCH").pk,
            f"loss_{bundles[1].pk}": "1", f"rejection_{bundles[1].pk}": "2"}
    ask = c.post(reverse("move_bundles"), move)                 # the style's list has a zipper a piece at stitching
    assert ask.status_code == 200 and "Materials for Stitching" in ask.content.decode() and 'value="42"' in ask.content.decode()
    assert Bundle.objects.get(pk=bundles[1].pk).current_step is None      # nothing has moved yet
    r = c.post(reverse("move_bundles"), {**move, "materials_step": "1", "mat_material": [ns.zipper.pk], "mat_qty": ["40"]})
    assert r.status_code == 302
    issue = ns.lot.material_issues.get()
    assert issue.lines.get().qty == D("40.000") and issue.step == step(ns, "STITCH")
    b1 = Bundle.objects.get(pk=bundles[1].pk)
    assert b1.qty == 22 and b1.current_step == step(ns, "STITCH")
    bad = c.post(reverse("move_bundles"), {"lot": ns.lot.pk, "bundle": [bundles[2].pk], "to_step": step(ns, "FINISH").pk})
    assert bad.status_code == 200 and b"mandatory" in bad.content
    back = c.post(reverse("move_bundles"), {"lot": ns.lot.pk, "bundle": [bundles[0].pk], "to_step": step(ns, "CUT").pk})
    assert b"BR-22" in back.content


# ---------------- job work through the screens ----------------

def test_challan_receipt_qc_and_bill_through_the_screens(company, factory, owner):
    ns = build(company, factory, owner)
    bundles = cut(ns)
    fab = fabricator(company)
    rates.save_rate(party=fab, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("25"), effective_from=date(2026, 4, 1))
    sup = user_with("sup", "Production Supervisor", factory)
    c = login(sup)
    form = c.get(reverse("challan_new"), {"lot": ns.lot.pk, "step": step(ns, "STITCH").pk}).content.decode()
    assert bundles[0].bundle_no in form and "Scan bundle QR" in form
    r = c.post(reverse("challan_new"), {"lot": ns.lot.pk, "step": step(ns, "STITCH").pk, "kind": "issue", "factory": factory.pk,
                                        "party": fab.pk, "date": "2026-06-16", "bundle": [bundles[0].pk, bundles[1].pk]})
    ch = JobWorkChallan.objects.get()
    assert r.status_code == 302 and ch.status == "draft"
    c.post(reverse("challan_detail", args=[ch.pk]), {"action": "issue"})
    ch.refresh_from_db()
    assert ch.status == "issued"
    pr = c.get(reverse("challan_print", args=[ch.pk])).content.decode()
    assert ch.number in pr and "JOB WORK CHALLAN" in pr and "Zipper" in pr and "<svg" in pr

    cbs = list(ch.bundles.order_by("id"))
    r = c.post(reverse("receipt_new", args=[ch.pk]), {
        "date": "2026-06-20", f"use_{cbs[0].pk}": "on", f"count_{cbs[0].pk}": "17", f"use_{cbs[1].pk}": "on", f"count_{cbs[1].pk}": "25",
        f"returned_{ch.trims.get().pk}": "", f"missing_{ch.trims.get().pk}": ""})
    rec = Receipt.objects.get()
    assert r.status_code == 302 and rec.status == "received"
    qc = user_with("qcer", "QC Checker", factory)
    q = login(qc)
    lines = list(rec.lines.order_by("id"))
    q.post(reverse("receipt_detail", args=[rec.pk]), {"action": "qc", "line": lines[0].pk, "accepted": "17", "rejected": "0", "rework": "0"})
    q.post(reverse("receipt_detail", args=[rec.pk]), {"action": "qc", "line": lines[1].pk, "accepted": "22", "rejected": "3", "rework": "0",
                                                      "reason": "Open seams", "destination": "rejects"})
    assert QcResult.objects.count() == 2
    bad = q.post(reverse("receipt_detail", args=[rec.pk]), {"action": "qc", "line": lines[1].pk, "accepted": "25"}, follow=True)
    assert b"already been recorded" in bad.content

    acct = make_user("acct")
    acct.roles.add(Role.objects.get(name="Accountant"))
    acct.all_factories = True
    acct.save()
    a = login(acct)
    page = a.get(reverse("bill_new"), {"party": fab.pk, "factory": factory.pk}).content.decode()
    assert "Pieces to pay" in page and "425.00" in page and "550.00" in page  # 17 x 25 and 22 x 25
    qcs = list(QcResult.objects.all())
    r = a.post(reverse("bill_new"), {"party": fab.pk, "factory": factory.pk, "date": "2026-06-30", "tds_template": "",
                                     **{f"qc_{x.pk}": "on" for x in qcs}})
    bill = JobWorkBill.objects.get()
    assert r.status_code == 302 and bill.gross == D("975.00") and bill.status == "draft"
    a.post(reverse("bill_detail", args=[bill.pk]), {"action": "post"})
    bill.refresh_from_db()
    assert bill.status == "posted" and bill.number
    assert b"Net payable" in a.get(reverse("bill_detail", args=[bill.pk])).content
    again = a.get(reverse("bill_new"), {"party": fab.pk, "factory": factory.pk}).content
    assert b"Nothing to pay" in again


def test_a_second_fabricator_warning_needs_confirmation_on_the_screen(company, factory, owner):
    ns = build(company, factory, owner)
    bundles = cut(ns)
    f1, f2 = fabricator(company), fabricator(company, "Gupta", "9822222233")
    for f in (f1, f2):
        rates.save_rate(party=f, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("25"), effective_from=date(2026, 4, 1))
    c = login(owner)
    base = {"lot": ns.lot.pk, "step": step(ns, "STITCH").pk, "kind": "issue", "factory": factory.pk, "date": "2026-06-16"}
    r = c.post(reverse("challan_new"), {**base, "party": f1.pk, "bundle": [bundles[0].pk]})
    c.post(reverse("challan_detail", args=[JobWorkChallan.objects.get().pk]), {"action": "issue"})
    r = c.post(reverse("challan_new"), {**base, "party": f2.pk, "bundle": [bundles[1].pk]})
    assert r.status_code == 200 and b"already open with" in r.content and b"issue this lot to another fabricator" in r.content
    r = c.post(reverse("challan_new"), {**base, "party": f2.pk, "bundle": [bundles[1].pk], "confirm_second": "on"})
    assert r.status_code == 302


def test_rate_screens(company, factory, owner):
    ns = build(company, factory, owner)
    fab = fabricator(company)
    c = login(owner)
    r = c.post(reverse("rate_new"), {"party": fab.pk, "process": step(ns, "STITCH").process.pk, "rate_type": "B", "effective_from": "2026-05-01",
                                     "base_rate": "20", "rework_rate": "4", "addon_name": ["Bar tack", "", ""], "addon_amount": ["2.5", "", ""]})
    assert r.status_code == 302
    assert b"Bar tack 2.50" in c.get(reverse("rate_list")).content
    bad = c.post(reverse("rate_new"), {"party": fab.pk, "process": step(ns, "STITCH").process.pk, "rate_type": "B", "effective_from": "2026-06-01", "base_rate": "20"})
    assert bad.status_code == 200 and b"at least one extra" in bad.content


# ---------------- dashboard, tracking, permissions ----------------

def test_dashboard_and_tracking_show_where_everything_is(company, factory, owner):
    ns = build(company, factory, owner)
    cut(ns)
    c = login(owner)
    html = c.get(reverse("production_dashboard")).content.decode()
    assert "Production dashboard" in html and "Cut, waiting" in html and "100" in html
    tr = c.get(reverse("production_track"), {"q": "JGR-1"}).content.decode()
    assert ns.lot.lot_no in tr and "B001" in tr and "Cut" in tr
    assert ns.lot.lot_no in c.get(reverse("production_track"), {"q": ns.order.number}).content.decode()
    assert b"Nothing found" in c.get(reverse("production_track"), {"q": "zzz-none"}).content


def test_roles_see_only_their_production_screens(company, factory, owner):
    ns = build(company, factory, owner)
    cutter = user_with("cutter", "Cutting Master", factory)
    qc = user_with("qc", "QC Checker", factory)
    sup = user_with("sup", "Production Supervisor", factory)
    c = login(cutter)
    assert c.get(reverse("lot_cutting", args=[ns.lot.pk])).status_code == 200
    assert c.get(reverse("bill_list")).status_code == 403 and c.get(reverse("challan_new")).status_code == 403
    q = login(qc)
    assert q.get(reverse("receipt_list")).status_code == 200
    assert q.get(reverse("challan_new")).status_code == 403 and q.get(reverse("lot_cutting", args=[ns.lot.pk])).status_code == 403
    s = login(sup)
    assert s.get(reverse("bill_list")).status_code == 403 and s.get(reverse("rate_list")).status_code == 403
    assert s.get(reverse("move_bundles")).status_code == 200 and s.get(reverse("order_new")).status_code == 403
    html = s.get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    assert "Lot cost" not in html  # cost is hidden from roles without the cost permission
    assert "Lot cost" in login(owner).get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()


def test_production_screens_never_show_a_customer(company, factory, owner):
    ns = build(company, factory, owner)
    from masters.services import parties

    parties.create_party(company=company, name="Secret Customer Traders", mobile="9876543210", is_customer=True)
    order = ProductionOrder.objects.get()
    order.purpose, order.order_reference = "mto", "SO-9"
    order.save()
    sup = user_with("sup", "Production Supervisor", factory)
    c = login(sup)
    for name, args in (("order_list", ()), ("order_detail", (order.pk,)), ("lot_detail", (ns.lot.pk,)), ("production_dashboard", ())):
        body = c.get(reverse(name, args=args)).content.decode()
        assert "Secret Customer" not in body and "9876543210" not in body


def test_production_scoping_on_the_screens(company, factory, factory2, owner):
    ns = build(company, factory, owner)
    other = user_with("sup2", "Production Supervisor", factory2)
    c = login(other)
    assert c.get(reverse("lot_detail", args=[ns.lot.pk])).status_code == 404
    assert c.get(reverse("order_detail", args=[ns.order.pk])).status_code == 404
    assert ns.lot.lot_no.encode() not in c.get(reverse("order_list")).content


def test_nav_shows_production_and_job_work_groups(company, factory, owner):
    ns = build(company, factory, owner)
    sup = user_with("sup", "Production Supervisor", factory)
    html = login(sup).get(reverse("home")).content.decode()
    assert "Move bundles" in html and "Sent to fabricators" in html and "Labour bills" not in html


# ---------------- home dashboard ----------------

def test_home_shows_lots_in_production_and_hides_money_from_production_roles(company, factory, owner):
    ns = build(company, factory, owner, with_stock=True)
    html = login(owner).get(reverse("home")).content.decode()
    assert "Items in production" in html and "Today at a glance" in html and ns.lot.lot_no in html
    sup = user_with("sup_home", "Production Supervisor", factory)
    body = login(sup).get(reverse("home")).content.decode()
    assert "Money received" not in body and "Sales today" not in body


# ---------------- the active factory drives production and job work ----------------

def test_production_and_job_work_entries_follow_the_active_factory(company, factory, factory2, owner):
    ns = build(company, factory, owner)
    c = login(owner)
    form = {"factory": factory.pk, "date": "2026-06-15", "purpose": "stock",
            "style": [ns.style.pk, ""], "colour": [ns.black.pk, ns.black.pk], "qty": ["60", ""], "ratios": ["S:1, M:2, L:2, XL:1", ""]}
    c.post(reverse("factory_switch"), {"factory": factory2.pk})
    c.post(reverse("order_new"), form)
    new = ProductionOrder.objects.exclude(pk=ns.order.pk).get()
    assert new.factory == factory2                                           # the form's factory value is ignored
    assert [o.factory for o in c.get(reverse("order_list")).context["orders"]] == [factory2]
    c.post(reverse("factory_switch"), {"factory": "all"})
    assert len(c.get(reverse("order_list")).context["orders"]) == 2
    for name in ("order_new", "bill_new"):
        r = c.get(reverse(name))
        assert r.status_code == 302 and "single factory" in str(list(r.wsgi_request._messages)[-1]), name
    c.post(reverse("order_new"), form)
    assert ProductionOrder.objects.count() == 2                              # nothing was saved in All mode


def test_the_dashboard_lists_orders_waiting_for_release_and_releases_them_there(company, factory, owner):
    ns = build(company, factory, owner)
    c = login(owner)
    c.post(reverse("order_new"), {
        "factory": factory.pk, "date": "2026-06-15", "due_date": "2026-07-15", "purpose": "mto", "order_reference": "SO-77",
        "style": [ns.style.pk, ""], "colour": [ns.black.pk, ns.black.pk], "qty": ["60", ""], "ratios": ["S:1, M:2, L:2, XL:1", ""]})
    order = ProductionOrder.objects.exclude(pk=ns.order.pk).get()
    html = c.get(reverse("production_dashboard")).content.decode()
    assert "Waiting for release" in html and "SO-77" in html and 'value="release"' in html and ">60<" in html
    r = c.post(reverse("production_dashboard"), {"action": "release", "order": order.pk})
    order.refresh_from_db()
    assert r.status_code == 302 and order.status == "released" and order.lines.get().lot
    assert "SO-77" not in c.get(reverse("production_dashboard")).content.decode()
    assert "Nothing is waiting for release" in c.get(reverse("production_dashboard")).content.decode()


# ---------------- pieces expected from fabric, loss in cutting, no-loss stages ----------------

def test_fabric_and_cutting_screens_show_expected_pieces_and_take_cutting_loss(company, factory, owner):
    ns = build(company, factory, owner)
    c = login(user_with("cutter", "Cutting Master", factory))
    assert "Pieces you expect from this fabric" in c.get(reverse("lot_fabric", args=[ns.lot.pk])).content.decode()
    c.post(reverse("lot_fabric", args=[ns.lot.pk]), {f"qty_{ns.roll_a.pk}": "30", "estimated_pieces": "75"})
    page = c.get(reverse("lot_fabric", args=[ns.lot.pk])).content.decode()
    assert "Your estimate so far" in page and ">75<" in page and "25 pieces short of the plan" in page
    c.post(reverse("lot_cutting", args=[ns.lot.pk]), {
        f"pieces_{ns.sizes['M'].pk}": "70", f"used_{ns.roll_a.pk}": "28", f"remnant_{ns.roll_a.pk}": "2"})
    entry = ns.lot.cuttings.get()
    assert "should give 70 pieces" in c.get(reverse("lot_cutting", args=[ns.lot.pk])).content.decode()   # 28 kg at 2.5 a kg
    bad = c.post(reverse("lot_cutting", args=[ns.lot.pk]), {
        "action": "bundles", "entry": entry.pk, f"bundles_{ns.sizes['M'].pk}": "25 25 17", f"loss_{ns.sizes['M'].pk}": "71"})
    assert bad.status_code == 200 and b"cannot be more than" in bad.content and not ns.lot.bundles.exists()
    bad = c.post(reverse("lot_cutting", args=[ns.lot.pk]), {     # 70 bundled with 3 lost: the lost pieces are not there
        "action": "bundles", "entry": entry.pk, f"bundles_{ns.sizes['M'].pk}": "25 25 20", f"loss_{ns.sizes['M'].pk}": "3"})
    assert bad.status_code == 200 and b"(3 too many)" in bad.content and not ns.lot.bundles.exists()
    assert not entry.sizes.filter(loss__gt=0).exists()           # a refused try saves nothing
    r = c.post(reverse("lot_cutting", args=[ns.lot.pk]), {
        "action": "bundles", "entry": entry.pk, f"bundles_{ns.sizes['M'].pk}": "25 25 17", f"loss_{ns.sizes['M'].pk}": "3"}, follow=True)
    assert b"3 pieces lost in cutting left out" in r.content
    assert sorted(b.qty for b in ns.lot.bundles.all()) == [17, 25, 25]
    page = login(owner).get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    assert "Estimated from fabric" in page and "Lost in cutting" in page


def test_the_move_screen_takes_no_loss_at_a_no_loss_stage(company, factory, owner):
    ns = build(company, factory, owner)
    routes.reassign_step(step(ns, "STITCH"), user=owner, reason="in-house", assignment="in_house", rate=D("10"))
    for code in ("EMB", "PRINT", "WASH"):
        routes.skip_step(step(ns, code), user=owner, reason="n/a")
    bundles = cut(ns)
    c = login(user_with("sup", "Production Supervisor", factory))
    for code in ("STITCH", "IRON"):
        c.post(reverse("move_bundles"), {"lot": ns.lot.pk, "bundle": [b.pk for b in bundles], "to_step": step(ns, code).pk,
                                         "materials_step": "1"})        # the materials step, with nothing issued
    page = c.get(reverse("move_bundles"), {"lot": ns.lot.pk}).content.decode()
    assert "No loss allowed at this stage" in page and f"loss_{bundles[0].pk}" not in page
    bad = c.post(reverse("move_bundles"), {"lot": ns.lot.pk, "bundle": [bundles[0].pk], "to_step": step(ns, "FINISH").pk,
                                           f"loss_{bundles[0].pk}": "1"})
    assert bad.status_code == 200 and b"allows no loss" in bad.content


# ---------------- pay basis on the screens ----------------

def test_pay_on_pieces_received_through_the_rate_bill_and_waive_screens(company, factory, owner):
    from jobwork.models import JobWorkDeductionWaiver, LabourRate
    from jobwork.services import challans, receipts
    from jobwork.services.receipts import Counted

    ns = build(company, factory, owner)
    bundles = cut(ns)
    fab = fabricator(company)
    c = login(owner)
    r = c.post(reverse("rate_new"), {"party": fab.pk, "process": step(ns, "STITCH").process.pk, "rate_type": "A",
                                     "effective_from": "2026-05-01", "base_rate": "25", "rework_rate": "5", "pay_basis": "received"})
    assert r.status_code == 302 and LabourRate.objects.get().pay_basis == "received"
    assert b"Pieces received back" in c.get(reverse("rate_list")).content

    ch = challans.create_and_issue(company=company, factory=factory, party=fab, lot=ns.lot, step=step(ns, "STITCH"),
                                   bundles=bundles[:2], date=DAY, user=owner)
    assert b"Paid on: pieces received back" in c.get(reverse("challan_detail", args=[ch.pk])).content
    cb1, cb2 = list(ch.bundles.order_by("id"))
    rec = receipts.create_receipt(challan=ch, user=owner, date=DAY, counts=[Counted(cb1, 17), Counted(cb2, 23)])   # 2 short
    l1, l2 = list(rec.lines.order_by("id"))
    receipts.record_qc(receipt_line=l1, accepted=17, user=owner)
    receipts.record_qc(receipt_line=l2, accepted=20, rejected=3, reject_reason="Open seams", user=owner)

    page = c.get(reverse("bill_new"), {"party": fab.pk}).content.decode()
    assert "Pieces to pay" in page and "575.00" in page                      # 23 received x 25, rejected ones included
    assert f'name="ded_{l2.pk}"  aria-label' in page and "We bear this" in page     # the shortage starts unticked

    acct = make_user("acct")
    acct.roles.add(Role.objects.get(name="Accountant"))
    acct.allowed_factories.add(factory)
    a = login(acct)
    assert "We bear this" not in a.get(reverse("bill_new"), {"party": fab.pk}).content.decode()
    assert a.post(reverse("bill_new"), {"party": fab.pk, "waive": str(l2.pk), f"reason_{l2.pk}": "x"}).status_code == 403
    assert not JobWorkDeductionWaiver.objects.exists()

    bad = c.post(reverse("bill_new"), {"party": fab.pk, "waive": str(l2.pk), f"reason_{l2.pk}": ""})
    assert bad.status_code == 200 and b"Give a reason" in bad.content
    ok = c.post(reverse("bill_new"), {"party": fab.pk, "waive": str(l2.pk), f"reason_{l2.pk}": "Ours to bear"}, follow=True)
    assert b"Deduction waived" in ok.content and JobWorkDeductionWaiver.objects.get().receipt_line == l2
    assert "Shortage of 2 pieces" not in ok.content.decode()

    qcs = list(QcResult.objects.all())
    c.post(reverse("bill_new"), {"party": fab.pk, "date": "2026-06-30", "tds_template": "", **{f"qc_{x.pk}": "on" for x in qcs}})
    bill = JobWorkBill.objects.get()
    assert bill.gross == D("1000.00") and bill.deductions == D("0.00")        # 40 received x 25, nothing taken off


# ---------------- QC split on the screens ----------------

def test_qc_screen_splits_rework_pieces_and_offers_their_tag(company, factory, owner):
    from jobwork.services import challans, receipts
    from jobwork.services.receipts import Counted

    ns = build(company, factory, owner)
    bundles = cut(ns)
    fab = fabricator(company)
    rates.save_rate(party=fab, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("25"), rework_rate=D("5"),
                    effective_from=date(2026, 4, 1))
    ch = challans.create_and_issue(company=company, factory=factory, party=fab, lot=ns.lot, step=step(ns, "STITCH"),
                                   bundles=bundles[1:3], date=DAY, user=owner)
    cb1, cb2 = list(ch.bundles.order_by("id"))
    rec = receipts.create_receipt(challan=ch, user=owner, date=DAY, counts=[Counted(cb1, 25), Counted(cb2, 8)])
    l1, l2 = list(rec.lines.order_by("id"))
    c = login(owner)
    assert b"Rework (send back)" in c.get(reverse("receipt_detail", args=[rec.pk])).content
    c.post(reverse("receipt_detail", args=[rec.pk]), {"action": "qc", "line": l1.pk, "accepted": "20", "rejected": "0", "rework": "5"})
    child = Bundle.objects.get(split_from=bundles[1])
    page = c.get(reverse("receipt_detail", args=[rec.pk])).content.decode()
    assert "as bundle B002-R1" in page and f"?bundle={child.pk}" in page
    tags = c.get(reverse("lot_tags", args=[ns.lot.pk]), {"bundle": child.pk}).content.decode()
    assert "B002-R1" in tags
    lot_page = c.get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    assert "from B002" in lot_page
    form = c.get(reverse("challan_new"), {"lot": ns.lot.pk, "kind": "rework", "step": step(ns, "STITCH").pk}).content.decode()
    assert "B002-R1" in form and f'<option value="{fab.pk}" selected' in form.replace("  ", " ")     # back to the same stitcher


# ---------------- boxes on the screens ----------------

def test_packing_into_boxes_and_box_labels_through_the_screens(company, factory, factory2, owner):
    from production.models import PackEntry
    from production.services import bundles as bundle_service

    ns = build(company, factory, owner)
    routes.reassign_step(step(ns, "STITCH"), user=owner, reason="in-house", assignment="in_house", rate=D("10"))
    for code in ("EMB", "PRINT", "WASH"):
        routes.skip_step(step(ns, code), user=owner, reason="n/a")
    bundles = cut(ns)
    for code in ("STITCH", "IRON", "FINISH", "QC", "PACK"):
        bundle_service.move_bundles(bundles=bundles, to_step=step(ns, code), user=owner, date=DAY)
    c = login(owner)
    r = c.post(reverse("inventory_settings"), {"valuation_method": "weighted_average", "po_approval_limit": "50000",
                                               "bom_tolerance_pct": "5", "pieces_per_box": "12"})
    company.refresh_from_db()
    assert r.status_code == 302 and company.pieces_per_box == 12
    page = c.get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    assert "Packed together they fill" in page and "M 2 boxes of 12 + a short box of 9" in page
    r = c.post(reverse("pack_bundles", args=[ns.lot.pk]), {"bundle": [bundles[1].pk, bundles[2].pk]}, follow=True)   # 33 of M
    assert b"33 pieces packed into finished goods: 2 boxes of 12 and 1 short box of 9" in r.content
    entry = PackEntry.objects.get()
    assert reverse("box_labels", args=[entry.pk]) in r.content.decode()
    labels = c.get(reverse("box_labels", args=[entry.pk])).content.decode()
    assert labels.count('<div class="tag">') == 3 and "Box 1 of 3" in labels and "Box 3 of 3" in labels
    assert "Short box" in labels and "<strong>9 pcs</strong>" in labels and "<svg" in labels and ns.lot.lot_no in labels

    stranger = user_with("unit2", "Production Supervisor", factory2)
    assert login(stranger).get(reverse("box_labels", args=[entry.pk])).status_code == 404        # another factory's packing
    acct = make_user("acct")
    acct.roles.add(Role.objects.get(name="Accountant"))
    acct.allowed_factories.add(factory)
    assert login(acct).get(reverse("box_labels", args=[entry.pk])).status_code == 403            # no production screens


def test_a_style_can_set_its_own_pieces_per_box(company, factory, owner):
    ns = build(company, factory, owner, with_stock=False)
    c = login(owner)
    form = c.get(reverse("style_edit", args=[ns.style.pk])).content.decode()
    assert 'name="pieces_per_box"' in form


def test_the_move_screen_can_take_out_loss_without_moving(company, factory, owner):
    ns = build(company, factory, owner)
    bundles = cut(ns)
    c = login(user_with("sup", "Production Supervisor", factory))
    assert b"Only take out loss, do not move" in c.get(reverse("move_bundles"), {"lot": ns.lot.pk}).content
    data = {"lot": ns.lot.pk, "bundle": [bundles[1].pk], "to_step": step(ns, "STITCH").pk, "action": "count",
            f"loss_{bundles[1].pk}": "2"}
    bad = c.post(reverse("move_bundles"), data)
    assert bad.status_code == 200 and b"Give a reason" in bad.content
    ok = c.post(reverse("move_bundles"), {**data, "reason": "Cut wrong"}, follow=True)
    b = Bundle.objects.get(pk=bundles[1].pk)
    assert b"2 piece(s) taken out of 1 bundle(s). Nothing was moved." in ok.content
    assert b.qty == 23 and b.status == "cut" and b.current_step is None
