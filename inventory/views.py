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
from masters.models import SKU, Material, Party, Style

from . import barcode
from .models import FabricRoll, OpeningStock, RollBalance, StockBalance, StockTransfer
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
        fields = ["valuation_method", "allow_negative_stock", "po_approval_limit"]
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
        if g.get("factory"):
            qs = qs.filter(factory_id=g["factory"])
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
            "factories": Factory.objects.for_user(request.user),
            "locations": Location.objects.filter(factory__in=Factory.objects.for_user(request.user)),
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

LAYOUTS = {"a4": "A4 sheet", "thermal4": "Thermal 4 x 2 in", "thermal2": "Thermal 2 x 1 in"}


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
            "company": _company(), "factories": Factory.objects.for_user(request.user).filter(is_active=True),
            "locations": Location.objects.filter(factory__in=Factory.objects.for_user(request.user), is_active=True).exclude(loc_type="transit"),
            "mats": mats, "skus": skus, "rows": rows or [{} for _ in range(6)], "d": d or {},
            "existing": OpeningStock.objects.filter(factory__in=Factory.objects.for_user(request.user)).select_related("factory", "location"),
            "can_create": request.user.has_screen_perm("inventory.opening", "create"),
        }

    def get(self, request):
        return render(request, "inventory/opening.html", self._ctx(request))

    def post(self, request):
        if not request.user.has_screen_perm("inventory.opening", "create"):
            raise PermissionDenied
        p = request.POST
        company = _company()
        rows, entries = [], []
        try:
            factory = get_object_or_404(Factory.objects.for_user(request.user), pk=p.get("factory"))
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
