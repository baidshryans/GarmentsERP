from django.urls import path,include
from goldrates import views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

app_name = "goldrates"
urlpatterns = [    
    


    path('api/purity/', views.PurityMasterView.as_view(), name='purity_view_api'),
    path('api/purity/<int:pk>/', views.PurityMasterDetailView.as_view(), name='purity_detail_api'),
    path('api/gold-rate/', views.GoldRatesView.as_view(), name='gold-rate'),
    path('api/gold-rate-create/', views.UpdateGoldRateView.as_view() , name='create-gold-rate'),
    
    path('api/current-gold-rate/', views.RecentGoldRatesView.as_view(), name='current-gold-rate'),
]

urlpatterns+= staticfiles_urlpatterns()