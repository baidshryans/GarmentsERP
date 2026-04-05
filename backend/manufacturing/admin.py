from django.contrib import admin

from manufacturing.models import HallmarkIssue, HallmarkReceive, HallmarkReceiveItem, KarigarGoldIssue, KarigarIssue, KarigarIssueItem, KarigarMaster, KarigarReceive, KarigarReceiveItem, KarigarReceiveItemDetails, KarigarStoneIssue, KarigarStoneReceive, RefinaryIssue

# Register your models here.
@admin.register(KarigarIssue)
class KarigarIssueAdmin(admin.ModelAdmin):
    list_display = ('id', 'issue_slip_no','retail')
    list_filter = ('retail',)
    search_fields = ('karigar__name', 'id')
admin.site.register(KarigarIssueItem)
admin.site.register(KarigarGoldIssue)
admin.site.register(KarigarReceiveItem)
admin.site.register(KarigarReceiveItemDetails)
admin.site.register(KarigarStoneReceive)
admin.site.register(KarigarStoneIssue)
admin.site.register(KarigarReceive)
admin.site.register(KarigarMaster)
admin.site.register(HallmarkIssue)
admin.site.register(HallmarkReceive)
admin.site.register(HallmarkReceiveItem)
admin.site.register(RefinaryIssue)