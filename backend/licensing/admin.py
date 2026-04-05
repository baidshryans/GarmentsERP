from django.contrib import admin
from .models import AppRegistry, CompanySubscription, AppLicense


class AppLicenseInline(admin.TabularInline):
    model = AppLicense
    extra = 0
    fields = ('app', 'is_enabled', 'licensed_at')
    readonly_fields = ('licensed_at',)
    autocomplete_fields = ('app',)


@admin.register(AppRegistry)
class AppRegistryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'django_app_label', 'monthly_price', 'is_core', 'is_active', 'sort_order')
    list_filter = ('is_core', 'is_active')
    search_fields = ('code', 'name')
    list_editable = ('sort_order', 'is_active', 'monthly_price')
    ordering = ('sort_order',)


@admin.register(CompanySubscription)
class CompanySubscriptionAdmin(admin.ModelAdmin):
    list_display = ('company', 'status', 'start_date', 'end_date', 'max_users', 'max_retails')
    list_filter = ('status',)
    search_fields = ('company__company_name',)
    inlines = [AppLicenseInline]
    fieldsets = (
        (None, {
            'fields': ('company', 'status', 'start_date', 'end_date')
        }),
        ('Limits', {
            'fields': ('max_users', 'max_retails')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
