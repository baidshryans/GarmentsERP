from django.urls import path,include
from userauth import views
from userauth import setup_views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from rest_framework.authtoken import views as drftokenvu

app_name = "userauth"
urlpatterns = [


]

urlpatterns += [
    path('api-token-auth/', views.UserLoginView.as_view()),
    # Setup wizard endpoints
    path('api/setup/status/', setup_views.setup_status),
    path('api/setup/sync-retails/', setup_views.sync_user_retails),
    path('api/setup/seed-states/', setup_views.seed_states),
    path('api/setup/seed-accounts/', setup_views.seed_account_groups),
    path('api/setup/seed-tds-tcs/', setup_views.seed_tds_tcs),
    path('api/setup/seed-hr-ledgers/', setup_views.seed_hr_ledgers),
    path('api/setup/seed-system-ledgers/', setup_views.seed_system_ledgers_view),
    path('api/setup/reset-erp/', setup_views.reset_erp),
    path('api/setup/rollback/', setup_views.setup_rollback),
    # User management
    path('api/users/', views.list_users),
    path('api/users/create/', views.create_user),
    path('api/users/<int:pk>/', views.update_user),
    path('api/users/<int:pk>/assign-retail/', views.assign_retail),
    path('api/users/<int:pk>/assign-role/', views.assign_user_role),
    # Roles & permissions
    path('api/roles/', views.list_create_roles),
    path('api/roles/<int:pk>/', views.role_detail),
    path('api/roles/<int:pk>/permissions/', views.role_permissions),
    path('api/modules/', views.list_modules),
    path('api/backup-database/', views.backup_database),
    path('api/audit-log/', views.audit_log),
    path('api/audit-log/reverse-transaction/', views.reverse_transaction_view),
    path('api/audit-log/restore-to-point/',    views.restore_to_point_view),
    path('api/dashboard-summary/', views.dashboard_summary),
]

urlpatterns+= staticfiles_urlpatterns()