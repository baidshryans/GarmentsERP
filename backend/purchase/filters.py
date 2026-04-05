import django_filters

from manufacturing.filters import CharInFilter
from .models import PurchaseVoucherItems



class PurchaseItemFilterSet(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name='billno__date1', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='billno__date1', lookup_expr='lte')
    ldgr = CharInFilter(field_name='billno__ldgr')

    class Meta:
        model =  PurchaseVoucherItems
        fields = ['is_finished','ldgr','purity', 'date_from', 'date_to']



