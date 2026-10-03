from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from core import views as core
from ledger import views as ledger
from masters import views as m
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
    path("masters/unit/", m.SimpleList.as_view(key="unit"), name="unit_list"),
    path("masters/unit/new/", m.SimpleSave.as_view(key="unit"), name="unit_new"),
    path("masters/unit/<int:pk>/edit/", m.SimpleSave.as_view(key="unit"), name="unit_edit"),
    path("masters/size/", m.SimpleList.as_view(key="size"), name="size_list"),
    path("masters/size/new/", m.SimpleSave.as_view(key="size"), name="size_new"),
    path("masters/size/<int:pk>/edit/", m.SimpleSave.as_view(key="size"), name="size_edit"),
    path("masters/colour/", m.SimpleList.as_view(key="colour"), name="colour_list"),
    path("masters/colour/new/", m.SimpleSave.as_view(key="colour"), name="colour_new"),
    path("masters/colour/<int:pk>/edit/", m.SimpleSave.as_view(key="colour"), name="colour_edit"),
    path("masters/product/", m.SimpleList.as_view(key="product"), name="product_list"),
    path("masters/product/new/", m.SimpleSave.as_view(key="product"), name="product_new"),
    path("masters/product/<int:pk>/edit/", m.SimpleSave.as_view(key="product"), name="product_edit"),
    path("masters/material/", m.SimpleList.as_view(key="material"), name="material_list"),
    path("masters/material/new/", m.SimpleSave.as_view(key="material"), name="material_new"),
    path("masters/material/<int:pk>/edit/", m.SimpleSave.as_view(key="material"), name="material_edit"),
    path("masters/process/", m.SimpleList.as_view(key="process"), name="process_list"),
    path("masters/process/new/", m.SimpleSave.as_view(key="process"), name="process_new"),
    path("masters/process/<int:pk>/edit/", m.SimpleSave.as_view(key="process"), name="process_edit"),
    path("masters/pricelist/", m.SimpleList.as_view(key="pricelist"), name="pricelist_list"),
    path("masters/pricelist/new/", m.SimpleSave.as_view(key="pricelist"), name="pricelist_new"),
    path("masters/pricelist/<int:pk>/edit/", m.SimpleSave.as_view(key="pricelist"), name="pricelist_edit"),
    path("masters/hsn/", m.SimpleList.as_view(key="hsn"), name="hsn_list"),
    path("masters/hsn/new/", m.SimpleSave.as_view(key="hsn"), name="hsn_new"),
    path("masters/hsn/<int:pk>/edit/", m.SimpleSave.as_view(key="hsn"), name="hsn_edit"),
    path("masters/hsn/<int:pk>/", tax.HsnDetail.as_view(), name="hsn_detail"),
    path("masters/pricelist/<int:pk>/", m.PriceListDetail.as_view(), name="pricelist_detail"),
    path("masters/styles/", m.StyleList.as_view(), name="style_list"),
    path("masters/styles/new/", m.StyleSave.as_view(), name="style_new"),
    path("masters/styles/<int:pk>/", m.StyleDetail.as_view(), name="style_detail"),
    path("masters/styles/<int:pk>/edit/", m.StyleSave.as_view(), name="style_edit"),
    path("masters/styles/<int:pk>/bom/", m.BomEdit.as_view(), name="bom_edit"),
    path("masters/routes/", m.RouteList.as_view(), name="route_list"),
    path("masters/routes/new/", m.RouteSave.as_view(), name="route_new"),
    path("masters/routes/<int:pk>/", m.RouteSave.as_view(), name="route_edit"),
    path("masters/parties/", m.PartyList.as_view(), name="party_list"),
    path("masters/parties/new/", m.PartySave.as_view(), name="party_new"),
    path("masters/parties/<int:pk>/", m.PartyDetail.as_view(), name="party_detail"),
    path("masters/parties/<int:pk>/edit/", m.PartySave.as_view(), name="party_edit"),
    path("search/", m.Search.as_view(), name="search"),
    path("import/", m.ExcelImport.as_view(), name="excel_import"),
    path("import/template/<str:kind>/", m.import_template, name="import_template"),
    path("api/v1/", include("api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
