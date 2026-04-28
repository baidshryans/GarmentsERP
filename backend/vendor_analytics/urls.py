from django.urls import path
from . import views

app_name = 'vendor_analytics'

urlpatterns = [
    path('api/vendor-dashboard/', views.VendorDashboardView.as_view(), name='vendor-dashboard'),
    path('api/stock-ageing/', views.StockAgeingView.as_view(), name='stock-ageing'),
    path('api/design-performance/', views.DesignPerformanceView.as_view(), name='design-performance'),
    path('api/inventory-turnover/', views.InventoryTurnoverView.as_view(), name='inventory-turnover'),
    path('api/item-performance/', views.ItemPerformanceView.as_view(), name='item-performance'),
    path('api/vendor-comparison/', views.VendorComparisonView.as_view(), name='vendor-comparison'),
]
