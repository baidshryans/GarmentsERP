from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import TaxSetting

admin.site.register(TaxSetting, SimpleHistoryAdmin)

from .models import HSN, HsnSlab

admin.site.register(HSN, SimpleHistoryAdmin)
admin.site.register(HsnSlab, SimpleHistoryAdmin)
