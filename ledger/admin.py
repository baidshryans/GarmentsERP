from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from core.admin import ReadOnlyAdminMixin

from . import models


@admin.register(models.AccountGroup)
class AccountGroupAdmin(SimpleHistoryAdmin):
    list_display = ("name", "parent", "nature", "statement", "is_active")
    list_filter = ("nature", "statement", "is_active")


@admin.register(models.Ledger)
class LedgerAdmin(SimpleHistoryAdmin):
    list_display = ("name", "group", "system_key", "bill_wise", "is_active")
    list_filter = ("group", "is_active", "bill_wise")
    search_fields = ("name", "code")

    def has_delete_permission(self, request, obj=None):
        # A ledger with entries can only be deactivated (E1.3).
        return obj is not None and not obj.lines.exists() and not obj.is_system


class LineInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = models.VoucherLine
    extra = 0


@admin.register(models.Voucher)
class VoucherAdmin(ReadOnlyAdminMixin, SimpleHistoryAdmin):
    """Vouchers are created through the posting service, never in the admin."""

    list_display = ("number", "voucher_type", "date", "factory", "total", "status")
    list_filter = ("voucher_type", "status", "factory")
    search_fields = ("number", "narration")
    inlines = [LineInline]

    def get_queryset(self, request):
        return super().get_queryset(request).for_user(request.user)
