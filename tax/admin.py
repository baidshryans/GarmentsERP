from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import TaxSetting

admin.site.register(TaxSetting, SimpleHistoryAdmin)

from .models import HSN, HsnSlab

admin.site.register(HSN, SimpleHistoryAdmin)
admin.site.register(HsnSlab, SimpleHistoryAdmin)

from .models import TaxTemplate, TaxTemplateLine


class TaxTemplateLineInline(admin.TabularInline):
    model = TaxTemplateLine
    extra = 0


@admin.register(TaxTemplate)
class TaxTemplateAdmin(SimpleHistoryAdmin):
    inlines = [TaxTemplateLineInline]
    list_display = ("name", "kind", "is_interstate", "is_reverse_charge", "section", "is_active")
