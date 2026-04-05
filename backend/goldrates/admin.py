from django.contrib import admin

from goldrates.models import PurityMaster

# Register your models here.

class PurityMasterAdmin(admin.ModelAdmin):
    list_display = ('id','purity', 'gw_per')

admin.site.register(PurityMaster, PurityMasterAdmin)
