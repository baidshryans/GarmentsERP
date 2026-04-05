from django.contrib import admin

from contacts.models import UserLocation, Ledger


class UserLocationAdmin(admin.ModelAdmin):
    list_display = ['username', 'locations_display', 'default_location']
    filter_horizontal = ['location']  # Easy multi-select for ManyToMany
    readonly_fields = ['user']  # User is OneToOne, don't allow change
    search_fields = ['user__username', 'user__email']

    def username(self, obj):
        """Display the username instead of object string"""
        return obj.user.username
    username.short_description = 'User'

    def locations_display(self, obj):
        """Show comma-separated list of assigned locations"""
        locations = obj.location.all()
        if locations.exists():
            return ', '.join([r.retail_code for r in locations])
        return '(none)'
    locations_display.short_description = 'Assigned Retails'

    def get_queryset(self, request):
        """Optimize queryset to avoid N+1 queries"""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'default_location').prefetch_related('location')

    def save_model(self, request, obj, form, change):
        """Call full_clean() to validate before saving"""
        obj.full_clean()
        super().save_model(request, obj, form, change)


admin.site.register(UserLocation, UserLocationAdmin)


class LedgerAdmin(admin.ModelAdmin):
    list_display = ['id', 'ac_name', 'primary_role_display']
    search_fields = ['id', 'ac_name']

    def primary_role_display(self, obj):
        r = obj.roles.filter(is_primary=True).first()
        return r.role if r else '—'
    primary_role_display.short_description = 'Primary Role'


admin.site.register(Ledger, LedgerAdmin)