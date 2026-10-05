# Guided Steps for Making Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show every lot's journey and one "Next" button, and make each production step lead to the next, so a first-time user never has to know the order of screens.

**Architecture:** One read-only service, `production/services/guide.py`, turns a lot's real state (fabric issues, lays, bundles, challans, receipts) into a journey strip and an ordered list of permitted next actions. Templates render it through one partial. A few views change where they redirect. No model, URL, migration or posting change.

**Tech Stack:** Django 5 templates, CSS tokens (`static/css/tokens.css`), pytest + pytest-django.

**Spec:** `docs/superpowers/specs/2026-10-06-guided-making-design.md` (read its action table; it is the acceptance list).

**Run tests with:** `.venv/Scripts/python.exe -m pytest <paths> -p no:cacheprovider` from `D:\Garment ERP`. `pytest.ini` already sets `-q`; do not add another. The machine is slow (about 25 s per database test): run only the files a task names, with timeouts of 10 minutes or more.

**Project rules that apply (from CLAUDE.md):** business logic in services, not views; every queryset for a user goes through `for_user`; MTO customer name and phone never reach production screens; CSS uses tokens only, no raw hex; the user guide `docs/SETUP_GUIDE.md` is updated with any UI change.

---

## File map

| File | Change | Responsibility |
| --- | --- | --- |
| `production/services/guide.py` | create | `lot_guide(lot, user)`, `order_next(order, user)`, `pack_ready(bundle, steps)` |
| `tests/test_guide.py` | create | Service and screen tests |
| `production/views.py` | modify | Use the guide; `_pack_ready` moves to the service; release and move redirects |
| `jobwork/views.py` | modify | QC-complete redirect; `can_open_lot` in challan and receipt context |
| `reports/services/overview.py` | modify | `next` on each home production row |
| `templates/production/_lot_guide.html` | create | Journey strip and next actions |
| `templates/production/lot_detail.html` | modify | Guide on top; route, cost, history folded |
| `templates/production/order_detail.html`, `order_list.html`, `templates/core/home.html` | modify | Next-step button per lot / order / row |
| `templates/production/move.html`, `tags.html`, `cutting.html`, `fabric_issue.html`, `templates/jobwork/challan_detail.html`, `receipt_detail.html` | modify | "Back to lot" button; `back` hidden field on move |
| `static/css/base.css` | append | Journey and guide styles |
| `docs/SETUP_GUIDE.md` | modify | Production sections describe the guided flow |

---

### Task 1: The guide service

**Files:**
- Create: `production/services/guide.py`, `tests/test_guide.py`
- Modify: `production/views.py` (`_pack_ready` at about line 236 and its one use in `LotDetail.get`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_guide.py`. Use the existing helpers: `tests/prod_helpers.py` (`build`, `cut`, `step`, `go`, `fabricator`, `D`, `DAY`) and copy the small `issue`, `receive`, `qc` helpers and the `ns` fixture's rate set-up from `tests/test_jobwork.py:26-52` (read that file first to see how a STITCH challan is issued, received, over-received, QC'd and sent for rework; reuse the same calls). Read `masters` seed data or `tests/test_production.py` to learn the process codes on "Standard track pant route" and which steps follow cutting.

Write one test per behaviour, each asserting on `lot_guide(ns.lot, ns.owner)`:

```python
from django.urls import reverse

from production.services.guide import lot_guide, order_next


def primary(ns, user=None):
    return lot_guide(ns.lot, user or ns.owner)["primary"]


def test_a_released_lot_needs_fabric_first(company, factory, owner):
    ns = build(company, factory, owner)
    g = lot_guide(ns.lot, owner)
    assert g["primary"]["label"] == "Issue fabric" and g["primary"]["url"] == reverse("lot_fabric", args=[ns.lot.pk])
    labels = [s["label"] for s in g["journey"]]
    assert labels[:3] == ["Order", "Fabric", "Cut"] and labels[-1] == "Finished goods"
    assert [s["state"] for s in g["journey"]][:3] == ["done", "now", "todo"]
    assert not g["complete"] and g["others"] == [] and g["waiting"] == ""
```

Then, in the same style, with exact label and URL assertions:

1. After `cutting.issue_fabric(...)` only: primary is "Record cutting" → `lot_cutting`; journey Fabric is `done`, Cut is `now`.
2. After `cutting.record_cutting(...)` without bundles: "Make bundles" → `lot_cutting`.
3. After `cut(ns)`: with `nxt` = the first non-skipped step whose sequence is above `bundles[0].completed_seq`, and `nxt` in-house: label `f"Move to {nxt.process.name}"`, URL `reverse("move_bundles") + f"?lot={ns.lot.pk}&back=1"`, `pieces == 100`; journey Cut is `done` with `pieces == 100`.
4. Next step subcontracted to a named fabricator (set it the way the app does, `routes.reassign_step(step, user=owner, reason="test", assignment="subcontract", party=fab, factory=None, rate=D("25"), rework_rate=D("5"))`, moving bundles through any earlier in-house steps with `go` if STITCH is not the first): label `f"Send to {fab.name} for {process name}"`, URL `reverse("challan_new") + f"?lot={lot.pk}&step={step.pk}"`.
5. A draft challan (created, not issued): label `f"Issue challan to {fab.name}"` → `challan_detail`; the bundles on it do NOT also produce a "Send to" action.
6. Issued challan: `f"Receive from {fab.name}"` → `reverse("receipt_new", args=[challan.pk])`, `pieces == 100`.
7. Half the bundles issued, half still cut: primary is the "Send to" action (furthest behind) and `others` contains the "Receive from" action.
8. Received, QC pending: "Check received pieces" → `receipt_detail`.
9. Over-receipt awaiting approval: "Approve over-receipt" → `receipt_detail`.
10. QC sends pieces for rework: an action labelled "Send back for rework" whose URL is `reverse("challan_new") + f"?lot={lot.pk}&kind=rework"` is in primary-or-others.
11. Bundles brought to packing (move through every remaining step with `go`): "Pack into finished goods" → `reverse("lot_detail", args=[lot.pk]) + "#pack"`. After `bundle_service.pack_bundles(...)` of every bundle: `primary is None`, `complete is True`, last journey stage is `done`.
12. A user whose role lacks `production.cutting` create (use the seeded "Accountant" role with `make_user`, allowed on the factory) on a freshly released lot: `primary is None`, `waiting == "Issue fabric"`.
13. A closed order's lot (`orders.close_order(order, user=owner, reason="x")`): `primary is None`, `waiting == ""`, `closed is True`.
14. `order_next`: draft order → `{"release": True}` for the owner and `None` for the Accountant user; released single-lot order → the same dict as that lot's primary; completed order → `None`.

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_guide.py -p no:cacheprovider`
Expected: collection error, `ModuleNotFoundError: No module named 'production.services.guide'`.

- [ ] **Step 3: Implement the service**

Create `production/services/guide.py`:

```python
"""Where a lot is on its way from order to finished goods, and what it needs next (read-only).

The lot page, the order screens and Home all ask here, so every screen names the same next step. Callers fetch the
lot through `for_user`; nothing here widens that. Only labels, piece counts and links come back: a fabricator's name
is the only party name used (BR-15)."""
from django.urls import reverse

from core.models import Location
from jobwork.models import ChallanBundle, JobWorkChallan, Receipt
from production.models import Bundle, LotStep

B = Bundle.Status
AT_A_STAGE = (B.AT_STAGE, B.DONE, B.RECEIVED, B.REWORK)
# Within one stage, what is furthest behind comes first.
RANK = {"send": 0, "move": 0, "issue": 1, "receive": 2, "approve": 3, "qc": 4, "rework": 5}
STATE = {LotStep.Status.DONE: "done", LotStep.Status.IN_PROGRESS: "now", LotStep.Status.PENDING: "todo"}


def _packing_step(steps):
    return next((s for s in reversed(steps) if s.process.kind == "packing"), None)


def pack_ready(bundle, steps):
    """A bundle can be packed once it is at an in-house packing step, or has come back ready from one."""
    ps = _packing_step(steps)
    if ps is None:
        return False
    return (bundle.status == B.AT_STAGE and bundle.current_step_id == ps.pk and ps.assignment == LotStep.Assignment.IN_HOUSE) or \
           (bundle.status == B.READY and bundle.completed_seq >= ps.sequence)


def _journey(lot, steps, bundles, cuts, issued):
    cut_pieces = sum(b.original_qty for b in bundles)
    bundled = bool(cuts) and all(c.bundled for c in cuts)
    at = {}
    for b in bundles:
        if b.status in AT_A_STAGE and b.current_step_id:
            at[b.current_step_id] = at.get(b.current_step_id, 0) + b.qty
    stages = [
        {"label": "Order", "detail": "", "state": "done", "pieces": None},
        {"label": "Fabric", "detail": "", "state": "done" if issued or cuts else "now", "pieces": None},
        {"label": "Cut", "detail": "", "state": "done" if bundled else ("now" if issued or cuts else "todo"),
         "pieces": cut_pieces or None},
    ]
    for s in steps:
        if s.process.kind == "cutting":
            continue
        outside = s.assignment == LotStep.Assignment.SUBCONTRACT and s.party_id
        stages.append({"label": s.process.name, "detail": s.party.name if outside else "",
                       "state": STATE[s.status], "pieces": at.get(s.pk) or None})
    packed = sum(b.qty for b in bundles if b.status in (B.PACKED, B.DISPATCHED))
    done = lot.status == lot.Status.COMPLETED
    stages.append({"label": "Finished goods", "detail": "", "state": "done" if done else ("now" if packed else "todo"),
                   "pieces": packed or None})
    return stages


def _actions(lot, steps, bundles, cuts, issued):
    found = {}

    def add(key, seq, label, hint, url, perm, pieces=0):
        a = found.setdefault(key, {"label": label, "hint": hint, "url": url, "perm": perm, "pieces": 0,
                                   "order": (seq, RANK.get(key[0], 0))})
        a["pieces"] += pieces

    cutting_perm = ("production.cutting", "create")
    if not cuts and not issued:
        add(("fabric",), -3, "Issue fabric", "Send rolls from the store to the cutting floor.",
            reverse("lot_fabric", args=[lot.pk]), cutting_perm)
    elif not cuts:
        add(("cut",), -2, "Record cutting", "Enter the pieces cut in each size.", reverse("lot_cutting", args=[lot.pk]), cutting_perm)
    elif any(not c.bundled for c in cuts):
        add(("bundle",), -1, "Make bundles", "A lay is cut but not bundled yet.", reverse("lot_cutting", args=[lot.pk]), cutting_perm)

    open_status = (JobWorkChallan.Status.DRAFT, JobWorkChallan.Status.ISSUED, JobWorkChallan.Status.PARTLY)
    on_draft = set()
    for ch in lot.challans.filter(status__in=open_status).select_related("party", "step__process"):
        lines = list(ChallanBundle.objects.filter(challan=ch).select_related("bundle"))
        if ch.status == JobWorkChallan.Status.DRAFT:
            on_draft.update(l.bundle_id for l in lines)
            add(("issue", ch.pk), ch.step.sequence, f"Issue challan to {ch.party.name}",
                "The challan is a draft. Issue it to hand the bundles over.",
                reverse("challan_detail", args=[ch.pk]), ("jobwork.challan", "edit"), sum(l.bundle.qty for l in lines))
        else:
            out = sum(l.bundle.qty for l in lines if not (l.qty_received or l.qty_shortage))
            if out:
                add(("receive", ch.pk), ch.step.sequence, f"Receive from {ch.party.name}",
                    f"Count the pieces that came back from {ch.step.process.name}.",
                    reverse("receipt_new", args=[ch.pk]), ("jobwork.receipt", "create"), out)

    waiting = (Receipt.Status.PENDING_APPROVAL, Receipt.Status.RECEIVED)
    for r in Receipt.objects.filter(challan__lot=lot, status__in=waiting).select_related("challan__party", "challan__step"):
        url, seq = reverse("receipt_detail", args=[r.pk]), r.challan.step.sequence
        if r.status == Receipt.Status.PENDING_APPROVAL:
            add(("approve", r.pk), seq, "Approve over-receipt", "More pieces were counted than were sent. The owner must approve.",
                url, ("jobwork.receipt", "approve"))
        else:
            add(("qc", r.pk), seq, "Check received pieces", f"Accept, reject or send back what {r.challan.party.name} returned.",
                url, ("jobwork.qc", "create"))

    for b in bundles:
        if not b.is_live or b.pk in on_draft:
            continue
        here = b.current_step.sequence if b.current_step_id else b.completed_seq
        if b.status == B.REWORK or b.rework_qty:
            add(("rework",), here, "Send back for rework", "QC sent these pieces back to the fabricator.",
                reverse("challan_new") + f"?lot={lot.pk}&kind=rework", ("jobwork.challan", "create"), b.rework_qty or b.qty)
            continue
        if b.status not in (B.CUT, B.READY, B.AT_STAGE):
            continue
        if b.status == B.AT_STAGE and b.location.loc_type == Location.Type.FABRICATOR:
            continue                                         # out on a challan: the challan's own line covers it
        if pack_ready(b, steps):
            add(("pack",), 10_000, "Pack into finished goods", "These bundles have reached packing.",
                reverse("lot_detail", args=[lot.pk]) + "#pack", ("production.move", "create"), b.qty)
            continue
        done = here if b.status == B.AT_STAGE else b.completed_seq
        nxt = next((s for s in steps if s.sequence > done), None)
        if nxt is None:
            continue
        if nxt.assignment == LotStep.Assignment.SUBCONTRACT:
            who = nxt.party.name if nxt.party_id else "a fabricator"
            add(("send", nxt.pk), nxt.sequence, f"Send to {who} for {nxt.process.name}",
                "Make a challan and hand the bundles over.",
                reverse("challan_new") + f"?lot={lot.pk}&step={nxt.pk}", ("jobwork.challan", "create"), b.qty)
        else:
            add(("move", nxt.pk), nxt.sequence, f"Move to {nxt.process.name}", "Scan or tick the bundles that are ready.",
                reverse("move_bundles") + f"?lot={lot.pk}&back=1", ("production.move", "create"), b.qty)
    return sorted(found.values(), key=lambda a: a["order"])


def lot_guide(lot, user):
    """{'journey': [...], 'primary': action or None, 'others': [...], 'waiting': label, 'complete': bool, 'closed': bool}.
    An action is offered only if the user's role may do it; `waiting` names the next step when it is someone else's."""
    steps = [s for s in lot.steps.select_related("process", "party") if s.status != LotStep.Status.SKIPPED]
    bundles = list(lot.bundles.select_related("location", "current_step"))
    cuts = list(lot.cuttings.all())
    issued = lot.fabric_issues.exists()
    closed, complete = lot.status == lot.Status.CLOSED, lot.status == lot.Status.COMPLETED
    actions = [] if closed or complete else _actions(lot, steps, bundles, cuts, issued)
    allowed = [a for a in actions if user.has_screen_perm(*a["perm"])]
    return {
        "journey": _journey(lot, steps, bundles, cuts, issued),
        "primary": allowed[0] if allowed else None, "others": allowed[1:],
        "waiting": actions[0]["label"] if actions and not allowed else "",
        "complete": complete, "closed": closed,
    }


def order_next(order, user):
    """The one thing to do next on an order, for the orders list: release it, act on its lot, or open it."""
    if order.status == order.Status.DRAFT:
        return {"release": True} if user.has_screen_perm("production.order", "edit") else None
    if order.status in (order.Status.COMPLETED, order.Status.CLOSED):
        return None
    lots = [line.lot for line in order.lines.all() if hasattr(line, "lot")]
    if len(lots) == 1:
        return lot_guide(lots[0], user)["primary"]
    return {"label": "Open", "hint": "", "url": reverse("order_detail", args=[order.pk])} if lots else None
```

Before relying on it, check each of these against the real code and adjust the service (not the tests' intent) if one differs, reporting what you changed: `ChallanBundle` field names `qty_received` / `qty_shortage`; `Location.Type.FABRICATOR`; `Process.kind` values `"cutting"` and `"packing"`; `JobWorkChallan.Status.PARTLY`; whether a `ready` bundle keeps `current_step` set (the journey must not count ready bundles as sitting at a stage; `AT_A_STAGE` excludes `ready` for that reason).

- [ ] **Step 4: Use `pack_ready` from the service in the view**

In `production/views.py`: delete the `_pack_ready` function, add `guide` to the `from .services import ...` line, and in `LotDetail.get` change the `pack_ready` context entry to:

```python
            "pack_ready": [b for b in live if guide.pack_ready(b, [s for s in steps if s.status != "skipped"])],
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_guide.py tests/test_production_ui.py -p no:cacheprovider`
Expected: all pass. A failure in a guide test means the service or the test set-up is wrong: read the bundle's actual status and fix the cause; do not weaken an assertion to make it pass.

- [ ] **Step 6: Commit**

```bash
git add production/services/guide.py production/views.py tests/test_guide.py
git commit -m "E7 guide: a lot's journey and its next step, worked out in one service"
```

---

### Task 2: Show the guide on the lot page, order screens and Home

**Files:**
- Create: `templates/production/_lot_guide.html`
- Modify: `production/views.py` (`LotDetail.get`, `OrderDetail.get`, `OrderList.get`), `reports/services/overview.py` (`production_overview`), `templates/production/lot_detail.html`, `order_detail.html`, `order_list.html`, `templates/core/home.html`, `static/css/base.css`, `tests/test_guide.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_guide.py`; `login` and `user_with` come from the same place `tests/test_production_ui.py` imports them)

1. Lot page for the owner on a fresh lot: contains `class="journey"`, the text "Issue fabric" inside an `<a class="btn primary"` whose href is `lot_fabric`, and `<summary>Route and rates</summary>`; the page still contains the Route table text (it is folded, not removed).
2. Lot page for a role that may view lots but not cut: contains "Waiting for: Issue fabric" and no `href="{lot_fabric url}"` inside the guide.
3. Orders list for the owner: the released order's row contains "Issue fabric"; a draft order's row contains a `<button` with `value="release"`.
4. Order page: the lot line shows the "Issue fabric" button.
5. Home for the owner with a lot in production: the "Items in production" table row contains "Issue fabric". Home for a Production Supervisor still shows no money figure (keep the existing assertion style).
6. Lot page after everything is packed: "This lot is complete." and no `btn primary` in the guide.

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_guide.py -p no:cacheprovider`
Expected: the six new tests fail.

- [ ] **Step 3: Views**

- `LotDetail.get`: add `"guide": guide.lot_guide(lot, request.user)` to the context.
- `OrderDetail.get`: in each `lines` entry add `"next": guide.lot_guide(lot, request.user)["primary"] if lot else None`.
- `OrderList.get`: build `orders = list(qs[:200])`, then for each `o.next = guide.order_next(o, request.user)`; add `.prefetch_related("lines__lot")` to the queryset.
- `reports/services/overview.py::production_overview`: import `from production.services import guide` and add `"next": guide.lot_guide(lot, user)["primary"]` to each row dict.

- [ ] **Step 4: The partial**

Create `templates/production/_lot_guide.html`:

```html
<div class="island guide">
  <ol class="journey" aria-label="Where this lot is">{% for s in guide.journey %}
    <li class="{{ s.state }}"{% if s.state == "now" %} aria-current="step"{% endif %}>
      <span class="j-label">{{ s.label }}</span>
      {% if s.detail %}<span class="j-detail">{{ s.detail }}</span>{% endif %}
      {% if s.pieces %}<span class="j-pieces">{{ s.pieces }} pcs</span>{% endif %}
      <span class="sr-only">{% if s.state == "done" %}done{% elif s.state == "now" %}in progress{% else %}to come{% endif %}</span>
    </li>{% endfor %}
  </ol>
  {% if guide.primary %}
    <div class="guide-next"><a class="btn primary" href="{{ guide.primary.url }}">{{ guide.primary.label }}</a><span class="muted">{{ guide.primary.hint }}{% if guide.primary.pieces %} {{ guide.primary.pieces }} pieces.{% endif %}</span></div>
    {% if guide.others %}<p class="muted guide-also">Also waiting: {% for a in guide.others %}<a href="{{ a.url }}">{{ a.label }}</a>{% if not forloop.last %} · {% endif %}{% endfor %}</p>{% endif %}
  {% elif guide.waiting %}<p class="muted">Waiting for: {{ guide.waiting }}</p>
  {% elif guide.complete %}<p>This lot is complete.</p>
  {% elif guide.closed %}<p class="muted">This lot is closed.</p>{% endif %}
</div>
```

Check `static/css/base.css` for an existing visually-hidden class (`sr-only`, `visually-hidden`); use the existing name, or add `.sr-only` if none exists.

- [ ] **Step 5: Lot page**

In `templates/production/lot_detail.html`:

- Header `actions`: keep only "Print tags" (the existing `lot_tags` link, relabelled from "QR tags", shown when bundles exist) and the order link.
- Directly under the page head: `{% include "production/_lot_guide.html" %}`.
- Keep the planned / cut / in progress island visible.
- Move the Bundles island up to follow the figures, and give the packing form's wrapper `id="pack"`.
- Wrap the Route island's content in `<details><summary>Route and rates</summary>…</details>`, the Lot cost island in `<details><summary>Lot cost</summary>…</details>` (only when `breakdown`), and Route changes in `<details><summary>History</summary>…</details>`. All closed by default. Keep every form inside them unchanged.
- Add a last row of ghost buttons for corrections, shown under the same permission flags as today: "Fabric issue" (`lot_fabric`), "Cutting" (`lot_cutting`), "Move bundles" (`move_bundles?lot=…&back=1`).

- [ ] **Step 6: Orders list, order page, Home**

- `order_list.html`: add a last column "Next step". Cell: if `o.next.release`, a small form `method="post" action="{% url 'order_detail' o.pk %}"` with `{% csrf_token %}` and `<button class="btn primary" name="action" value="release">Release</button>`; elif `o.next`, `<a class="btn" href="{{ o.next.url }}">{{ o.next.label }}</a>`.
- `order_detail.html`: beside the lot button, `{% if r.next %}<a class="btn primary" href="{{ r.next.url }}">{{ r.next.label }}</a>{% endif %}`.
- `templates/core/home.html`: add a last column "Next step" to the Items in production table with `{% if r.next %}<a class="btn" href="{{ r.next.url }}">{{ r.next.label }}</a>{% endif %}`.

- [ ] **Step 7: Styles**

Append to `static/css/base.css`, tokens only (confirm each token name in `tokens.css`; `--color-success` exists for status use):

```css
/* ---- lot journey and next step ---- */
.journey { display: flex; flex-wrap: wrap; gap: var(--space-2); list-style: none; margin: 0 0 var(--space-4); padding: 0; }
.journey li { flex: 1 1 110px; display: flex; flex-direction: column; gap: 2px; padding: var(--space-2) var(--space-3); border-radius: var(--radius); background: var(--color-primary-soft); color: var(--color-muted); border-top: 3px solid var(--color-hairline); }
.journey li.done { color: var(--color-ink); border-top-color: var(--color-success); }
.journey li.now { color: var(--color-ink); background: var(--color-primary-pale); border-top-color: var(--color-primary); }
.journey .j-label { font-weight: 600; }
.journey .j-detail, .journey .j-pieces { font-size: var(--text-label); font-variant-numeric: tabular-nums; }
.guide-next { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-3); }
.guide-next .btn { min-height: 44px; }
.guide-also { margin: var(--space-2) 0 0; }
```

Check the done / now / to-come text meets WCAG AA contrast on its background in both themes; state is also carried by the hidden text and `aria-current`, never by colour alone.

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_guide.py tests/test_production_ui.py tests/test_navigation.py -p no:cacheprovider`
Expected: all pass. Existing tests that looked for "Issue fabric", "Cutting", "QR tags" or "Move bundles" as header buttons on the lot page: update them to the new places (guide button or the corrections row); do not delete them.

- [ ] **Step 9: Commit**

```bash
git add production/views.py reports/services/overview.py templates/production/_lot_guide.html templates/production/lot_detail.html templates/production/order_detail.html templates/production/order_list.html templates/core/home.html static/css/base.css tests/test_guide.py
git commit -m "E7 guide: journey and next step on the lot, the orders screens and Home"
```

(Add by name any existing test file you updated.)

---

### Task 3: Each step leads to the next

**Files:**
- Modify: `production/views.py` (`OrderDetail.post`, `MoveView`), `jobwork/views.py` (`ChallanDetail.get`, `ReceiptDetail.get`, `ReceiptDetail.post`), `templates/production/move.html`, `tags.html`, `cutting.html`, `fabric_issue.html`, `templates/jobwork/challan_detail.html`, `receipt_detail.html`, `tests/test_guide.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_guide.py`, through the test client as the owner unless stated)

1. POST `action=release` on a draft order with one line redirects to `lot_detail` of its lot.
2. The same POST by a user who may edit orders but not view lots (build a role for it, or skip with a clear reason if no seeded role fits) redirects to `order_detail`.
3. POST a valid move on `move_bundles` with `back=1` redirects to `lot_detail`; the same POST without `back` redirects to `move_bundles?lot=…`.
4. GET `move_bundles?lot=…&back=1` renders a hidden input `name="back" value="1"`.
5. Recording QC on the last unchecked line of a receipt redirects to `lot_detail`; with another line still unchecked it redirects to `receipt_detail`.
6. Tags, cutting, fabric issue, challan and receipt pages each contain a link to `lot_detail` with the text "Back to lot" for the owner; the challan page for a role without `production.lot` view does not.

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_guide.py -p no:cacheprovider`

- [ ] **Step 3: Implement**

`production/views.py`, `OrderDetail.post`, release branch: after the success message,

```python
                lots = [l.lot for l in order.lines.all() if hasattr(l, "lot")]
                if len(lots) == 1 and user.has_screen_perm("production.lot", "view"):
                    return redirect("lot_detail", pk=lots[0].pk)
```

`MoveView`: in `_ctx` add `"back": (request.GET.get("back") or request.POST.get("back")) == "1"`; at the end of `post`:

```python
        if p.get("back") == "1" and request.user.has_screen_perm("production.lot", "view"):
            return redirect("lot_detail", pk=lot.pk)
        return redirect(f"{request.path}?lot={lot.pk}")
```

`templates/production/move.html`: inside the move form, `{% if back %}<input type="hidden" name="back" value="1">{% endif %}`.

`jobwork/views.py`: add `"can_open_lot": request.user.has_screen_perm("production.lot", "view")` to the `ChallanDetail.get` and `ReceiptDetail.get` contexts. In `ReceiptDetail.post`, after a successful QC:

```python
                r.refresh_from_db()
                if r.status == Receipt.Status.QC_DONE and user.has_screen_perm("production.lot", "view"):
                    messages.success(request, "QC recorded. Every bundle on this receipt is checked.")
                    return redirect("lot_detail", pk=r.challan.lot_id)
```

(Check how the receipt's status becomes `qc_done` in `jobwork/services/receipts.py`; if the service does not set it when the last line is checked, use "no receipt line with `qc_done=False`" instead, and report it.)

"Back to lot" button, in each page's header `actions`:

- `tags.html`, `cutting.html`, `fabric_issue.html` (these views already require a production permission; show the link only `{% if perms_lot %}`; add `"perms_lot": request.user.has_screen_perm("production.lot", "view")` to the three views' contexts): `<a class="btn" href="{% url 'lot_detail' lot.pk %}">Back to lot</a>`.
- `challan_detail.html`: `{% if can_open_lot %}<a class="btn" href="{% url 'lot_detail' ch.lot_id %}">Back to lot</a>{% endif %}`.
- `receipt_detail.html`: the same with `r.challan.lot_id`.

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_guide.py tests/test_production_ui.py tests/test_jobwork.py -p no:cacheprovider`
Expected: all pass. An existing test that asserted the old redirect after release (to `order_detail`) for a single-lot order: update it to the lot.

- [ ] **Step 5: Commit**

```bash
git add production/views.py jobwork/views.py templates/production/move.html templates/production/tags.html templates/production/cutting.html templates/production/fabric_issue.html templates/jobwork/challan_detail.html templates/jobwork/receipt_detail.html tests/test_guide.py
git commit -m "E7 guide: each production step leads on to the next"
```

---

### Task 4: User guide

**Files:** `docs/SETUP_GUIDE.md` only. Do not rename, add or reorder headings (`core/help.py` anchors depend on them).

- [ ] **Step 1:** In the production sections (orders, release, fabric issue, cutting, bundles and tags, moving bundles, packing) and the dry-run walkthrough, rewrite the click paths to the guided flow: the lot page shows the journey strip and one Next button; releasing a single-lot order opens the lot; the Next button names the step (Issue fabric, Record cutting, Make bundles, Move to …, Send to …, Receive from …, Check received pieces, Pack into finished goods); "Also waiting" lists other pending steps; "Waiting for: …" appears when the step belongs to another role; Route and rates, Lot cost and History are folded sections; the corrections row keeps Fabric issue, Cutting and Move bundles reachable; the orders list and Home show the same Next step.
- [ ] **Step 2:** `git diff -U0 docs/SETUP_GUIDE.md | grep '^[-+]#'` prints nothing.
- [ ] **Step 3:** Commit `docs/SETUP_GUIDE.md` with message `Docs: production guide follows the guided lot flow`.

---

## Done when

- The full suite is green (`.venv/Scripts/python.exe -m pytest -p no:cacheprovider`), including the autouse trial-balance and stock checks.
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` reports no changes.
- In the browser, a fresh order can be taken to finished goods by pressing only the Next button on each screen, plus the entry forms themselves.
