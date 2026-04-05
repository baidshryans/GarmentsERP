from django.contrib import admin

from inventory.models import (
    BarcodeMain, BarcodeDetails, BarcodeTransaction, BarcodeSplitMerge,
    DesignMain, DesignDetails, DesignDocument,
    UnBarcodedMain, UnBarcodedDetails,
    StockJournal, StockJournalDetail,
    StockTransfer, StockTransferMain,
    RawMaterialInventory,
)


# ---------------------------------------------------------------------------
# BarcodeMain (2-level: BarcodeMain → BarcodeDetails)
# ---------------------------------------------------------------------------

class BarcodeDetailsInline(admin.TabularInline):
    model = BarcodeDetails
    fk_name = 'barcode'
    extra = 0
    fields = ('item', 'packet', 'pcs', 'ct', 'gw', 'rate', 'amt')


@admin.register(BarcodeMain)
class BarcodeMainAdmin(admin.ModelAdmin):
    list_display = ('barcode', 'item', 'purity', 'gw', 'stk_status', 'retail', 'created_date')
    list_select_related = ('item', 'purity', 'retail')
    search_fields = ('barcode', 'item__item_name', 'design_code')
    list_filter = ('stk_status', 'retail', 'created_date')
    inlines = [BarcodeDetailsInline]


# ---------------------------------------------------------------------------
# DesignMain (2-level: DesignMain → DesignDetails + DesignDocument)
# ---------------------------------------------------------------------------

class DesignDetailsInline(admin.TabularInline):
    model = DesignDetails
    fk_name = 'design_no'
    extra = 0
    fields = ('sub_item', 'metal_purity', 'pcs', 'ct', 'rate', 'amt')


class DesignDocumentInline(admin.TabularInline):
    model = DesignDocument
    fk_name = 'design'
    extra = 0
    fields = ('asset_type', 'file')


@admin.register(DesignMain)
class DesignMainAdmin(admin.ModelAdmin):
    list_display = ('design_no', 'item', 'pcs', 'gw', 'nw', 'making_type', 'retail')
    list_select_related = ('item', 'retail')
    search_fields = ('design_no', 'item_desc')
    list_filter = ('retail',)
    inlines = [DesignDetailsInline, DesignDocumentInline]


# ---------------------------------------------------------------------------
# UnBarcodedMain (2-level: UnBarcodedMain → UnBarcodedDetails)
# ---------------------------------------------------------------------------

class UnBarcodedDetailsInline(admin.TabularInline):
    model = UnBarcodedDetails
    fk_name = 'main_item'
    extra = 0
    fields = ('item', 'packet', 'pcs', 'ct', 'gw', 'rate', 'amt')


@admin.register(UnBarcodedMain)
class UnBarcodedMainAdmin(admin.ModelAdmin):
    list_display = ('label', 'item', 'purity', 'gw', 'stk_status', 'retail', 'created_date')
    list_select_related = ('item', 'purity', 'retail')
    search_fields = ('label', 'item__item_name', 'design_code')
    list_filter = ('stk_status', 'retail')
    inlines = [UnBarcodedDetailsInline]


# ---------------------------------------------------------------------------
# StockJournal (2-level: StockJournal → StockJournalDetail)
# ---------------------------------------------------------------------------

class StockJournalDetailInline(admin.TabularInline):
    model = StockJournalDetail
    fk_name = 'billno'
    extra = 0
    fields = ('doc_type', 'item', 'pcs', 'ct', 'gw', 'packet', 'metal_purity')


@admin.register(StockJournal)
class StockJournalAdmin(admin.ModelAdmin):
    list_display = ('billno', 'date1', 'retail')
    list_select_related = ('retail',)
    search_fields = ('billno',)
    list_filter = ('date1', 'retail')
    inlines = [StockJournalDetailInline]


# ---------------------------------------------------------------------------
# Remaining models (no inlines needed)
# ---------------------------------------------------------------------------


@admin.register(BarcodeTransaction)
class BarcodeTransactionAdmin(admin.ModelAdmin):
    list_display = ('barcode', 'billno', 'trans_type', 'date', 'user')
    list_select_related = ('barcode', 'user')


@admin.register(BarcodeSplitMerge)
class BarcodeSplitMergeAdmin(admin.ModelAdmin):
    list_display = ('date1', 'transaction_type', 'old_barcode', 'new_barcode', 'retail')
    list_select_related = ('old_barcode', 'new_barcode', 'retail')


class StockTransferMainInline(admin.TabularInline):
    model = StockTransferMain
    fk_name = 'billno'
    extra = 0
    fields = ('sl_no', 'barcode', 'rec_status')


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = ('billno', 'date1', 'retail', 'to_rt_code', 'sent_status', 'rec_status')
    list_select_related = ('retail', 'to_rt_code')
    search_fields = ('billno',)
    list_filter = ('sent_status', 'rec_status', 'retail')
    inlines = [StockTransferMainInline]


admin.site.register(RawMaterialInventory)
