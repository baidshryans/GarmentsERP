import django_filters

from contacts.models import Ledger
from .models import KarigarIssueItem, KarigarReceiveItem, KarigarStoneReceive

class CharInFilter(django_filters.BaseInFilter, django_filters.CharFilter):
    pass


class JobCompletedFilter(django_filters.FilterSet):
    from_date = django_filters.DateFilter(field_name='issue_slip__date1', lookup_expr='gte')
    to_date   = django_filters.DateFilter(field_name='issue_slip__date1', lookup_expr='lte')
    karigar   = django_filters.NumberFilter(field_name='issue_slip__karigar_ldgr')

    class Meta:
        model = KarigarIssueItem
        fields = ['rec_status', 'from_date', 'to_date', 'karigar']


class KarigarReceiveItemFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name='receive_slip_no__date1', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='receive_slip_no__date1', lookup_expr='lte')
    karigar_ldgr = CharInFilter(
        field_name='receive_slip_no__karigar_ldgr',
        # queryset=Ledger.objects.filter(type="KR")
    )

    class Meta:
        model = KarigarReceiveItem 
        fields = ['finish_status', 'karigar_ldgr','purity', 'date_from', 'date_to']
        # fields = []

class KarigarStoneReceiveItemFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name='receive_slip_no__date1', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='receive_slip_no__date1', lookup_expr='lte')

    class Meta:
        model = KarigarStoneReceive
        # fields = ['finish_status', 'receive_slip_no__karigar_ldgr','purity','hallmark_status', 'date_from', 'date_to']
        fields = []