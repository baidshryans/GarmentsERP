from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from core.exceptions import BusinessRuleError
from core.models import Company, Factory, Location
from core.scoping import ScreenPermissionMixin
from tax.models import HSN

from . import forms as f
from .models import (
    SKU, Colour, CustomerRate, Material, Party, PartyAddress, PriceList, PriceListRate, Process, RouteStep,
    RouteTemplate, Size, Style,
)
from .services import boms, imports, parties, routes, styles


def _company():
    return Company.objects.get(setup_complete=True)


def _messages_for(request, exc):
    if isinstance(exc, ValidationError):
        for m in exc.messages:
            messages.error(request, m)
    else:
        messages.error(request, str(exc))


def _decimal(text, label, default=None):
    text = (text or "").strip().replace(",", "")
    if not text:
        if default is not None:
            return default
        raise ValueError(f"{label} is required.")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError(f"{label}: '{text}' is not a number.")


# ---------------------------------------------------------------- generic simple masters

SIMPLE = {
    "unit": dict(model="Unit", form=f.UnitForm, screen="masters.basics", title="Units", tabs=True,
                 cols=[("Code", "code"), ("Name", "name"), ("Kind", "get_kind_display")]),
    "size": dict(model="Size", form=f.SizeForm, screen="masters.basics", title="Sizes", tabs=True,
                 cols=[("Code", "code"), ("Name", "name"), ("Order", "sort_order")]),
    "colour": dict(model="Colour", form=f.ColourForm, screen="masters.basics", title="Colours", tabs=True,
                   cols=[("Name", "name"), ("Code", "code")]),
    "product": dict(model="Product", form=f.ProductForm, screen="masters.basics", title="Products", tabs=True,
                    cols=[("Code", "code"), ("Name", "name")]),
    "material": dict(model="Material", form=f.MaterialForm, screen="masters.material", title="Materials",
                     cols=[("Code", "code"), ("Name", "name"), ("Kind", "get_kind_display"), ("Unit", "unit"), ("GSM", "gsm")]),
    "process": dict(model="Process", form=f.ProcessForm, screen="masters.process", title="Processes",
                    cols=[("Code", "code"), ("Name", "name"), ("Kind", "get_kind_display")]),
    "pricelist": dict(model="PriceList", form=f.PriceListForm, screen="masters.pricelist", title="Price lists",
                      cols=[("Name", "name"), ("Kind", "get_kind_display")]),
    "hsn": dict(model="HSN", form=f.HsnForm, screen="tax.hsn", title="HSN codes",
                cols=[("Code", "code"), ("Description", "description")]),
}


def _model(name):
    from tax.models import HSN as HSNModel

    from . import models as m

    return HSNModel if name == "HSN" else getattr(m, name)


class SimpleList(LoginRequiredMixin, ScreenPermissionMixin, View):
    key = None

    def dispatch(self, request, *args, **kwargs):
        self.cfg = SIMPLE[self.key]
        self.screen_code = self.cfg["screen"]
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        rows = []
        for obj in _model(self.cfg["model"]).objects.all():
            cells = []
            for _, attr in self.cfg["cols"]:
                v = getattr(obj, attr)
                cells.append(v() if callable(v) else v)
            rows.append({"obj": obj, "cells": cells, "active": getattr(obj, "is_active", True)})
        return render(request, "masters/simple_list.html", {
            "cfg": self.cfg, "key": self.key, "rows": rows, "headers": [h for h, _ in self.cfg["cols"]],
            "can_create": request.user.has_screen_perm(self.cfg["screen"], "create"),
            "can_edit": request.user.has_screen_perm(self.cfg["screen"], "edit"),
        })


class SimpleSave(LoginRequiredMixin, ScreenPermissionMixin, View):
    key = None

    def dispatch(self, request, *args, **kwargs):
        self.cfg = SIMPLE[self.key]
        self.screen_code = self.cfg["screen"]
        self.screen_action = "edit" if kwargs.get("pk") else "create"
        return super().dispatch(request, *args, **kwargs)

    def _obj(self, pk):
        return get_object_or_404(_model(self.cfg["model"]), pk=pk) if pk else None

    def get(self, request, pk=None):
        return render(request, "core/form.html", {"form": self.cfg["form"](instance=self._obj(pk)), "title": self.cfg["title"]})

    def post(self, request, pk=None):
        form = self.cfg["form"](request.POST, instance=self._obj(pk))
        if form.is_valid():
            form.save()
            messages.success(request, "Saved.")
            if self.key == "hsn" and not pk:
                return redirect("hsn_detail", pk=form.instance.pk)
            return redirect(f"{self.key}_list")
        return render(request, "core/form.html", {"form": form, "title": self.cfg["title"]})


# ---------------------------------------------------------------- styles (E2.1)

class StyleList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "masters.style"

    def get(self, request):
        q = request.GET.get("q", "").strip()
        qs = Style.objects.select_related("product")
        if not request.GET.get("archived"):
            qs = qs.filter(is_archived=False)
        if q:
            qs = qs.filter(Q(style_no__icontains=q) | Q(name__icontains=q))
        return render(request, "masters/style_list.html", {
            "styles": qs[:300], "q": q, "archived": bool(request.GET.get("archived")),
            "can_create": request.user.has_screen_perm("masters.style", "create"),
        })


class StyleSave(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "masters.style"

    def dispatch(self, request, *args, **kwargs):
        self.screen_action = "edit" if kwargs.get("pk") else "create"
        return super().dispatch(request, *args, **kwargs)

    def _obj(self, pk):
        return get_object_or_404(Style, pk=pk) if pk else None

    def get(self, request, pk=None):
        return render(request, "masters/style_form.html", {"form": f.StyleForm(instance=self._obj(pk)), "style": self._obj(pk)})

    def post(self, request, pk=None):
        style = self._obj(pk)
        form = f.StyleForm(request.POST, request.FILES, instance=style)
        if form.is_valid():
            try:
                d = form.cleaned_data
                if style is None:
                    extra = {k: d[k] for k in ("description", "hsn", "default_route", "mrp", "image", "is_archived")}
                    style = styles.create_style(
                        company=_company(), style_no=d["style_no"], product=d["product"], name=d["name"],
                        colours=d["colours"], sizes=d["sizes"], **extra,
                    )
                else:
                    form.save()
                    styles.sync_variants(style, colours=d["colours"], sizes=d["sizes"], company=_company())
                    if "image" in form.changed_data and style.image:
                        styles.make_thumbnail(style)
            except (BusinessRuleError, ValidationError) as exc:
                _messages_for(request, exc)
            else:
                messages.success(request, f"{style.style_no} saved with {style.skus.filter(is_active=True).count()} SKUs.")
                return redirect("style_detail", pk=style.pk)
        return render(request, "masters/style_form.html", {"form": form, "style": style})


class StyleDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "masters.style"

    def get(self, request, pk):
        style = get_object_or_404(Style.objects.select_related("product", "hsn", "default_route"), pk=pk)
        sizes = [ss.size for ss in style.style_sizes.select_related("size").order_by("size__sort_order")]
        colours = [sc.colour for sc in style.style_colours.select_related("colour").order_by("colour__name")]
        by_key = {(s.colour_id, s.size_id): s for s in style.skus.all()}
        grid = [{"colour": c, "cells": [by_key.get((c.pk, s.pk)) for s in sizes]} for c in colours]
        bom = boms.current_version(style)
        return render(request, "masters/style_detail.html", {
            "style": style, "sizes": sizes, "grid": grid, "bom": bom,
            "bom_lines": bom.lines.select_related("material__unit").prefetch_related("size_overrides") if bom else [],
            "bom_charges": bom.charges.all() if bom else [],
            "versions": style.bom_versions.all(),
            "can_edit": request.user.has_screen_perm("masters.style", "edit"),
            "can_bom": request.user.has_screen_perm("masters.bom", "edit"),
            "route_steps": style.default_route.steps.select_related("process") if style.default_route else [],
        })


class BomEdit(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "masters.bom"
    screen_action = "edit"

    def _context(self, style, rows=None, charge_rows=None):
        sizes = [ss.size for ss in style.style_sizes.select_related("size").order_by("size__sort_order")]
        bom = boms.current_version(style)
        if rows is None:
            rows = []
            if bom:
                for line in bom.lines.select_related("material").prefetch_related("size_overrides"):
                    rows.append({"material": str(line.material_id), "qty": line.qty_per_piece, "wastage": line.wastage_pct,
                                 "sizes": {str(o.size_id): o.qty_per_piece for o in line.size_overrides.all()}})
            rows = rows or [{}]
        if charge_rows is None:
            charge_rows = [{"description": c.description, "process": str(c.process_id or ""), "amount": c.amount_per_piece}
                           for c in (bom.charges.all() if bom else [])]
        return {
            "style": style, "sizes": sizes, "rows": rows + [{}, {}], "charge_rows": charge_rows + [{}, {}],
            "materials": Material.objects.filter(is_active=True).select_related("unit"),
            "processes": Process.objects.filter(is_active=True), "bom": bom,
        }

    def get(self, request, pk):
        style = get_object_or_404(Style, pk=pk)
        return render(request, "masters/bom_form.html", self._context(style))

    def post(self, request, pk):
        style = get_object_or_404(Style, pk=pk)
        sizes = [ss.size for ss in style.style_sizes.select_related("size")]
        post = request.POST
        mats, qtys, wastes = post.getlist("material"), post.getlist("qty"), post.getlist("wastage")
        rows, specs, charge_rows = [], [], None
        try:
            for i, mid in enumerate(mats):
                size_vals = {str(s.pk): post.getlist(f"size_{s.pk}")[i] for s in sizes}
                rows.append({"material": mid, "qty": qtys[i], "wastage": wastes[i], "sizes": size_vals})
                if not mid:
                    continue
                specs.append(boms.BomLineSpec(
                    material=get_object_or_404(Material, pk=mid), qty_per_piece=_decimal(qtys[i], "Consumption"),
                    wastage_pct=_decimal(wastes[i], "Wastage", Decimal("0")),
                    size_qty={s: _decimal(size_vals[str(s.pk)], "Size consumption") for s in sizes if size_vals[str(s.pk)].strip()},
                ))
            charge_rows, charges = [], []  # noqa: F841
            for i, desc in enumerate(post.getlist("charge_desc")):
                amt, proc = post.getlist("charge_amount")[i], post.getlist("charge_process")[i]
                charge_rows.append({"description": desc, "process": proc, "amount": amt})
                if desc.strip():
                    charges.append(boms.BomChargeSpec(
                        desc.strip(), _decimal(amt, "Charge amount"), Process.objects.filter(pk=proc).first() if proc else None))
            version, new = boms.save_bom(style, lines=specs, charges=charges, user=request.user, notes=post.get("notes", ""))
        except (ValueError, BusinessRuleError) as exc:
            _messages_for(request, exc)
            return render(request, "masters/bom_form.html", self._context(style, rows, charge_rows))
        if new:
            messages.warning(request, f"Lots already use the previous BOM, so this was saved as version {version.version_no}. Old lots keep the old version.")
        else:
            messages.success(request, f"BOM version {version.version_no} saved.")
        return redirect("style_detail", pk=style.pk)


# ---------------------------------------------------------------- routes (E2.3)

class RouteList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "masters.route"

    def get(self, request):
        return render(request, "masters/route_list.html", {
            "routes": RouteTemplate.objects.prefetch_related("steps__process"),
            "can_create": request.user.has_screen_perm("masters.route", "create"),
        })


class RouteSave(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "masters.route"

    def dispatch(self, request, *args, **kwargs):
        self.screen_action = "edit" if kwargs.get("pk") else "create"
        return super().dispatch(request, *args, **kwargs)

    def _context(self, route, rows=None, name=None):
        if rows is None:
            rows = [{"process": str(s.process_id), "mandatory": s.is_mandatory, "assignment": s.assignment,
                     "factory": str(s.default_factory_id or ""), "party": str(s.default_party_id or ""), "rate": s.rate}
                    for s in route.steps.all()] if route else []
        return {
            "route": route, "rows": rows + [{"mandatory": True}] * 2, "name": name if name is not None else (route.name if route else ""),
            "processes": Process.objects.filter(is_active=True), "factories": Factory.objects.filter(is_active=True),
            "fabricators": Party.objects.filter(is_fabricator=True, is_active=True),
        }

    def get(self, request, pk=None):
        route = get_object_or_404(RouteTemplate, pk=pk) if pk else None
        return render(request, "masters/route_form.html", self._context(route))

    def post(self, request, pk=None):
        route = get_object_or_404(RouteTemplate, pk=pk) if pk else None
        post = request.POST
        rows, specs = [], []
        try:
            for i, pid in enumerate(post.getlist("process")):
                row = {"process": pid, "mandatory": f"mandatory_{i}" in post, "assignment": post.getlist("assignment")[i],
                       "factory": post.getlist("factory")[i], "party": post.getlist("party")[i], "rate": post.getlist("rate")[i]}
                rows.append(row)
                if not pid:
                    continue
                specs.append(routes.StepSpec(
                    process=get_object_or_404(Process, pk=pid), is_mandatory=row["mandatory"], assignment=row["assignment"],
                    default_factory=Factory.objects.filter(pk=row["factory"]).first() if row["factory"] else None,
                    default_party=Party.objects.filter(pk=row["party"]).first() if row["party"] else None,
                    rate=_decimal(row["rate"], "Rate", Decimal("0")),
                ))
            saved = routes.save_route(name=post.get("name", "").strip(), steps=specs, template=route)
        except (ValueError, BusinessRuleError, ValidationError) as exc:
            _messages_for(request, exc)
            return render(request, "masters/route_form.html", self._context(route, rows, post.get("name", "")))
        messages.success(request, "Route saved.")
        return redirect("route_list")


# ---------------------------------------------------------------- parties (E3.1)

PARTY_ROLES = {"customer": "is_customer", "vendor": "is_vendor", "fabricator": "is_fabricator",
               "agent": "is_agent", "transporter": "is_transporter"}


class PartyList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "masters.party"

    def get(self, request):
        role, q = request.GET.get("role", ""), request.GET.get("q", "").strip()
        qs = Party.objects.all()
        if role in PARTY_ROLES:
            qs = qs.filter(**{PARTY_ROLES[role]: True})
        can_phone = request.user.can_view_field("customer_phone")
        if q:
            cond = Q(name__icontains=q) | Q(code__icontains=q)
            if can_phone:
                cond |= Q(mobile__icontains=q)
            qs = qs.filter(cond)
        return render(request, "masters/party_list.html", {
            "parties": qs[:300], "role": role, "q": q, "roles": list(PARTY_ROLES), "can_phone": can_phone,
            "can_create": request.user.has_screen_perm("masters.party", "create"),
        })


class PartySave(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "masters.party"

    def dispatch(self, request, *args, **kwargs):
        self.screen_action = "edit" if kwargs.get("pk") else "create"
        return super().dispatch(request, *args, **kwargs)

    def _obj(self, pk):
        return get_object_or_404(Party, pk=pk) if pk else None

    def _can_phone(self, request, party):
        return request.user.can_view_field("customer_phone")

    def get(self, request, pk=None):
        party = self._obj(pk)
        form = f.PartyForm(instance=party, initial={"is_customer": request.GET.get("role") == "customer",
                                                    "is_fabricator": request.GET.get("role") == "fabricator",
                                                    "is_vendor": request.GET.get("role") == "vendor"} if not party else None)
        return render(request, "masters/party_form.html", {"form": form, "party": party})

    def post(self, request, pk=None):
        party = self._obj(pk)
        form = f.PartyForm(request.POST, instance=party)
        if form.is_valid():
            try:
                if party is None:
                    party = parties.create_party(company=_company(), **form.cleaned_data)
                else:
                    party = parties.update_party(party, **form.cleaned_data)
            except ValidationError as exc:
                for m in exc.messages:
                    form.add_error(None, m)
            except BusinessRuleError as exc:
                form.add_error("mobile", str(exc))
            else:
                messages.success(request, f"{party.name} saved.")
                return redirect("party_detail", pk=party.pk)
        return render(request, "masters/party_form.html", {"form": form, "party": party})


class PartyDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "masters.party"

    def get(self, request, pk):
        party = get_object_or_404(Party, pk=pk)
        return render(request, "masters/party_detail.html", {
            "party": party, "addresses": party.addresses.all(), "address_form": f.PartyAddressForm(),
            "can_phone": request.user.can_view_field("customer_phone"),
            "can_edit": request.user.has_screen_perm("masters.party", "edit"),
        })

    def post(self, request, pk):
        if not request.user.has_screen_perm("masters.party", "edit"):
            raise PermissionDenied
        party = get_object_or_404(Party, pk=pk)
        form = f.PartyAddressForm(request.POST)
        if form.is_valid():
            addr = form.save(commit=False)
            addr.party = party
            if addr.kind == "billing" and party.addresses.filter(kind="billing").exists():
                messages.error(request, "A party has only one billing address. Edit it in the admin or add a shipping address.")
            else:
                addr.save()
                messages.success(request, "Address added.")
        else:
            messages.error(request, "Please complete the address.")
        return redirect("party_detail", pk=pk)


# ---------------------------------------------------------------- price lists

class PriceListDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "masters.pricelist"

    def _ctx(self, request, plist, form=None):
        return {"plist": plist, "rates": plist.rates.select_related("style", "size"),
                "form": form or f.PriceListRateForm(),
                "can_edit": request.user.has_screen_perm("masters.pricelist", "edit")}

    def get(self, request, pk):
        plist = get_object_or_404(PriceList, pk=pk)
        return render(request, "masters/pricelist_detail.html", self._ctx(request, plist))

    def post(self, request, pk):
        if not request.user.has_screen_perm("masters.pricelist", "edit"):
            raise PermissionDenied
        plist = get_object_or_404(PriceList, pk=pk)
        form = f.PriceListRateForm(request.POST)
        if form.is_valid():
            rate = form.save(commit=False)
            rate.price_list = plist
            rate.save()
            messages.success(request, "Rate added. It applies to documents dated from its effective date; earlier ones keep their rate.")
            return redirect("pricelist_detail", pk=pk)
        return render(request, "masters/pricelist_detail.html", self._ctx(request, plist, form))


# ---------------------------------------------------------------- type-ahead search (E2.4)

class Search(LoginRequiredMixin, View):
    def get(self, request):
        q = request.GET.get("q", "").strip()
        user = request.user
        groups = []
        if len(q) >= 2:
            if user.has_screen_perm("masters.style", "view"):
                items = Style.objects.filter(Q(style_no__icontains=q) | Q(name__icontains=q))[:6]
                groups.append(("Styles", [(f"{s.style_no} — {s.name}", "style_detail", s.pk) for s in items]))
                skus = SKU.objects.filter(barcode__startswith=q).select_related("style", "colour", "size")[:4] if q.isdigit() else []
                groups.append(("SKUs", [(f"{k.barcode} · {k}", "style_detail", k.style_id) for k in skus]))
            if user.has_screen_perm("masters.material", "view"):
                items = Material.objects.filter(Q(code__icontains=q) | Q(name__icontains=q))[:6]
                groups.append(("Materials", [(str(m), "material_edit", m.pk) for m in items]))
            if user.has_screen_perm("masters.party", "view"):
                cond = Q(name__icontains=q) | Q(code__icontains=q)
                if user.can_view_field("customer_phone"):
                    cond |= Q(mobile__icontains=q)
                items = Party.objects.filter(cond)[:6]
                groups.append(("Parties", [(f"{p.name} · {', '.join(p.roles)}", "party_detail", p.pk) for p in items]))
        groups = [(title, items) for title, items in groups if items]
        return render(request, "masters/search_results.html", {"groups": groups, "q": q})


# ---------------------------------------------------------------- Excel import

IMPORT_PERMISSION = {"parties": "masters.party", "styles": "masters.style", "materials": "masters.material",
                     "opening": "ledger.opening", "opening_stock": "inventory.opening"}


class ExcelImport(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "masters.import"

    def _ctx(self, request, result=None, kind=""):
        kinds = [(k, spec["title"], spec["notes"]) for k, spec in imports.TEMPLATES.items()
                 if request.user.has_screen_perm(IMPORT_PERMISSION[k], "create")]
        factories = Factory.objects.for_user(request.user).filter(is_active=True)
        return {"kinds": kinds, "result": result, "kind": kind, "factories": factories,
                "locations": Location.objects.filter(factory__in=factories, is_active=True).exclude(loc_type="transit")}

    def get(self, request):
        return render(request, "masters/import.html", self._ctx(request))

    def post(self, request):
        if not request.user.has_screen_perm("masters.import", "create"):
            raise PermissionDenied
        kind = request.POST.get("kind", "")
        if kind not in imports.TEMPLATES or not request.user.has_screen_perm(IMPORT_PERMISSION[kind], "create"):
            raise PermissionDenied
        upload = request.FILES.get("file")
        if upload is None:
            messages.error(request, "Choose an .xlsx file.")
            return render(request, "masters/import.html", self._ctx(request, kind=kind))
        factory = location = None
        if kind in ("opening", "opening_stock"):
            factory = get_object_or_404(Factory.objects.for_user(request.user), pk=request.POST.get("factory"))
        if kind == "opening_stock":
            location = get_object_or_404(Location, pk=request.POST.get("location"), factory=factory)
        commit = request.POST.get("mode") == "import"
        try:
            result = imports.run_import(kind=kind, fileobj=upload, company=_company(), user=request.user,
                                        factory=factory, location=location, commit=commit)
        except BusinessRuleError as exc:
            messages.error(request, str(exc))
            return render(request, "masters/import.html", self._ctx(request, kind=kind))
        if result.committed:
            messages.success(request, f"Imported {result.ok} rows.")
        elif result.clean:
            messages.success(request, f"Check passed: all {result.ok} rows are valid. Choose Import to save them.")
        else:
            messages.error(request, "Nothing was imported. Fix the rows below and upload again.")
        return render(request, "masters/import.html", self._ctx(request, result, kind))


def import_template(request, kind):
    from django.http import Http404, HttpResponse

    if not request.user.is_authenticated:
        raise PermissionDenied
    if kind not in imports.TEMPLATES or not request.user.has_screen_perm(IMPORT_PERMISSION[kind], "create"):
        raise Http404
    response = HttpResponse(
        imports.build_template(kind),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{kind}-import-template.xlsx"'
    return response


# ---------------------------------------------------------------- delete (masters are deletable while unused)

from core.crud import ObjectDelete  # noqa: E402


class SimpleDelete(ObjectDelete):
    key = None

    def dispatch(self, request, *args, **kwargs):
        self.screen_code = SIMPLE[self.key]["screen"]
        self.success_url_name = f"{self.key}_list"
        self.noun = SIMPLE[self.key]["title"].lower().rstrip("s") if self.key != "hsn" else "HSN code"
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, request, pk):
        return get_object_or_404(_model(SIMPLE[self.key]["model"]), pk=pk)


class StyleDelete(ObjectDelete):
    screen_code, success_url_name, noun = "masters.style", "style_list", "style"

    def get_object(self, request, pk):
        return get_object_or_404(Style, pk=pk)


class PartyDelete(ObjectDelete):
    screen_code, success_url_name, noun = "masters.party", "party_list", "party"

    def get_object(self, request, pk):
        return get_object_or_404(Party, pk=pk)


class RouteDelete(ObjectDelete):
    screen_code, success_url_name, noun = "masters.route", "route_list", "route template"

    def get_object(self, request, pk):
        return get_object_or_404(RouteTemplate, pk=pk)
