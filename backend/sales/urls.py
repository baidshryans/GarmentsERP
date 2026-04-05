from django.urls import path,include
from sales import views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'customer-orders-vs', views.CustomerOrderViewset, basename='customer-orders')
router.register(r'sale-return', views.SalesReturnViewset)
router.register(r'sale-voucher', views.SalesVoucherViewset)
router.register(r'sale-approval', views.SalesApprovalViewset)
app_name = "sales"
urlpatterns = [
    path('api/', include(router.urls)),
    path('api/customer-orders/', views.CustomerOrderView.as_view(), name='customer_order_view_api'),
    path('api/customer-orders/unique', views.CustomerOrderNumberView.as_view(), name='customer_order_view_api'),
    path('api/customer-orders/<int:pk>/', views.RetrieveCustomerOrderView.as_view(), name='customer_order_view_api'),
    path('api/order-no/',views.order_no_view, name='order-no'),
    path('api/customer-item/<int:order_no>/<int:sl_no>/', views.get_customer_item_as_purchase_style),
    path('api/get-sale-vou-for-return/', views.get_sale_voucher_for_return),
    path('api/next_sv_no', views.get_next_sv_no),
    path('api/next_sr_no', views.get_next_sr_no),
    path('api/next_sa_no', views.get_next_sa_no),
    path('api/generate-json', views.GenerateJsonView.as_view()),
    path('api/gst-input', views.GSTInputRegisterView.as_view()),
    path('api/gst-output', views.GSTOutputRegisterView.as_view()),
    path('api/sale-voucher-initial-data/', views.sale_voucher_initial_data),
    path('api/sale-return-initial-data/', views.sale_return_initial_data),
    path('api/sale-voucher/<int:pk>/print-data/', views.sale_voucher_print_data),
    path('api/customer-cash-received/', views.customer_cash_received_view),
    path('api/tcs-register/', views.tcs_register),
    path('api/gstr1/', views.gstr1_report),
    path('api/gstr3b/', views.gstr3b_report),
    path('api/sale-voucher/<int:pk>/eway-transport/', views.eway_transport_update),
    path('api/generate-eway-bill', views.EwayBillGenerateView.as_view()),
    path('api/customer-orders/delivery-overview/', views.customer_order_delivery_overview),
    path('api/customer-orders/<int:pk>/update-delivery/', views.customer_order_update_delivery),
]
urlpatterns+= staticfiles_urlpatterns()