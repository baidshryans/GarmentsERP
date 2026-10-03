from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from . import models


class StyleColourInline(admin.TabularInline):
    model = models.StyleColour
    extra = 0


@admin.register(models.Style)
class StyleAdmin(SimpleHistoryAdmin):
    list_display = ("style_no", "name", "product", "is_archived")
    search_fields = ("style_no", "name")
    list_filter = ("product", "is_archived")


@admin.register(models.SKU)
class SKUAdmin(SimpleHistoryAdmin):
    list_display = ("style", "colour", "size", "barcode", "is_active")
    search_fields = ("barcode", "style__style_no")


@admin.register(models.Party)
class PartyAdmin(SimpleHistoryAdmin):
    list_display = ("code", "name", "mobile", "is_customer", "is_vendor", "is_fabricator", "is_active")
    search_fields = ("name", "mobile", "code", "gstin")


admin.site.register(
    [models.Unit, models.UnitConversion, models.Size, models.Colour, models.Product, models.Material,
     models.Process, models.RouteTemplate, models.RouteStep, models.PriceList, models.PriceListRate,
     models.CustomerRate, models.PartyAddress, models.BomVersion],
    SimpleHistoryAdmin,
)
