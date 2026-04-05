from django.urls import path
from . import views

urlpatterns = [
    path('api/my-apps/', views.my_apps, name='my-apps'),
    path('api/all-apps/', views.all_apps, name='all-apps'),
]
