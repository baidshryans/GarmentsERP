from django.contrib import admin
from .models import (
    Account, CashGoldConversion, VoucherDetail, VoucherMain,
    FixedAsset, DepreciationSuggestion, DepreciationSuggestionLine, FixedAssetSettings,
)

# Register your models here.
admin.site.register(Account)
class VoucherDetailInline(admin.TabularInline):
    model = VoucherDetail
    extra = 1
    fields = ('account', 'credit', 'debit')
    readonly_fields=('account',)

class VoucherMainAdmin(admin.ModelAdmin):
    inlines = [VoucherDetailInline]

admin.site.register(VoucherMain, VoucherMainAdmin)
admin.site.register(CashGoldConversion)


# Fixed Assets admin
class SuggestionLineInline(admin.TabularInline):
    model  = DepreciationSuggestionLine
    extra  = 0
    fields = ('asset', 'opening_wdv', 'calculated_amount', 'approved_amount', 'overridden', 'narration')
    readonly_fields = ('opening_wdv', 'calculated_amount')


@admin.register(FixedAsset)
class FixedAssetAdmin(admin.ModelAdmin):
    list_display  = ('asset_code', 'asset_name', 'retail', 'purchase_date', 'purchase_cost',
                     'depreciation_method', 'rate_or_life', 'accumulated_depreciation', 'status')
    list_filter   = ('retail', 'status', 'depreciation_method')
    search_fields = ('asset_code', 'asset_name')


@admin.register(DepreciationSuggestion)
class DepreciationSuggestionAdmin(admin.ModelAdmin):
    list_display    = ('label', 'retail', 'period_from', 'period_to', 'total_amount', 'status')
    list_filter     = ('retail', 'status')
    inlines         = [SuggestionLineInline]
    readonly_fields = ('total_amount', 'voucher', 'approved_at', 'approved_by')


@admin.register(FixedAssetSettings)
class FixedAssetSettingsAdmin(admin.ModelAdmin):
    list_display = ('retail', 'default_depreciation_expense_ldgr', 'default_accum_depreciation_ldgr')

