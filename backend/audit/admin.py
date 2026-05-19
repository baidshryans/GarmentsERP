from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'action', 'model_label', 'object_pk',
                    'username_snapshot', 'retail', 'is_parent_event')
    list_filter  = ('action', 'is_parent_event', 'created_month', 'retail')
    search_fields = ('model_label', 'object_pk', 'username_snapshot',
                     'object_repr')
    readonly_fields = [f.name for f in AuditEvent._meta.fields]
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
