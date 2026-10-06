from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from . import models


class LotStepInline(admin.TabularInline):
    model = models.LotStep
    extra = 0
    raw_id_fields = ("party",)


class CuttingSizeInline(admin.TabularInline):
    model = models.CuttingSize
    extra = 0


class PackEntryLineInline(admin.TabularInline):
    model = models.PackEntryLine
    extra = 0
    raw_id_fields = ("sku",)


@admin.register(models.ProductionOrder)
class ProductionOrderAdmin(SimpleHistoryAdmin):
    list_display = ("number", "status", "date", "factory")
    list_filter = ("status", "factory")


@admin.register(models.Lot)
class LotAdmin(SimpleHistoryAdmin):
    list_display = ("lot_no", "style", "colour", "status", "factory")
    list_filter = ("status", "factory")
    raw_id_fields = ("order_line", "style", "bom_version")
    inlines = [LotStepInline]


@admin.register(models.FabricIssue)
class FabricIssueAdmin(SimpleHistoryAdmin):
    list_display = ("lot", "date", "expected_pieces", "mixed_shades", "factory")
    raw_id_fields = ("lot",)


@admin.register(models.CuttingEntry)
class CuttingEntryAdmin(SimpleHistoryAdmin):
    list_display = ("lot", "lay_no", "date", "expected_pieces", "variance_pct", "over_tolerance", "bundled", "factory")
    list_filter = ("over_tolerance", "bundled", "factory")
    raw_id_fields = ("lot",)
    inlines = [CuttingSizeInline]


@admin.register(models.Bundle)
class BundleAdmin(SimpleHistoryAdmin):
    list_display = ("bundle_no", "lot", "sku", "qty", "status", "location", "split_from", "is_rework")
    list_filter = ("status", "is_rework")
    search_fields = ("bundle_no", "qr_token", "lot__lot_no")
    raw_id_fields = ("lot", "entry", "sku", "current_step", "split_from")


@admin.register(models.PackEntry)
class PackEntryAdmin(SimpleHistoryAdmin):
    list_display = ("lot", "date", "location", "factory")
    list_filter = ("factory",)
    raw_id_fields = ("lot",)
    inlines = [PackEntryLineInline]
