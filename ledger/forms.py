from django import forms

from .models import AccountGroup, Ledger


class GroupForm(forms.ModelForm):
    class Meta:
        model = AccountGroup
        fields = ["name", "parent", "is_active"]

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        qs = AccountGroup.objects.filter(company=company)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = qs
        self.fields["parent"].required = False
        if self.instance.pk:
            # Nature is inherited from the parent; a top-level group keeps its own.
            pass
        else:
            self.fields["nature"] = forms.ChoiceField(
                choices=AccountGroup.Nature.choices, required=False,
                help_text="Needed for a top-level group; sub-groups inherit it from their parent",
            )

    def clean(self):
        data = super().clean()
        if not data.get("parent") and not self.instance.pk and not data.get("nature"):
            self.add_error("nature", "Choose the nature for a top-level group.")
        return data

    def save(self, commit=True):
        group = super().save(commit=False)
        group.company = self.company
        if group.parent:
            group.nature, group.statement = group.parent.nature, group.parent.statement
        elif not group.pk:
            nature = self.cleaned_data["nature"]
            group.nature = nature
            group.statement = "bs" if nature in ("asset", "liability") else "pl"
        if commit:
            group.save()
        return group


class LedgerForm(forms.ModelForm):
    class Meta:
        model = Ledger
        fields = ["name", "group", "code", "bill_wise", "is_active"]

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.fields["group"].queryset = AccountGroup.objects.filter(company=company, is_active=True)

    def save(self, commit=True):
        ledger = super().save(commit=False)
        ledger.company = self.company
        if commit:
            ledger.save()
        return ledger
