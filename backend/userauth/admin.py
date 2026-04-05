from django.contrib import admin

from userauth.models import *

# Register your models here.
admin.site.register([ Permission, UserRole])
admin.site.site_header = "Retail Management System"

class PermissionInline(admin.TabularInline):
    model = Permission
    extra = 1

class RoleAdmin(admin.ModelAdmin):
    inlines = [PermissionInline]

admin.site.register(Role, RoleAdmin)