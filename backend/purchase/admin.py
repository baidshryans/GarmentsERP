from django.contrib import admin
import nested_admin

from purchase.models import (
    PurchaseVoucher, PurchaseVoucherItems, PurchaseVoucherDetails,
    PurchaseOrder, PurchaseOrderItems,
    PurchaseReturn, PurchaseReturnItems, PurchaseReturnDetails,
)


# ---------------------------------------------------------------------------
# PurchaseVoucher (true 3-level nested: Voucher → Items → Details)
# ---------------------------------------------------------------------------

class PurchaseVoucherDetailsInline(nested_admin.NestedTabularInline):
    model = PurchaseVoucherDetails
    fk_name = 'main_item'
    extra = 0
    fields = ('sub_item', 'sub_pcs', 'sub_gw', 'sub_ct', 'metal_purity', 'tunch', 'packet', 'rate', 'value')


class PurchaseVoucherItemsInline(nested_admin.NestedTabularInline):
    model = PurchaseVoucherItems
    fk_name = 'billno'
    extra = 0
    fields = ('item', 'barcode', 'pcs', 'gw', 'purity', 'making', 'making_type', 'making_value', 'item_value', 'sl_no')
    inlines = [PurchaseVoucherDetailsInline]


@admin.register(PurchaseVoucher)
class PurchaseVoucherAdmin(nested_admin.NestedModelAdmin):
    list_display = ('billno', 'date1', 'voucher_type', 'ldgr', 'bill_value', 'retail')
    list_select_related = ('ldgr', 'retail')
    search_fields = ('billno', 'ldgr__ac_name')
    list_filter = ('date1', 'voucher_type', 'retail')
    inlines = [PurchaseVoucherItemsInline]



# ---------------------------------------------------------------------------
# PurchaseOrder (2-level: PurchaseOrder → PurchaseOrderItems)
# ---------------------------------------------------------------------------

class PurchaseOrderItemsInline(nested_admin.NestedTabularInline):
    model = PurchaseOrderItems
    fk_name = 'po_slip'
    extra = 0
    fields = ('item', 'purity', 'pcs', 'approx_wt', 'design_code', 'size', 'making_type', 'due_date', 'remarks', 'rec_status', 'po_sl_no')


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(nested_admin.NestedModelAdmin):
    list_display = ('po_no', 'date1', 'po_type', 'ldgr', 'retail')
    list_select_related = ('ldgr', 'retail')
    search_fields = ('po_no', 'ldgr__ac_name')
    list_filter = ('date1', 'po_type', 'retail')
    inlines = [PurchaseOrderItemsInline]


# ---------------------------------------------------------------------------
# PurchaseReturn (true 3-level nested: Return → Items → Details)
# ---------------------------------------------------------------------------

class PurchaseReturnDetailsInline(nested_admin.NestedTabularInline):
    model = PurchaseReturnDetails
    fk_name = 'main_item'
    extra = 0
    fields = ('sub_item', 'sub_pcs', 'sub_gw', 'sub_ct', 'metal_purity', 'tunch', 'packet', 'rate', 'value')


class PurchaseReturnItemsInline(nested_admin.NestedTabularInline):
    model = PurchaseReturnItems
    fk_name = 'billno'
    extra = 0
    fields = ('item', 'pcs', 'gw', 'purity', 'making', 'making_type', 'making_value', 'sl_no', 'remarks')
    inlines = [PurchaseReturnDetailsInline]


@admin.register(PurchaseReturn)
class PurchaseReturnAdmin(nested_admin.NestedModelAdmin):
    list_display = ('billno', 'date1', 'ldgr', 'bill_value', 'retail')
    list_select_related = ('ldgr', 'retail')
    search_fields = ('billno', 'ldgr__ac_name')
    list_filter = ('date1', 'retail')
    inlines = [PurchaseReturnItemsInline]


