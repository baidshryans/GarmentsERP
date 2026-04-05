import django_filters
from .models import BarcodeDetails


class StockValuationReportFilter(django_filters.FilterSet):
        # Filter for checking if customer_order is null or not
    customer_order_is_null = django_filters.BooleanFilter(field_name='barcode__customer_order', lookup_expr='isnull')

    # Filter for filtering by purity type (assuming purity has a 'type' field)
    purity_type = django_filters.CharFilter(field_name='barcode__purity__purity', lookup_expr='icontains')

    class Meta:
        model = BarcodeDetails
        fields = ['customer_order_is_null', 'purity_type']
