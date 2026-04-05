from django.urls import path
from . import views

urlpatterns = [
    path('nl-query/', views.NLQueryView.as_view(), name='ai-nl-query'),
    path('invoice-parse/', views.InvoiceParserView.as_view(), name='ai-invoice-parse'),
    path('suggest-accounts/', views.AccountSuggestionView.as_view(), name='ai-suggest-accounts'),
    path('query-history/', views.NLQueryHistoryView.as_view(), name='ai-query-history'),
]
