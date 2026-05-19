"""
URL configuration for jewel_test project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
#from contacts import views
from userauth import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('nested_admin/', include('nested_admin.urls')),
    path('contacts/', include("contacts.urls")),
    path('userauth/', include("userauth.urls")),
    path('mastersconfig/', include("mastersconfig.urls")),
    path('goldrates/', include("goldrates.urls")),
    path('sales/', include("sales.urls")),
    path('manufacturing/', include('manufacturing.urls')),
    path('inventory/', include('inventory.urls')),
    path('accounting/', include('accounting.urls')),
    path('purchase/', include('purchase.urls')),
    path('ai/', include('ai_layer.urls')),
    path('licensing/', include('licensing.urls')),
    path('goldscheme/', include('goldscheme.urls')),
    path('hr/', include('hr.urls')),
    path('carryforward/', include('carryforward.urls')),
    path('vendor-analytics/', include('vendor_analytics.urls')),
    path('audit/', include('audit.urls')),
]

urlpatterns += static(settings.STATIC_URL, document_root = settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)

