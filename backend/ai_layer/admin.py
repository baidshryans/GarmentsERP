from django.contrib import admin
from .models import NLQueryLog


@admin.register(NLQueryLog)
class NLQueryLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'retail', 'short_query', 'tokens_used', 'created_at')
    list_filter = ('retail', 'created_at')
    search_fields = ('query_text', 'response_text', 'user__username')
    readonly_fields = ('query_text', 'response_text', 'tool_calls_json', 'tokens_used', 'created_at', 'user', 'retail')

    def short_query(self, obj):
        return obj.query_text[:80]
    short_query.short_description = 'Query'
