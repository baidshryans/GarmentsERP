from django.urls import path

from . import views

app_name = 'audit'

urlpatterns = [
    path('api/log/',                  views.audit_log_list,         name='log_list'),
    path('api/log/detail/',           views.audit_log_detail,       name='log_detail'),
    path('api/log/correlation/',      views.audit_log_correlation,  name='log_correlation'),
    path('api/log/reverse/',          views.reverse_correlation_view, name='log_reverse'),
    path('api/log/restore-row/',      views.restore_row_view,       name='log_restore_row'),
]
