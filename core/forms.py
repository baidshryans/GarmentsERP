import calendar
import re

from django import forms
from django.core.exceptions import ValidationError

from .constants import INDIAN_STATES
from .models import Company, Factory, FieldPermission, Location, Role, RolePermission, User
from .screens import SCREENS
from .validators import validate_gstin, validate_pan, validate_tan

MONTHS = [(i, calendar.month_name[i]) for i in range(1, 13)]


# ---------------- setup wizard ----------------

class CompanyStepForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name", "legal_name", "address", "city", "state_code", "pincode", "pan"]
        widgets = {"address": forms.Textarea(attrs={"rows": 2})}

    def clean_pan(self):
        return self.cleaned_data["pan"].strip().upper()


class TaxStepForm(forms.Form):
    gst_registered = forms.BooleanField(required=False, label="The business is registered for GST")
    gstin = forms.CharField(required=False, label="GSTIN", max_length=15, validators=[validate_gstin])
    gst_from = forms.DateField(required=False, label="GST applies from", widget=forms.DateInput(attrs={"type": "date"}))
    tds_deductor = forms.BooleanField(required=False, label="The business deducts TDS")
    tan = forms.CharField(required=False, label="TAN", max_length=10, validators=[validate_tan])
    tds_from = forms.DateField(required=False, label="TDS applies from", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, company_state=None, books_from=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company_state = company_state
        self.books_from = books_from

    def clean(self):
        data = super().clean()
        if data.get("gst_registered"):
            gstin = (data.get("gstin") or "").strip().upper()
            if not gstin:
                self.add_error("gstin", "Enter the GSTIN, or untick GST registered.")
            elif self.company_state and gstin[:2] != self.company_state:
                self.add_error("gstin", "The GSTIN's state code does not match the company's state.")
            data["gstin"] = gstin
            data["gst_from"] = data.get("gst_from") or self.books_from
        if data.get("tds_deductor"):
            data["tan"] = (data.get("tan") or "").strip().upper()
            data["tds_from"] = data.get("tds_from") or self.books_from
        return data


class YearStepForm(forms.Form):
    fy_start_month = forms.TypedChoiceField(
        choices=MONTHS, coerce=int, initial=4, label="Financial year starts in",
        help_text="April for most Indian businesses",
    )
    books_from = forms.DateField(
        label="Books begin on", widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Opening balances are dated this day; nothing earlier can be posted",
    )


class FactoryStepForm(forms.Form):
    code = forms.CharField(max_length=10, label="Short code", help_text="Used in document numbers, for example LDH1")
    name = forms.CharField(max_length=150, label="Factory name")
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    city = forms.CharField(required=False, max_length=100)
    state_code = forms.ChoiceField(choices=INDIAN_STATES, label="State")
    gstin = forms.CharField(
        required=False, max_length=15, label="Factory GSTIN", validators=[validate_gstin],
        help_text="Leave blank to use the company's GSTIN",
    )

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        if not re.fullmatch(r"[A-Z0-9]+", code):
            raise ValidationError("Use letters and digits only.")
        return code

    def clean_gstin(self):
        return self.cleaned_data["gstin"].strip().upper()


# ---------------- factories, users, roles ----------------

class FactoryEditForm(forms.ModelForm):
    class Meta:
        model = Factory
        fields = ["name", "address", "city", "state_code", "gstin", "is_active"]
        widgets = {"address": forms.Textarea(attrs={"rows": 2})}
        labels = {"gstin": "GSTIN", "is_active": "Active"}


class FactoryCreateForm(FactoryStepForm):
    pass


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ["name", "loc_type"]


class UserForm(forms.ModelForm):
    password = forms.CharField(
        required=False, widget=forms.PasswordInput(render_value=False),
        help_text="Required for a new user; leave blank to keep the current password",
    )
    roles = forms.ModelMultipleChoiceField(queryset=Role.objects.all(), required=False, widget=forms.CheckboxSelectMultiple)
    allowed_factories = forms.ModelMultipleChoiceField(
        queryset=Factory.objects.none(), required=False, widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "mobile", "roles",
                  "all_factories", "allowed_factories", "is_active"]
        labels = {"is_active": "Active"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["allowed_factories"].queryset = Factory.objects.filter(is_active=True)

    def clean_password(self):
        pw = self.cleaned_data["password"]
        if not self.instance.pk and not pw:
            raise ValidationError("Set a password for the new user.")
        if pw:
            from django.contrib.auth.password_validation import validate_password

            validate_password(pw, self.instance)
        return pw

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data["password"]:
            user.set_password(self.cleaned_data["password"])
        user.save()
        self.save_m2m()
        return user


class RoleForm(forms.Form):
    """Permissions per screen (view, create, edit, cancel, approve) and per sensitive field (E1.6)."""

    name = forms.CharField(max_length=80)
    description = forms.CharField(required=False, max_length=255)

    ACTIONS = ["view", "create", "edit", "cancel", "approve"]

    def __init__(self, *args, role=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role
        granted = set()
        fields_granted = set()
        if role:
            granted = set(role.permissions.values_list("screen", "action"))
            fields_granted = set(role.field_permissions.values_list("field_key", flat=True))
            self.initial.setdefault("name", role.name)
            self.initial.setdefault("description", role.description)
        from .constants import SENSITIVE_FIELDS

        self.matrix = []
        for screen, label in SCREENS.items():
            cells = []
            for action in self.ACTIONS:
                name = f"perm__{screen}__{action}"
                self.fields[name] = forms.BooleanField(required=False, initial=(screen, action) in granted)
                cells.append(self[name])
            self.matrix.append((label, cells))
        self.field_checks = []
        for key, label in SENSITIVE_FIELDS.items():
            name = f"field__{key}"
            self.fields[name] = forms.BooleanField(required=False, label=label, initial=key in fields_granted)
            self.field_checks.append(self[name])

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        clash = Role.objects.filter(name__iexact=name)
        if self.role:
            clash = clash.exclude(pk=self.role.pk)
        if clash.exists():
            raise ValidationError("A role with this name already exists.")
        return name

    def save(self):
        from django.db import transaction

        with transaction.atomic():
            role = self.role or Role()
            role.name = self.cleaned_data["name"]
            role.description = self.cleaned_data["description"]
            role.save()
            RolePermission.objects.filter(role=role).delete()
            FieldPermission.objects.filter(role=role).delete()
            for name, value in self.cleaned_data.items():
                if not value:
                    continue
                if name.startswith("perm__"):
                    _, screen, action = name.split("__")
                    RolePermission.objects.create(role=role, screen=screen, action=action)
                elif name.startswith("field__"):
                    FieldPermission.objects.create(role=role, field_key=name.split("__")[1])
        return role
