import django_filters
from .models import Ledger


class LedgerFilter(django_filters.FilterSet):
    # Role-based filter — supports ?role=CO or ?role=CO,DL (comma-separated)
    # A ledger appears if it has ANY of the requested roles (multi-role aware)
    role = django_filters.BaseInFilter(method='filter_by_role')

    class Meta:
        model = Ledger
        fields = ['role']

    def filter_by_role(self, queryset, name, value):
        if value:
            return queryset.filter(roles__role__in=value).distinct()
        return queryset
