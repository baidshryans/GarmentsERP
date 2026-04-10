from django.contrib import admin
from .models import (
    Employee, SalaryStructure, PayrollDeductionConfig,
    SalarySlip, LeaveBalance, HRSettings,
)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display   = ('employee_code', 'full_name', 'designation', 'department', 'retail', 'is_active')
    list_filter    = ('retail', 'is_active', 'department')
    search_fields  = ('employee_code', 'full_name', 'pan_number')
    raw_id_fields  = ('user', 'salesperson')


@admin.register(SalaryStructure)
class SalaryStructureAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'effective_from', 'is_active', 'gross_ctc')
    list_filter   = ('is_active',)
    raw_id_fields = ('employee',)


@admin.register(PayrollDeductionConfig)
class PayrollDeductionConfigAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'pf_applicable', 'esi_applicable', 'pt_applicable', 'tds_monthly')
    raw_id_fields = ('employee',)


@admin.register(SalarySlip)
class SalarySlipAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'month', 'year', 'gross_salary', 'net_salary', 'status')
    list_filter   = ('status', 'year', 'month', 'retail')
    raw_id_fields = ('employee', 'voucher')


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'year', 'earned_leave_balance', 'casual_leave_balance', 'sick_leave_balance')
    raw_id_fields = ('employee',)


@admin.register(HRSettings)
class HRSettingsAdmin(admin.ModelAdmin):
    list_display  = ('retail',)
