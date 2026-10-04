from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from core.exceptions import BusinessRuleError
from core.models import Company, Location
from core.scoping import ScreenPermissionMixin
from core.services.active_factory import in_active, require_active_factory
from inventory.views import item_choices, parse_item
from masters.models import Material, Party
from tax.models import TaxTemplate

from .models import DebitNote, Grn, GrnLine, PurchaseInvoice, PurchaseInvoiceLine, PurchaseOrder, PurchaseOrderLine
from .services import debit_notes, grn as grn_service, invoices, orders


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
        qs = in_active(PurchaseOrder.objects.for_user(request.user), request).select_related("vendor", "factory")
        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return render(request, "purchases/po_list.html", {
            "pos": qs[:200], "status": status, "statuses": PurchaseOrder.Status.choices,
            "can_create": request.user.has_screen_perm("purchases.po", "create"),
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
                "vals": form_values(po, d, ("vendor", "date", "expected_date", "remarks"))}

    def get(self, request, pk=None):
        po = get_object_or_404(PurchaseOrder.objects.for_user(request.user), pk=pk) if pk else None
        if po is None and (back := _need_factory(request, "po_list")):
            return back
        return render(request, "purchases/po_form.html", self._ctx(request, po))

    def post(self, request, pk=None):
        po = get_object_or_404(PurchaseOrder.objects.for_user(request.user), pk=pk) if pk else None
        p = request.POST
        rows, specs = [], []
        try:
            for i, value in enumerate(p.getlist("item")):
                row = {"item": value, "qty": p.getlist("qty")[i], "rate": p.getlist("rate")[i]}
                rows.append(row)
                if value:
                    specs.append(orders.POLineSpec(parse_item(value), _decimal(row["qty"], "Quantity"), _decimal(row["rate"], "Rate")))
            vendor = get_object_or_404(Party, pk=p.get("vendor"))
            expected = _date(p.get("expected_date"), default=None) if p.get("expected_date") else None
            if po is None:
                po = orders.create_po(
                    company=_company(), factory=require_active_factory(request),
                    vendor=vendor, date=_date(p.get("date")), lines=specs, user=request.user,
                    expected_date=expected, remarks=p.get("remarks", ""))
            else:
                orders.update_po(po, lines=specs, user=request.user, vendor=vendor, date=_date(p.get("date")),
                                 expected_date=expected, remarks=p.get("remarks", ""))
        except (ValueError, BusinessRuleError) as exc:
            _msgs(request, exc)
            return render(request, "purchases/po_form.html", self._ctx(request, po, rows, p))
        messages.success(request, "Purchase order saved as a draft.")
        return redirect("po_detail", pk=po.pk)


class PODetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.po"

    def _po(self, request, pk):
        return get_object_or_404(PurchaseOrder.objects.for_user(request.user).select_related("vendor", "factory", "approved_by", "company"), pk=pk)

    def get(self, request, pk):
        po = self._po(request, pk)
        lines = [{"line": l, "received": orders.received_qty(l), "pending": orders.pending_qty(l)} for l in po.lines.select_related("material", "sku__style", "sku__colour", "sku__size")]
        user = request.user
        return render(request, "purchases/po_detail.html", {
            "po": po, "lines": lines, "grns": po.grns.all(),
            "can_edit": user.has_screen_perm("purchases.po", "edit"),
            "can_approve": user.has_screen_perm("purchases.po", "approve"),
            "can_grn": user.has_screen_perm("purchases.grn", "create"),
            "limit": po.company.po_approval_limit,
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
            "grns": qs[:200], "can_create": request.user.has_screen_perm("purchases.grn", "create"),
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
        rows, specs = [], []
        try:
            for i, value in enumerate(p.getlist("item")):
                row = {"item": value, "rate": p.getlist("rate")[i], "qty": p.getlist("qty")[i],
                       "rolls": p.getlist("rolls")[i], "po_line": p.getlist("po_line")[i]}
                rows.append(row)
                if not value:
                    continue
                item = parse_item(value)
                po_line = PurchaseOrderLine.objects.filter(pk=row["po_line"], po=po).first() if row["po_line"] and po else None
                spec = grn_service.GrnLineSpec(item=item, rate=_decimal(row["rate"], "Rate"), po_line=po_line)
                if isinstance(item, Material) and item.kind == "fabric":
                    spec.rolls = parse_rolls(row["rolls"])
                else:
                    spec.qty_received = _decimal(row["qty"], f"Quantity of {item}")
                specs.append(spec)
            vendor = get_object_or_404(Party, pk=p.get("vendor"))
            location = get_object_or_404(Location, pk=p.get("location"))
            challan_date = _date(p.get("vendor_challan_date")) if p.get("vendor_challan_date") else None
            if grn is None:
                grn = grn_service.create_grn(
                    company=_company(), factory=po.factory if po else require_active_factory(request),
                    location=location, vendor=vendor, date=_date(p.get("date")), lines=specs, user=request.user, po=po,
                    vendor_challan_no=p.get("vendor_challan_no", ""), vendor_challan_date=challan_date, remarks=p.get("remarks", ""))
            else:
                grn_service.update_grn(grn, lines=specs, user=request.user, date=_date(p.get("date")), location=location,
                                       vendor_challan_no=p.get("vendor_challan_no", ""), remarks=p.get("remarks", ""))
        except (ValueError, BusinessRuleError) as exc:
            _msgs(request, exc)
            return render(request, "purchases/grn_form.html", self._ctx(request, grn, po, rows, p))
        messages.success(request, "GRN saved. Now record the QC result for each line.")
        return redirect("grn_detail", pk=grn.pk)


class GrnDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.grn"

    def _grn(self, request, pk):
        return get_object_or_404(Grn.objects.for_user(request.user).select_related("vendor", "factory", "location", "po"), pk=pk)

    def get(self, request, pk):
        grn = self._grn(request, pk)
        lines = grn.lines.select_related("material", "sku__style", "sku__colour", "sku__size").prefetch_related("rolls")
        return render(request, "purchases/grn_detail.html", {
            "grn": grn, "lines": lines, "notes": grn.debit_notes.all(),
            "can_edit": request.user.has_screen_perm("purchases.grn", "edit"),
            "can_cancel": request.user.has_screen_perm("purchases.grn", "cancel") or request.user.has_screen_perm("purchases.grn", "edit"),
            "qc_choices": [("accepted", "Accepted"), ("rejected", "Rejected"), ("accepted_remark", "Accepted with remark")],
        })

    def post(self, request, pk):
        grn = self._grn(request, pk)
        if not request.user.has_screen_perm("purchases.grn", "edit"):
            raise PermissionDenied
        p, action, user = request.POST, request.POST.get("action"), request.user
        try:
            if action in ("save_qc", "finish_qc"):
                rolls, lines = {}, {}
                for key, val in p.items():
                    if key.startswith("roll_status_"):
                        rid = key[len("roll_status_"):]
                        rolls[int(rid)] = (val, p.get(f"roll_remark_{rid}", ""))
                    elif key.startswith("rejected_"):
                        lid = key[len("rejected_"):]
                        lines[int(lid)] = (_decimal(val, "Rejected quantity", Decimal("0")), p.get(f"remark_{lid}", ""))
                grn_service.record_qc(grn, user=user, rolls=rolls, lines=lines)
                if action == "finish_qc":
                    grn_service.finish_qc(grn, user=user)
                    messages.success(request, "QC recorded. The GRN is ready to post.")
                else:
                    messages.success(request, "QC saved.")
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
            "invoices": qs[:200], "can_create": request.user.has_screen_perm("purchases.invoice", "create"),
        })


class InvoiceNew(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.invoice"
    screen_action = "create"

    def _ctx(self, request, d=None):
        d = d or {}
        vendor = Party.objects.filter(pk=d.get("vendor"), is_vendor=True).first() if d.get("vendor") else None
        factory = request.factory
        grn_lines = []
        if vendor and factory:
            for gl in GrnLine.objects.filter(grn__status="posted", grn__vendor=vendor, grn__factory=factory).select_related(
                    "grn", "material", "sku__style", "sku__colour", "sku__size").order_by("grn__date", "id"):
                left = invoices.billable_qty(gl)
                if left > 0:
                    grn_lines.append({"gl": gl, "left": left, "last": invoices.last_rate(vendor, gl)})
        return {
            "vendors": _vendors(), "vendor": vendor, "factory": factory,
            "grn_lines": grn_lines, "d": d,
            "gst_templates": TaxTemplate.objects.filter(kind="gst", is_active=True),
            "tds_templates": TaxTemplate.objects.filter(kind="tds", is_active=True),
            "modes": PurchaseInvoice.TaxMode.choices,
        }

    def get(self, request):
        if back := _need_factory(request, "invoice_list"):
            return back
        return render(request, "purchases/invoice_form.html", self._ctx(request, request.GET))

    def post(self, request):
        p = request.POST
        try:
            vendor = get_object_or_404(Party, pk=p.get("vendor"), is_vendor=True)
            factory = require_active_factory(request)
            specs = []
            for key in p:
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
            inv = invoices.save_invoice(
                company=_company(), factory=factory, vendor=vendor, vendor_invoice_no=p.get("vendor_invoice_no", ""),
                vendor_invoice_date=_date(p.get("vendor_invoice_date")), date=_date(p.get("date")), lines=specs,
                user=request.user, tax_mode=p.get("tax_mode", "none"), gst_template=gst_t, tds_template=tds_t,
                itc_claimable=p.get("itc_claimable") == "on", manual_tax=manual, notes=p.get("notes", ""))
        except (ValueError, BusinessRuleError) as exc:
            _msgs(request, exc)
            return render(request, "purchases/invoice_form.html", self._ctx(request, p))
        messages.success(request, "Invoice saved as a draft. Check the figures, then post it.")
        return redirect("invoice_detail", pk=inv.pk)


class InvoiceDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.invoice"

    def _inv(self, request, pk):
        return get_object_or_404(PurchaseInvoice.objects.for_user(request.user).select_related("vendor", "factory", "gst_template", "tds_template", "voucher"), pk=pk)

    def get(self, request, pk):
        inv = self._inv(request, pk)
        return render(request, "purchases/invoice_detail.html", {
            "inv": inv, "lines": inv.lines.select_related("grn_line__grn", "grn_line__material", "grn_line__sku__style", "grn_line__sku__colour", "grn_line__sku__size"),
            "gst": inv.tax_lines.filter(kind="gst"), "tds": inv.tax_lines.filter(kind="tds"),
            "can_edit": request.user.has_screen_perm("purchases.invoice", "edit"),
            "can_cancel": request.user.has_screen_perm("purchases.invoice", "cancel"),
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
                        lines=[invoices.InvoiceLineSpec(l.grn_line, l.qty, l.rate) for l in inv.lines.all()],
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
        })


class DebitNoteNew(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.debitnote"
    screen_action = "create"

    def _ctx(self, request, rows=None, d=None):
        from inventory.models import RollBalance

        mats, skus = item_choices()
        return {
            "vendors": _vendors(), "factory": request.factory, "mats": mats, "skus": skus,
            "locations": Location.objects.filter(factory=request.factory, is_active=True).exclude(loc_type="transit"),
            "rolls": RollBalance.objects.for_user(request.user).filter(qty__gt=0).select_related("roll__material", "location"),
            "gst_templates": TaxTemplate.objects.filter(kind="gst", is_active=True, is_reverse_charge=False),
            "rows": rows or [{}, {}, {}], "d": d or {},
        }

    def get(self, request):
        if back := _need_factory(request, "debitnote_list"):
            return back
        return render(request, "purchases/debitnote_form.html", self._ctx(request))

    def post(self, request):
        from inventory.models import FabricRoll

        p = request.POST
        rows, specs = [], []
        try:
            for i, value in enumerate(p.getlist("item")):
                row = {k: p.getlist(k)[i] for k in ("item", "location", "roll", "qty", "rate")}
                rows.append(row)
                if not value:
                    continue
                specs.append(debit_notes.ReturnLineSpec(
                    item=parse_item(value), qty=_decimal(row["qty"], "Quantity"), rate=_decimal(row["rate"], "Rate"),
                    location=get_object_or_404(Location, pk=row["location"]),
                    roll=get_object_or_404(FabricRoll, pk=row["roll"]) if row["roll"] else None))
            note = debit_notes.create_return_note(
                company=_company(), factory=require_active_factory(request),
                vendor=get_object_or_404(Party, pk=p.get("vendor"), is_vendor=True), date=_date(p.get("date")),
                lines=specs, user=request.user, reason=p.get("reason", ""),
                gst_template=TaxTemplate.objects.filter(pk=p["gst_template"]).first() if p.get("gst_template") else None,
                itc_claimable=p.get("itc_claimable") == "on")
        except (ValueError, BusinessRuleError) as exc:
            _msgs(request, exc)
            return render(request, "purchases/debitnote_form.html", self._ctx(request, rows, p))
        messages.success(request, "Return note saved as a draft.")
        return redirect("debitnote_detail", pk=note.pk)


class DebitNoteDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "purchases.debitnote"

    def _note(self, request, pk):
        return get_object_or_404(DebitNote.objects.for_user(request.user).select_related("vendor", "factory", "grn", "gst_template"), pk=pk)

    def get(self, request, pk):
        note = self._note(request, pk)
        return render(request, "purchases/debitnote_detail.html", {
            "note": note, "lines": note.lines.select_related("material", "sku__style", "sku__colour", "sku__size", "roll", "location"),
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
