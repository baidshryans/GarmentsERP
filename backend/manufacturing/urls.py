from django.urls import path, include
from manufacturing import views
from manufacturing import utils
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from rest_framework.routers import DefaultRouter
from .views import (
    KarigarGoldIssueViewset,
    KarigarStoneReceiveViewset,
    KarigarStoneIssueViewset,
    HallMarkIssueViewSet,
    HallMarkReceiveViewSet,
    KarigarIssueViewSet,
    KarigarReceiveViewSet,
    RefineryIssueViewset,
    RefineryReceiveViewset,
    MeltingIssueViewset,
    MeltingReceiveViewset,
    AssayIssueViewset,
    AssayReceiveViewset,
    CombinedGoldTransactionView,
    RepairJobCardViewSet,
    KarigarSubcontractorLedgerView,
)



# Create the router and register all viewsets
router = DefaultRouter()
router.register(r'karigar-receive', KarigarReceiveViewSet)
router.register(r'karigar-issue-vs', KarigarIssueViewSet)
router.register(r'karigar-stone-receive', KarigarStoneReceiveViewset)
router.register(r'karigar-stone-issue', KarigarStoneIssueViewset)
router.register(r'karigar-gold-issue', KarigarGoldIssueViewset)
router.register(r'hallmark-receive', HallMarkReceiveViewSet)
router.register(r'hallmark-issue', HallMarkIssueViewSet)
router.register(r'refinery-issue', RefineryIssueViewset)
router.register(r'refinery-receive', RefineryReceiveViewset)
router.register(r'melting-issue', MeltingIssueViewset)
router.register(r'melting-receive', MeltingReceiveViewset)
router.register(r'assay-issue', AssayIssueViewset)
router.register(r'assay-receive', AssayReceiveViewset)
router.register(r'repair-job-card', RepairJobCardViewSet, basename='repair-job-card')
app_name = "manufacturing"
urlpatterns = [   
    path('gold-transactions/', CombinedGoldTransactionView.as_view(), name='gold-transactions'),

    # JSONRESPONSE
    path('fetch-sl-no/', utils.fetch_sl_no, name='fetch_sl_no'),
    path('fetch-order-details/', utils.fetch_order_details, name='fetch_order_details'),
    path('filter-job-items/', views.filter_job_items, name='filter_job_items'),
    path('get-pojo-list/', views.get_pojo_list, name='get_pojo_list'),
    path('get-kr-receive-slip-numbers/', utils.get_kr_receive_slip_numbers, name='get_kr_receive_slip_numbers'),
    path('get-kr-receive-sl-no/', utils.get_kr_receive_sl_no, name='get_kr_receive_sl_no'),
    #JSONRESPONSE

    path('api/karigar-making/', views.KarigarMasterView.as_view(), name='karigar_making_view_api'),
    path('api/karigar-making/<int:pk>/', views.KarigarMasterDetailView.as_view(), name='karigar_making_detail_api'),
    path('api/karigar-making/csv-upload/', views.KarigarMakingCSVUploadView.as_view(), name='karigar_making_csv_upload'),

    path('api/karigar-issue/create/', views.create_karigar_issue, name='insert_karigar_issue_api'),
    path('api/karigar-issue/', views.ListKarigarIssueView.as_view(), name='get_karigar_issue'),
    
    path('api/next-slip-no/', views.get_next_slip_no,),
    path('api/next_hmis_no', views.hallmark_issue_billno_view, name='hallmark_issue_billno'),
    path('api/next_hmrec_no', views.hallmark_receive_billno_view, name='hallmark_receive_billno'),
    path('api/next_ref_iss_no', views.refinery_issue_billno_view, name='refinery_issue_billno'),
    path('api/next_ref_rec_no', views.refinery_receive_billno_view, name='refinery_receive_billno'),
    path('api/next_melt_iss_no', views.melting_issue_billno_view, name='melting_issue_billno'),
    path('api/next_melt_rec_no', views.melting_receive_billno_view, name='melting_receive_billno'),
    path('api/next_assay_iss_no', views.assay_issue_billno_view, name='assay_issue_billno'),
    path('api/next_assay_rec_no', views.assay_receive_billno_view, name='assay_receive_billno'),
    path('api/karigar-jobs/', views.KarigarJobsView.as_view(), name='karigar_jobs_view_api'),
    
    
    path('api/next-stone-bill-no/', views.stone_issue_billno_view,),
    path('api/karigar-stone-issue/create/', views.create_karigar_stone_issue, name='create_karigar_stone_issue'),
    
    # path('karigar-stone-receive/', views.karigar_stone_receive_view, name='karigar_stone_receive_view'),
    path('api/stone-receive-billno/', views.stone_receive_billno_view,),
    path('api/karigar-stone-receive/create/', views.create_karigar_stone_receive, name='create_karigar_stone_receive'),

    path('fetch-receive-packets/', views.fetch_receive_packets, name='fetch_receive_packets'),

    path('api/', include(router.urls)),
    path('api/karigar-stone-issues/',views.ListKarigarStoneIssue.as_view()),
    path('api/karigar-gold-issue/bill-no',views.gold_issue_billno_view ),
    path('api/fetch-rcv-slip-nos', views.KarigarReceiveforNoView.as_view()),
    path('api/karigar-receive-slip-no/', views.receiver_slip_no_view,),
    path('fetch-main-details/', views.fetch_main_details, name='fetch_main_details'),
    path('fetch-main-item-id/', views.fetch_main_item_id, name='fetch_main_item_id'),




    path("api/job-status-report",views.JobStatusView.as_view()),
    path("api/hallmark-issue-report",views.HallmarkIssueReportView.as_view()),
    path("api/hallmark-receive-report",views.HallmarkReceiveReportView.as_view()),
    
    path("api/karigar-receive-item-report",views.KarigarReceiveItemView.as_view()),
    path("api/karigar-stoneissue-item-report",views.KarigarStoneIssueReportView.as_view()),
    path("api/karigar-stonerec-item-report",views.KarigarStoneReceiveReportView.as_view()),
    path("api/metalreport",views.LedgerGoldStockPerPurityView.as_view()),
    path('api/stoneworkorder-report/', views.KarigarWorkOrderStoneReportView.as_view(), name='stonework_order_view_api'),
    path('api/packetwise-stone-api/', views.PacketWiseLooseStoneReportView.as_view(), name='loose_stone'),
    path('api/refinery-report/', views.refinery_report, name='refinery_report'),
    path('api/repair-job-card-no/', views.repair_job_card_billno_view, name='rjc_billno'),
    path('api/karigar-subcontractor-ledger/', KarigarSubcontractorLedgerView.as_view(), name='karigar_subcontractor_ledger'),
]
urlpatterns+= staticfiles_urlpatterns()