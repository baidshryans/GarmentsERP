from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    EmployeeViewSet, SalaryStructureViewSet, PayrollDeductionConfigViewSet,
    SalarySlipViewSet, LeaveBalanceViewSet,
    GeneratePayslipView, BulkGeneratePayslipView, ApprovePayslipView,
    HRSettingsView,
    PortalMyProfileView, PortalMySlipsView, PortalMySlipDetailView,
)

router = DefaultRouter()
router.register(r'employees',       EmployeeViewSet,              basename='hr-employee')
router.register(r'salary-structure', SalaryStructureViewSet,      basename='hr-salary-structure')
router.register(r'deduction-config', PayrollDeductionConfigViewSet, basename='hr-deduction-config')
router.register(r'salary-slips',    SalarySlipViewSet,            basename='hr-salary-slip')
router.register(r'leave-balance',   LeaveBalanceViewSet,          basename='hr-leave-balance')

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/generate-payslip/',       GeneratePayslipView.as_view(),         name='hr-generate-payslip'),
    path('api/bulk-generate-payslip/',  BulkGeneratePayslipView.as_view(),     name='hr-bulk-generate'),
    path('api/approve-payslip/<int:pk>/', ApprovePayslipView.as_view(),        name='hr-approve-payslip'),
    path('api/hr-settings/',            HRSettingsView.as_view(),              name='hr-settings'),

    # Employee portal
    path('api/portal/my-profile/',      PortalMyProfileView.as_view(),         name='hr-portal-profile'),
    path('api/portal/my-slips/',        PortalMySlipsView.as_view(),           name='hr-portal-slips'),
    path('api/portal/my-slip/<int:month>/<int:year>/', PortalMySlipDetailView.as_view(), name='hr-portal-slip-detail'),
]
