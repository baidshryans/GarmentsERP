from django.contrib import admin
import nested_admin

from sales.models import (
    CustomerOrder, CustomerOrderItems,
    SalesVou, SalesVouItem, SalesVouItemDetails, BankDetail,
    SaleReturn, SaleReturnItem, SaleReturnDetails,
    SalesApproval, SalesApprovalItem, SalesApprovalItemDetails,
)


class CustomerOrderItemsInline(admin.TabularInline):
    model = CustomerOrderItems
    fk_name = 'order_no'
    extra = 0
    fields = ('sl_no', 'item_id', 'purity', 'pcs', 'gw', 'size', 'making_type', 'making_amt',
              'other_chg', 'iss_status', 'rec_status', 'del_status', 'sale_status', 'remarks')


@admin.register(CustomerOrder)
class CustomerOrderAdmin(admin.ModelAdmin):
    list_display = ('order_no', 'date1', 'ldgr', 'est_amount', 'advance_amt', 'status', 'delivery_date', 'retail')
    list_select_related = ('ldgr', 'retail')
    search_fields = ('order_no', 'ldgr__ac_name')
    list_filter = ('status', 'nature', 'retail', 'date1')
    inlines = [CustomerOrderItemsInline]


# ============= SalesVou Admin (formerly in sale_voucher app) =============

class SalesVouItemDetailsInline(nested_admin.NestedTabularInline):
    model = SalesVouItemDetails
    fk_name = 'main_item'
    extra = 0
    fields = ('item', 'pcs', 'ct', 'gw', 'metal_purity', 'tunch', 'rate', 'amount', 'packet')


class SalesVouItemInline(nested_admin.NestedTabularInline):
    model = SalesVouItem
    fk_name = 'billno'
    extra = 0
    fields = ('barcode', 'item', 'pcs', 'gw', 'purity', 'making', 'making_type', 'making_value', 'amount')
    inlines = [SalesVouItemDetailsInline]


class BankDetailInline(nested_admin.NestedTabularInline):
    model = BankDetail
    fk_name = 'sales_vou'
    extra = 0
    fields = ('bank_name', 'amount', 'chq_no', 'chq_date')


@admin.register(SalesVou)
class SalesVouAdmin(nested_admin.NestedModelAdmin):
    list_display = ('billno', 'date1', 'ldgr', 'mrp', 'discount', 'retail')
    list_select_related = ('ldgr', 'retail')
    search_fields = ('billno', 'ldgr__ac_name')
    list_filter = ('date1', 'retail')
    inlines = [SalesVouItemInline, BankDetailInline]


# ============= SaleReturn Admin =============

class SaleReturnDetailsInline(nested_admin.NestedTabularInline):
    model = SaleReturnDetails
    fk_name = 'main_item'
    extra = 0
    fields = ('item', 'pcs', 'ct', 'gw', 'metal_purity', 'tunch', 'rate', 'amount', 'packet')


class SaleReturnItemInline(nested_admin.NestedTabularInline):
    model = SaleReturnItem
    fk_name = 'billno'
    extra = 0
    fields = ('barcode', 'item', 'pcs', 'gw', 'purity', 'making', 'making_type', 'making_value')
    inlines = [SaleReturnDetailsInline]


@admin.register(SaleReturn)
class SaleReturnAdmin(nested_admin.NestedModelAdmin):
    list_display = ('billno', 'date1', 'ldgr', 'mrp', 'discount', 'retail')
    list_select_related = ('ldgr', 'retail')
    search_fields = ('billno', 'ldgr__ac_name')
    list_filter = ('date1', 'retail')
    inlines = [SaleReturnItemInline]


# ============= SalesApproval Admin =============

class SalesApprovalItemDetailsInline(nested_admin.NestedTabularInline):
    model = SalesApprovalItemDetails
    fk_name = 'main_item'
    extra = 0
    fields = ('item', 'pcs', 'ct', 'gw', 'metal_purity', 'rate', 'amount', 'packet')


class SalesApprovalItemInline(nested_admin.NestedTabularInline):
    model = SalesApprovalItem
    fk_name = 'billno'
    extra = 0
    fields = ('barcode', 'item', 'pcs', 'gw', 'purity', 'amount')
    inlines = [SalesApprovalItemDetailsInline]


@admin.register(SalesApproval)
class SalesApprovalAdmin(nested_admin.NestedModelAdmin):
    list_display = ('billno', 'date1', 'ldgr', 'taxable_value', 'discount', 'retail')
    list_select_related = ('ldgr', 'retail')
    search_fields = ('billno', 'ldgr__ac_name')
    list_filter = ('date1', 'retail')
    inlines = [SalesApprovalItemInline]
