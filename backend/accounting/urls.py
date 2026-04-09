from django.urls import include, path
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from . import views
from rest_framework import routers

router = routers.DefaultRouter()
router.register('journal', views.JournalEntryViewSet, basename='journal')
router.register('open-balance', views.LedgerOpenBalanceViewSet, basename='open-balance')
router.register('credit-debit-notes', views.CreditDebitNoteViewSet, basename='credit-debit-notes')

accounts_router = routers.SimpleRouter()
accounts_router.register('', views.AccountViewSet, basename='accounts')

app_name = 'accounting'

urlpatterns = [
    path('account-tree/', views.account_tree, name='account_tree'),
    path('api/', include(router.urls)),
    path('api/accounts/', include(accounts_router.urls)),
    # path('api/add-journal/', views.AddJournalEntryView.as_view(), name='add_journal_api'),
    path('initial-data/', views.initial_data_view, name='initial_data'),
    path('api/due-payments/',views.PurchaseVoucherView.as_view(),name="due-payments-api"),
    path('api/due-payments/sale/',views.SaleVoucherView.as_view(),name="due-payments-api-sale"),
    path('api/outstanding-bills/', views.OutstandingBillsView.as_view(), name='outstanding-bills'),
    path('api/aged-receivables/', views.AgedReceivablesView.as_view(), name='aged-receivables'),
    path('api/advance-register/', views.AdvanceRegisterView.as_view(), name='advance-register'),
    path('api/gc/',views.GoldCashConversionView.as_view()),
    path('api/gc-no/',views.get_next_gc_no),
    path('api/vou-no/<str:type>/',views.get_next_vou_no),
    path('api/cg-no/',views.get_next_cg_no),
    path('api/get-ldgr-cash-total/<int:ledger_id>',views.cash_total_of_ledger),
    path('api/pnl',views.ProfitLossAPIView.as_view()),
    path('api/bal-sheet',views.BalanceSheetAPIView.as_view()),
    path('api/cash-book',views.CashbookReportView.as_view()),
    path('api/bank-book',views.BankbookReportView.as_view()),
    path('api/trial',views.TrialBalanceReportView.as_view()),
    path('api/ledger-statement/', views.LedgerStatementView.as_view(), name='ledger-statement'),
    path('api/day-book/', views.DayBookView.as_view(), name='day-book'),
    path('api/outstanding/', views.OutstandingReportView.as_view(), name='outstanding'),
    path('api/pnl-drilldown/', views.PnlDrilldownView.as_view(), name='pnl-drilldown'),
    path('api/financial-ratios/', views.FinancialRatiosView.as_view(), name='financial-ratios'),
    path('api/audit-queue/', views.AuditQueueView.as_view(), name='audit-queue'),
    path('api/audit-mark/', views.AuditMarkView.as_view(), name='audit-mark'),
    path('api/voucher-attachments/', views.VoucherAttachmentListCreate.as_view(), name='voucher-attachments'),
    path('api/voucher-attachments/<int:pk>/', views.VoucherAttachmentDelete.as_view(), name='voucher-attachment-delete'),
    # Bank Reconciliation
    path('api/bank-statement/', views.BankStatementListCreate.as_view(), name='bank-statement'),
    path('api/bank-statement/<int:pk>/', views.BankStatementDetail.as_view(), name='bank-statement-detail'),
    path('api/bank-statement/<int:pk>/match/', views.bank_statement_match, name='bank-statement-match'),
    path('api/bank-reconciliation/book-entries/', views.bank_book_for_recon, name='bank-recon-book'),
    # Credit / Debit Notes
    path('api/cn-dn-no/<str:note_type>/', views.NextCNDNNumberView.as_view(), name='cn-dn-next-no'),

]

urlpatterns+= staticfiles_urlpatterns()
