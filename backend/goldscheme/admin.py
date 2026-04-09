from django.contrib import admin
from .models import (
    SchemeMaster, SchemeBenefitTier, SchemeEnrollment, SchemePayment,
    CustomerPortalCredential, CustomerPortalOTP, CustomerPortalToken,
)


class SchemeBenefitTierInline(admin.TabularInline):
    model = SchemeBenefitTier
    extra = 1


@admin.register(SchemeMaster)
class SchemeMasterAdmin(admin.ModelAdmin):
    list_display = ('scheme_code', 'name', 'scheme_type', 'tenure_months', 'is_active', 'retail')
    list_filter = ('scheme_type', 'is_active', 'retail')
    inlines = [SchemeBenefitTierInline]


@admin.register(SchemeEnrollment)
class SchemeEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('enrollment_no', 'customer', 'scheme', 'start_date', 'maturity_date',
                    'total_paid', 'payments_made', 'status')
    list_filter = ('status', 'scheme', 'retail')
    search_fields = ('enrollment_no', 'customer__ac_name')


@admin.register(SchemePayment)
class SchemePaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_no', 'enrollment', 'date', 'amount', 'payment_mode', 'installment_number')
    list_filter = ('payment_mode', 'retail')
    search_fields = ('payment_no', 'enrollment__enrollment_no')


@admin.register(CustomerPortalCredential)
class CustomerPortalCredentialAdmin(admin.ModelAdmin):
    list_display = ('ledger', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('ledger__ac_name', 'ledger__mobile1')


@admin.register(CustomerPortalOTP)
class CustomerPortalOTPAdmin(admin.ModelAdmin):
    list_display = ('mobile', 'retail', 'otp_code', 'is_verified', 'attempts', 'created_at')
    list_filter = ('is_verified', 'retail')


@admin.register(CustomerPortalToken)
class CustomerPortalTokenAdmin(admin.ModelAdmin):
    list_display = ('ledger', 'mobile', 'retail', 'created_at', 'expires_at')
    list_filter = ('retail',)
    search_fields = ('ledger__ac_name', 'mobile')
