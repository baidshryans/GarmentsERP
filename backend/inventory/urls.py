from django.urls import path
from . import views
from inventory.api_views import (
    BarcodeOpeningValidateView,
    BarcodeOpeningImportView,
    BarcodeMainTemplateView,
    BarcodeDetailsTemplateView,
    OpeningStockTemplateView,
    OpeningStockImportView,
)
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path
from rest_framework.routers import DefaultRouter


app_name = 'inventory'

router = DefaultRouter()
router.register(r'design-main', views.DesignMainViewSet, basename='design-main')
router.register(r'barcode', views.BarCodeView, basename='barcode')
router.register(r'brcode-history', views.BarcodeTransactionView, basename='barcode-history')
router.register(r'unbarcoded', views.UnBarCodeView, basename='unbarcoded')
router.register(r'stock-journal', views.StockJournalViewSet, basename='stock-journal')
router.register(r'stock-transfer', views.StockTransferViewset, basename='stock-transfer')
router.register(r'raw-material', views.RawMaterialInventoryViewSet, basename='raw-material')
router.register(r'raw-material-txn', views.RawMaterialTransactionListView, basename='raw-material-txn')
router.register(r'rfid-sessions', views.RfidCountSessionViewSet, basename='rfid-sessions')
router.register(r'inter-retail-transfers', views.InterRetailTransferVoucherViewSet, basename='inter-retail-transfers')
router.register(r'opening-inventory', views.OpeningInventoryViewSet, basename='opening-inventory')


urlpatterns = [
    #path('create-barcode/', views.create_barcode_view, name='create_barcode_view'),
    path('api/next_stock_journal_no', views.stock_journal_billno_view, name='stock_journal_billno'),
    path('api/next_stock_transfer_no', views.stock_transfer_billno_view, name='stock_transfer_billno'),
    path('api/next_inter_retail_transfer_no', views.inter_retail_transfer_next_no, name='inter_retail_transfer_next_no'),
    path('api/create-barcode-from-receive/', views.create_barcode_from_receive_api, name='create_barcode_from_receive_api'),
    path('api/create-barcode-from-pur/', views.create_barcode_from_purchase),
    path('api/stock-valuation-report/',views.StockValuationReportView.as_view() ),
    path('api/generate-barcode/',views.gen_barcode ),
    path('api/get-barcode-detail/<str:barcode>/<str:hsn>/',views.get_barcode ),
    path('api/get-barcode-detail/<str:barcode>/',views.get_barcode_only ),
    path('api/get-barcode-for-return/<str:barcode>/', views.get_barcode_for_return),
    path('api/barcode-merge/',views.barcode_merge_view ),
    path('api/barcode-split/<str:old_barcode>',views.barcode_split_view ),
    path('api/closing-stock',views.ClosingStockCalculator.as_view() ),
    path('api/closing-stock-txns/', views.ClosingStockTxnView.as_view(), name='closing_stock_txns'),
    path('api/stock-report',views.StockReportView.as_view() ),
    path('api/stock-report/barcodes', views.StockReportBarcodesView.as_view(), name='stock_report_barcodes'),
    path('api/cvd-check',views.CVDTestViewSet.as_view() ),
    path('api/idgeneration',views.IDGenerationReport.as_view() ),
    path('api/brcode-split-merge',views.BarcodeSplitMergeView.as_view() ),
    path('api/bar-unbar/',views.ConvertBarcodeToUnbarcodedView.as_view() ),
    path('api/barcode-creation-report/', views.BarcodeCreationReportView.as_view(), name='barcode_creation_report'),
    path('api/item-barcode-report/', views.ItemwiseBarcodeReport.as_view(), name='item_barcode_report'),
    path('api/barcode-bulk/', views.BarcodeBulkListView.as_view(), name='barcode_bulk'),
    path('api/barcode-images/', views.BarcodeImageListCreate.as_view(), name='barcode_images'),
    path('api/barcode-images/reorder/', views.barcode_image_reorder, name='barcode_image_reorder'),
    path('api/barcode-images/<int:pk>/', views.BarcodeImageDelete.as_view(), name='barcode_image_delete'),
    re_path(r'^api/barcode-image-file/(?P<name>.+)$', views.serve_barcode_image_file, name='barcode_image_file'),

    path('api/design-images/', views.DesignImageListCreate.as_view(), name='design_images'),
    path('api/design-images/reorder/', views.design_image_reorder, name='design_image_reorder'),
    path('api/design-images/<int:pk>/', views.DesignImageDelete.as_view(), name='design_image_delete'),

    path('api/catalog/', views.catalog_list, name='catalog_list'),
    path('api/catalog/pdf/', views.catalog_pdf, name='catalog_pdf'),
    path('api/catalog-shares/', views.CatalogShareListCreate.as_view(), name='catalog_shares'),
    path('api/catalog-shares/<int:pk>/', views.CatalogShareDelete.as_view(), name='catalog_share_delete'),
    path('api/catalog-share/<uuid:token>/', views.public_catalog, name='public_catalog'),
    path('api/catalog-share/<uuid:token>/pdf/', views.public_catalog_pdf, name='public_catalog_pdf'),
    path('api/catalog/<int:pk>/', views.catalog_detail, name='catalog_detail'),
    path('api/raw-material-balance/', views.RawMaterialBalanceReportView.as_view(), name='raw_material_balance'),
    path('api/unbarcoded-stock-report/', views.UnbarcodedStockReportView.as_view(), name='unbarcoded_stock_report'),
    path('api/raw-material-ledger/', views.RawMaterialMovementLedgerView.as_view(), name='raw_material_ledger'),
    path('api/semi-finished-stock/', views.SemiFinishedStockReportView.as_view(), name='semi_finished_stock'),
    path('api/rfid/assign/', views.RfidTagAssignView.as_view(), name='rfid_tag_assign'),
    path('api/rfid/count/', views.RfidInventoryCountView.as_view(), name='rfid_inventory_count'),
    path('api/rfid/tags/', views.RfidTagListView.as_view(), name='rfid_tag_list'),
    path('api/barcode-opening/validate/', BarcodeOpeningValidateView.as_view(), name='barcode-opening-validate'),
    path('api/barcode-opening/import/', BarcodeOpeningImportView.as_view(), name='barcode-opening-import'),
    path('api/templates/barcode-main/', BarcodeMainTemplateView.as_view(), name='barcode-main-template'),
    path('api/templates/barcode-details/', BarcodeDetailsTemplateView.as_view(), name='barcode-details-template'),
    path('api/templates/opening-stock/', OpeningStockTemplateView.as_view(), name='opening-stock-template'),
    path('api/opening-stock/import/', OpeningStockImportView.as_view(), name='opening-stock-import'),
    *router.urls
    
]

urlpatterns += staticfiles_urlpatterns()

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)