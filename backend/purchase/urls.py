from django.urls import path, include, re_path
from purchase import views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from rest_framework.routers import DefaultRouter
from .views import PurchaseOrderViewset, PurchaseReturnViewset, PurchaseVoucherViewset, get_purchase_for_return

router = DefaultRouter()
router.register(r'purchase-return', PurchaseReturnViewset)
router.register(r'purchase-voucher', PurchaseVoucherViewset)
router.register(r'purchase-order', PurchaseOrderViewset)

app_name = "purchase"

urlpatterns = [    

    path('api/purchase-order-v/', views.PurchaseOrderView.as_view(), name='po_view_api'),
    
    path('get-next-pv-no/',views.get_next_pv_no),
    path('get-next-pr-no/',views.get_next_pr_no),
    path('get-next-po-no/',views.get_next_po_no),

    path('fetch-po-sl-no/', views.fetch_po_sl_no, name='fetch_po_sl_no'),
    path('fetch-po-items/', views.fetch_po_items, name='fetch_po_items'),
    # path('api/fetch-pv-for-return/<str:po_no>',views.get_purchase_for_return),
    re_path(r'^api/fetch-pv-for-return/(?P<po_no>.+)$', views.get_purchase_for_return),
    path('api/purchase-vou-item',views.PurchaseItemView.as_view()),
    path("api/",include(router.urls)),
    path("api/purchase-return-initial-data/", views.purchase_return_initial_data),
    path("api/purchase-attachments/", views.PurchaseAttachmentListCreate.as_view()),
    path("api/purchase-attachments/<int:pk>/", views.PurchaseAttachmentDelete.as_view()),
    # Serve attachment files from the dynamically configured storage path
    re_path(r'^api/attachment-file/(?P<name>.+)$', views.serve_attachment_file),
    path('api/tds-register/', views.tds_register, name='tds_register'),
    path('api/rcm-register/', views.rcm_register, name='rcm_register'),
    path('api/customer-purchases-for-adjustment/', views.customer_purchases_for_adjustment),
    path('api/gstr2b-reconcile/', views.GSTR2BReconcileView.as_view(), name='gstr2b_reconcile'),
]
urlpatterns+= staticfiles_urlpatterns()