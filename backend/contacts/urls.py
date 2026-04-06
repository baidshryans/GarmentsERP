from django.urls import path,include
from contacts import views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from rest_framework.routers import DefaultRouter
from .views import AccountTreeViewSet

router = DefaultRouter()
router.register(r'accounts', AccountTreeViewSet, basename='account-tree')


app_name = "contacts"
urlpatterns = [

    path('api/', include(router.urls)),
    
    path("api/custom-tags/",views.get_customer_type,name='cutomer_type_api'),
    path("api/states/",views.get_states_of_india,name='states_api'),
    path("api/ledger/",views.ListCreateLedger.as_view(),name='ledger_view_api'),
    path("api/ledger/<int:pk>/",views.RetrieveUpdateDestroyLedger.as_view(),name='ledger_update_view_api'),
    path("api/ledger/<int:pk>/roles/",views.manage_ledger_role,name='ledger_roles_api'),
    path("api/ledger/<int:pk>/roles/primary/",views.set_primary_ledger_role,name='ledger_primary_role_api'),
    path("api/allowed_retail_list",views.AllowedRetailView.as_view(),name='retail_list'),
    path("api/ledger-documents/",views.LedgerDocumentListCreate.as_view(),name='ledger-documents'),
    path("api/ledger-documents/<int:pk>/",views.LedgerDocumentDelete.as_view(),name='ledger-document-delete'),
    path('api/ledger/<int:pk>/tds-info/', views.ledger_tds_info, name='ledger_tds_info'),
    path('api/crm/occasions/', views.crm_occasions, name='crm_occasions'),
    path('api/ledger/check-name/', views.check_ledger_name, name='ledger_check_name'),
    path('api/ledger/template/', views.LedgerTemplateDownloadView.as_view(), name='ledger_template'),
    path('api/ledger/csv-upload/', views.LedgerCSVUploadView.as_view(), name='ledger_csv_upload'),

]

urlpatterns+= staticfiles_urlpatterns()