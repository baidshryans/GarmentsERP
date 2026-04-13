from django.urls import path
from . import views

urlpatterns = [
    path('api/carry-forward/preview/', views.carry_forward_preview, name='carry_forward_preview'),
    path('api/carry-forward/execute/', views.carry_forward_execute, name='carry_forward_execute'),
    path('api/carry-forward/log/', views.carry_forward_log, name='carry_forward_log'),
]
