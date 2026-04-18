import django_filters
from .models import Ledger


class LedgerFilter(django_filters.FilterSet):
    # Role-based filter — supports ?role=CO or ?role=CO,DL (comma-separated)
    # A ledger appears if it has ANY of the requested roles (multi-role aware)
    role = django_filters.BaseInFilter(method='filter_by_role')

    # Account-group code filter — supports ?ac_group_code=INC-DIR-SAL
    # Supports comma-separated codes as well (BaseInFilter)
    ac_group_code = django_filters.BaseInFilter(method='filter_by_ac_group_code')

    class Meta:
        model = Ledger
        fields = ['role', 'ac_group_code']

    def filter_by_role(self, queryset, name, value):
        if value:
            return queryset.filter(roles__role__in=value).distinct()
        return queryset

    def filter_by_ac_group_code(self, queryset, name, value):
        """Filter ledgers whose account group (or any ancestor) has one of the given codes."""
        if value:
            return queryset.filter(ac_group__code__in=value).distinct()
        return queryset
