from django.urls import path,include
from sales import views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'customer-orders-vs', views.CustomerOrderViewset, basename='customer-orders')
router.register(r'sale-return', views.SalesReturnViewset)
router.register(r'sale-voucher', views.SalesVoucherViewset)
router.register(r'sale-approval', views.SalesApprovalViewset)
router.register(r'quotation', views.QuotationViewset)
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
    path('api/sale-return/<int:pk>/print-data/', views.sale_return_print_data),
    path('api/customer-cash-received/', views.customer_cash_received_view),
    path('api/tcs-register/', views.tcs_register),
    path('api/gstr1/', views.gstr1_report),
    path('api/gstr3b/', views.gstr3b_report),
    path('api/sale-voucher/<int:pk>/eway-transport/', views.eway_transport_update),
    path('api/generate-eway-bill', views.EwayBillGenerateView.as_view()),
    path('api/eway-bills/', views.EWayBillListView.as_view(), name='eway-bill-list'),
    path('api/eway-bills/<int:pk>/cancel/', views.eway_bill_cancel, name='eway-bill-cancel'),
    path('api/eway-bills/<int:pk>/update-ebn/', views.eway_bill_update_ebn, name='eway-bill-update-ebn'),
    path('api/eway-bills/<int:pk>/', views.eway_bill_delete, name='eway-bill-delete'),
    path('api/customer-history/', views.CustomerPurchaseHistoryView.as_view(), name='customer_history'),
    path('api/customer-orders/delivery-overview/', views.customer_order_delivery_overview),
    path('api/customer-orders/<int:pk>/update-delivery/', views.customer_order_update_delivery),
    path('api/pending-cheques/', views.pending_cheques, name='pending-cheques'),
    path('api/deposit-cheque/<int:pk>/', views.deposit_cheque, name='deposit-cheque'),
    path('api/b2b-pricelist/<int:ledger_id>/', views.b2b_pricelist_for_ledger, name='b2b_pricelist_for_ledger'),
    path('api/retail-discount-pricelist/<int:ledger_id>/', views.retail_discount_pricelist_for_ledger, name='retail_discount_pricelist_for_ledger'),
    # Quotation
    path('api/next_qt_no', views.get_next_qt_no),
    path('api/quotation-initial-data/', views.quotation_initial_data),
    path('api/quotation/<int:pk>/print-data/', views.quotation_print_data),
    path('api/quotation/<int:pk>/duplicate/', views.quotation_duplicate),
    path('api/quotation/<int:pk>/finalize/', views.quotation_finalize),
]
urlpatterns+= staticfiles_urlpatterns()