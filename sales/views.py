"""Sales screens: orders with the size-colour grid, packing and cartons, barcode billing, invoices, credit notes (E4)."""
import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from core import viewutils as vu
from core.exceptions import BusinessRuleError
from core.models import Location
from core.scoping import ScreenPermissionMixin
from core.services.active_factory import in_active, require_active_factory
from core.viewutils import company as _company, day as _day, dec as _dec, report as _msgs
from inventory import barcode
from inventory.views import LAYOUTS
from masters.models import SKU, Party, Style
from tax.models import TaxTemplate

from .models import (
    Carton, PackingList, SaleCreditNote, SaleInvoice, SaleOrder, SaleSetting, SaleInvoiceLine,
)
from .services import credit_notes, einvoice, guide as guide_service, invoices, orders, packing as packing_service, pricing
from .services.common import settings_for
from ledger.settlement import settlement

ERRORS = (ValueError, BusinessRuleError)


def _pk(value):
    """A posted id as a number, or None when it is blank or not a number (a blank select posts an empty string)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _choose(qs, value, what):
    obj = qs.filter(pk=_pk(value)).first() if _pk(value) is not None else None
    if obj is None:
        raise BusinessRuleError(f"Choose a {what}.")
    return obj


def _need_factory(request, to):
    """New documents are entered in one factory. In "All factories" mode say so and go back to the list."""
    if request.factory is None:
        messages.error(request, "Choose a single factory in the top bar before entering a document.")
        return redirect(to)
    return None


def _customers():
    return Party.objects.filter(is_customer=True, is_active=True)


def _locations(factory):
    return Location.objects.filter(factory=factory, is_active=True).exclude(
        loc_type__in=packing_service.NOT_PACKED_FROM) if factory else Location.objects.none()


def _can(request, screen, action):
    return request.user.has_screen_perm(screen, action)


def _need(request, screen, action):
    if not _can(request, screen, action):
        raise PermissionDenied


def _with_next(rows, next_step, user):
    """The rows shown on a list, each with its next step. One memo serves the page: every permission and every
    customer's open bills are asked once."""
    rows, memo = list(rows), {}
    for row in rows:
        row.next = next_step(row, user, memo)
    return rows


def _orders_with_next(rows, user):
    """Sale orders for a list: the next step, or what a made-to-order order waits for from production."""
    rows, memo = list(rows), {}
    for row in rows:
        guide = guide_service.order_guide(row, user, memo)
        row.next, row.waits_for = guide["primary"], guide["waiting"] if guide["blocked"] else ""
    return rows


# ================================================================ settings

class SalesSettings(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "sales.settings"

    def get(self, request):
        return render(request, "sales/settings.html", {"s": settings_for(_company()), "rounding": SaleSetting.Rounding.choices,
                                                      "can_edit": _can(request, "sales.settings", "edit")})

    def post(self, request):
        _need(request, "sales.settings", "edit")
        s = settings_for(_company())
        p = request.POST
        try:
            rounding = p.get("rounding")
            if rounding not in dict(SaleSetting.Rounding.choices):
                raise ValueError("Choose how the invoice total is rounded.")
            limit = _dec(p.get("max_discount_pct"), "Discount limit")
            if not 0 <= limit <= 100:
                raise ValueError("The discount limit must be between 0 and 100.")
            threshold = _dec(p.get("eway_threshold"), "E-way bill limit")
            if threshold < 0:
                raise ValueError("The e-way bill limit cannot be negative.")
        except ValueError as exc:
            _msgs(request, exc)
            return redirect("sales_settings")
        s.rounding, s.max_discount_pct, s.eway_threshold = rounding, limit, threshold
        s.einvoice_enabled = p.get("einvoice_enabled") == "on"
        s.save()
        messages.success(request, "Sales settings saved.")
        return redirect("sales_settings")


# ================================================================ sale orders (E4.1)

def grid_context(style, *, customer=None, on_date=None, cells=None, rate=None, disc=None):
    """Colours as rows, the style's sizes as columns (E4.1). `cells` is {(colour_id, size_id): qty text}."""
    colours = [sc.colour for sc in style.style_colours.select_related("colour").order_by("colour__name")]
    sizes = [ss.size for ss in style.style_sizes.select_related("size").order_by("size__sort_order", "size__code")]
    skus = {(k.colour_id, k.size_id): k for k in SKU.objects.filter(style=style, is_active=True)}
    cells = cells or {}
    rows = []
    for c in colours:
        row_cells, row_total = [], 0
        for s in sizes:
            value = cells.get((c.pk, s.pk), "")
            try:
                row_total += int(value or 0)
            except ValueError:
                pass
            row_cells.append({"size": s, "sku": skus.get((c.pk, s.pk)), "value": value, "name": f"q_{style.pk}_{c.pk}_{s.pk}"})
        rows.append({"colour": c, "cells": row_cells, "total": row_total})
    col_totals = [sum(int(r["cells"][i]["value"] or 0) if str(r["cells"][i]["value"] or 0).isdigit() else 0 for r in rows)
                  for i in range(len(sizes))]
    hint = ""
    if rate is None and customer is not None and skus:
        first = next(iter(skus.values()))
        price = pricing.resolve(customer, first, 1, on_date or timezone.localdate())
        if price is not None:
            rate, hint = price.rate, price.source
    if disc is None:
        disc = customer.discount_pct if customer is not None else Decimal("0")
    return {"style": style, "sizes": sizes, "rows": rows, "col_totals": col_totals, "grand": sum(col_totals),
            "rate": "" if rate is None else rate, "disc": disc, "hint": hint}


def parse_grid(post):
    """[(style, {(colour_id, size_id): qty}, rate text, disc text)] from the posted grids."""
    out = []
    for sid in post.getlist("style"):
        style = get_object_or_404(Style, pk=sid)
        cells = {}
        for key, value in post.items():
            if key.startswith(f"q_{sid}_") and value.strip():
                _, _, cid, zid = key.split("_")
                cells[(int(cid), int(zid))] = value.strip()
        out.append((style, cells, post.get(f"rate_{sid}", ""), post.get(f"disc_{sid}", "")))
    return out


class OrderList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "sales.order"

    def get(self, request):
        qs = in_active(SaleOrder.objects.for_user(request.user), request).select_related(
            "customer", "factory", "production_order").prefetch_related("lines", "packing_lists", "invoices")
        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return render(request, "sales/order_list.html", {
            "orders": _orders_with_next(qs[:200], request.user), "status": status, "statuses": SaleOrder.Status.choices,
            "can_create": _can(request, "sales.order", "create")})


class OrderSave(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "sales.order"

    def dispatch(self, request, *args, **kwargs):
        self.screen_action = "edit" if kwargs.get("pk") else "create"
        return super().dispatch(request, *args, **kwargs)

    def _ctx(self, request, order=None, p=None, grids=None):
        if grids is None:
            grids = []
            if order is not None:
                by_style = {}
                for l in order.lines.select_related("sku__style"):
                    g = by_style.setdefault(l.sku.style, {"cells": {}, "rate": l.rate, "disc": l.discount_pct})
                    g["cells"][(l.sku.colour_id, l.sku.size_id)] = str(int(l.qty))
                grids = [grid_context(s, cells=g["cells"], rate=g["rate"], disc=g["disc"]) for s, g in by_style.items()]
        vals = p if p else None
        if vals is None and order is not None:
            vals = {"customer": str(order.customer_id), "date": order.date.isoformat(),
                    "due_date": order.due_date.isoformat() if order.due_date else "", "order_type": order.order_type,
                    "remarks": order.remarks}
        return {"order": order, "factory": order.factory if order else request.factory, "customers": _customers(), "grids": grids,
                # confirming is the order page's `edit` action: a new order can be saved and confirmed by a role that has it
                "can_confirm": order is None and _can(request, "sales.order", "edit"),
                "styles": Style.objects.filter(is_archived=False), "vals": vals or {}, "types": SaleOrder.Type.choices,
                "today": timezone.localdate().isoformat()}

    def get(self, request, pk=None):
        order = get_object_or_404(SaleOrder.objects.for_user(request.user), pk=pk) if pk else None
        if order is not None and order.status != "draft":
            messages.error(request, "Only a draft order can be edited.")
            return redirect("saleorder_detail", pk=pk)
        if order is None and (back := _need_factory(request, "saleorder_list")):
            return back
        return render(request, "sales/order_form.html", self._ctx(request, order))

    def post(self, request, pk=None):
        order = get_object_or_404(SaleOrder.objects.for_user(request.user), pk=pk) if pk else None
        p = request.POST
        confirm_now = order is None and p.get("then") == "confirm"
        if confirm_now:
            _need(request, "sales.order", "edit")
        customer = Party.objects.filter(pk=_pk(p.get("customer"))).first()
        grids = []
        try:
            specs = []
            for style, cells, rate, disc in parse_grid(p):
                grids.append(grid_context(style, customer=customer, cells={k: v for k, v in cells.items()},
                                          rate=_dec(rate, "Rate", Decimal("0")) if rate.strip() else None,
                                          disc=_dec(disc, "Discount", Decimal("0")) if disc.strip() else None))
                for (cid, zid), qty in cells.items():
                    sku = get_object_or_404(SKU, style=style, colour_id=cid, size_id=zid)
                    specs.append(orders.OrderLineSpec(
                        sku=sku, qty=_dec(qty, f"Quantity of {sku}"),
                        rate=_dec(rate, "Rate") if rate.strip() else None,
                        discount_pct=_dec(disc, "Discount") if disc.strip() else None))
            customer = vu.chosen(_customers(), p.get("customer"), "customer")
            due = _day(p.get("due_date"), "Due date", default=None) if p.get("due_date") else None
            if order is None:
                order = (orders.create_and_confirm if confirm_now else orders.create_order)(
                    company=_company(), factory=require_active_factory(request),
                    customer=customer, date=_day(p.get("date"), "Date"), lines=specs, user=request.user,
                    order_type=p.get("order_type", "stock"), due_date=due, remarks=p.get("remarks", ""))
            else:
                orders.update_order(order, lines=specs, user=request.user, customer=customer, date=_day(p.get("date"), "Date"),
                                    due_date=due, order_type=p.get("order_type", "stock"), remarks=p.get("remarks", ""))
        except ERRORS as exc:
            _msgs(request, exc)
            return render(request, "sales/order_form.html", self._ctx(request, order, p, grids))
        if confirm_now:
            messages.success(request, self.confirmed(order))
        else:
            messages.success(request, "Order saved as a draft. Confirm it when it is final.")
        return redirect("saleorder_detail", pk=order.pk)

    @staticmethod
    def confirmed(order):
        raised = f" Production requirement {order.production_order.number or 'draft'} raised." if order.production_order_id else ""
        return f"Order {order.number} confirmed.{raised}"


class OrderGrid(LoginRequiredMixin, ScreenPermissionMixin, View):
    """One style's grid, loaded into the order form when a style is picked (HTMX)."""

    screen_code = "sales.order"

    def get(self, request):
        style = Style.objects.filter(pk=_pk(request.GET.get("style"))).first()
        if style is None:
            return HttpResponse("")
        customer = Party.objects.filter(pk=_pk(request.GET.get("customer")), is_customer=True).first()
        try:
            on_date = _day(request.GET.get("date"), default=timezone.localdate())
        except ValueError:
            on_date = timezone.localdate()
        return render(request, "sales/_order_grid.html", {"g": grid_context(style, customer=customer, on_date=on_date)})


class OrderDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "sales.order"

    def _order(self, request, pk):
        return get_object_or_404(SaleOrder.objects.for_user(request.user).select_related(
            "customer", "factory", "production_order"), pk=pk)

    def get(self, request, pk):
        order = self._order(request, pk)
        u = request.user
        return render(request, "sales/order_detail.html", {
            "order": order, "lines": order.lines.select_related("sku__style", "sku__colour", "sku__size"),
            "packings": order.packing_lists.all(), "invoices": order.invoices.all(),
            "can_edit": _can(request, "sales.order", "edit"), "can_cancel": _can(request, "sales.order", "cancel"),
            "guide": guide_service.order_guide(order, u), "can_open_packing": _can(request, "sales.packing", "view"),
            "can_open_invoice": _can(request, "sales.invoice", "view"),
            "show_phone": u.can_view_field("customer_phone"), "stages": orders.production_stages(order),
            "can_production": _can(request, "production.order", "view")})

    def post(self, request, pk):
        order = self._order(request, pk)
        _need(request, "sales.order", "edit")
        action, reason = request.POST.get("action"), request.POST.get("reason", "")
        try:
            if action == "confirm":
                order = orders.confirm_order(order, user=request.user)
                messages.success(request, OrderSave.confirmed(order))
            elif action == "cancel":
                orders.cancel_order(order, user=request.user, reason=reason)
                messages.success(request, "Order cancelled.")
            elif action == "close":
                orders.close_order(order, user=request.user, reason=reason)
                messages.success(request, "Order closed; the balance will not be dispatched.")
        except ERRORS as exc:
            _msgs(request, exc)
        return redirect("saleorder_detail", pk=pk)


class OrderBook(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Open orders and the balance pending on each (E4.6)."""

    screen_code = "sales.order"

    def get(self, request):
        # the active factory's orders, like the Sale orders list beside it; every factory of the user's in "All" mode
        return render(request, "sales/order_book.html", {"rows": orders.order_book(request.user, request.factory)})


# ================================================================ packing list, cartons, labels (E4.6)

class PackingListView(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "sales.packing"

    def get(self, request):
        qs = in_active(PackingList.objects.for_user(request.user), request).select_related("order__customer", "factory")
        return render(request, "sales/packing_list.html", {
            "lists": _with_next(qs[:200], guide_service.packing_next, request.user),
            "book": orders.order_book(request.user, request.factory), "can_open_order": _can(request, "sales.order", "view"),
            # the form needs `create`, and saving it lands on the packing list's page
            "can_pack": _can(request, "sales.packing", "create")})


class PackingSave(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "sales.packing"

    def dispatch(self, request, *args, **kwargs):
        self.screen_action = "edit" if kwargs.get("pk") else "create"
        return super().dispatch(request, *args, **kwargs)

    def _objs(self, request, order_pk, pk):
        packing = get_object_or_404(PackingList.objects.for_user(request.user), pk=pk) if pk else None
        order = packing.order if packing else get_object_or_404(SaleOrder.objects.for_user(request.user), pk=order_pk)
        return order, packing

    def _ctx(self, request, order, packing, n, cells=None, vals=None):
        lines = list(order.lines.select_related("sku__style", "sku__colour", "sku__size"))
        if packing is not None and cells is None:
            cells = {}
            for c in packing.cartons.prefetch_related("lines"):
                for cl in c.lines.all():
                    cells[(c.carton_no, cl.sku_id)] = str(int(cl.qty))
            n = max(n, packing.cartons.count())
        cells = cells or {}
        rows = [{"line": l, "left": l.qty - packing_service.packed_qty(l, exclude=packing),
                 "cells": [{"name": f"c{i}_{l.sku_id}", "value": cells.get((i, l.sku_id), "")} for i in range(1, n + 1)]}
                for l in lines]
        if vals is None and packing is not None:
            vals = {"location": str(packing.location_id), "date": packing.date.isoformat(), "transporter": str(packing.transporter_id or ""),
                    "lr_no": packing.lr_no, "lr_date": packing.lr_date.isoformat() if packing.lr_date else "",
                    "vehicle_no": packing.vehicle_no, "remarks": packing.remarks}
        return {"order": order, "packing": packing, "rows": rows, "n": n, "cartons": list(range(1, n + 1)),
                "locations": _locations(order.factory), "transporters": Party.objects.filter(is_transporter=True, is_active=True),
                "vals": vals or {}}

    def get(self, request, order_pk=None, pk=None):
        order, packing = self._objs(request, order_pk, pk)
        if packing is not None and packing.status != "draft":
            messages.error(request, "Only a draft packing list can be edited.")
            return redirect("packing_detail", pk=packing.pk)
        try:
            n = max(1, min(30, int(request.GET.get("cartons", 2))))
        except ValueError:
            n = 2
        return render(request, "sales/packing_form.html", self._ctx(request, order, packing, n))

    def post(self, request, order_pk=None, pk=None):
        order, packing = self._objs(request, order_pk, pk)
        p = request.POST
        try:
            n = max(1, min(30, int(p.get("n", 1))))
        except ValueError:
            n = 1
        cells, specs = {}, []
        if p.get("add_carton"):
            for key, value in p.items():
                if key.startswith("c") and "_" in key and value.strip():
                    head, _, sku_id = key[1:].partition("_")
                    if head.isdigit() and sku_id.isdigit():
                        cells[(int(head), int(sku_id))] = value.strip()
            return render(request, "sales/packing_form.html", self._ctx(request, order, packing, min(n + 1, 30), cells, p))
        try:
            for i in range(1, n + 1):
                items = {}
                for l in order.lines.select_related("sku__style", "sku__colour", "sku__size"):
                    raw = p.get(f"c{i}_{l.sku_id}", "").strip()
                    cells[(i, l.sku_id)] = raw
                    if raw:
                        items[l.sku] = _dec(raw, f"Carton {i} quantity of {l.sku}")
                if items:
                    specs.append(packing_service.CartonSpec(items))
            location = _choose(_locations(order.factory), p.get("location"), "location")
            kwargs = dict(order=order, location=location, date=_day(p.get("date"), "Date"), cartons=specs, user=request.user,
                          transporter=Party.objects.filter(pk=_pk(p.get("transporter")), is_transporter=True).first(),
                          lr_no=p.get("lr_no", ""), lr_date=_day(p["lr_date"]) if p.get("lr_date") else None,
                          vehicle_no=p.get("vehicle_no", ""), remarks=p.get("remarks", ""))
            saved = packing_service.save_packing(packing=packing, **kwargs)
        except ERRORS as exc:
            _msgs(request, exc)
            return render(request, "sales/packing_form.html", self._ctx(request, order, packing, n, cells, p))
        messages.success(request, "Packing list saved as a draft. Finish packing when the cartons are closed.")
        return redirect("packing_detail", pk=saved.pk)


def _draft_bill(p, make):
    """Draft the bill of a packing list. The packing page has no GST choice, so when GST cannot be suggested the
    message names the style and where to put it right, instead of offering choices this page does not have."""
    try:
        return make()
    except invoices.NoGstRate as exc:
        styles = {sku.style for sku in packing_service.sku_totals(p)}
        hsn = exc.hsn
        found = sorted(s.style_no for s in styles if s.hsn_id == (hsn.pk if hsn else None))
        names = ", ".join(found) or "A style"
        if hsn is None:
            raise BusinessRuleError(f"{names} {'have' if len(found) > 1 else 'has'} no HSN code. Set it in "
                                    "Masters → Styles, then make the bill again.") from exc
        raise BusinessRuleError(f"{names}: HSN {hsn.code} has no GST slab for this value and date. Add it in "
                                "Masters → Setup → HSN and GST slabs, then make the bill again.") from exc


class PackingDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "sales.packing"

    def _p(self, request, pk):
        return get_object_or_404(PackingList.objects.for_user(request.user).select_related(
            "order__customer", "factory", "location", "transporter"), pk=pk)

    def get(self, request, pk):
        p = self._p(request, pk)
        return render(request, "sales/packing_detail.html", {
            "p": p, "cartons": p.cartons.prefetch_related("lines__sku__style", "lines__sku__colour", "lines__sku__size"),
            "invoice": p.invoices.exclude(status="cancelled").first(),
            "guide": guide_service.packing_guide(p, request.user), "can_edit": _can(request, "sales.packing", "edit"),
            # making the bill opens the bill, so it needs both rights on bills
            "can_invoice": _can(request, "sales.invoice", "create") and _can(request, "sales.invoice", "view"),
            "can_open_order": _can(request, "sales.order", "view"), "can_open_invoice": _can(request, "sales.invoice", "view")})

    def post(self, request, pk):
        p = self._p(request, pk)
        action = request.POST.get("action")
        try:
            if action == "invoice":
                _need(request, "sales.invoice", "create")
                inv = _draft_bill(p, lambda: invoices.invoice_from_packing(p, user=request.user, date=timezone.localdate()))
                messages.success(request, "Bill drafted for the packed pieces. Check it, then post it.")
                return redirect("saleinvoice_detail", pk=inv.pk)
            _need(request, "sales.packing", "edit")
            if action == "finish_and_bill":
                # every right the two steps and the bill's own page ask for
                _need(request, "sales.invoice", "create")
                _need(request, "sales.invoice", "view")
                inv = _draft_bill(p, lambda: invoices.finish_packing_and_bill(p, user=request.user, date=timezone.localdate()))
                messages.success(request, "Packing finished and the bill drafted. Check the GST and the total, then post it.")
                return redirect("saleinvoice_detail", pk=inv.pk)
            if action == "finalize":
                packing_service.finalize_packing(p, user=request.user)
                messages.success(request, "Packing finished.")
            elif action == "cancel":
                packing_service.cancel_packing(p, user=request.user, reason=request.POST.get("reason", ""))
                messages.success(request, "Packing list cancelled.")
        except ERRORS as exc:
            _msgs(request, exc)
        return redirect("packing_detail", pk=pk)


class PackingPrint(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "sales.packing"

    def get(self, request, pk):
        p = get_object_or_404(PackingList.objects.for_user(request.user).select_related(
            "order__customer", "factory", "location", "transporter", "company"), pk=pk)
        return render(request, "sales/packing_print.html", {
            "p": p, "cartons": p.cartons.prefetch_related("lines__sku__style", "lines__sku__colour", "lines__sku__size")})


class CartonLabels(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Carton labels with a scannable carton barcode (E6.4: labels as well as bundle QR)."""

    screen_code = "sales.packing"

    def get(self, request, pk):
        p = get_object_or_404(PackingList.objects.for_user(request.user).select_related("order__customer", "factory"), pk=pk)
        cartons = list(p.cartons.prefetch_related("lines__sku__style", "lines__sku__colour", "lines__sku__size"))
        total = len(cartons)
        layout = request.GET.get("layout", "thermal6")
        labels = [{"carton": c, "svg": barcode.svg(c.code), "total": total} for c in cartons]
        return render(request, "inventory/labels.html", {"labels": labels, "kind": "carton", "layout": layout, "layouts": LAYOUTS})


# ================================================================ invoices and barcode billing (E4.2 - E4.5)

def _tax_ctx():
    return {"gst_templates": TaxTemplate.objects.filter(kind="gst", is_active=True, is_reverse_charge=False),
            "modes": SaleInvoice.TaxMode.choices}


def _tax_args(p):
    mode = p.get("tax_mode") or None
    template = TaxTemplate.objects.filter(pk=_pk(p.get("gst_template")), kind="gst").first()
    return {"tax_mode": mode, "gst_template": template, "tax_note": p.get("tax_note", "")}


def _line_specs(p):
    specs = []
    for i, sku_id in enumerate(p.getlist("sku")):
        if not sku_id:
            continue
        sku = get_object_or_404(SKU.objects.select_related("style", "colour", "size"), pk=sku_id)
        rate, disc = p.getlist("rate")[i].strip(), p.getlist("disc")[i].strip()
        specs.append(invoices.InvoiceLineSpec(
            sku=sku, qty=_dec(p.getlist("qty")[i], f"Quantity of {sku}"),
            rate=_dec(rate, "Rate") if rate else None, discount_pct=_dec(disc, "Discount") if disc else None))
    return specs


class InvoiceList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "sales.invoice"

    def get(self, request):
        qs = in_active(SaleInvoice.objects.for_user(request.user), request).select_related("customer", "factory", "packing")
        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return render(request, "sales/invoice_list.html", {
            "invoices": _with_next(qs[:200], guide_service.invoice_next, request.user), "status": status, "statuses": SaleInvoice.Status.choices,
            "can_create": _can(request, "sales.invoice", "create")})


class Billing(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Barcode billing: scan goods, each scan adds one piece at the customer's rate (E4.2)."""

    screen_code = "sales.invoice"
    screen_action = "create"

    def _ctx(self, request, p=None, rows=None):
        p = p or request.GET
        factory = request.factory
        return {"factory": factory, "customers": _customers(), "p": p,
                "locations": _locations(factory), "rows": rows or [], "today": timezone.localdate().isoformat(),
                "gst": invoices.gst_on(_company(), factory, timezone.localdate()) if factory else False,
                **_tax_ctx()}

    def get(self, request):
        if back := _need_factory(request, "saleinvoice_list"):
            return back
        return render(request, "sales/billing.html", self._ctx(request))

    def post(self, request):
        p = request.POST
        rows = []
        try:
            for i, sku_id in enumerate(p.getlist("sku")):
                if sku_id:
                    sku = get_object_or_404(SKU.objects.select_related("style", "colour", "size"), pk=sku_id)
                    rows.append({"sku": sku, "qty": p.getlist("qty")[i], "rate": p.getlist("rate")[i], "disc": p.getlist("disc")[i]})
            factory = require_active_factory(request)
            inv = invoices.save_invoice(
                company=_company(), factory=factory, customer=vu.chosen(_customers(), p.get("customer"), "customer"),
                date=_day(p.get("date"), "Date"), lines=_line_specs(p), user=request.user,
                location=_choose(_locations(factory), p.get("location"), "location"), notes=p.get("notes", ""), **_tax_args(p))
            if p.get("action") == "post":
                inv = invoices.post_invoice(inv, user=request.user)
                messages.success(request, f"Bill {inv.number} posted.")
                return redirect("saleinvoice_detail", pk=inv.pk)
        except ERRORS as exc:
            _msgs(request, exc)
            return render(request, "sales/billing.html", self._ctx(request, p, rows))
        messages.success(request, "Bill saved as a draft. Check the figures, then post it.")
        return redirect("saleinvoice_detail", pk=inv.pk)


class Scan(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Resolve a scanned code to the pieces to add: a SKU barcode gives 1 piece, a carton code gives its contents."""

    screen_code = "sales.invoice"
    screen_action = "create"

    def get(self, request):
        code = request.GET.get("code", "").strip()
        customer = Party.objects.filter(pk=_pk(request.GET.get("customer")), is_customer=True).first()
        try:
            on_date = _day(request.GET.get("date"), default=timezone.localdate())
        except ValueError:
            on_date = timezone.localdate()
        if not code:
            return JsonResponse({"ok": False, "error": "Nothing was scanned."})
        sku = SKU.objects.select_related("style", "colour", "size").filter(barcode=code, is_active=True).first()
        items = []
        if sku is not None:
            items = [(sku, 1)]
        else:
            carton = Carton.objects.filter(code=code, packing__factory__in=request.active_factories).first()
            if carton is not None:
                items = [(cl.sku, int(cl.qty)) for cl in carton.lines.select_related("sku__style", "sku__colour", "sku__size")]
        if not items:
            return JsonResponse({"ok": False, "error": f"Unknown barcode {code}."})
        out = []
        for k, qty in items:
            price = pricing.resolve(customer, k, qty, on_date) if customer else None
            out.append({"sku": k.pk, "label": f"{k.style.style_no} · {k.colour} · {k.size}", "qty": qty,
                        "rate": str(price.rate) if price else "", "source": price.source if price else "",
                        "disc": str(customer.discount_pct) if customer else "0"})
        return JsonResponse({"ok": True, "items": out})


class InvoiceDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "sales.invoice"

    def _inv(self, request, pk):
        return get_object_or_404(SaleInvoice.objects.for_user(request.user).select_related(
            "customer", "factory", "gst_template", "voucher", "order", "packing", "location", "company"), pk=pk)

    def _ctx(self, request, inv):
        guide = guide_service.invoice_guide(inv, request.user)
        settle = None
        if inv.status == "posted" and inv.customer.customer_ledger_id:
            settle = settlement(request.user, ledger=inv.customer.customer_ledger, reference=inv.number, direction="receive",
                                narration=f"Received against {inv.number}")
            # the pill shows what the ledger holds open on the bill; the button is the guide's step, so a role that
            # could not open the voucher it leads to gets no button
            settle["url"] = next((a["url"] for a in [guide["primary"], *guide["others"]] if a and a["kind"] == "receive"), None)
        return {"inv": inv, "guide": guide, "held": guide_service.held(inv, request.user),
                "lines": inv.lines.select_related("sku__style", "sku__colour", "sku__size"),
                "taxes": inv.tax_lines.all(), "can_edit": _can(request, "sales.invoice", "edit"),
                "can_cancel": _can(request, "sales.invoice", "cancel"),
                "can_return": _can(request, "sales.creditnote", "create"),
                "can_open_order": _can(request, "sales.order", "view"), "can_open_packing": _can(request, "sales.packing", "view"),
                "can_open_return": _can(request, "sales.creditnote", "view"), "can_open_voucher": _can(request, "ledger.voucher", "view"),
                "einvoice": einvoice.is_available(inv), "credit_notes": inv.credit_notes.all(), "settle": settle,
                "gst": invoices.gst_on(inv.company, inv.factory, inv.date), **_tax_ctx()}

    def get(self, request, pk):
        return render(request, "sales/invoice_detail.html", self._ctx(request, self._inv(request, pk)))

    def post(self, request, pk):
        inv = self._inv(request, pk)
        action, p = request.POST.get("action"), request.POST
        try:
            if action in ("post", "discard", "tax") and not _can(request, "sales.invoice", "edit"):
                raise PermissionDenied
            if action == "tax":
                specs = [invoices.InvoiceLineSpec(sku=l.sku, qty=l.qty, rate=l.rate, discount_pct=l.discount_pct, order_line=l.order_line)
                         for l in inv.lines.select_related("sku__style")]
                invoices.save_invoice(
                    company=inv.company, factory=inv.factory, customer=inv.customer, date=inv.date, lines=specs, user=request.user,
                    location=inv.location, invoice=inv, order=inv.order, packing=inv.packing, transporter=inv.transporter,
                    lr_no=inv.lr_no, vehicle_no=inv.vehicle_no, notes=inv.notes, due_date=inv.due_date, **_tax_args(p))
                messages.success(request, "Tax updated.")
            elif action == "post":
                invoices.post_invoice(inv, user=request.user)
                messages.success(request, "Bill posted.")
            elif action == "discard":
                invoices.discard_draft(inv, user=request.user)
                messages.success(request, "Draft discarded.")
                return redirect("saleinvoice_list")
            elif action == "cancel":
                if not _can(request, "sales.invoice", "cancel"):
                    raise PermissionDenied
                invoices.cancel_invoice(inv, user=request.user, reason=p.get("reason", ""))
                messages.success(request, "Bill cancelled; the goods are back in stock.")
            elif action == "einvoice":
                if not _can(request, "sales.invoice", "edit"):
                    raise PermissionDenied
                dist = int(p.get("distance_km") or 0)
                inv = einvoice.submit(inv, user=request.user, vehicle_no=p.get("vehicle_no", ""), distance_km=dist)
                if inv.einvoice_error:
                    messages.error(request, f"The portal said: {inv.einvoice_error}")
                else:
                    messages.success(request, "E-invoice generated." + (" E-way bill generated." if inv.eway_bill_no else ""))
            elif action == "einvoice_cancel":
                if not _can(request, "sales.invoice", "cancel"):
                    raise PermissionDenied
                einvoice.cancel(inv, user=request.user, reason=p.get("reason", ""))
                messages.success(request, "E-invoice cancelled.")
        except ERRORS as exc:
            _msgs(request, exc)
        return redirect("saleinvoice_detail", pk=pk)


class InvoicePrint(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "sales.invoice"

    def get(self, request, pk):
        inv = get_object_or_404(SaleInvoice.objects.for_user(request.user).select_related(
            "customer", "factory", "company", "packing", "order", "transporter"), pk=pk)
        qr = ""
        if inv.qr_text:
            import segno

            qr = segno.make(inv.qr_text, error="m").svg_inline(scale=3, border=1, dark="#000", light="#fff")
        billing = inv.customer.addresses.filter(kind="billing").first()
        return render(request, "sales/invoice_print.html", {
            "inv": inv, "lines": inv.lines.select_related("sku__style", "sku__colour", "sku__size"), "taxes": inv.tax_lines.all(),
            "qr": qr, "billing": billing, "cartons": inv.packing.cartons.count() if inv.packing_id else 0})


# ================================================================ credit notes

class CreditNoteList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "sales.creditnote"

    def get(self, request):
        qs = in_active(SaleCreditNote.objects.for_user(request.user), request).select_related("customer", "factory", "invoice")
        return render(request, "sales/creditnote_list.html", {"notes": qs[:200], "can_open_invoice": _can(request, "sales.invoice", "view")})


class CreditNoteNew(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "sales.creditnote"
    screen_action = "create"

    def _inv(self, request, pk):
        return get_object_or_404(SaleInvoice.objects.for_user(request.user).select_related("customer", "factory"), pk=pk)

    def _ctx(self, request, inv, p=None):
        return {"inv": inv, "lines": [l for l in inv.lines.select_related("sku__style", "sku__colour", "sku__size") if l.returnable > 0],
                "locations": _locations(inv.factory), "p": p or {}, "today": timezone.localdate().isoformat()}

    def get(self, request, pk):
        return render(request, "sales/creditnote_form.html", self._ctx(request, self._inv(request, pk)))

    def post(self, request, pk):
        inv, p = self._inv(request, pk), request.POST
        try:
            pairs = []
            for line in inv.lines.all():
                raw = p.get(f"qty_{line.pk}", "").strip()
                if raw:
                    pairs.append((line, _dec(raw, f"Returned quantity of {line.sku}")))
            note = credit_notes.save_credit_note(
                invoice=inv, location=_choose(_locations(inv.factory), p.get("location"), "location"),
                date=_day(p.get("date"), "Date"), lines=pairs, reason=p.get("reason", ""), user=request.user)
        except ERRORS as exc:
            _msgs(request, exc)
            return render(request, "sales/creditnote_form.html", self._ctx(request, inv, p))
        messages.success(request, "Return saved as a draft. Check the figures, then post it.")
        return redirect("salecn_detail", pk=note.pk)


class CreditNoteDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "sales.creditnote"

    def _note(self, request, pk):
        return get_object_or_404(SaleCreditNote.objects.for_user(request.user).select_related(
            "customer", "factory", "invoice", "voucher", "location"), pk=pk)

    def get(self, request, pk):
        note = self._note(request, pk)
        lines = note.lines.select_related("invoice_line__sku__style", "invoice_line__sku__colour", "invoice_line__sku__size").prefetch_related("taxes")
        taxes = {}
        for l in lines:
            for t in l.taxes.all():
                taxes[(t.component, t.rate)] = taxes.get((t.component, t.rate), Decimal("0")) + t.amount
        guide = guide_service.creditnote_guide(note, request.user)
        note.invoice.customer = note.customer
        return render(request, "sales/creditnote_detail.html", {
            "note": note, "guide": guide, "can_post": guide["primary"] is not None,
            "held": guide_service.held(note.invoice, request.user) if note.status == "posted" else None,
            "lines": lines, "taxes": [{"component": c, "rate": r, "amount": a} for (c, r), a in sorted(taxes.items())],
            "can_cancel": _can(request, "sales.creditnote", "cancel"),
            "can_open_invoice": _can(request, "sales.invoice", "view"), "can_open_voucher": _can(request, "ledger.voucher", "view")})

    def post(self, request, pk):
        note, action = self._note(request, pk), request.POST.get("action")
        try:
            if action == "post":
                if not _can(request, "sales.creditnote", "create"):
                    raise PermissionDenied
                credit_notes.post_credit_note(note, user=request.user)
                messages.success(request, "Return posted.")
            elif action == "cancel":
                if not _can(request, "sales.creditnote", "cancel"):
                    raise PermissionDenied
                credit_notes.cancel_credit_note(note, user=request.user, reason=request.POST.get("reason", ""))
                messages.success(request, "Return cancelled.")
        except ERRORS as exc:
            _msgs(request, exc)
        return redirect("salecn_detail", pk=pk)
