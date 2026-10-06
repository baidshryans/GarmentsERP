from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from core.exceptions import BusinessRuleError
from core import forms_ui, viewutils as vu
from core.models import Company, Location
from core.scoping import ScreenPermissionMixin
from core.services.active_factory import in_active, require_active_factory
from inventory.views import item_choices, parse_item
from masters.models import Material, Party
from tax.models import TaxTemplate

from .models import DebitNote, Grn, GrnLine, PurchaseInvoice, PurchaseInvoiceLine, PurchaseOrder, PurchaseOrderLine
from .services import debit_notes, grn as grn_service, invoices, orders
from .services import guide as guide_service
from ledger.settlement import settlement


def _company():
    return Company.objects.get(setup_complete=True)


def _decimal(text, label, default=None):
    text = (text or "").strip().replace(",", "")
    if not text:
        if default is not None:
            return default
        raise ValueError(f"{label} is required.")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError(f"{label} '{text}' is not a number.")


def _msgs(request, exc):
    if isinstance(exc, ValidationError):
        for m in exc.messages:
            messages.error(request, m)
    else:
        messages.error(request, str(exc))


def _date(value, default=None):
    if not value:
        if default is not None:
            return default
        raise ValueError("Enter a date.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"'{value}' is not a valid date (use YYYY-MM-DD).")


def form_values(obj, data, fields):
    """Field values for a form: what was just posted, else the saved object's. Everything as strings, so
    templates never touch an object that does not exist yet."""
    out = {}
    for f in fields:
        if data:
            out[f] = data.get(f, "") or ""
        elif obj is not None:
            raw = getattr(obj, f"{f}_id", None) if f in ("vendor", "factory", "location") else getattr(obj, f, "")
            out[f] = raw.isoformat() if hasattr(raw, "isoformat") else ("" if raw is None else str(raw))
        else:
            out[f] = ""
    return out


def _vendors():
    return Party.objects.filter(is_vendor=True, is_active=True)


def _offers(guide, kind):
    """Does the guide offer this step to the user? Page buttons that repeat a step show only while it does."""
    return any(a["kind"] == kind for a in [guide["primary"], *guide["others"]] if a)


def _with_next(rows, next_step, user):
    """The rows shown on a list, each with its next step. One memo serves the page: every permission and every
    supplier's open bills are asked once."""
    rows, memo = list(rows), {}
    for row in rows:
        row.next = next_step(row, user, memo)
    return rows


def _need_factory(request, to):
    """New documents are entered in one factory. In "All factories" mode say so and go back to the list."""
    if request.factory is None:
        messages.error(request, "Choose a single factory in the top bar before entering a document.")
        return redirect(to)
    return None


# ================================================================ purchase orders

class POList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.po"

    def get(self, request):
        qs = in_active(PurchaseOrder.objects.for_user(request.user), request).select_related("vendor", "factory", "company")
        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return render(request, "purchases/po_list.html", {
            "pos": _with_next(qs[:200], guide_service.po_next, request.user), "status": status, "statuses": PurchaseOrder.Status.choices,
            "can_create": request.user.has_screen_perm("purchases.po", "create"),
            "can_edit": request.user.has_screen_perm("purchases.po", "edit"),
        })


class POSave(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.po"

    def dispatch(self, request, *args, **kwargs):
        self.screen_action = "edit" if kwargs.get("pk") else "create"
        return super().dispatch(request, *args, **kwargs)

    def _ctx(self, request, po=None, rows=None, d=None):
        mats, skus = item_choices()
        if rows is None:
            rows = [{"item": f"m:{l.material_id}" if l.material_id else f"s:{l.sku_id}", "qty": l.qty, "rate": l.rate}
                    for l in po.lines.all()] if po else []
        return {"po": po, "factory": po.factory if po else request.factory, "vendors": _vendors(), "mats": mats, "skus": skus,
                "rows": rows + [{}, {}], "d": d or {},
                # submitting is the order page's `edit` action: a new order can be saved and submitted by a role that has it
                "can_submit": po is None and request.user.has_screen_perm("purchases.po", "edit"),
                "vals": form_values(po, d, ("vendor", "date", "expected_date", "remarks"))}

    def get(self, request, pk=None):
        po = get_object_or_404(PurchaseOrder.objects.for_user(request.user), pk=pk) if pk else None
        if po is None and (back := _need_factory(request, "po_list")):
            return back
        return render(request, "purchases/po_form.html", self._ctx(request, po))

    def post(self, request, pk=None):
        po = get_object_or_404(PurchaseOrder.objects.for_user(request.user), pk=pk) if pk else None
        p = request.POST
        submit_now = po is None and p.get("then") == "submit"
        if submit_now and not request.user.has_screen_perm("purchases.po", "edit"):
            raise PermissionDenied
        # every line as typed first, so the form comes back whole whatever is refused below
        rows = [{"item": value, "qty": p.getlist("qty")[i], "rate": p.getlist("rate")[i]} for i, value in enumerate(p.getlist("item"))]
        specs = []
        try:
            vendor = vu.chosen(Party.objects.all(), p.get("vendor"), "supplier")
            for row in rows:
                if row["item"]:
                    specs.append(orders.POLineSpec(parse_item(row["item"]), _decimal(row["qty"], "Quantity"), _decimal(row["rate"], "Rate")))
            expected = _date(p.get("expected_date"), default=None) if p.get("expected_date") else None
            if po is None:
                po = (orders.create_and_submit if submit_now else orders.create_po)(
                    company=_company(), factory=require_active_factory(request),
                    vendor=vendor, date=_date(p.get("date")), lines=specs, user=request.user,
                    expected_date=expected, remarks=p.get("remarks", ""))
            else:
                orders.update_po(po, lines=specs, user=request.user, vendor=vendor, date=_date(p.get("date")),
                                 expected_date=expected, remarks=p.get("remarks", ""))
        except (ValueError, BusinessRuleError) as exc:
            _msgs(request, exc)
            return render(request, "purchases/po_form.html", self._ctx(request, po, rows, p))
        if not submit_now:
            messages.success(request, "Purchase order saved as a draft.")
        elif po.status == PurchaseOrder.Status.PENDING:
            messages.warning(request, f"{po.number} is above the approval limit and is waiting for the owner.")
        else:
            messages.success(request, f"{po.number} approved. You can receive goods against it.")
        return redirect("po_detail", pk=po.pk)


class PODetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.po"

    def _po(self, request, pk):
        return get_object_or_404(PurchaseOrder.objects.for_user(request.user).select_related("vendor", "factory", "approved_by", "company"), pk=pk)

    def get(self, request, pk):
        po = self._po(request, pk)
        lines = [{"line": l, "received": orders.received_qty(l), "pending": orders.pending_qty(l)} for l in po.lines.select_related("material", "sku__style", "sku__colour", "sku__size")]
        user = request.user
        guide = guide_service.po_guide(po, user)
        return render(request, "purchases/po_detail.html", {
            "po": po, "lines": lines, "grns": po.grns.all(),
            "can_edit": user.has_screen_perm("purchases.po", "edit"),
            "can_approve": user.has_screen_perm("purchases.po", "approve"),
            "can_receive": guide["receive"] is not None, "can_open_grn": user.has_screen_perm("purchases.grn", "view"),
            "limit": po.company.po_approval_limit, "guide": guide,
        })

    def post(self, request, pk):
        po = self._po(request, pk)
        action = request.POST.get("action")
        user = request.user
        try:
            if action in ("submit", "short_close") and not user.has_screen_perm("purchases.po", "edit"):
                raise PermissionDenied
            if action == "submit":
                po = orders.submit_po(po, user=user)
                if po.status == "pending_approval":
                    messages.warning(request, f"{po.number} is above the approval limit and is waiting for the owner.")
                else:
                    messages.success(request, f"{po.number} approved.")
            elif action == "approve":
                orders.approve_po(po, user=user)
                messages.success(request, "Purchase order approved.")
            elif action == "reject":
                orders.reject_po(po, user=user, reason=request.POST.get("reason", ""))
                messages.success(request, "Sent back to draft.")
            elif action == "short_close":
                orders.short_close(po, user=user, reason=request.POST.get("reason", ""))
                messages.success(request, "Purchase order short-closed.")
        except BusinessRuleError as exc:
            messages.error(request, str(exc))
        return redirect("po_detail", pk=pk)


class PendingPOs(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.po"

    def get(self, request):
        return render(request, "purchases/po_pending.html", {"rows": orders.pending_report(request.user)})


# ================================================================ GRN

def parse_rolls(text):
    """One roll per line: roll no, qty [, metres, lot, gsm, width_cm]. Commas, tabs or semicolons separate."""
    rolls = []
    for n, raw in enumerate((text or "").splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        parts = [x.strip() for x in raw.replace("\t", ",").replace(";", ",").split(",")]
        if len(parts) < 2:
            raise ValueError(f"Roll line {n}: give the roll number and the quantity, for example  R-101, 24.5")
        parts += [""] * (6 - len(parts))
        gsm = parts[4]
        rolls.append(grn_service.RollSpec(
            vendor_roll_no=parts[0], qty=_decimal(parts[1], f"Roll {parts[0]} quantity"),
            length_m=_decimal(parts[2], "Metres", Decimal("0")) or None, lot_no=parts[3],
            gsm=int(gsm) if gsm else None, width_cm=_decimal(parts[5], "Width", Decimal("0")) or None,
        ))
    return rolls


def rolls_to_text(line):
    out = []
    for r in line.rolls.all():
        out.append(", ".join([r.vendor_roll_no, f"{r.qty.normalize():f}", f"{r.length_m.normalize():f}" if r.length_m else "",
                              r.lot_no, str(r.gsm or ""), f"{r.width_cm.normalize():f}" if r.width_cm else ""]).rstrip(", "))
    return "\n".join(out)


class GrnList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.grn"

    def get(self, request):
        qs = in_active(Grn.objects.for_user(request.user), request).select_related("vendor", "factory", "po")
        return render(request, "purchases/grn_list.html", {
            "grns": _with_next(qs[:200], guide_service.grn_next, request.user), "can_create": request.user.has_screen_perm("purchases.grn", "create"),
            "can_edit": request.user.has_screen_perm("purchases.grn", "edit"),
        })


class GrnSave(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.grn"

    def dispatch(self, request, *args, **kwargs):
        self.screen_action = "edit" if kwargs.get("pk") else "create"
        return super().dispatch(request, *args, **kwargs)

    def _rows_from_po(self, po):
        rows = []
        for l in po.lines.select_related("material", "sku__style", "sku__colour", "sku__size"):
            pending = orders.pending_qty(l)
            if pending > 0:
                rows.append({"item": f"m:{l.material_id}" if l.material_id else f"s:{l.sku_id}", "rate": l.rate,
                             "qty": "" if (l.material_id and l.material.kind == "fabric") else pending,
                             "po_line": l.pk, "hint": f"Pending {pending.normalize():f}"})
        return rows

    def _rows_from_grn(self, grn):
        return [{"item": f"m:{l.material_id}" if l.material_id else f"s:{l.sku_id}", "rate": l.rate,
                 "qty": "" if l.is_fabric_rolls else l.qty_received, "po_line": l.po_line_id or "",
                 "rolls": rolls_to_text(l) if l.is_fabric_rolls else ""} for l in grn.lines.select_related("material")]

    def _ctx(self, request, grn=None, po=None, rows=None, d=None):
        mats, skus = item_choices()
        if rows is None:
            rows = self._rows_from_grn(grn) if grn else (self._rows_from_po(po) if po else [])
        factory = grn.factory if grn else (po.factory if po else request.factory)
        locations = Location.objects.filter(factory=factory, is_active=True).exclude(loc_type="transit")
        vals = form_values(grn, d, ("vendor", "location", "date", "vendor_challan_no", "vendor_challan_date", "remarks"))
        if po is not None and not (d or grn):
            vals.update(vendor=str(po.vendor_id))
        return {"grn": grn, "po": po or (grn.po if grn else None), "mats": mats, "skus": skus, "rows": rows + [{}, {}],
                "factory": factory, "locations": locations, "vendors": _vendors(), "d": d or {}, "vals": vals}

    def get(self, request, pk=None):
        grn = get_object_or_404(Grn.objects.for_user(request.user), pk=pk) if pk else None
        po = None
        if request.GET.get("po"):
            po = get_object_or_404(PurchaseOrder.objects.for_user(request.user), pk=request.GET["po"])
        if grn is None and po is None and (back := _need_factory(request, "grn_list")):
            return back
        return render(request, "purchases/grn_form.html", self._ctx(request, grn, po))

    def post(self, request, pk=None):
        grn = get_object_or_404(Grn.objects.for_user(request.user), pk=pk) if pk else None
        p = request.POST
        po = PurchaseOrder.objects.for_user(request.user).filter(pk=p.get("po")).first() if p.get("po") else None
        rows = [{"item": value, "rate": p.getlist("rate")[i], "qty": p.getlist("qty")[i],
                 "rolls": p.getlist("rolls")[i], "po_line": p.getlist("po_line")[i]} for i, value in enumerate(p.getlist("item"))]
        specs = []
        try:
            vendor = vu.chosen(Party.objects.all(), p.get("vendor"), "supplier")
            for row in rows:
                if not row["item"]:
                    continue
                item = parse_item(row["item"])
                po_line = PurchaseOrderLine.objects.filter(pk=row["po_line"], po=po).first() if row["po_line"] and po else None
                spec = grn_service.GrnLineSpec(item=item, rate=_decimal(row["rate"], "Rate"), po_line=po_line)
                if isinstance(item, Material) and item.kind == "fabric":
                    spec.rolls = parse_rolls(row["rolls"])
                else:
                    spec.qty_received = _decimal(row["qty"], f"Quantity of {item}")
                specs.append(spec)
            location = get_object_or_404(Location, pk=p.get("location"))
            challan_date = _date(p.get("vendor_challan_date")) if p.get("vendor_challan_date") else None
            if grn is None:
                grn = grn_service.create_grn(
                    company=_company(), factory=po.factory if po else require_active_factory(request),
                    location=location, vendor=vendor, date=_date(p.get("date")), lines=specs, user=request.user, po=po,
                    vendor_challan_no=p.get("vendor_challan_no", ""), vendor_challan_date=challan_date, remarks=p.get("remarks", ""))
            else:
                grn_service.update_grn(grn, lines=specs, user=request.user, date=_date(p.get("date")), location=location,
                                       vendor=vendor, vendor_challan_no=p.get("vendor_challan_no", ""),
                                       vendor_challan_date=challan_date, remarks=p.get("remarks", ""))
        except (ValueError, BusinessRuleError) as exc:
            _msgs(request, exc)
            return render(request, "purchases/grn_form.html", self._ctx(request, grn, po, rows, p))
        messages.success(request, "Goods received saved. Now record the QC result for each line.")
        return redirect("grn_detail", pk=grn.pk)


class GrnDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.grn"

    def _grn(self, request, pk):
        return get_object_or_404(Grn.objects.for_user(request.user).select_related("vendor", "factory", "location", "po"), pk=pk)

    def get(self, request, pk):
        grn = self._grn(request, pk)
        lines = grn.lines.select_related("material", "sku__style", "sku__colour", "sku__size").prefetch_related("rolls")
        return render(request, "purchases/grn_detail.html", {
            "grn": grn, "lines": lines, "notes": grn.debit_notes.all(), "guide": guide_service.grn_guide(grn, request.user),
            "can_open_po": request.user.has_screen_perm("purchases.po", "view"),
            "can_open_note": request.user.has_screen_perm("purchases.debitnote", "view"),
            "can_edit": request.user.has_screen_perm("purchases.grn", "edit"),
            # recording QC, finishing it and posting are each this screen's `edit`; the POST below checks it
            "can_accept_all": request.user.has_screen_perm("purchases.grn", "edit") and grn_service.untouched(grn),
            "can_cancel": request.user.has_screen_perm("purchases.grn", "cancel")
            or request.user.has_screen_perm("purchases.grn", "edit"),
            "qc_choices": [("accepted", "Accepted"), ("rejected", "Rejected"), ("accepted_remark", "Accepted with remark")],
        })

    def post(self, request, pk):
        grn = self._grn(request, pk)
        p, action, user = request.POST, request.POST.get("action"), request.user
        # everything on this page needs `edit`; cancelling a posted GRN may also be done with `cancel` alone
        allowed = user.has_screen_perm("purchases.grn", "edit") or (
            action == "cancel" and user.has_screen_perm("purchases.grn", "cancel"))
        if not allowed:
            raise PermissionDenied
        try:
            rolls, lines = {}, {}
            if action in ("save_qc", "finish_qc", "accept_all"):
                for key, val in p.items():
                    if key.startswith("roll_status_"):
                        rid = key[len("roll_status_"):]
                        rolls[int(rid)] = (val, p.get(f"roll_remark_{rid}", ""))
                    elif key.startswith("rejected_"):
                        lid = key[len("rejected_"):]
                        lines[int(lid)] = (_decimal(val, "Rejected quantity", Decimal("0")), p.get(f"remark_{lid}", ""))
            if action in ("save_qc", "finish_qc"):
                grn_service.record_qc(grn, user=user, rolls=rolls, lines=lines)
                if action == "finish_qc":
                    grn_service.finish_qc(grn, user=user)
                    messages.success(request, "QC recorded. The GRN is ready to post.")
                else:
                    messages.success(request, "QC saved.")
            elif action == "accept_all":
                typed = (any(status not in ("", "pending") or remark.strip() for status, remark in rolls.values())
                         or any(rejected or remark.strip() for rejected, remark in lines.values()))
                if typed and grn.status == Grn.Status.DRAFT:
                    # the form came with a result on it: keep it exactly as Save QC would, and post nothing
                    grn_service.record_qc(grn, user=user, rolls=rolls, lines=lines)
                    raise BusinessRuleError("You entered a rejection or a remark. Press Finish QC to keep it, or clear it to "
                                            "accept everything. What you typed is saved.")
                grn = grn_service.accept_all_and_post(grn, user=user)
                messages.success(request, f"{grn.number} posted with everything accepted. Stock and books are updated.")
            elif action == "post":
                grn = grn_service.post_grn(grn, user=user)
                messages.success(request, f"{grn.number} posted. Stock and books are updated.")
            elif action == "cancel":
                grn_service.cancel_grn(grn, user=user, reason=p.get("reason", ""))
                messages.success(request, "GRN cancelled; stock and books reversed.")
        except (ValueError, BusinessRuleError) as exc:
            _msgs(request, exc)
        return redirect("grn_detail", pk=pk)


# ================================================================ purchase invoices

class InvoiceList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.invoice"

    def get(self, request):
        qs = in_active(PurchaseInvoice.objects.for_user(request.user), request).select_related("vendor", "factory")
        return render(request, "purchases/invoice_list.html", {
            "invoices": _with_next(qs[:200], guide_service.invoice_next, request.user), "can_create": request.user.has_screen_perm("purchases.invoice", "create"),
            "can_edit": request.user.has_screen_perm("purchases.invoice", "edit"),
        })


class InvoiceSave(LoginRequiredMixin, ScreenPermissionMixin, View):
    """New invoice, or edit a draft one (pk given). Posted invoices are cancelled, never edited."""

    screen_code = "purchases.invoice"

    def dispatch(self, request, *args, **kwargs):
        self.screen_action = "edit" if kwargs.get("pk") else "create"
        return super().dispatch(request, *args, **kwargs)

    def _inv(self, request, pk):
        qs = PurchaseInvoice.objects.for_user(request.user).select_related("vendor", "factory")
        return get_object_or_404(qs, pk=pk) if pk else None

    @staticmethod
    def _saved_values(inv):
        d = {"vendor": str(inv.vendor_id), "vendor_invoice_no": inv.vendor_invoice_no, "notes": inv.notes,
             "vendor_invoice_date": inv.vendor_invoice_date.isoformat(), "date": inv.date.isoformat(),
             "tax_mode": inv.tax_mode, "gst_template": str(inv.gst_template_id or ""),
             "tds_template": str(inv.tds_template_id or ""), "location": str(inv.location_id or "")}
        if inv.tax_mode == PurchaseInvoice.TaxMode.MANUAL:
            for t in inv.tax_lines.filter(kind="gst"):
                d[f"manual_{t.component}"] = str(t.amount)
        return d

    def _ctx(self, request, d=None, inv=None, posted=False):
        if inv is not None and not posted:
            d = self._saved_values(inv)
        d = d or {}
        vendor = inv.vendor if inv else (
            Party.objects.filter(pk=d.get("vendor"), is_vendor=True).first() if d.get("vendor") else None)
        factory = inv.factory if inv else request.factory
        direct = inv.is_direct if inv else (d.get("mode") == "direct")
        existing = {l.grn_line_id: l for l in inv.lines.all()} if inv else {}
        # opened from a goods receipt's Next button: its lines are ticked, the supplier's other receipts are listed unticked
        only = "" if (posted or inv) else d.get("grn", "")
        grn_lines, rows, locations = [], [], []
        mats, skus = item_choices() if direct else ([], [])
        if direct and factory:
            locations = Location.objects.filter(factory=factory, is_active=True).exclude(
                loc_type__in=("cutting", "process", "fabricator", "rejects", "transit"))
            if posted:
                items, qtys, rates = d.getlist("item"), d.getlist("qty"), d.getlist("rate")
                rows = [{"item": v, "qty": qtys[i], "rate": rates[i]} for i, v in enumerate(items) if v or qtys[i] or rates[i]]
            elif inv:
                rows = [{"item": f"m:{l.material_id}" if l.material_id else f"s:{l.sku_id}", "qty": l.qty, "rate": l.rate}
                        for l in inv.lines.all()]
            rows += [{}, {}]
        held = {}
        if vendor and factory and not direct:
            # quantity sitting on another draft bill is left out of the list (posting the second draft would fail);
            # the form says which draft holds it. Posting itself is unchanged and still checks what is left.
            on_drafts, holders = {}, {}
            drafts = PurchaseInvoiceLine.objects.filter(
                invoice__status="draft", grn_line__grn__vendor=vendor, grn_line__grn__factory=factory).select_related("invoice")
            for dl in (drafts.exclude(invoice=inv) if inv else drafts).order_by("invoice_id", "id"):
                on_drafts[dl.grn_line_id] = on_drafts.get(dl.grn_line_id, Decimal("0")) + dl.qty
                holders.setdefault(dl.grn_line_id, dl.invoice)
            for gl in GrnLine.objects.filter(grn__status="posted", grn__vendor=vendor, grn__factory=factory).select_related(
                    "grn", "material", "sku__style", "sku__colour", "sku__size").order_by("grn__date", "id"):
                left = invoices.billable_qty(gl, exclude=inv)
                if left > 0 and gl.pk in on_drafts:
                    holder = holders[gl.pk]
                    held.setdefault(holder.pk, {"bill": holder, "count": 0})["count"] += 1
                    left -= on_drafts[gl.pk]
                if left <= 0:
                    continue
                row = {"gl": gl, "left": left, "last": invoices.last_rate(vendor, gl, exclude=inv),
                       "use": not only.isdigit() or str(gl.grn_id) == only, "qty": left, "rate": gl.rate}
                if posted:
                    row.update(use=f"use_{gl.pk}" in d, qty=d.get(f"qty_{gl.pk}", left), rate=d.get(f"rate_{gl.pk}", gl.rate))
                elif inv:
                    line = existing.get(gl.pk)
                    row["use"] = line is not None
                    if line:
                        row.update(qty=line.qty, rate=line.rate)
                grn_lines.append(row)
        itc = (d.get("itc_claimable") == "on") if posted else (inv.itc_claimable if inv else True)
        tax_mode, today = d.get("tax_mode") or PurchaseInvoice.TaxMode.NONE, timezone.localdate().isoformat()
        return {
            "vendors": _vendors(), "vendor": vendor, "factory": factory, "inv": inv, "itc": itc, "tax_mode": tax_mode,
            # the tax section opens once a GST choice needs its details, or TDS is chosen; the booking date is today unless changed
            "tax_open": forms_ui.more_open({"tax_mode": tax_mode, "tds_template": d.get("tds_template")},
                                           {"tax_mode": PurchaseInvoice.TaxMode.NONE, "tds_template": ""}),
            "more_is_open": forms_ui.more_open({"date": d.get("date") or today, "notes": d.get("notes")}, {"date": today, "notes": ""}),
            "grn_lines": grn_lines, "d": d, "direct": direct, "mats": mats, "skus": skus, "rows": rows,
            "locations": locations, "held": list(held.values()),
            "gst_templates": TaxTemplate.objects.filter(kind="gst", is_active=True),
            "tds_templates": TaxTemplate.objects.filter(kind="tds", is_active=True),
            "modes": PurchaseInvoice.TaxMode.choices,
        }

    def _draft_or_back(self, request, pk):
        inv = self._inv(request, pk)
        if inv is not None and inv.status != "draft":
            messages.error(request, "Only a draft supplier bill can be edited; cancel a posted one instead.")
            return inv, redirect("invoice_detail", pk=inv.pk)
        return inv, None

    def _other_factory(self, request):
        """Opened from a goods receipt's Next button while another factory (or all of them) is active: the bill would be
        for the active factory, where these goods are not. Send the user back to the goods receipt to switch first.
        The `factory` in the link never chooses the bill's factory; the top bar does."""
        wanted, came_from, user = request.GET.get("factory", ""), request.GET.get("grn", ""), request.user
        if not (wanted.isdigit() and came_from.isdigit()) or (request.factory is not None and str(request.factory.pk) == wanted):
            return None
        if not user.has_screen_perm("purchases.grn", "view"):
            return None
        grn = Grn.objects.for_user(user).select_related("factory").filter(pk=came_from, factory_id=wanted).first()
        if grn is None:
            return None
        messages.error(request, f"These goods were received in {grn.factory.name}. Choose it in the top bar, then press the button again.")
        return redirect("grn_detail", pk=grn.pk)

    def get(self, request, pk=None):
        inv, back = self._draft_or_back(request, pk)
        if back:
            return back
        if inv is None:
            if back := self._other_factory(request) or _need_factory(request, "invoice_list"):
                return back
            return render(request, "purchases/invoice_form.html", self._ctx(request, request.GET))
        return render(request, "purchases/invoice_form.html", self._ctx(request, inv=inv))

    def post(self, request, pk=None):
        inv, back = self._draft_or_back(request, pk)
        if back:
            return back
        p = request.POST
        try:
            vendor = inv.vendor if inv else get_object_or_404(Party, pk=p.get("vendor"), is_vendor=True)
            factory = inv.factory if inv else require_active_factory(request)
            specs, location = [], None
            direct = inv.is_direct if inv else p.get("mode") == "direct"
            if direct:
                location = get_object_or_404(Location, pk=p.get("location"), factory=factory) if p.get("location") else None
                if location is None:
                    raise ValueError("Choose where the goods are received.")
                qtys, rates = p.getlist("qty"), p.getlist("rate")
                for i, value in enumerate(p.getlist("item")):
                    if not value:
                        continue
                    item = parse_item(value)
                    specs.append(invoices.InvoiceLineSpec(None, _decimal(qtys[i], f"Quantity of {item}"),
                                                          _decimal(rates[i], f"Rate of {item}"), item=item))
            for key in ([] if direct else p):
                if key.startswith("use_"):
                    gid = key[4:]
                    gl = get_object_or_404(GrnLine, pk=gid)
                    specs.append(invoices.InvoiceLineSpec(gl, _decimal(p.get(f"qty_{gid}"), "Quantity"), _decimal(p.get(f"rate_{gid}"), "Rate")))
            manual = []
            for comp in ("cgst", "sgst", "igst"):
                if p.get(f"manual_{comp}", "").strip():
                    manual.append((comp, _decimal(p[f"manual_{comp}"], comp.upper())))
            gst_t = TaxTemplate.objects.filter(pk=p.get("gst_template"), kind="gst").first() if p.get("gst_template") else None
            tds_t = TaxTemplate.objects.filter(pk=p.get("tds_template"), kind="tds").first() if p.get("tds_template") else None
            saved = invoices.save_invoice(
                company=_company(), factory=factory, vendor=vendor, vendor_invoice_no=p.get("vendor_invoice_no", ""),
                vendor_invoice_date=_date(p.get("vendor_invoice_date")), date=_date(p.get("date")), lines=specs,
                user=request.user, invoice=inv, tax_mode=p.get("tax_mode", "none"), gst_template=gst_t, tds_template=tds_t,
                itc_claimable=p.get("itc_claimable") == "on", manual_tax=manual, notes=p.get("notes", ""),
                location=location)
        except (ValueError, BusinessRuleError) as exc:
            _msgs(request, exc)
            return render(request, "purchases/invoice_form.html", self._ctx(request, p, inv, posted=True))
        messages.success(request, "Supplier bill saved as a draft. Check the figures, then post it.")
        return redirect("invoice_detail", pk=saved.pk)


class InvoiceDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.invoice"

    def _inv(self, request, pk):
        return get_object_or_404(PurchaseInvoice.objects.for_user(request.user).select_related("vendor", "factory", "gst_template", "tds_template", "voucher"), pk=pk)

    def get(self, request, pk):
        inv = self._inv(request, pk)
        memo = {}
        guide = guide_service.invoice_guide(inv, request.user, memo)
        owed = guide_service.owed(inv, request.user, memo)
        settle = settlement(request.user, ledger=inv.vendor.payable_ledger, reference=inv.vendor_invoice_no, direction="pay",
                            narration=f"Paid against {inv.vendor_invoice_no}") if inv.status == "posted" and inv.vendor.payable_ledger_id else None
        if settle:
            # the pill shows what the ledger holds open on the bill; the button is the guide's step, with its amount
            settle["url"] = next((a["url"] for a in [guide["primary"], *guide["others"]] if a and a["kind"] == "pay"), None)
        return render(request, "purchases/invoice_detail.html", {
            "inv": inv, "guide": guide, "owed": owed if owed.less else None, "lines": inv.lines.select_related("grn_line__grn", "grn_line__material", "grn_line__sku__style", "grn_line__sku__colour", "grn_line__sku__size", "material", "sku__style", "sku__colour", "sku__size"),
            "gst": inv.tax_lines.filter(kind="gst"), "tds": inv.tax_lines.filter(kind="tds"),
            "can_edit": request.user.has_screen_perm("purchases.invoice", "edit"),
            "can_cancel": request.user.has_screen_perm("purchases.invoice", "cancel"),
            "settle": settle,
        })

    def post(self, request, pk):
        inv = self._inv(request, pk)
        p, action, user = request.POST, request.POST.get("action"), request.user
        try:
            if action == "cancel":
                if not user.has_screen_perm("purchases.invoice", "cancel"):
                    raise PermissionDenied
                invoices.cancel_invoice(inv, user=user, reason=p.get("reason", ""))
                messages.success(request, "Invoice cancelled; books and stock value reversed.")
            else:
                if not user.has_screen_perm("purchases.invoice", "edit"):
                    raise PermissionDenied
                if action == "post":
                    inv = invoices.post_invoice(inv, user=user)
                    messages.success(request, f"{inv.number} posted.")
                elif action == "discard":
                    if inv.status != "draft":
                        raise BusinessRuleError("Only a draft can be discarded.")
                    inv.delete()
                    messages.success(request, "Draft discarded.")
                    return redirect("invoice_list")
                elif action == "overrides":
                    overrides = {}
                    for tl in inv.tax_lines.all():
                        amount, reason = p.get(f"amount_{tl.pk}", "").strip(), p.get(f"reason_{tl.pk}", "")
                        if amount and _decimal(amount, "Amount") != tl.amount:
                            overrides[tl.component] = (_decimal(amount, "Amount"), reason)
                    manual = [(t.component, t.amount) for t in inv.tax_lines.filter(kind="gst")] if inv.tax_mode == "manual" else None
                    invoices.save_invoice(
                        company=inv.company, factory=inv.factory, vendor=inv.vendor, vendor_invoice_no=inv.vendor_invoice_no,
                        vendor_invoice_date=inv.vendor_invoice_date, date=inv.date, user=user, invoice=inv,
                        lines=[invoices.InvoiceLineSpec(l.grn_line, l.qty, l.rate, item=None if l.grn_line_id else l.item)
                               for l in inv.lines.all()], location=inv.location,
                        tax_mode=inv.tax_mode, gst_template=inv.gst_template, itc_claimable=inv.itc_claimable,
                        tds_template=inv.tds_template, tax_overrides=overrides, manual_tax=manual, notes=inv.notes)
                    messages.success(request, "Tax amounts updated.")
        except (ValueError, BusinessRuleError) as exc:
            _msgs(request, exc)
        return redirect("invoice_detail", pk=pk)


# ================================================================ debit notes

class DebitNoteList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.debitnote"

    def get(self, request):
        qs = in_active(DebitNote.objects.for_user(request.user), request).select_related("vendor", "factory")
        return render(request, "purchases/debitnote_list.html", {
            "notes": qs[:200], "can_create": request.user.has_screen_perm("purchases.debitnote", "create"),
            "can_edit": request.user.has_screen_perm("purchases.debitnote", "edit"),
        })


class DebitNoteSave(LoginRequiredMixin, ScreenPermissionMixin, View):
    """New return note, or edit a draft one (pk given)."""

    screen_code = "purchases.debitnote"

    def dispatch(self, request, *args, **kwargs):
        self.screen_action = "edit" if kwargs.get("pk") else "create"
        return super().dispatch(request, *args, **kwargs)

    def _note(self, request, pk):
        qs = DebitNote.objects.for_user(request.user).select_related("factory")
        return get_object_or_404(qs, pk=pk) if pk else None

    @staticmethod
    def _saved(note):
        d = {"vendor": str(note.vendor_id), "date": note.date.isoformat(), "reason": note.reason,
             "gst_template": str(note.gst_template_id or "")}
        rows = [{"item": f"m:{l.material_id}" if l.material_id else f"s:{l.sku_id}", "location": str(l.location_id or ""),
                 "roll": str(l.roll_id or ""), "qty": l.qty.normalize(), "rate": l.rate.normalize()}
                for l in note.lines.all()]
        return d, rows

    def _ctx(self, request, rows=None, d=None, note=None, posted=False):
        from inventory.models import RollBalance

        if note is not None and not posted:
            d, rows = self._saved(note)
        factory = note.factory if note else request.factory
        mats, skus = item_choices()
        itc = (d.get("itc_claimable") == "on") if posted else (note.itc_claimable if note else True)
        return {
            "vendors": _vendors(), "factory": factory, "mats": mats, "skus": skus, "note": note, "itc": itc,
            "tax_open": forms_ui.more_open({"gst_template": (d or {}).get("gst_template"), "itc_claimable": itc},
                                           {"gst_template": "", "itc_claimable": True}),
            "locations": Location.objects.filter(factory=factory, is_active=True).exclude(loc_type="transit"),
            "rolls": RollBalance.objects.for_user(request.user).filter(qty__gt=0).select_related("roll__material", "location"),
            "gst_templates": TaxTemplate.objects.filter(kind="gst", is_active=True, is_reverse_charge=False),
            "rows": (rows or [{}, {}, {}]) + ([{}] if note else []), "d": d or {},
        }

    def _editable_or_back(self, request, pk):
        note = self._note(request, pk)
        if note is not None and (note.status != "draft" or note.kind != DebitNote.Kind.RETURN):
            messages.error(request, "Only a draft return note can be edited; cancel a posted one instead.")
            return note, redirect("debitnote_detail", pk=note.pk)
        return note, None

    def get(self, request, pk=None):
        note, back = self._editable_or_back(request, pk)
        if back:
            return back
        if note is None and (back := _need_factory(request, "debitnote_list")):
            return back
        return render(request, "purchases/debitnote_form.html", self._ctx(request, note=note))

    def post(self, request, pk=None):
        from inventory.models import FabricRoll

        note, back = self._editable_or_back(request, pk)
        if back:
            return back
        p = request.POST
        rows = [{k: p.getlist(k)[i] for k in ("item", "location", "roll", "qty", "rate")} for i in range(len(p.getlist("item")))]
        specs = []
        try:
            vendor = vu.chosen(Party.objects.filter(is_vendor=True), p.get("vendor"), "supplier")
            for row in rows:
                if not row["item"]:
                    continue
                specs.append(debit_notes.ReturnLineSpec(
                    item=parse_item(row["item"]), qty=_decimal(row["qty"], "Quantity"), rate=_decimal(row["rate"], "Rate"),
                    location=get_object_or_404(Location, pk=row["location"]),
                    roll=get_object_or_404(FabricRoll, pk=row["roll"]) if row["roll"] else None))
            fields = dict(
                vendor=vendor, date=_date(p.get("date")),
                lines=specs, user=request.user, reason=p.get("reason", ""),
                gst_template=TaxTemplate.objects.filter(pk=p["gst_template"]).first() if p.get("gst_template") else None,
                itc_claimable=p.get("itc_claimable") == "on")
            if note is None:
                note = debit_notes.create_return_note(company=_company(), factory=require_active_factory(request), **fields)
            else:
                note = debit_notes.update_return_note(note, **fields)
        except (ValueError, BusinessRuleError) as exc:
            _msgs(request, exc)
            return render(request, "purchases/debitnote_form.html", self._ctx(request, rows, p, note, posted=True))
        messages.success(request, "Return note saved as a draft.")
        return redirect("debitnote_detail", pk=note.pk)


class DebitNoteDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.debitnote"

    def _note(self, request, pk):
        return get_object_or_404(DebitNote.objects.for_user(request.user).select_related("vendor", "factory", "grn", "gst_template"), pk=pk)

    def get(self, request, pk):
        note = self._note(request, pk)
        guide = guide_service.debitnote_guide(note, request.user)
        return render(request, "purchases/debitnote_detail.html", {
            "note": note, "guide": guide, "can_post": guide["primary"] is not None,
            "can_open_grn": request.user.has_screen_perm("purchases.grn", "view"), "lines": note.lines.select_related("material", "sku__style", "sku__colour", "sku__size", "roll", "location"),
            "can_edit": request.user.has_screen_perm("purchases.debitnote", "edit"),
            "can_cancel": request.user.has_screen_perm("purchases.debitnote", "cancel"),
        })

    def post(self, request, pk):
        note = self._note(request, pk)
        action, user = request.POST.get("action"), request.user
        try:
            if action == "post":
                if not user.has_screen_perm("purchases.debitnote", "edit"):
                    raise PermissionDenied
                note = debit_notes.post_debit_note(note, user=user)
                messages.success(request, f"{note.number} posted.")
            elif action == "cancel":
                if not user.has_screen_perm("purchases.debitnote", "cancel"):
                    raise PermissionDenied
                debit_notes.cancel_debit_note(note, user=user, reason=request.POST.get("reason", ""))
                messages.success(request, "Debit note cancelled.")
        except BusinessRuleError as exc:
            messages.error(request, str(exc))
        return redirect("debitnote_detail", pk=pk)


# ================================================================ delete (drafts only)

from core.crud import ObjectDelete  # noqa: E402


class _DraftDelete(ObjectDelete):
    """Drafts can be deleted. Anything posted is cancelled instead (rule 1), and is never offered here."""

    model = None
    draft_states = ("draft",)
    cancel_hint = "Posted documents are cancelled, not deleted."

    def get_object(self, request, pk):
        return get_object_or_404(self.model.objects.for_user(request.user), pk=pk)

    def blocked_reason(self, obj):
        if obj.status not in self.draft_states:
            return f"This {self.noun} is {obj.get_status_display().lower()} and cannot be deleted. {self.cancel_hint}"
        return None


class PODelete(_DraftDelete):
    screen_code, success_url_name, noun, model = "purchases.po", "po_list", "purchase order", PurchaseOrder
    cancel_hint = "Short-close an approved purchase order instead."


class GrnDelete(_DraftDelete):
    screen_code, success_url_name, noun, model = "purchases.grn", "grn_list", "GRN", Grn
    draft_states = ("draft", "qc_done")
    cancel_hint = "Cancel a posted GRN instead; that reverses its stock and books."


class InvoiceDelete(_DraftDelete):
    screen_code, success_url_name, noun, model = "purchases.invoice", "invoice_list", "purchase invoice", PurchaseInvoice
    cancel_hint = "Cancel a posted invoice instead; that reverses its books."


class DebitNoteDelete(_DraftDelete):
    screen_code, success_url_name, noun, model = "purchases.debitnote", "debitnote_list", "debit note", DebitNote
    cancel_hint = "Cancel a posted debit note instead."

    def blocked_reason(self, obj):
        if obj.kind != DebitNote.Kind.RETURN:
            return "This note was raised automatically from a GRN rejection, so it cannot be deleted. Cancel it from its page if it is not needed."
        return super().blocked_reason(obj)
