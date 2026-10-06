from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from . import models


class ChallanBundleInline(admin.TabularInline):
    model = models.ChallanBundle
    extra = 0
    raw_id_fields = ("bundle",)


class BillLineInline(admin.TabularInline):
    model = models.JobWorkBillLine
    extra = 0
    raw_id_fields = ("challan", "lot")


@admin.register(models.LabourRate)
class LabourRateAdmin(SimpleHistoryAdmin):
    list_display = ("party", "process", "rate_type", "base_rate", "rework_rate", "pay_basis", "effective_from", "is_active")
    list_filter = ("rate_type", "pay_basis", "process", "is_active")


@admin.register(models.JobWorkChallan)
class JobWorkChallanAdmin(SimpleHistoryAdmin):
    list_display = ("number", "party", "lot", "kind", "status", "pay_basis", "date", "factory")
    list_filter = ("status", "kind", "pay_basis", "factory")
    raw_id_fields = ("lot", "step", "voucher")
    inlines = [ChallanBundleInline]


@admin.register(models.Receipt)
class ReceiptAdmin(SimpleHistoryAdmin):
    list_display = ("number", "challan", "status", "date", "factory")
    list_filter = ("status", "factory")
    raw_id_fields = ("challan",)


@admin.register(models.QcResult)
class QcResultAdmin(SimpleHistoryAdmin):
    list_display = ("line", "accepted", "rejected", "rework", "pay_qty", "rate", "is_rework_pass", "checked_at")
    raw_id_fields = ("line", "bill_line")


@admin.register(models.JobWorkBill)
class JobWorkBillAdmin(SimpleHistoryAdmin):
    list_display = ("number", "party", "status", "date", "gross", "deductions", "net", "factory")
    list_filter = ("status", "factory")
    raw_id_fields = ("voucher",)
    inlines = [BillLineInline]


@admin.register(models.JobWorkDeductionWaiver)
class JobWorkDeductionWaiverAdmin(SimpleHistoryAdmin):
    list_display = ("receipt_line", "receipt_trim", "reason", "waived_by", "waived_at")
    raw_id_fields = ("receipt_line", "receipt_trim")
