from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views import View

from core.models import Company, Factory
from core.scoping import ScreenPermissionMixin

from .models import TaxSetting
from .services import set_tax_status


class TaxStatusForm(forms.Form):
    kind = forms.ChoiceField(choices=TaxSetting.Kind.choices, label="Tax")
    enabled = forms.TypedChoiceField(
        choices=[("True", "Switch on"), ("False", "Switch off")], coerce=lambda v: v == "True", label="Action"
    )
    effective_from = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    registration_number = forms.CharField(required=False, label="GSTIN / TAN", max_length=15)
    factory = forms.ModelChoiceField(
        queryset=Factory.objects.none(), required=False, empty_label="Whole company",
        help_text="Only if a factory has its own GSTIN or its own status",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["factory"].queryset = Factory.objects.filter(is_active=True)


class TaxSettingsView(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "tax.settings"

    def _render(self, request, form):
        company = Company.objects.get(setup_complete=True)
        return render(request, "tax/settings.html", {
            "form": form, "settings": TaxSetting.objects.filter(company=company).select_related("factory"),
            "can_edit": request.user.has_screen_perm("tax.settings", "edit"),
        })

    def get(self, request):
        return self._render(request, TaxStatusForm())

    def post(self, request):
        if not request.user.has_screen_perm("tax.settings", "edit"):
            return self._render(request, TaxStatusForm())
        form = TaxStatusForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            try:
                set_tax_status(
                    company=Company.objects.get(setup_complete=True), kind=d["kind"], enabled=d["enabled"],
                    effective_from=d["effective_from"], registration_number=d["registration_number"],
                    factory=d["factory"],
                )
            except ValidationError as exc:
                form.add_error(None, "; ".join(exc.messages))
            else:
                messages.success(request, "Tax status updated. Earlier documents are untouched.")
                return redirect("tax_settings")
        return self._render(request, form)


class HsnDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    """An HSN code and its value-based GST slabs. Slabs are append-only: a change is a new dated row."""

    screen_code = "tax.hsn"

    def _ctx(self, request, hsn, form=None):
        from masters.forms import HsnSlabForm

        return {"hsn": hsn, "slabs": hsn.slabs.all(), "form": form or HsnSlabForm(),
                "can_edit": request.user.has_screen_perm("tax.hsn", "edit")}

    def get(self, request, pk):
        from django.shortcuts import get_object_or_404

        from .models import HSN

        return render(request, "tax/hsn_detail.html", self._ctx(request, get_object_or_404(HSN, pk=pk)))

    def post(self, request, pk):
        from django.core.exceptions import PermissionDenied
        from django.shortcuts import get_object_or_404

        from masters.forms import HsnSlabForm

        from .models import HSN

        if not request.user.has_screen_perm("tax.hsn", "edit"):
            raise PermissionDenied
        hsn = get_object_or_404(HSN, pk=pk)
        form = HsnSlabForm(request.POST)
        if form.is_valid():
            slab = form.save(commit=False)
            slab.hsn = hsn
            slab.save()
            messages.success(request, "Slab added. It applies from its effective date; earlier bills keep their rate.")
            return redirect("hsn_detail", pk=pk)
        return render(request, "tax/hsn_detail.html", self._ctx(request, hsn, form))
