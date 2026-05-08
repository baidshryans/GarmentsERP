from django.contrib import admin
from .models import BranchMaster, Colors, CompanyMaster, Hsn, Item, ItemGroupMaster, Packet, PacketGroup, RetailMaster, SalesPersonMaster, Shapes, State

@admin.register(CompanyMaster)
class CompanyMasterAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'phone', 'email']
    search_fields = ['company_name']

@admin.register(BranchMaster)
class BranchMasterAdmin(admin.ModelAdmin):
    list_display = ['branch_name', 'branch_code', 'company', 'state']
    search_fields = ['branch_name', 'branch_code']
    list_filter = ['company']

admin.site.register(Colors)
admin.site.register(Hsn)
@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['item_name', "short_code","purchase_ledger","sale_ledger","hsn_no"]
    search_fields = ['short_code']
admin.site.register(ItemGroupMaster)
admin.site.register(Packet)
admin.site.register(PacketGroup)
admin.site.register(SalesPersonMaster)
admin.site.register(Shapes)
admin.site.register(RetailMaster)
admin.site.register(State)

