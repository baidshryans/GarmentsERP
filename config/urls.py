from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from core import views as core
from ledger import views as ledger
from tax import views as tax

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", core.home, name="home"),
    path("setup/", core.setup_wizard, name="setup"),
    path("setup/<str:step>/", core.setup_wizard, name="setup_step"),
    # admin
    path("factories/", core.FactoryList.as_view(), name="factory_list"),
    path("factories/new/", core.FactoryCreate.as_view(), name="factory_create"),
    path("factories/<int:pk>/", core.FactoryEdit.as_view(), name="factory_edit"),
    path("factories/<int:pk>/locations/", core.location_add, name="location_add"),
    path("users/", core.UserList.as_view(), name="user_list"),
    path("users/new/", core.UserSave.as_view(), name="user_create"),
    path("users/<int:pk>/", core.UserSave.as_view(), name="user_edit"),
    path("roles/", core.RoleList.as_view(), name="role_list"),
    path("roles/new/", core.RoleSave.as_view(), name="role_create"),
    path("roles/<int:pk>/", core.RoleSave.as_view(), name="role_edit"),
    path("tax/", tax.TaxSettingsView.as_view(), name="tax_settings"),
    # accounts
    path("accounts/chart/", ledger.ChartView.as_view(), name="chart_of_accounts"),
    path("accounts/chart/groups/new/", ledger.GroupSave.as_view(), name="group_create"),
    path("accounts/chart/groups/<int:pk>/", ledger.GroupSave.as_view(), name="group_edit"),
    path("accounts/chart/ledgers/new/", ledger.LedgerSave.as_view(), name="ledger_create"),
    path("accounts/chart/ledgers/<int:pk>/", ledger.LedgerSave.as_view(), name="ledger_edit"),
    path("accounts/vouchers/", ledger.VoucherList.as_view(), name="voucher_list"),
    path("accounts/vouchers/<int:pk>/", ledger.VoucherDetail.as_view(), name="voucher_detail"),
    path("accounts/opening/", ledger.OpeningBalances.as_view(), name="opening_balances"),
    path("accounts/trial-balance/", ledger.TrialBalanceView.as_view(), name="trial_balance"),
    path("api/v1/", include("api.urls")),
]
