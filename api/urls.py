from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.MeView.as_view(), name="api_me"),
    path("vouchers/", views.VoucherListView.as_view(), name="api_vouchers"),
]
