import django_filters
from .models import BarcodeDetails, BarcodeMain


class BarCodeMainFilter(django_filters.FilterSet):
    """FilterSet for BarcodeMain with support for related field lookups"""
    rec_item__receive_slip_no = django_filters.CharFilter(
        field_name='rec_item__receive_slip_no',
        lookup_expr='exact'
    )
    rec_item__sl_no = django_filters.NumberFilter(
        field_name='rec_item__sl_no',
        lookup_expr='exact'
    )

    class Meta:
        model = BarcodeMain
        fields = ['barcode', 'item', 'purity', 'stk_status', 'rec_item__receive_slip_no', 'rec_item__sl_no']


class StockValuationReportFilter(django_filters.FilterSet):
        # Filter for checking if customer_order is null or not
    customer_order_is_null = django_filters.BooleanFilter(field_name='barcode__customer_order', lookup_expr='isnull')

    # Filter for filtering by purity type (assuming purity has a 'type' field)
    purity_type = django_filters.CharFilter(field_name='barcode__purity__purity', lookup_expr='icontains')

    class Meta:
        model = BarcodeDetails
        fields = ['customer_order_is_null', 'purity_type']
