from django.urls import path,include
from mastersconfig import views
from mastersconfig import commission_views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

app_name = "mastersconfig"
urlpatterns = [
    

    
    path('api/hsn/',views.ListCreateHsn.as_view(), name='hsn_view_api'),
    path('api/hsn/<int:pk>/',views.RetrieveUpdateDeleteHsn.as_view(), name='hsn_edit_delete_api'),



    path('api/item/',views.ListCreateItem.as_view(), name='item_view_api'),
    path('api/item/<int:pk>/',views.RetrieveUpdateDestroyItem.as_view(), name='item_edit_delete_api'),

 
    path('api/packet/',views.ListCreatePacket.as_view(), name='packet_view_api'),
    path('api/packet/<int:pk>/',views.RetrieveUpdateDestroyPacket.as_view(), name='packet_edit_delete_api'),

  
    path('api/shape/',views.ListCreateShape.as_view(), name='shape_view_api'),
    path('api/shape/<int:pk>/',views.RetrieveUpdateDestroyShape.as_view(), name='shape_edit_delete_api'),

   
    path('api/color/',views.ListCreateColor.as_view(), name='color_view_api'),
    path('api/color/<int:pk>/',views.RetrieveUpdateDestroyColor.as_view(), name='color_edit_delete_api'),


   
    path('api/packet_group/',views.ListCreatePacketGroup.as_view(), name='packet_group_view_api'),
    path('api/packet_group/<int:pk>/',views.RetrieveUpdateDestroyPacketGroup.as_view(), name='packet_group_edit_delete_api'),

   
    path('api/salesperson/',views.ListCreateSalesPersonMaster.as_view(), name='salesperson_view_api'),
    path('api/salesperson/<int:pk>/',views.RetrieveUpdateDestroySalesPersonMaster.as_view(), name='salesperson_edit_delete_api'),


    path('api/item_group/',views.ListCreateItemGroupMaster.as_view(), name='item_group_view_api'),
    path('api/item_group/<int:pk>/',views.RetrieveUpdateDestroyItemGroupMaster.as_view(), name='item_group_edit_delete_api'),

    path('api/retail/',views.RetailMasterView.as_view(), name='retail_master_view'),
    path('api/retail/<int:pk>/',views.RetailMasterDetailView.as_view(), name='retail_master_detail'),
    path('api/state/',views.StateListView.as_view(), name='state_list_view'),
    path('api/tds-section/', views.ListCreateTDSSection.as_view(), name='tds_section_list_create'),
    path('api/tds-section/<int:pk>/', views.RetrieveUpdateDestroyTDSSection.as_view(), name='tds_section_detail'),
    path('api/tcs-section/', views.ListCreateTCSSection.as_view(), name='tcs_section_list_create'),
    path('api/tcs-section/<int:pk>/', views.RetrieveUpdateDestroyTCSSection.as_view(), name='tcs_section_detail'),

    # CSV Upload endpoints
    path('api/hsn/csv-upload/', views.HSNCSVUploadView.as_view(), name='hsn_csv_upload'),
    path('api/item/csv-upload/', views.ItemCSVUploadView.as_view(), name='item_csv_upload'),
    path('api/item_group/csv-upload/', views.ItemGroupCSVUploadView.as_view(), name='item_group_csv_upload'),
    path('api/packet_group/csv-upload/', views.PacketGroupCSVUploadView.as_view(), name='packet_group_csv_upload'),
    path('api/packet/csv-upload/', views.PacketCSVUploadView.as_view(), name='packet_csv_upload'),

    # MySQL Sync endpoint
    path('api/mysql-sync/', views.MySQLSyncView.as_view(), name='mysql_sync'),

    # Fiscal Year Management
    path('api/fiscal-years/', views.FiscalYearListCreate.as_view(), name='fiscal_year_list_create'),
    path('api/fiscal-years/<int:pk>/set-active/', views.set_active_fiscal_year, name='fiscal_year_set_active'),
    path('api/fiscal-years/<int:pk>/close/', views.close_fiscal_year, name='fiscal_year_close'),
    path('api/fiscal-years/<int:pk>/reopen/', views.reopen_fiscal_year, name='fiscal_year_reopen'),
    path('api/fiscal-years/<int:pk>/hard-close/', views.hard_close_fiscal_year, name='fiscal_year_hard_close'),
    path('api/fiscal-years/<int:pk>/reopen-hard-close/', views.reopen_hard_close_fiscal_year, name='fiscal_year_reopen_hard_close'),
    path('api/fiscal-years/<int:pk>/sync-opening-balances/', views.sync_opening_balances, name='fiscal_year_sync_ob'),

    # Exhibition Profiles
    path('api/exhibition/', views.ExhibitionListCreate.as_view(), name='exhibition_list_create'),
    path('api/exhibition/<int:pk>/', views.ExhibitionDetail.as_view(), name='exhibition_detail'),
    path('api/exhibition/<int:pk>/activate/', views.activate_exhibition, name='exhibition_activate'),
    path('api/exhibition/<int:pk>/deactivate/', views.deactivate_exhibition, name='exhibition_deactivate'),

    # System Settings (singleton)
    path('api/system-settings/', views.system_settings_view, name='system_settings'),

    # Company Master
    path('api/company/', views.CompanyMasterView.as_view(), name='company_master_list_create'),
    path('api/company/<int:pk>/', views.CompanyMasterDetailView.as_view(), name='company_master_detail'),

    # Branch Master
    path('api/branch/', views.BranchMasterView.as_view(), name='branch_master_list_create'),
    path('api/branch/<int:pk>/', views.BranchMasterDetailView.as_view(), name='branch_master_detail'),
    path('api/branch/<int:pk>/analytics/', views.BranchAnalyticsView.as_view(), name='branch_analytics'),

    # Salesperson Commission
    path('api/commission/report/',         commission_views.commission_report,       name='commission_report'),
    path('api/commission/create-jv/',      commission_views.commission_create_jv,    name='commission_create_jv'),
    path('api/commission/ledger-config/',  commission_views.commission_ledger_config, name='commission_ledger_config'),
    path('api/commission/ledger-set/',     commission_views.commission_ledger_set,   name='commission_ledger_set'),

    path('api/crm-settings/',     views.crm_settings_view, name='crm_settings'),
    path('api/crm-send-log/',     views.crm_send_log,      name='crm_send_log'),
    path('api/crm-test-send/',    views.crm_test_send,     name='crm_test_send'),
]

urlpatterns+= staticfiles_urlpatterns()