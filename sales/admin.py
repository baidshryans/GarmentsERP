from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from . import models


class OrderLineInline(admin.TabularInline):
    model = models.SaleOrderLine
    extra = 0
    raw_id_fields = ("sku",)


class InvoiceLineInline(admin.TabularInline):
    model = models.SaleInvoiceLine
    extra = 0
    raw_id_fields = ("sku", "order_line")


@admin.register(models.SaleOrder)
class SaleOrderAdmin(SimpleHistoryAdmin):
    list_display = ("number", "customer", "order_type", "status", "date", "factory")
    list_filter = ("status", "order_type", "factory")
    inlines = [OrderLineInline]


@admin.register(models.SaleInvoice)
class SaleInvoiceAdmin(SimpleHistoryAdmin):
    list_display = ("number", "customer", "status", "date", "total", "factory")
    list_filter = ("status", "factory")
    inlines = [InvoiceLineInline]


@admin.register(models.SaleSetting, models.PackingList, models.Carton, models.CartonLine, models.SaleCreditNote,
                models.SaleCreditNoteLine)
class SalesAdmin(SimpleHistoryAdmin):
    pass
