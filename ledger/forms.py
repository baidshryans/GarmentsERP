from django import forms

from .models import AccountGroup, Ledger


INDENT = "    "


def tree_choices(groups, blank="— none (top-level group) —"):
    """Group choices in tree order, indented by depth so the hierarchy is visible in a drop-down.

    `groups` is a queryset or list of AccountGroup; children whose parent is not in the list are shown at the top.
    """
    groups = list(groups)
    ids = {g.pk for g in groups}
    by_parent = {}
    for g in sorted(groups, key=lambda g: g.name):
        by_parent.setdefault(g.parent_id if g.parent_id in ids else None, []).append(g)
    out = [("", blank)] if blank else []

    def walk(parent_id, depth):
        for g in by_parent.get(parent_id, []):
            label = INDENT * depth + ("└ " if depth else "") + g.name
            if not g.is_active:
                label += " (inactive)"
            out.append((g.pk, label))
            walk(g.pk, depth + 1)

    walk(None, 0)
    return out


class GroupForm(forms.ModelForm):
    class Meta:
        model = AccountGroup
        fields = ["name", "parent", "is_active"]

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        qs = AccountGroup.objects.filter(company=company)
        if self.instance.pk:                      # a group cannot move under itself or one of its own sub-groups
            banned, frontier = {self.instance.pk}, {self.instance.pk}
            while frontier:
                frontier = set(qs.filter(parent_id__in=frontier).values_list("pk", flat=True)) - banned
                banned |= frontier
            qs = qs.exclude(pk__in=banned)
        self.fields["parent"].queryset = qs
        self.fields["parent"].required = False
        self.fields["parent"].choices = tree_choices(qs)
        self.fields["parent"].help_text = "Leave empty for a top-level group. Sub-groups take their nature from the parent."
        if self.instance.pk:
            # Nature is inherited from the parent; a top-level group keeps its own.
            pass
        else:
            self.fields["nature"] = forms.ChoiceField(
                choices=AccountGroup.Nature.choices, required=False,
                help_text="Needed for a top-level group; sub-groups inherit it from their parent",
            )
            self.order_fields(["name", "parent", "nature", "is_active"])

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
        groups = AccountGroup.objects.filter(company=company, is_active=True)
        self.fields["group"].queryset = groups
        self.fields["group"].choices = tree_choices(groups, blank="— choose a group —")
        self.fields["group"].help_text = "The group this ledger sits under, e.g. Sundry Debtors for a customer."

    def save(self, commit=True):
        ledger = super().save(commit=False)
        ledger.company = self.company
        if commit:
            ledger.save()
        return ledger
