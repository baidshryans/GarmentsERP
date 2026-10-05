from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView

from core.exceptions import BusinessRuleError, FactoryNotAllowed
from core.scoping import ScreenPermissionMixin
from reports.services.overview import build_overview

from .forms import (
    CompanyStepForm, FactoryCreateForm, FactoryEditForm, FactoryStepForm, LocationForm, RoleForm,
    TaxStepForm, UserForm, YearStepForm,
)
from .models import Company, Factory, Role, User
from .services import active_factory
from .services.factories import create_factory
from .services.setup import run_setup


# ---------------- home ----------------

@login_required
def home(request):
    from .home_actions import home_actions

    ctx = build_overview(request.user)
    ctx["islands"] = home_actions(request.user)
    return render(request, "core/home.html", ctx)


@login_required
def help_page(request):
    """The setup guide and user guide, rendered from docs/SETUP_GUIDE.md. Every signed-in user may read it."""
    from .help import render_guide

    return render(request, "core/help.html", render_guide())


class PasswordChange(PasswordChangeView):
    """Every signed-in user can change their own password; the session stays signed in afterwards."""
    template_name = "registration/password_change_form.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        messages.success(self.request, "Your password has been changed.")
        return super().form_valid(form)


# ---------------- setup wizard (E1.1) ----------------

WIZARD_STEPS = ["company", "tax", "year", "factory", "review"]
STEP_LABELS = {"company": "Company", "tax": "Tax status", "year": "Financial year",
               "factory": "First factory", "review": "Review"}


def _stored(request, step):
    return request.session.get("setup", {}).get(step)


def _store(request, step, data):
    setup = request.session.get("setup", {})
    setup[step] = {k: v for k, v in data.items() if k != "csrfmiddlewaretoken"}
    request.session["setup"] = setup
    request.session.modified = True


def _build_form(step, request, data=None):
    initial = data if data is not None else _stored(request, step)
    company_data = _stored(request, "company") or {}
    year_data = _stored(request, "year") or {}
    if step == "company":
        return CompanyStepForm(initial) if initial is not None else CompanyStepForm()
    if step == "tax":
        kwargs = {"company_state": company_data.get("state_code"), "books_from": _parse_date(year_data.get("books_from"))}
        return TaxStepForm(initial, **kwargs) if initial is not None else TaxStepForm(**kwargs)
    if step == "year":
        return YearStepForm(initial) if initial is not None else YearStepForm()
    if step == "factory":
        if initial is not None:
            return FactoryStepForm(initial)
        return FactoryStepForm(initial={"state_code": company_data.get("state_code"), "city": company_data.get("city"),
                                        "address": company_data.get("address")})
    raise KeyError(step)


def _parse_date(value):
    from datetime import date

    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _collect(request):
    """Revalidate every stored step. Returns (cleaned dict, first invalid step or None)."""
    cleaned = {}
    for step in WIZARD_STEPS[:-1]:
        stored = _stored(request, step)
        if stored is None:
            return cleaned, step
        form = _build_form(step, request, stored)
        if not form.is_valid():
            return cleaned, step
        cleaned[step] = form.cleaned_data
    return cleaned, None


@login_required
def setup_wizard(request, step="company"):
    if Company.objects.filter(setup_complete=True).exists():
        return redirect("home")
    if not request.user.is_superuser:
        raise PermissionDenied("Only the administrator can run the first-install setup.")
    if step not in WIZARD_STEPS:
        return redirect("setup")

    idx = WIZARD_STEPS.index(step)
    # Cannot jump ahead of the first incomplete step.
    for earlier in WIZARD_STEPS[:idx]:
        if _stored(request, earlier) is None:
            return redirect("setup_step", step=earlier)

    if step == "review":
        cleaned, bad = _collect(request)
        if bad:
            messages.error(request, "Please complete this step first.")
            return redirect("setup_step", step=bad)
        if request.method == "POST":
            company_data = {
                **{k: cleaned["company"][k] for k in ("name", "legal_name", "address", "city", "state_code", "pincode", "pan")},
                "fy_start_month": cleaned["year"]["fy_start_month"], "books_from": cleaned["year"]["books_from"],
            }
            factory_data = {k: cleaned["factory"][k] for k in ("code", "name", "address", "city", "state_code", "gstin")}
            if not factory_data["gstin"] and cleaned["tax"].get("gst_registered"):
                factory_data["gstin"] = cleaned["tax"]["gstin"]
            try:
                run_setup(company_data=company_data, tax_data=cleaned["tax"], factory_data=factory_data,
                          admin_user=request.user)
            except Exception as exc:  # shown to the admin; the transaction has rolled back
                messages.error(request, f"Setup failed and nothing was saved: {exc}")
                return redirect("setup_step", step="review")
            request.session.pop("setup", None)
            messages.success(request, "Setup complete. Your chart of accounts, roles and defaults are ready.")
            return redirect("home")
        return render(request, "core/setup_review.html", {"cleaned": cleaned, **_wizard_context(step)})

    if request.method == "POST":
        form = _build_form(step, request, request.POST.dict())
        if form.is_valid():
            _store(request, step, request.POST.dict())
            return redirect("setup_step", step=WIZARD_STEPS[idx + 1])
    else:
        form = _build_form(step, request)
    return render(request, "core/setup_step.html", {"form": form, **_wizard_context(step)})


def _wizard_context(step):
    idx = WIZARD_STEPS.index(step)
    return {
        "step": step, "step_label": STEP_LABELS[step],
        "steps": [
            {"label": STEP_LABELS[s], "state": "done" if i < idx else "current" if i == idx else ""}
            for i, s in enumerate(WIZARD_STEPS)
        ],
        "back": WIZARD_STEPS[idx - 1] if idx else None,
    }


# ---------------- factories (E1.4) ----------------

class FactoryList(LoginRequiredMixin, ScreenPermissionMixin, ListView):
    screen_code = "core.factory"
    template_name = "core/factory_list.html"
    context_object_name = "factories"

    def get_queryset(self):
        return Factory.objects.for_user(self.request.user).prefetch_related("locations")


class FactoryCreate(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "core.factory"
    screen_action = "create"

    def get(self, request):
        return render(request, "core/form.html", {"form": FactoryCreateForm(), "title": "New factory"})

    def post(self, request):
        form = FactoryCreateForm(request.POST)
        if form.is_valid():
            company = Company.objects.get(setup_complete=True)
            try:
                create_factory(company=company, **form.cleaned_data)
            except Exception as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Factory added. It now appears in every factory filter.")
                return redirect("factory_list")
        return render(request, "core/form.html", {"form": form, "title": "New factory"})


class FactoryEdit(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "core.factory"
    screen_action = "edit"

    def _factory(self, request, pk):
        return get_object_or_404(Factory.objects.for_user(request.user), pk=pk)

    def get(self, request, pk):
        factory = self._factory(request, pk)
        return render(request, "core/factory_edit.html", {
            "form": FactoryEditForm(instance=factory), "factory": factory, "location_form": LocationForm(),
        })

    def post(self, request, pk):
        factory = self._factory(request, pk)
        form = FactoryEditForm(request.POST, instance=factory)
        if form.is_valid():
            form.save()
            messages.success(request, "Factory saved.")
            return redirect("factory_list")
        return render(request, "core/factory_edit.html", {"form": form, "factory": factory, "location_form": LocationForm()})


@login_required
def location_add(request, pk):
    if not request.user.has_screen_perm("core.factory", "edit"):
        raise PermissionDenied
    factory = get_object_or_404(Factory.objects.for_user(request.user), pk=pk)
    form = LocationForm(request.POST)
    if request.method == "POST" and form.is_valid():
        location = form.save(commit=False)
        location.factory = factory
        try:
            location.save()
            messages.success(request, "Location added.")
        except Exception:
            messages.error(request, "That factory already has a location with this name.")
    return redirect("factory_edit", pk=pk)


# ---------------- users (E1.5, E1.7) ----------------

class UserList(LoginRequiredMixin, ScreenPermissionMixin, ListView):
    screen_code = "core.user"
    template_name = "core/user_list.html"
    context_object_name = "users"
    queryset = User.objects.prefetch_related("roles", "allowed_factories").order_by("username")


class UserSave(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "core.user"
    screen_action = "edit"

    def dispatch(self, request, *args, **kwargs):
        if kwargs.get("pk") is None:
            self.screen_action = "create"
        return super().dispatch(request, *args, **kwargs)

    def _instance(self, pk):
        return get_object_or_404(User, pk=pk, is_superuser=False) if pk else None

    def get(self, request, pk=None):
        instance = self._instance(pk)
        return render(request, "core/form.html", {"form": UserForm(instance=instance), "title": "Edit user" if pk else "New user"})

    def post(self, request, pk=None):
        instance = self._instance(pk)
        form = UserForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "User saved. Changes apply from their next action.")
            return redirect("user_list")
        return render(request, "core/form.html", {"form": form, "title": "Edit user" if pk else "New user"})


# ---------------- roles (E1.6) ----------------

class RoleList(LoginRequiredMixin, ScreenPermissionMixin, ListView):
    screen_code = "core.role"
    template_name = "core/role_list.html"
    context_object_name = "roles"
    queryset = Role.objects.prefetch_related("users")


class RoleSave(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "core.role"
    screen_action = "edit"

    def dispatch(self, request, *args, **kwargs):
        if kwargs.get("pk") is None:
            self.screen_action = "create"
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk=None):
        role = get_object_or_404(Role, pk=pk) if pk else None
        return render(request, "core/role_form.html", {"form": RoleForm(role=role), "role": role})

    def post(self, request, pk=None):
        role = get_object_or_404(Role, pk=pk) if pk else None
        form = RoleForm(request.POST, role=role)
        if form.is_valid():
            form.save()
            messages.success(request, "Role saved. Changes apply at each user's next action.")
            return redirect("role_list")
        return render(request, "core/role_form.html", {"form": form, "role": role})


def _safe_next(request, fallback="home"):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    return nxt if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}) else reverse(fallback)


@login_required
def factory_select(request):
    """Pick the factory to work in (after login, when the user has several and no last-used one)."""
    if request.method == "POST":
        try:
            active_factory.switch(request, request.POST.get("factory", ""))
        except FactoryNotAllowed as exc:
            messages.error(request, str(exc))
        else:
            return redirect(_safe_next(request))
    factories = active_factory.allowed_factories(request.user)
    return render(request, "core/factory_select.html", {
        "factories": factories, "can_all": factories.count() > 1, "next": _safe_next(request),
    })


@login_required
def factory_switch(request):
    """Top-bar switcher: change the active factory and return to the page the user was on."""
    if request.method != "POST":
        return redirect("home")
    try:
        active_factory.switch(request, request.POST.get("factory", ""))
    except FactoryNotAllowed as exc:
        messages.error(request, str(exc))
    return redirect(_safe_next(request))


# ---------------- reset database (Settings) ----------------

class ResetDatabase(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Clears every transaction and keeps the masters. Superuser only, behind a typed phrase and the user's password."""

    screen_code = "core.reset"
    template = "core/reset_database.html"
    phrase = "RESET"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_superuser:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        from .services import reset

        return render(request, self.template, {"rows": reset.counts(), "phrase": self.phrase})

    def post(self, request):
        from .services import reset

        if request.POST.get("phrase", "").strip() != self.phrase:
            messages.error(request, f"Type {self.phrase} in capitals to confirm.")
        elif not request.user.check_password(request.POST.get("password", "")):
            messages.error(request, "That password is not right.")
        else:
            try:
                deleted, backup = reset.reset_transactions(user=request.user, backup=bool(request.POST.get("backup")))
            except BusinessRuleError as exc:
                messages.error(request, str(exc))
            else:
                note = f" A copy of the old database was saved as {backup.name}." if backup else ""
                messages.success(request, f"Database reset: {deleted} records cleared, masters kept.{note}")
                return redirect("home")
        return render(request, self.template, {"rows": reset.counts(), "phrase": self.phrase})
