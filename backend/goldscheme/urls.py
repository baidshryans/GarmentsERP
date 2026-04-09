from django.urls import include, path
from rest_framework import routers
from . import views, portal_views

router = routers.DefaultRouter()
router.register('schemes', views.SchemeMasterViewSet, basename='schemes')
router.register('enrollments', views.SchemeEnrollmentViewSet, basename='enrollments')
router.register('payments', views.SchemePaymentViewSet, basename='scheme-payments')

app_name = 'goldscheme'

urlpatterns = [
    path('api/', include(router.urls)),
    # Reports
    path('api/reports/scheme-summary/', views.SchemeSummaryView.as_view(), name='scheme-summary'),
    path('api/reports/maturity-calendar/', views.MaturityCalendarView.as_view(), name='maturity-calendar'),
    path('api/reports/overdue-payments/', views.OverduePaymentsView.as_view(), name='overdue-payments'),
    path('api/reports/scheme-collection/', views.SchemeCollectionView.as_view(), name='scheme-collection'),
    # Customer Portal — legacy public endpoints (mobile-number auth)
    path('api/customer-portal/my-schemes/', views.CustomerPortalMySchemes.as_view(), name='portal-my-schemes'),
    path('api/customer-portal/scheme/<str:enrollment_no>/', views.CustomerPortalSchemeDetail.as_view(), name='portal-scheme-detail'),
    # Customer Portal — authenticated (OTP + password + token)
    path('api/portal/request-otp/', portal_views.PortalRequestOTPView.as_view(), name='portal-request-otp'),
    path('api/portal/verify-otp/', portal_views.PortalVerifyOTPView.as_view(), name='portal-verify-otp'),
    path('api/portal/set-password/', portal_views.PortalSetPasswordView.as_view(), name='portal-set-password'),
    path('api/portal/dashboard/', portal_views.PortalDashboardView.as_view(), name='portal-dashboard'),
    path('api/portal/enrollment/<str:enrollment_no>/', portal_views.PortalEnrollmentDetailView.as_view(), name='portal-enrollment-detail'),
    path('api/portal/pay/', portal_views.PortalPayInstallmentView.as_view(), name='portal-pay'),
    path('api/portal/logout/', portal_views.PortalLogoutView.as_view(), name='portal-logout'),
]
