from datetime import date
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from core.exceptions import BusinessRuleError
from core.models import Company, Factory, Location
from core.scoping import ScreenPermissionMixin
from core.services.active_factory import need_factory, require_active_factory
from masters.models import SKU, Material, Party, Style

from . import barcode
from .models import (
    FabricRoll, OpeningStock, ReorderLevel, RollBalance, StockAlert, StockBalance, StockJournal, StockJournalLine, StockTransfer,
)
from .services import alerts as alert_service
from .services import journal as journal_service
from .services import opening as opening_service
from .services import transfers


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


def parse_item(value):
    """Item selects hold 'm:<id>' for a material or 's:<id>' for a SKU."""
    kind, _, pk = (value or "").partition(":")
    if kind == "m":
        return get_object_or_404(Material, pk=pk)
    if kind == "s":
        return get_object_or_404(SKU.objects.select_related("style", "colour", "size"), pk=pk)
    raise ValueError("Choose an item.")


def item_choices():
    """(value, label) pairs for item selects: materials then SKUs."""
    mats = [(f"m:{m.pk}", f"{m.name} ({m.code})") for m in Material.objects.filter(is_active=True)]
    skus = [(f"s:{k.pk}", f"{k.style.style_no} / {k.colour} / {k.size}")
            for k in SKU.objects.filter(is_active=True).select_related("style", "colour", "size")]
    return mats, skus


def _messages_for(request, exc):
    if isinstance(exc, ValidationError):
        for m in exc.messages:
            messages.error(request, m)
    else:
        messages.error(request, str(exc))


# ---------------------------------------------------------------- settings

class SettingsForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["valuation_method", "allow_negative_stock", "po_approval_limit", "bom_tolerance_pct"]
        widgets = {"valuation_method": forms.RadioSelect}


class InventorySettings(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "inventory.settings"

    def _ctx(self, request, form):
        company = _company()
        return {"form": form, "history": company.history.all()[:15],
                "can_edit": request.user.has_screen_perm("inventory.settings", "edit")}

    def get(self, request):
        return render(request, "inventory/settings.html", self._ctx(request, SettingsForm(instance=_company())))

    def post(self, request):
        if not request.user.has_screen_perm("inventory.settings", "edit"):
            raise PermissionDenied
        form = SettingsForm(request.POST, instance=_company())
        if form.is_valid():
            form.save()
            messages.success(request, "Settings saved. The valuation method applies to movements from now on; earlier stock keeps its value.")
            return redirect("inventory_settings")
        return render(request, "inventory/settings.html", self._ctx(request, form))


# ---------------------------------------------------------------- stock enquiry (E6.1)

class StockEnquiry(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "inventory.stock"

    def get(self, request):
        qs = StockBalance.objects.for_user(request.user).exclude(qty=0, value=0).select_related(
            "factory", "location", "material", "sku__style", "sku__colour", "sku__size")
        g = request.GET
        if request.factory:
            qs = qs.filter(factory=request.factory)
        if g.get("location"):
            qs = qs.filter(location_id=g["location"])
        if g.get("kind") == "material":
            qs = qs.filter(material__isnull=False)
        elif g.get("kind") == "sku":
            qs = qs.filter(sku__isnull=False)
        q = g.get("q", "").strip()
        if q:
            qs = qs.filter(Q(material__name__icontains=q) | Q(material__code__icontains=q)
                           | Q(sku__style__style_no__icontains=q) | Q(sku__barcode__startswith=q))
        rows = []
        can_cost = request.user.can_view_field("cost")
        for b in qs.order_by("factory__code", "location__name")[:500]:
            avg = (b.value / b.qty).quantize(Decimal("0.0001")) if b.qty else None
            rows.append({"b": b, "item": b.item, "avg": avg, "transit": b.location.loc_type == "transit"})
        return render(request, "inventory/stock.html", {
            "rows": rows, "can_cost": can_cost, "f": g, "q": q,
            "locations": Location.objects.filter(factory__in=request.active_factories),
        })


class RollList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "inventory.stock"

    def get(self, request):
        qs = RollBalance.objects.for_user(request.user).filter(qty__gt=0).select_related(
            "roll__material", "roll__supplier", "location__factory")
        q = request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(roll__label_code__icontains=q) | Q(roll__vendor_roll_no__icontains=q)
                           | Q(roll__lot_no__icontains=q) | Q(roll__material__name__icontains=q))
        return render(request, "inventory/rolls.html", {
            "rows": qs.order_by("roll__material__name", "roll__lot_no", "roll__label_code")[:500], "q": q,
            "can_cost": request.user.can_view_field("cost"),
        })


# ---------------------------------------------------------------- labels (E5.2, E6.4)

LAYOUTS = {"a4": "A4 sheet", "thermal4": "Thermal 4 x 2 in", "thermal2": "Thermal 2 x 1 in", "thermal6": "Thermal 4 x 6 in (cartons)"}


class RollLabels(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Printable roll labels: one for a roll, or every roll of a GRN."""

    screen_code = "inventory.stock"

    def get(self, request, pk=None, grn_pk=None):
        if pk is not None:
            rolls = [get_object_or_404(FabricRoll.objects.select_related("material", "supplier"), pk=pk)]
        else:
            rolls = list(FabricRoll.objects.filter(source_type="purchases.grn", source_id=grn_pk)
                         .select_related("material", "supplier"))
            if not rolls:
                messages.error(request, "That GRN has no rolls to label.")
                return redirect("grn_list")
        labels = [{"roll": r, "svg": barcode.svg(r.label_code)} for r in rolls]
        return render(request, "inventory/labels.html", {
            "labels": labels, "kind": "roll", "layout": request.GET.get("layout", "thermal4"), "layouts": LAYOUTS,
        })


class TagPrint(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Bulk SKU tags: filter by style / colour / size, choose a quantity per SKU, print (E6.4)."""

    screen_code = "inventory.labels"

    def get(self, request):
        skus = SKU.objects.filter(is_active=True).select_related("style", "colour", "size")
        g = request.GET
        if g.get("style"):
            skus = skus.filter(style_id=g["style"])
        if g.get("colour"):
            skus = skus.filter(colour_id=g["colour"])
        if g.get("size"):
            skus = skus.filter(size_id=g["size"])
        from masters.models import Colour, Size

        return render(request, "inventory/tag_picker.html", {
            "skus": skus[:300], "styles": Style.objects.filter(is_archived=False), "colours": Colour.objects.all(),
            "sizes": Size.objects.all(), "f": g, "layouts": LAYOUTS,
            "filtered": any(g.get(k) for k in ("style", "colour", "size")),
        })

    def post(self, request):
        labels = []
        try:
            for key, value in request.POST.items():
                if not key.startswith("qty_") or not value.strip():
                    continue
                n = int(value)
                if n <= 0:
                    continue
                if n > 500:
                    raise ValueError("Print at most 500 tags of one SKU at a time.")
                sku = get_object_or_404(SKU.objects.select_related("style", "colour", "size"), pk=key[4:])
                svg = barcode.svg(sku.barcode)
                labels += [{"sku": sku, "svg": svg} for _ in range(n)]
        except ValueError as exc:
            messages.error(request, str(exc) if "at most" in str(exc) else "Quantities must be whole numbers.")
            return redirect("tag_print")
        if not labels:
            messages.error(request, "Enter a quantity for at least one SKU.")
            return redirect("tag_print")
        return render(request, "inventory/labels.html", {
            "labels": labels, "kind": "sku", "layout": request.POST.get("layout", "thermal2"), "layouts": LAYOUTS,
            "show_mrp": True,
        })


# ---------------------------------------------------------------- stock journal (E9.2)

class JournalList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "inventory.journal"

    def get(self, request):
        qs = StockJournal.objects.for_user(request.user).select_related("factory", "location")
        return render(request, "inventory/journal_list.html", {
            "journals": qs[:200], "can_create": request.user.has_screen_perm("inventory.journal", "create")})


class JournalNew(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "inventory.journal"
    screen_action = "create"

    def _ctx(self, request, rows=None, data=None):
        mats, skus = item_choices()
        rolls = RollBalance.objects.for_user(request.user).filter(qty__gt=0).select_related("roll__material", "location")
        return {"factory": request.factory,
                "locations": Location.objects.filter(factory=request.factory, is_active=True).exclude(loc_type="transit"),
                "mats": mats, "skus": skus, "rolls": rolls, "rows": rows or [{}, {}, {}, {}], "d": data or {},
                "reasons": StockJournal.Reason.choices}

    def get(self, request):
        if back := need_factory(request, "journal_list"):
            return back
        return render(request, "inventory/journal_form.html", self._ctx(request))

    def post(self, request):
        p = request.POST
        rows, specs = [], []
        try:
            for i, value in enumerate(p.getlist("item")):
                row = {k: p.getlist(k)[i] for k in ("direction", "roll", "new_roll_no", "qty", "rate")} | {"item": value}
                rows.append(row)
                if not value:
                    continue
                rate = _decimal(row["rate"], "Rate") if row["rate"].strip() else None
                roll = get_object_or_404(FabricRoll, pk=int(row["roll"])) if row["roll"] else None
                specs.append(journal_service.JournalLineSpec(
                    direction=row["direction"], item=parse_item(value), qty=_decimal(row["qty"], "Quantity"), rate=rate, roll=roll,
                    new_roll_no=row["new_roll_no"]))
            factory = require_active_factory(request)
            j = journal_service.post_journal(
                company=_company(), factory=factory, location=get_object_or_404(Location, pk=p.get("location")),
                date=date.fromisoformat(p.get("date")), reason=p.get("reason", ""), lines=specs, user=request.user,
                remarks=p.get("remarks", ""))
        except (ValueError, BusinessRuleError) as exc:
            _messages_for(request, exc)
            return render(request, "inventory/journal_form.html", self._ctx(request, rows, p))
        messages.success(request, f"Stock journal {j.number} posted.")
        return redirect("journal_detail", pk=j.pk)


class JournalDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "inventory.journal"

    def _j(self, request, pk):
        return get_object_or_404(StockJournal.objects.for_user(request.user).select_related("factory", "location", "voucher"), pk=pk)

    def get(self, request, pk):
        j = self._j(request, pk)
        return render(request, "inventory/journal_detail.html", {
            "j": j, "lines": j.lines.select_related("material", "sku__style", "sku__colour", "sku__size", "roll"),
            "can_cancel": request.user.has_screen_perm("inventory.journal", "cancel")})

    def post(self, request, pk):
        j = self._j(request, pk)
        if not request.user.has_screen_perm("inventory.journal", "cancel"):
            raise PermissionDenied
        try:
            journal_service.cancel_journal(j, user=request.user, reason=request.POST.get("reason", ""))
            messages.success(request, "Stock journal cancelled; the stock is back as it was.")
        except BusinessRuleError as exc:
            _messages_for(request, exc)
        return redirect("journal_detail", pk=pk)


# ---------------------------------------------------------------- reorder levels and low-stock alerts (E6.3)

class ReorderLevels(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Minimum, reorder quantity and maximum per material or style, per factory or for all factories (INV-06)."""

    screen_code = "inventory.reorder"

    def _ctx(self, request, vals=None):
        return {"rows": alert_service.level_rows(request.user), "vals": vals or {},
                "materials": [(f"m:{m.pk}", m.name) for m in Material.objects.filter(is_active=True).order_by("name")],
                "styles": [(f"s:{st.pk}", f"{st.style_no} — {st.name}") for st in Style.objects.filter(is_archived=False)],
                "factory": request.factory,
                "can_edit": request.user.has_screen_perm("inventory.reorder", "edit")}

    def get(self, request):
        return render(request, "inventory/reorder.html", self._ctx(request))

    def post(self, request):
        p = request.POST
        if not request.user.has_screen_perm("inventory.reorder", "edit"):
            raise PermissionDenied
        try:
            if p.get("action") == "delete":
                level = get_object_or_404(ReorderLevel, pk=p.get("level"))
                alert_service.delete_level(level, user=request.user)
                messages.success(request, "Level removed.")
                return redirect("reorder_levels")
            kind, _, pk = (p.get("item") or "").partition(":")
            if kind == "m":
                item = get_object_or_404(Material, pk=int(pk))
            elif kind == "s":
                item = get_object_or_404(Style, pk=int(pk))
            else:
                raise ValueError("Choose a material or a style.")
            factory = request.factory           # None in "All factories" mode = a level for all factories together
            alert_service.set_level(
                item=item, factory=factory, user=request.user,
                min_qty=_decimal(p.get("min_qty"), "Minimum"), reorder_qty=_decimal(p.get("reorder_qty"), "Reorder quantity", Decimal("0")),
                max_qty=_decimal(p.get("max_qty"), "Maximum", Decimal("0")))
        except (ValueError, BusinessRuleError) as exc:
            _messages_for(request, exc)
            return render(request, "inventory/reorder.html", self._ctx(request, p))
        messages.success(request, "Level saved. Stock below the minimum will raise an alert at the next check.")
        return redirect("reorder_levels")


class StockAlerts(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Items below their minimum right now, and the recent history. Each crossing is one alert (E6.3)."""

    screen_code = "inventory.alerts"

    def get(self, request):
        visible = StockAlert.visible_to(request.user)
        return render(request, "inventory/alerts.html", {
            "rows": alert_service.alert_rows(request.user),
            "history": visible.filter(cleared_at__isnull=False).select_related("factory", "material", "style")[:30],
            "can_edit": request.user.has_screen_perm("inventory.alerts", "edit")})

    def post(self, request):
        if not request.user.has_screen_perm("inventory.alerts", "edit"):
            raise PermissionDenied
        action = request.POST.get("action")
        try:
            if action == "check":
                raised = alert_service.check_low_stock(_company())
                messages.success(request, f"{len(raised)} new alert{'s' if len(raised) != 1 else ''}." if raised else "Nothing new below its minimum.")
            elif action == "ack":
                alert = get_object_or_404(StockAlert.visible_to(request.user), pk=request.POST.get("alert"))
                alert_service.acknowledge(alert, user=request.user)
                messages.success(request, "Marked as seen.")
        except BusinessRuleError as exc:
            _messages_for(request, exc)
        return redirect("stock_alerts")


# ---------------------------------------------------------------- transfers (E6.2)

class TransferList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "inventory.transfer"

    def get(self, request):
        qs = StockTransfer.visible_to(request.user).select_related("from_factory", "to_factory", "from_location", "to_location")
        return render(request, "inventory/transfer_list.html", {
            "transfers": qs[:200], "can_create": request.user.has_screen_perm("inventory.transfer", "create"),
        })


class TransferNew(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "inventory.transfer"
    screen_action = "create"

    def _ctx(self, request, rows=None, data=None):
        mats, skus = item_choices()
        rolls = RollBalance.objects.for_user(request.user).filter(qty__gt=0).select_related("roll__material", "location")
        return {
            "factories_from": Factory.objects.for_user(request.user).filter(is_active=True),
            "factories_to": Factory.objects.filter(is_active=True),
            "locations": Location.objects.filter(factory__is_active=True, is_active=True).select_related("factory"),
            "mats": mats, "skus": skus, "rolls": rolls, "rows": rows or [{}, {}, {}], "d": data or {},
            "documents": StockTransfer.Document.choices,
        }

    def get(self, request):
        return render(request, "inventory/transfer_form.html", self._ctx(request))

    def post(self, request):
        p = request.POST
        rows, lines = [], []
        try:
            for i, value in enumerate(p.getlist("item")):
                qty = p.getlist("qty")[i]
                rows.append({"item": value, "qty": qty, "roll": p.getlist("roll")[i]})
                if not value:
                    continue
                roll = get_object_or_404(FabricRoll, pk=p.getlist("roll")[i]) if p.getlist("roll")[i] else None
                lines.append((parse_item(value), _decimal(qty, "Quantity"), roll))
            t = transfers.create_transfer(
                company=_company(), from_factory=get_object_or_404(Factory.objects.for_user(request.user), pk=p.get("from_factory")),
                from_location=get_object_or_404(Location, pk=p.get("from_location")),
                to_factory=get_object_or_404(Factory, pk=p.get("to_factory")),
                to_location=get_object_or_404(Location, pk=p.get("to_location")),
                date=date.fromisoformat(p.get("date")), lines=lines, user=request.user,
                document_type=p.get("document_type", "challan"), vehicle_no=p.get("vehicle_no", ""), remarks=p.get("remarks", ""),
            )
        except (ValueError, BusinessRuleError) as exc:
            _messages_for(request, exc)
            return render(request, "inventory/transfer_form.html", self._ctx(request, rows, p))
        messages.success(request, "Transfer saved as a draft. Review it, then issue it.")
        return redirect("transfer_detail", pk=t.pk)


class TransferDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "inventory.transfer"

    def _t(self, request, pk):
        return get_object_or_404(StockTransfer.visible_to(request.user).select_related(
            "from_factory", "to_factory", "from_location", "to_location"), pk=pk)

    def get(self, request, pk):
        t = self._t(request, pk)
        from core.integrations import eway

        return render(request, "inventory/transfer_detail.html", {
            "t": t, "lines": t.lines.select_related("material", "sku__style", "sku__colour", "sku__size", "roll"),
            "can_edit": request.user.has_screen_perm("inventory.transfer", "edit"),
            "can_issue": request.user.can_access_factory(t.from_factory),
            "can_receive": request.user.can_access_factory(t.to_factory),
            "eway_ready": not isinstance(eway.get_provider(), eway.NullEwayBillProvider),
        })

    def post(self, request, pk):
        t = self._t(request, pk)
        if not request.user.has_screen_perm("inventory.transfer", "edit"):
            raise PermissionDenied
        action = request.POST.get("action")
        try:
            if action == "issue":
                t = transfers.issue_transfer(t, user=request.user)
                messages.success(request, f"{t.number} issued." + (" Stock is in transit." if t.is_inter_factory else ""))
            elif action == "receive":
                transfers.receive_transfer(t, user=request.user)
                messages.success(request, "Received into the destination location.")
            elif action == "eway":
                t.eway_bill_no = request.POST.get("eway_bill_no", "").strip()[:20]
                t.vehicle_no = request.POST.get("vehicle_no", t.vehicle_no).strip()[:20]
                t.save(update_fields=["eway_bill_no", "vehicle_no"])
                messages.success(request, "Transport details saved.")
        except BusinessRuleError as exc:
            messages.error(request, str(exc))
        return redirect("transfer_detail", pk=pk)


# ---------------------------------------------------------------- opening stock

class OpeningStockView(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "inventory.opening"

    def _ctx(self, request, rows=None, d=None):
        mats, skus = item_choices()
        return {
            "company": _company(), "factory": request.factory,
            "locations": Location.objects.filter(factory=request.factory, is_active=True).exclude(loc_type="transit"),
            "mats": mats, "skus": skus, "rows": rows or [{} for _ in range(6)], "d": d or {},
            "existing": OpeningStock.objects.filter(factory__in=request.active_factories).select_related("factory", "location"),
            "can_create": request.user.has_screen_perm("inventory.opening", "create"),
        }

    def get(self, request):
        if back := need_factory(request, "stock_enquiry"):
            return back
        return render(request, "inventory/opening.html", self._ctx(request))

    def post(self, request):
        if not request.user.has_screen_perm("inventory.opening", "create"):
            raise PermissionDenied
        p = request.POST
        company = _company()
        rows, entries = [], []
        try:
            factory = require_active_factory(request)
            location = get_object_or_404(Location, pk=p.get("location"))
            n = len(p.getlist("item"))
            for i in range(n):
                row = {k: p.getlist(k)[i] for k in ("item", "qty", "rate", "roll_no", "lot", "gsm", "width", "length", "supplier")}
                rows.append(row)
                if not row["item"]:
                    continue
                gsm = row["gsm"].strip()
                entries.append(opening_service.OpeningItem(
                    item=parse_item(row["item"]), qty=_decimal(row["qty"], "Quantity"), rate=_decimal(row["rate"], "Rate"),
                    vendor_roll_no=row["roll_no"], lot_no=row["lot"], gsm=int(gsm) if gsm else None,
                    width_cm=_decimal(row["width"], "Width", Decimal("0")) or None,
                    length_m=_decimal(row["length"], "Length", Decimal("0")) or None,
                    supplier=Party.objects.filter(pk=row["supplier"]).first() if row["supplier"] else None,
                ))
            doc = opening_service.post_opening_stock(
                company=company, factory=factory, location=location, entries=entries, user=request.user,
                date=date.fromisoformat(p["date"]) if p.get("date") else None)
        except (ValueError, BusinessRuleError, ValidationError) as exc:
            _messages_for(request, exc)
            return render(request, "inventory/opening.html", self._ctx(request, rows, p))
        messages.success(request, f"Opening stock {doc.number} posted: value {doc.total_value}.")
        return redirect("opening_stock")
