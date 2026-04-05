from django.contrib import admin
from .models import Account, CashGoldConversion, VoucherDetail, VoucherMain

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

