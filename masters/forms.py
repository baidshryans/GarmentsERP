from django import forms

from core.models import Factory
from tax.models import HSN, HsnSlab

from .models import (
    Colour, Material, Party, PartyAddress, PriceList, PriceListRate, Process, Product, RouteTemplate, Size, Style, Unit,
)


class StyleForm(forms.ModelForm):
    colours = forms.ModelMultipleChoiceField(
        queryset=Colour.objects.filter(is_active=True), widget=forms.CheckboxSelectMultiple
    )
    sizes = forms.ModelMultipleChoiceField(
        queryset=Size.objects.filter(is_active=True), widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Style
        fields = ["style_no", "name", "product", "description", "hsn", "default_route", "mrp", "pieces_per_box", "image",
                  "is_archived"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}
        labels = {"style_no": "Style no", "hsn": "HSN code", "mrp": "MRP", "is_archived": "Archived"}

    def __init__(self, *args, gst_registered=False, **kwargs):
        super().__init__(*args, **kwargs)
        # the HSN code is needed every time only by a GST-registered company; otherwise it folds away with the rest
        self.more_fields = ["description", "mrp", "pieces_per_box", "image"] + ([] if gst_registered else ["hsn"]) + ["is_archived"]
        self.more_label = "description, MRP, pieces per box, image, " + ("" if gst_registered else "HSN code, ") + "archived"
        self.fields["hsn"].queryset = HSN.objects.filter(is_active=True)
        self.fields["default_route"].queryset = RouteTemplate.objects.filter(is_active=True)
        if self.instance.pk:
            self.fields["style_no"].disabled = True
            self.initial["colours"] = list(self.instance.style_colours.values_list("colour_id", flat=True))
            self.initial["sizes"] = list(self.instance.style_sizes.values_list("size_id", flat=True))

    def clean_style_no(self):
        return self.cleaned_data["style_no"].strip().upper()


class PartyForm(forms.ModelForm):
    class Meta:
        model = Party
        fields = [
            "name", "contact_person", "is_customer", "is_vendor", "is_fabricator", "is_agent", "is_transporter",
            "mobile", "mobile2", "mobile3", "landline", "email", "gstin", "pan", "category", "price_list",
            "discount_pct", "credit_limit", "credit_days", "payment_terms", "agent", "transporter", "destination",
            "tds_section", "is_active",
        ]
        labels = {
            "name": "Firm name", "is_customer": "Customer", "is_vendor": "Supplier", "is_fabricator": "Fabricator",
            "is_agent": "Agent", "is_transporter": "Transporter", "gstin": "GSTIN", "pan": "PAN",
            "discount_pct": "Discount %", "tds_section": "TDS section", "is_active": "Active",
        }

    def __init__(self, *args, gst_registered=False, **kwargs):
        super().__init__(*args, **kwargs)
        # three things are needed every time: the firm, what it is to us, and a mobile. A GST-registered company
        # also needs the GSTIN every time; otherwise it folds away with the rest.
        self.more_fields = (["contact_person", "mobile2", "mobile3", "landline", "email"]
                            + ([] if gst_registered else ["gstin"])
                            + ["pan", "tds_section", "category", "price_list", "discount_pct", "credit_limit", "credit_days",
                               "payment_terms", "agent", "transporter", "destination", "is_agent", "is_transporter", "is_active"])
        self.more_label = "contact, " + ("PAN and TDS" if gst_registered else "GSTIN and PAN") + ", selling terms, agent or transporter"
        self.fields["price_list"].queryset = PriceList.objects.filter(is_active=True)
        self.fields["agent"].queryset = Party.objects.filter(is_agent=True, is_active=True)
        self.fields["transporter"].queryset = Party.objects.filter(is_transporter=True, is_active=True)
        # The service normalises "+91 98765 43210" to ten digits, so allow typed spaces and a country code.
        for name, label, required in (("mobile", "Mobile", True), ("mobile2", "Other mobile", False),
                                      ("mobile3", "Other mobile 2", False)):
            self.fields[name] = forms.CharField(label=label, required=required, max_length=20)
        for name in ("discount_pct", "credit_limit", "credit_days"):
            self.fields[name].required = False
        self.fields["is_active"].initial = True
        if not self.instance.pk:
            self.initial.setdefault("discount_pct", 0)
            self.initial.setdefault("credit_limit", 0)
            self.initial.setdefault("credit_days", 0)

    def clean(self):
        data = super().clean()
        for name in ("discount_pct", "credit_limit", "credit_days"):
            if data.get(name) in (None, ""):
                data[name] = 0
        return data

    def validate_unique(self):
        pass  # duplicate mobiles are reported by the party service with the existing party's name

    def _post_clean(self):
        # The service validates and derives fields (state from GSTIN, mobile format) and owns the constraints.
        pass


class PartyAddressForm(forms.ModelForm):
    class Meta:
        model = PartyAddress
        fields = ["kind", "line1", "line2", "city", "state_code", "pincode"]


class PriceListRateForm(forms.ModelForm):
    class Meta:
        model = PriceListRate
        fields = ["style", "size", "min_qty", "rate", "effective_from"]
        widgets = {"effective_from": forms.DateInput(attrs={"type": "date"})}


class HsnSlabForm(forms.ModelForm):
    class Meta:
        model = HsnSlab
        fields = ["value_from", "value_to", "gst_rate", "effective_from"]
        widgets = {"effective_from": forms.DateInput(attrs={"type": "date"})}


def simple_form(model, fields, labels=None, more=(), more_label=""):
    """A small master's form. `more` names the fields that fold under "More options" (core.forms_ui)."""
    class Meta:
        pass

    Meta.model = model
    Meta.fields = fields
    Meta.labels = {"is_active": "Active", **(labels or {})}

    def __init__(self, *args, **kwargs):
        forms.ModelForm.__init__(self, *args, **kwargs)
        if not self.instance.pk:
            self.fields.pop("is_active", None)       # a new one is active; the box appears when editing

    return type(f"{model.__name__}Form", (forms.ModelForm,), {
        "Meta": Meta, "__init__": __init__, "more_fields": tuple(more), "more_label": more_label,
        "more_defaults": {"is_active": True}})


UnitForm = simple_form(Unit, ["code", "name", "kind", "is_active"])
SizeForm = simple_form(Size, ["code", "name", "sort_order", "is_active"])
ColourForm = simple_form(Colour, ["name", "code", "is_active"])
ProductForm = simple_form(Product, ["code", "name", "is_active"])
MaterialForm = simple_form(Material, ["code", "name", "kind", "unit", "composition", "gsm", "width_cm", "is_active"],
                           labels={"gsm": "GSM", "width_cm": "Width (cm)"},
                           more=("composition", "gsm", "width_cm", "is_active"), more_label="composition, GSM, width")
ProcessForm = simple_form(Process, ["code", "name", "kind", "no_loss", "is_active"])
PriceListForm = simple_form(PriceList, ["name", "kind", "is_active"])
HsnForm = simple_form(HSN, ["code", "description", "is_active"])
