from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from simple_history.admin import SimpleHistoryAdmin

from . import models


class ReadOnlyAdminMixin:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.User)
class UserAdminConfig(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Garment ERP", {"fields": ("mobile", "roles", "all_factories", "allowed_factories")}),
    )
    list_display = ("username", "mobile", "is_active", "all_factories")
    filter_horizontal = UserAdmin.filter_horizontal + ("roles", "allowed_factories")


class RolePermissionInline(admin.TabularInline):
    model = models.RolePermission
    extra = 0


class FieldPermissionInline(admin.TabularInline):
    model = models.FieldPermission
    extra = 0


@admin.register(models.Role)
class RoleAdmin(SimpleHistoryAdmin):
    inlines = [RolePermissionInline, FieldPermissionInline]


@admin.register(models.Company, models.FinancialYear, models.Factory, models.Location, models.NumberSeries)
class HistoryAdmin(SimpleHistoryAdmin):
    pass


@admin.register(models.PeriodLock, models.PeriodLockLog, models.AuditEvent)
class ReadOnlyLogAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    pass
