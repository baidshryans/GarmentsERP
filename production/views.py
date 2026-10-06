import re
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from core import viewutils as vu
from core.exceptions import BusinessRuleError
from core.models import Factory, Location
from core.scoping import ScreenPermissionMixin
from core.services.active_factory import in_active, require_active_factory
from core.services.factories import cutting_location, godown_location
from inventory.models import RollBalance
from masters.models import Colour, Party, Process, Size, Style

from . import labels
from .models import Bundle, CuttingEntry, Lot, LotStep, ProductionOrder, StageMovement
from .services import bundles as bundle_service
from .services import costing, cutting, guide, orders, routes


def _factories(user):
    return Factory.objects.for_user(user).filter(is_active=True)


def _need_factory(request, to):
    """New documents are entered in one factory. In "All factories" mode say so and go back to the list."""
    if request.factory is None:
        messages.error(request, "Choose a single factory in the top bar before entering a document.")
        return redirect(to)
    return None


# ================================================================ orders (E7.1)

class OrderList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "production.order"

    def get(self, request):
        qs = in_active(ProductionOrder.objects.for_user(request.user), request).select_related("factory").prefetch_related("lines__lot")
        if request.GET.get("status"):
            qs = qs.filter(status=request.GET["status"])
        orders_shown = list(qs[:200])
        perms = {}                                               # one user: each permission is asked once for the page
        for o in orders_shown:                                   # only the orders on the page: the guide reads each lot
            o.next = guide.order_next(o, request.user, perms)
        return render(request, "production/order_list.html", {
            "orders": orders_shown, "statuses": ProductionOrder.Status.choices, "status": request.GET.get("status", ""),
            "can_create": request.user.has_screen_perm("production.order", "create"),
        })


def parse_ratios(text, style):
    """'S:1, M:2, L:2, XL:1' -> {Size: ratio} using the style's own sizes."""
    by_code = {s.size.code.upper(): s.size for s in style.style_sizes.select_related("size")}
    out = {}
    for part in re.split(r"[,;\n]+", text or ""):
        part = part.strip()
        if not part:
            continue
        code, _, ratio = part.partition(":")
        size = by_code.get(code.strip().upper())
        if size is None:
            raise ValueError(f"'{code.strip()}' is not a size of {style.style_no} (sizes: {', '.join(by_code)}).")
        out[size] = vu.whole(ratio, f"Ratio for {code.strip()}")
    return out


class OrderSave(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "production.order"

    def dispatch(self, request, *args, **kwargs):
        self.screen_action = "edit" if kwargs.get("pk") else "create"
        return super().dispatch(request, *args, **kwargs)

    def _ctx(self, request, order=None, rows=None, d=None):
        if rows is None:
            rows = []
            if order:
                for l in order.lines.select_related("style", "colour").prefetch_related("sizes__size"):
                    rows.append({"style": str(l.style_id), "colour": str(l.colour_id), "qty": l.total_qty,
                                 "ratios": ", ".join(f"{s.size.code}:{s.ratio}" for s in l.sizes.all())})
        return {"order": order, "rows": rows + [{}, {}], "d": d or {}, "factory": order.factory if order else request.factory,
                "styles": Style.objects.filter(is_archived=False).prefetch_related("style_sizes__size"),
                "colours": Colour.objects.filter(is_active=True),
                "vals": {k: (d or {}).get(k, "") or (getattr(order, k, "") if order and k != "factory" else "")
                         for k in ("date", "due_date", "purpose", "order_reference", "remarks")}}

    def get(self, request, pk=None):
        order = get_object_or_404(ProductionOrder.objects.for_user(request.user), pk=pk) if pk else None
        if order is None and (back := _need_factory(request, "order_list")):
            return back
        ctx = self._ctx(request, order)
        for k in ("date", "due_date"):
            if order and getattr(order, k):
                ctx["vals"][k] = getattr(order, k).isoformat()
        return render(request, "production/order_form.html", ctx)

    def post(self, request, pk=None):
        order = get_object_or_404(ProductionOrder.objects.for_user(request.user), pk=pk) if pk else None
        p = request.POST
        rows, specs = [], []
        try:
            for i, sid in enumerate(p.getlist("style")):
                row = {"style": sid, "colour": p.getlist("colour")[i], "qty": p.getlist("qty")[i], "ratios": p.getlist("ratios")[i]}
                rows.append(row)
                if not sid:
                    continue
                style = get_object_or_404(Style, pk=sid)
                specs.append(orders.OrderLineSpec(style, get_object_or_404(Colour, pk=row["colour"]),
                                                  vu.whole(row["qty"], "Quantity"), parse_ratios(row["ratios"], style)))
            due = vu.day(p.get("due_date"), default=None) if p.get("due_date") else None
            if order is None:
                order = orders.create_order(
                    company=vu.company(), factory=require_active_factory(request),
                    date=vu.day(p.get("date")), due_date=due, lines=specs, user=request.user, purpose=p.get("purpose", "stock"),
                    order_reference=p.get("order_reference", ""), remarks=p.get("remarks", ""))
            else:
                orders.update_order(order, lines=specs, user=request.user, date=vu.day(p.get("date")), due_date=due,
                                    order_reference=p.get("order_reference", ""), remarks=p.get("remarks", ""))
        except (ValueError, BusinessRuleError) as exc:
            vu.report(request, exc)
            return render(request, "production/order_form.html", self._ctx(request, order, rows, p))
        messages.success(request, "Order saved as a draft. Release it to make the lots.")
        return redirect("order_detail", pk=order.pk)


class OrderDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "production.order"

    def _order(self, request, pk):
        return get_object_or_404(ProductionOrder.objects.for_user(request.user).select_related("factory"), pk=pk)

    def get(self, request, pk):
        order = self._order(request, pk)
        lines, perms = [], {}
        for l in order.lines.select_related("style", "colour", "bom_version", "route").prefetch_related("sizes__size"):
            lot = getattr(l, "lot", None) if hasattr(l, "lot") else None
            lines.append({"line": l, "lot": lot, "sizes": l.sizes.all(),
                          "next": guide.lot_guide(lot, request.user, perms)["primary"] if lot else None})
        return render(request, "production/order_detail.html", {
            "order": order, "lines": lines,
            "can_edit": request.user.has_screen_perm("production.order", "edit"),
            "can_close": request.user.has_screen_perm("production.order", "approve"),
        })

    def post(self, request, pk):
        order = self._order(request, pk)
        user, action = request.user, request.POST.get("action")
        try:
            if action == "release":
                if not user.has_screen_perm("production.order", "edit"):
                    raise PermissionDenied
                order = orders.release_order(order, user=user)
                messages.success(request, f"{order.number} released. Lots and routes are ready.")
                lots = [l.lot for l in order.lines.all() if hasattr(l, "lot")]
                if len(lots) == 1 and user.has_screen_perm("production.lot", "view"):
                    return redirect("lot_detail", pk=lots[0].pk)
            elif action == "close":
                orders.close_order(order, user=user, reason=request.POST.get("reason", ""))
                messages.success(request, "Order closed; remaining work in progress written off.")
        except BusinessRuleError as exc:
            messages.error(request, str(exc))
        return redirect("order_detail", pk=pk)


# ================================================================ lot: route planner, cost, bundles (E7.2, E7.3, E7.11)

class LotDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "production.lot"

    def _lot(self, request, pk):
        return get_object_or_404(Lot.objects.for_user(request.user).select_related(
            "style", "colour", "factory", "bom_version", "order_line__order"), pk=pk)

    def get(self, request, pk):
        lot = self._lot(request, pk)
        steps = list(lot.steps.select_related("process", "factory", "party"))
        bundles = list(lot.bundles.select_related("sku__size", "location", "current_step__process").order_by("bundle_no"))
        cuts = list(lot.cuttings.all())
        planned = sum(l.qty for l in lot.order_line.sizes.all())
        breakdown = costing.cost_breakdown(lot)
        can_cost = request.user.can_view_field("cost")
        can_edit = request.user.has_screen_perm("production.lot", "edit")
        live = [b for b in bundles if b.is_live]
        expected_charges = sum((c.amount_per_piece for c in lot.bom_version.charges.all()), Decimal("0")) * sum(b.original_qty for b in bundles) if lot.bom_version else None
        return render(request, "production/lot_detail.html", {
            "lot": lot, "guide": guide.lot_guide(lot, request.user),
            "steps": steps, "bundles": bundles, "cuttings": cuts, "planned": planned,
            "cut_pieces": sum(b.original_qty for b in bundles), "live_pieces": sum(b.qty for b in live),
            "breakdown": breakdown if can_cost else None, "total_cost": costing.lot_cost(lot) if can_cost else None,
            "expected_charges": expected_charges, "can_cost": can_cost,
            "changes": lot.route_changes.select_related("user")[:20],
            "processes": Process.objects.filter(is_active=True), "factories": _factories(request.user),
            "fabricators": Party.objects.filter(is_fabricator=True, is_active=True),
            "can_edit": can_edit, "route_open": can_edit and lot.status == Lot.Status.PLANNED,   # the route is planned then
            "can_cut": request.user.has_screen_perm("production.cutting", "create"),
            "can_move": request.user.has_screen_perm("production.move", "create"),
            "can_pack": request.user.has_screen_perm("production.move", "create"),
            "can_tags": request.user.has_screen_perm("production.bundle", "view"),
            "can_open_order": request.user.has_screen_perm("production.order", "view"),
            "pack_ready": [b for b in live if guide.pack_ready(b, [s for s in steps if s.status != "skipped"])],
            "dispatch_locations": Location.objects.filter(factory=lot.factory, is_active=True).exclude(loc_type__in=("transit", "rejects", "fabricator")),
        })

    def post(self, request, pk):
        lot = self._lot(request, pk)
        if not request.user.has_screen_perm("production.lot", "edit"):
            raise PermissionDenied
        p, user, action = request.POST, request.user, request.POST.get("action")
        reason = p.get("reason", "")
        try:
            step = LotStep.objects.filter(pk=p.get("step"), lot=lot).first() if p.get("step") else None
            if action == "skip":
                routes.skip_step(step, user=user, reason=reason)
            elif action == "remove":
                routes.remove_step(step, user=user, reason=reason)
            elif action == "reorder":
                routes.reorder_step(step, new_sequence=int(p.get("new_sequence") or 0), user=user, reason=reason)
            elif action == "reassign":
                routes.reassign_step(
                    step, user=user, reason=reason, assignment=p.get("assignment"),
                    factory=Factory.objects.filter(pk=p["factory"]).first() if p.get("factory") else None,
                    party=Party.objects.filter(pk=p["party"]).first() if p.get("party") else None,
                    rate=vu.dec(p.get("rate"), "Rate", Decimal("0")), rework_rate=vu.dec(p.get("rework_rate"), "Rework rate", Decimal("0")))
            elif action == "add":
                routes.add_step(
                    lot, process=get_object_or_404(Process, pk=p.get("process")), after_sequence=int(p.get("after_sequence") or 0),
                    user=user, reason=reason, assignment=p.get("assignment", "in_house"),
                    factory=Factory.objects.filter(pk=p["factory"]).first() if p.get("factory") else None,
                    party=Party.objects.filter(pk=p["party"]).first() if p.get("party") else None,
                    rate=vu.dec(p.get("rate"), "Rate", Decimal("0")), is_mandatory=p.get("is_mandatory") == "on")
            else:
                raise BusinessRuleError("Unknown action.")
            messages.success(request, "Route updated and logged.")
        except (ValueError, BusinessRuleError) as exc:
            vu.report(request, exc)
        return redirect("lot_detail", pk=pk)


class PackBundles(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "production.move"
    screen_action = "create"

    def post(self, request, pk):
        lot = get_object_or_404(Lot.objects.for_user(request.user), pk=pk)
        ids = request.POST.getlist("bundle")
        try:
            bundles = list(Bundle.objects.filter(pk__in=ids, lot=lot))
            location = Location.objects.filter(pk=request.POST.get("location"), factory=lot.factory).first() if request.POST.get("location") else None
            done = bundle_service.pack_bundles(bundles=bundles, user=request.user, location=location)
            messages.success(request, f"{sum(b.qty for b in done)} pieces packed into finished goods.")
        except BusinessRuleError as exc:
            messages.error(request, str(exc))
        return redirect("lot_detail", pk=pk)


# ================================================================ fabric issue and cutting (E7.4)

class FabricIssueView(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "production.cutting"

    def _ctx(self, request, lot, vals=None):
        godown = godown_location(lot.factory)
        rolls = RollBalance.objects.for_user(request.user).filter(location=godown, qty__gt=0).select_related("roll__material")
        return {"lot": lot, "rolls": rolls, "vals": vals or {}, "issues": lot.fabric_issues.prefetch_related("lines__roll")[:10],
                "can_create": request.user.has_screen_perm("production.cutting", "create"),
                "perms_lot": request.user.has_screen_perm("production.lot", "view")}

    def get(self, request, pk):
        lot = get_object_or_404(Lot.objects.for_user(request.user), pk=pk)
        return render(request, "production/fabric_issue.html", self._ctx(request, lot))

    def post(self, request, pk):
        lot = get_object_or_404(Lot.objects.for_user(request.user), pk=pk)
        if not request.user.has_screen_perm("production.cutting", "create"):
            raise PermissionDenied
        from inventory.models import FabricRoll

        try:
            lines = []
            for key, value in request.POST.items():
                if key.startswith("qty_") and value.strip():
                    lines.append((get_object_or_404(FabricRoll, pk=key[4:]), vu.dec(value, "Quantity")))
            issue = cutting.issue_fabric(lot=lot, lines=lines, user=request.user, date=vu.day(request.POST.get("date"), default=timezone.localdate()))
        except (ValueError, BusinessRuleError) as exc:
            vu.report(request, exc)
            return render(request, "production/fabric_issue.html", self._ctx(request, lot, request.POST))
        if issue.mixed_shades:
            messages.warning(request, "Warning: rolls of different shade lots are now issued to this lot. Check before cutting (PUR-03).")
        messages.success(request, "Fabric issued to the cutting floor.")
        return redirect("lot_cutting", pk=pk)


class CuttingView(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "production.cutting"

    def _ctx(self, request, lot, vals=None):
        floor = cutting_location(lot.factory)
        rolls = RollBalance.objects.for_user(request.user).filter(location=floor, qty__gt=0).select_related("roll__material")
        sizes = [ss.size for ss in lot.style.style_sizes.select_related("size").order_by("size__sort_order")]
        return {"lot": lot, "rolls": rolls, "sizes": sizes, "vals": vals or {}, "entries": lot.cuttings.prefetch_related("sizes__size", "rolls__roll"),
                "planned": {s.size_id: s.qty for s in lot.order_line.sizes.all()},
                "can_create": request.user.has_screen_perm("production.cutting", "create"),
                "perms_lot": request.user.has_screen_perm("production.lot", "view")}

    def get(self, request, pk):
        lot = get_object_or_404(Lot.objects.for_user(request.user), pk=pk)
        return render(request, "production/cutting.html", self._ctx(request, lot))

    def post(self, request, pk):
        lot = get_object_or_404(Lot.objects.for_user(request.user), pk=pk)
        if not request.user.has_screen_perm("production.cutting", "create"):
            raise PermissionDenied
        p = request.POST
        from inventory.models import FabricRoll

        try:
            if p.get("action") == "bundles":
                entry = get_object_or_404(CuttingEntry, pk=p.get("entry"), lot=lot)
                made = cutting.create_bundles(entry, bundle_size=vu.whole(p.get("bundle_size"), "Bundle size"), user=request.user)
                messages.success(request, f"{len(made)} bundles made. Print their QR tags now.")
                return redirect("lot_tags", pk=pk)
            pieces = {}
            for size in lot.style.style_sizes.select_related("size"):
                n = p.get(f"pieces_{size.size_id}", "").strip()
                if n:
                    pieces[size.size] = vu.whole(n, f"Pieces of {size.size.code}")
            rolls = []
            for key in p:
                if key.startswith("used_"):
                    rid = key[5:]
                    used, waste, rem = (vu.dec(p.get(f"{n}_{rid}"), n, Decimal("0")) for n in ("used", "waste", "remnant"))
                    if used or waste or rem:
                        rolls.append(cutting.RollUseSpec(get_object_or_404(FabricRoll, pk=rid), used, waste, rem))
            entry = cutting.record_cutting(lot=lot, pieces=pieces, rolls=rolls, user=request.user,
                                           date=vu.day(p.get("date"), default=timezone.localdate()), notes=p.get("notes", ""))
        except (ValueError, BusinessRuleError) as exc:
            vu.report(request, exc)
            return render(request, "production/cutting.html", self._ctx(request, lot, p))
        if entry.over_tolerance:
            messages.warning(request, f"Fabric used is {entry.variance_pct}% against the BOM ({entry.expected_fabric} expected): beyond the {lot.company.bom_tolerance_pct}% tolerance (BR-10).")
        else:
            messages.success(request, f"Lay {entry.lay_no} recorded." + (f" Variance against BOM: {entry.variance_pct}%." if entry.variance_pct is not None else ""))
        return redirect("lot_cutting", pk=pk)


# ================================================================ QR tags (E7.5)

class LotTags(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "production.bundle"

    def get(self, request, pk):
        lot = get_object_or_404(Lot.objects.for_user(request.user).select_related("style", "colour"), pk=pk)
        qs = lot.bundles.select_related("sku__size", "sku__colour").order_by("bundle_no")
        if request.GET.get("bundle"):
            qs = qs.filter(pk=request.GET["bundle"])
        items = [{"b": b, "svg": labels.qr_svg(b)} for b in qs]
        return render(request, "production/tags.html", {
            "lot": lot, "items": items, "layout": request.GET.get("layout", "thermal4"),
            "layouts": {"a4": "A4 sheet", "thermal4": "Thermal 4 x 2 in", "thermal2": "Thermal 2 x 1 in"},
            "perms_lot": request.user.has_screen_perm("production.lot", "view"),
        })


class LotZpl(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "production.bundle"

    def get(self, request, pk):
        lot = get_object_or_404(Lot.objects.for_user(request.user), pk=pk)
        size = request.GET.get("size", "4x2")
        w, h = (100, 50) if size == "4x2" else (50, 25)
        bundles = lot.bundles.select_related("sku__size", "sku__colour", "lot__style").order_by("bundle_no")
        response = HttpResponse(labels.zpl_for(bundles, width_mm=w, height_mm=h), content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{lot.lot_no.replace("/", "-")}-tags.zpl"'
        return response


# ================================================================ move bundles (E7.6, E7.7)

class MoveView(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "production.move"

    def _lot(self, request):
        lot_id = request.GET.get("lot") or request.POST.get("lot")
        return get_object_or_404(Lot.objects.for_user(request.user).select_related("style", "colour"), pk=lot_id) if lot_id else None

    def _ctx(self, request, lot, vals=None):
        ctx = {"lot": lot, "vals": vals or {},
               "back": (request.GET.get("back") or request.POST.get("back")) == "1",   # opened from a lot's Next button
               "to_step": request.POST.get("to_step") or request.GET.get("step") or "",  # the stage that button named
               "lots": in_active(Lot.objects.for_user(request.user), request).exclude(status__in=("closed", "completed")).select_related("style", "colour"),
               "can_move": request.user.has_screen_perm("production.move", "create")}
        if lot:
            bundles = list(lot.bundles.filter(status__in=("cut", "ready", "at_stage")).select_related(
                "sku__size", "location", "current_step__process").order_by("bundle_no"))
            steps = [s for s in lot.steps.select_related("process", "factory", "party").order_by("sequence") if s.status != "skipped"]
            for b in bundles:
                b.next_label = bundle_service.next_stage_label(b, steps)
                b.scan = labels.scan_text(b)
            ctx.update(bundles=bundles, steps=steps, factories=_factories(request.user))
        return ctx

    def get(self, request):
        return render(request, "production/move.html", self._ctx(request, self._lot(request)))

    def post(self, request):
        lot = self._lot(request)
        if not request.user.has_screen_perm("production.move", "create"):
            raise PermissionDenied
        p = request.POST
        try:
            ids = p.getlist("bundle")
            bundles = list(Bundle.objects.filter(pk__in=ids, lot=lot))
            counts = {}
            for b in bundles:
                c = bundle_service.Count(loss=vu.whole(p.get(f"loss_{b.pk}"), "Loss", 0), rejection=vu.whole(p.get(f"rejection_{b.pk}"), "Rejection", 0),
                                         shortage=vu.whole(p.get(f"shortage_{b.pk}"), "Shortage", 0))
                if c.loss or c.rejection or c.shortage:
                    counts[b.pk] = c
            to_step = get_object_or_404(LotStep, pk=p.get("to_step"), lot=lot)
            factory = Factory.objects.filter(pk=p.get("factory")).first() if p.get("factory") else None
            moves = bundle_service.move_bundles(bundles=bundles, to_step=to_step, user=request.user, factory=factory,
                                                counts=counts, reason=p.get("reason", ""))
        except (ValueError, BusinessRuleError) as exc:
            vu.report(request, exc)
            return render(request, "production/move.html", self._ctx(request, lot, p))
        messages.success(request, f"{len(moves)} bundle(s) moved to {to_step.process.name}.")
        if p.get("back") == "1" and request.user.has_screen_perm("production.lot", "view"):
            return redirect("lot_detail", pk=lot.pk)
        return redirect(f"{request.path}?lot={lot.pk}")


# ================================================================ dashboard and tracking (E7.10)

class Dashboard(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "production.dashboard"

    def get(self, request):
        user = request.user
        today = timezone.localdate()
        scope = in_active(Lot.objects.for_user(user), request)
        live = Bundle.objects.filter(status__in=Bundle.LIVE, lot__in=scope).select_related(
            "current_step__process", "location__factory", "location__party", "lot")
        by_stage, by_factory, by_fabricator = {}, {}, {}
        rework = 0
        for b in live:
            stage = b.current_step.process.name if b.current_step_id else "Cut, waiting"
            by_stage[stage] = by_stage.get(stage, 0) + b.qty
            f = b.location.factory.code
            by_factory[f] = by_factory.get(f, 0) + b.qty
            if b.location.party_id:
                by_fabricator[b.location.party.name] = by_fabricator.get(b.location.party.name, 0) + b.qty
            if b.is_rework:
                rework += b.qty
        in_house = sum(by_factory.values()) - sum(by_fabricator.values())
        lots = scope.exclude(status__in=("closed", "completed")).select_related("style", "colour", "order_line__order")
        late = [l for l in lots if l.order_line.order.due_date and l.order_line.order.due_date < today]
        ageing = sorted(({"lot": l, "days": (today - l.created_at.date()).days} for l in lots), key=lambda r: -r["days"])[:10]
        moves = in_active(StageMovement.objects.for_user(user), request).filter(at__date=today)
        cut_today = Bundle.objects.filter(lot__in=scope, created_at__date=today).aggregate(s=Sum("original_qty"))["s"] or 0
        packed_today = moves.filter(kind="pack").aggregate(s=Sum("qty_in"))["s"] or 0
        stitched_today = moves.filter(Q(from_step__process__kind="stitching", kind__in=("move", "factory")) |
                                      Q(kind="qc", from_step__process__kind="stitching")).aggregate(s=Sum("qty_in"))["s"] or 0
        waiting = list(in_active(ProductionOrder.objects.for_user(user), request).filter(
            status=ProductionOrder.Status.DRAFT).select_related("factory").prefetch_related("lines__style", "lines__colour"))
        return render(request, "production/dashboard.html", {
            "waiting": [{"order": o, "pieces": o.total_qty, "styles": ", ".join(sorted({l.style.style_no for l in o.lines.all()}))}
                        for o in waiting],
            "can_release": user.has_screen_perm("production.order", "edit"),
            "by_stage": sorted(by_stage.items(), key=lambda kv: -kv[1]), "by_factory": sorted(by_factory.items()),
            "by_fabricator": sorted(by_fabricator.items(), key=lambda kv: -kv[1]), "in_house": in_house,
            "total": sum(by_factory.values()), "rework": rework, "late": late, "ageing": ageing,
            "cut_today": cut_today, "stitched_today": stitched_today, "packed_today": packed_today, "today": today,
        })

    def post(self, request):
        """Release a waiting order from the dashboard; the same service as the order screen."""
        user = request.user
        if request.POST.get("action") == "release":
            if not user.has_screen_perm("production.order", "edit"):
                raise PermissionDenied
            order = get_object_or_404(ProductionOrder.objects.for_user(user), pk=request.POST.get("order"))
            try:
                order = orders.release_order(order, user=user)
                messages.success(request, f"{order.number} released. Lots and routes are ready.")
            except BusinessRuleError as exc:
                messages.error(request, f"{order}: {exc}")
        return redirect("production_dashboard")


class Track(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Find the current stage of every bundle by order, style, lot or order reference (E7.10)."""

    screen_code = "production.dashboard"

    def get(self, request):
        q = request.GET.get("q", "").strip()
        results = []
        if q:
            lots = Lot.objects.for_user(request.user).filter(
                Q(lot_no__icontains=q) | Q(style__style_no__icontains=q) | Q(order_line__order__number__icontains=q)
                | Q(order_line__order__order_reference__icontains=q)).select_related("style", "colour", "order_line__order")[:20]
            for lot in lots:
                bundles = lot.bundles.select_related("sku__size", "location", "current_step__process").order_by("bundle_no")
                results.append({"lot": lot, "bundles": bundles})
        return render(request, "production/track.html", {"q": q, "results": results})
