from django.db import models
from django.forms import ValidationError
from manufacturing.models import *
from contacts.models import *
from barcode import EAN13
from barcode.writer import ImageWriter
import qrcode
from io import BytesIO
from django.core.files import File
from django.contrib.auth.models import User
from django.db import  transaction
# from manufacturing.utils import create_or_update_nested
from mastersconfig import serializers


class BarcodeMain(models.Model):
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    barcode = models.CharField(
        max_length=50,
        unique=True,
    )
    qr_code = models.ImageField(upload_to='qrcodes/', blank=True)
    pur_voucher = models.ForeignKey("purchase.PurchaseVoucherItems", on_delete=models.SET_NULL, null=True)
    rec_item = models.ForeignKey("manufacturing.KarigarReceiveItem", on_delete=models.SET_NULL, null=True)
    pcs = models.IntegerField(blank=True, null=True)
    gw = models.DecimalField(max_digits=10, decimal_places=3, blank=True, null=True)
    nw = models.DecimalField(max_digits=10, decimal_places=3, blank=True, null=True)
    huid = models.CharField(max_length=30, blank=True,null=True)  # Added blank=True
    purity = models.ForeignKey(PurityMaster, on_delete=models.PROTECT)  # Added blank=True
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    making_val = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    making_type = models.CharField(max_length=50, blank=True)  # Added blank=True
    other_chg = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    design_code = models.CharField(max_length=50, blank=True)  # Added blank=True
    kr_code = models.ForeignKey(Ledger, on_delete=models.SET_NULL, null=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, default=0)
    size = models.CharField(max_length=50, blank=True, null=True)
    metal_color = models.CharField(max_length=50, blank=True, null=True)
    customer_order = models.ForeignKey(CustomerOrder,null=True,on_delete=models.SET_NULL)  
    created_by = models.CharField(max_length=50, blank=True)  # Added blank=True
    created_date = models.DateField(auto_now_add=True)  # Added auto_now_add=True
    
    stk_status = models.BooleanField(default=True)
    op_stk = models.BooleanField(default=False)
    op_retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True,related_name="opening_barcode")
    
    voucher_no = models.CharField(max_length=50, blank=True)  # Added blank=True

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    rfid_tag = models.CharField(max_length=100, blank=True, null=True, db_index=True, unique=True)

    def save(self, *args, **kwargs):
        self.generate_qr_code()
        super().save(*args, **kwargs)

    def generate_qr_code(self):
        if not self.qr_code:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(self.barcode)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, "PNG")
            self.qr_code.save(f'{self.barcode}_qr.png', File(buffer), save=False)

    class Meta:
        db_table = "barcode_main"
        indexes = [
            models.Index(fields=['retail', 'item'], name='idx_bm_retail_item'),
            models.Index(fields=['retail', 'stk_status'], name='idx_bm_retail_stkstatus'),
        ]

class BarcodeDetails(models.Model):  # Inherit models.Model
    barcode = models.ForeignKey(BarcodeMain, on_delete=models.CASCADE)

    packet = models.ForeignKey(Packet, null=True, blank=True, on_delete=models.SET_NULL)
    pcs = models.IntegerField(blank=True, null=True)  # Changed to IntegerField
    ct = models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=3)
    gw = models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=3)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    purity = models.ForeignKey(PurityMaster, null=True, blank=True, on_delete=models.SET_NULL)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amt = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    @property
    def barcode_text(self):
        return self.barcode.barcode
    
    @property
    def uom(self):
        return self.item.uom
    

        

    class Meta:
        db_table="barcode_details"

class BarcodeTransaction(models.Model):  # Inherit models.Model
    date = models.DateTimeField(auto_now_add=True)
    barcode = models.ForeignKey(BarcodeMain, on_delete=models.CASCADE)
    billno = models.CharField(max_length=50)
    trans_type = models.CharField(max_length=50)
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    ip_address = models.GenericIPAddressField(auto_created=True)
    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    class Meta:
        db_table = "barcode_transaction"

class AssetType(models.Model):
    asset_type = models.CharField(max_length=50)  # e.g., "Sketch", "CAD", "Product Image", "Photoshoot"

class DesignMain(models.Model):
    design_no = models.CharField(max_length=50)
    variation_suffix = models.CharField(max_length=50, blank=True, null=True)  # e.g., Colors etc
    

    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    item_desc = models.CharField(max_length=100)
    pcs = models.IntegerField()
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    nw = models.DecimalField(max_digits=10, decimal_places=3)
    making = models.DecimalField(max_digits=10, decimal_places=3)
    making_type = models.CharField(max_length=50)
    kr_code = models.ForeignKey(Ledger, on_delete=models.SET_NULL, null=True, blank=True)
    loss_rate = models.DecimalField(max_digits=10, decimal_places=2)
    making_rate = models.DecimalField(max_digits=10, decimal_places=2)
   
    created_date = models.DateTimeField(auto_now_add=True)
    
    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)


    class Meta:
        db_table = "design_main"

def upload_to_design(instance,filename):
    return f"design/{instance.design.design_no}/{filename}"

class DesignDocument(models.Model):
    design = models.ForeignKey(DesignMain,on_delete=models.CASCADE)
    asset_type = models.ForeignKey(AssetType, on_delete=models.SET_NULL, null=True)
    file = models.FileField(upload_to='design_assets/')

class DesignDetails(models.Model):  # Inherit models.Model
    design_no = models.ForeignKey(DesignMain, on_delete=models.CASCADE)
    sub_item = models.ForeignKey(Item, on_delete=models.PROTECT)
    metal_purity = models.ForeignKey(PurityMaster, on_delete=models.PROTECT)
    pcs = models.IntegerField() 
    ct = models.DecimalField(max_digits=10, decimal_places=3)
    rate = models.IntegerField()
    amt = models.IntegerField()

    class Meta:
        db_table = "design_details"


class CVDTest(models.Model):
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    item = GenericForeignKey('content_type', 'object_id')
    cvd_check = models.BooleanField()
    date = models.DateField(auto_now=True)
    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)


class BarcodeImage(models.Model):
    barcode = models.ForeignKey(BarcodeMain, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(
        upload_to='barcode_images/%Y/%m/',
        storage='mastersconfig.storage.DynamicBarcodeImageStorage',
    )
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'barcode_images'


class BarcodeSplitMerge(models.Model):
    date1 = models.DateField(auto_now_add=True)
    transaction_type = models.CharField(max_length=50, choices=[('Split', 'Split'), ('Merge', 'Merge')])
    old_barcode = models.ForeignKey(BarcodeMain, on_delete=models.SET_NULL, null=True, related_name='old_barcode')
    new_barcode = models.ForeignKey(BarcodeMain, on_delete=models.SET_NULL, null=True, related_name='new_barcode')
    retail = models.ForeignKey(RetailMaster, on_delete=models.SET_NULL, null=True)
    #when the transaction type is Split, the new barcode will be "<oldbarcode>"&"A"
    #when the transaction type is Merge, the new barcode will be a new random barcode


class RfidCountSession(models.Model):
    """Records a single RFID inventory count session for a retail branch."""
    STATUS_CHOICES = [('open', 'Open'), ('closed', 'Closed')]
    session_no = models.CharField(max_length=50)
    date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    note = models.CharField(max_length=255, blank=True)
    retail = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = 'rfid_count_session'
        unique_together = [('session_no', 'retail')]


class RfidCountResult(models.Model):
    """Each RFID tag read during a count session, with match status."""
    STATUS_CHOICES = [('matched', 'Matched'), ('unexpected', 'Unexpected')]
    session = models.ForeignKey(RfidCountSession, on_delete=models.CASCADE, related_name='results')
    rfid_tag = models.CharField(max_length=100)
    barcode = models.ForeignKey(BarcodeMain, on_delete=models.SET_NULL, null=True, blank=True)
    match_status = models.CharField(max_length=15, choices=STATUS_CHOICES)

    class Meta:
        db_table = 'rfid_count_result'


class UnBarcodedMain(models.Model):
    CREATED_FROM_CHOICES = [
        ('KAR_REC', 'Karigar Receipt'),
        ('PUR_VOU', 'Purchase Voucher'),
        ('BAR_CONV', 'Barcode Conversion'),
        ('MANUAL', 'Manual'),
        ('OP_STK', 'Opening Stock'),
    ]

    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    item_desc = models.CharField(max_length=50)
    label = models.CharField(max_length=255)
    pcs = models.IntegerField(blank=True, null=True)
    gw = models.DecimalField(max_digits=10, decimal_places=3, blank=True, null=True)
    nw = models.DecimalField(max_digits=10, decimal_places=3, blank=True, null=True)
    huid = models.CharField(max_length=30, blank=True,null=True)  # Added blank=True
    purity = models.ForeignKey(PurityMaster, on_delete=models.PROTECT)  # Added blank=True
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    making_val = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    making_type = models.CharField(max_length=50, blank=True, null=True)  # Added blank=True
    other_chg = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    design_code = models.CharField(max_length=50, blank=True,null=True)  # Added blank=True
    kr_code = models.ForeignKey(Ledger, on_delete=models.SET_NULL, null=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, default=0)
    size = models.CharField(max_length=50, blank=True, null=True)
    metal_color = models.CharField(max_length=50, blank=True, null=True)
    created_from = models.CharField(max_length=50, blank=True, null=True, choices=CREATED_FROM_CHOICES)
    customer_order = models.ForeignKey(CustomerOrder,null=True,on_delete=models.SET_NULL)
    created_by = models.CharField(max_length=50, blank=True,null=True)  # Added blank=True
    created_date = models.DateField(auto_now_add=True)  # Added auto_now_add=True
    source_barcode = models.ForeignKey(
        'BarcodeMain', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='unbarcoded_descendants',
        help_text="Set when this piece originated from a barcode-to-unbarcoded conversion."
    )
    # `next` chains a piece to its successor: when an UnBarcodedMain is issued
    # as a sample and the karigar returns a reworked piece, the new UnBarcodedMain
    # created on receive becomes this piece's `.next`. Populated by the
    # `create_unbarcoded_inventory` signal in manufacturing/signals.py.
    next = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,related_name="prevs")
    stk_status = models.BooleanField(default=True)

    op_stk=models.BooleanField(default=False)
    
    voucher_no = models.CharField(max_length=50, blank=True,null=True)  # Added blank=True

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)



    class Meta:
        db_table = "unbarcoded_main"

class UnBarcodedDetails(models.Model):  # Inherit models.Model
    main_item = models.ForeignKey(UnBarcodedMain, on_delete=models.CASCADE)
    
    packet = models.ForeignKey(Packet, null=True, blank=True, on_delete=models.SET_NULL)
    pcs = models.IntegerField(blank=True, null=True)  # Changed to IntegerField
    ct = models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=3)
    gw = models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=3)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    rate = models.IntegerField(null=True)
    amt = models.IntegerField(null=True)


    class Meta:
        db_table="unbarcoded_details"


class RawMaterialInventory(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    pcs = models.IntegerField(default=0)
    ct = models.DecimalField(decimal_places=3, max_digits=10, default=0)
    gw = models.DecimalField(decimal_places=3, max_digits=10, default=0)
    packet = models.ForeignKey(Packet, on_delete=models.SET_NULL, null=True, blank=True)
    purity = models.ForeignKey(PurityMaster, on_delete=models.SET_NULL, null=True, blank=True)
    retail = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "raw_material_inventory"
        unique_together = ['item', 'packet', 'purity', 'retail']


class RawMaterialTransaction(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    packet = models.ForeignKey(Packet, on_delete=models.SET_NULL, null=True, blank=True)
    purity = models.ForeignKey(PurityMaster, on_delete=models.SET_NULL, null=True, blank=True)
    trans_type = models.CharField(max_length=50)
    pcs = models.IntegerField(default=0)
    ct = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    gw = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amt = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billno = models.CharField(max_length=50, blank=True, default='')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    retail = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "raw_material_transaction"
        indexes = [
            models.Index(fields=['retail', 'item', 'trans_type'], name='idx_rmt_retail_item_type'),
            models.Index(fields=['retail', '-date'], name='idx_rmt_retail_date'),
        ]

class OpeningInventory(models.Model):
    item = models.ForeignKey(Item,on_delete=models.CASCADE)
    ldgr = models.ForeignKey(Ledger, on_delete=models.SET_NULL, null=True, blank=True)
    pcs = models.PositiveBigIntegerField(default=0)
    ct = models.DecimalField(decimal_places=3,max_digits=10,default=0)
    gw = models.DecimalField(decimal_places=3,max_digits=10,default=0)
    type = models.CharField(max_length=10, choices=[('SH', 'Showroom'), ('KR', 'Karigar'), ('CO', 'Customer')])
    packet = models.ForeignKey(Packet,on_delete=models.SET_NULL,null=True,blank=True)
    retail = models.ForeignKey(RetailMaster,on_delete=models.CASCADE,null=True)
    purity = models.ForeignKey(PurityMaster,on_delete=models.SET_NULL,null=True) 

    class Meta:
        db_table = "opening_stock"


class StockJournal(models.Model):
    date1 = models.DateField()
    billno = models.CharField(max_length=50)
    remarks = models.CharField(max_length=255, blank=True, default='')
    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)
    class Meta:
        db_table = "stock_journal"
        indexes = [
            models.Index(fields=['retail', '-billno'], name='idx_sj_retail_billno'),
        ]
class StockJournalDetail(models.Model):
    billno = models.ForeignKey(StockJournal, on_delete=models.CASCADE)
    doc_type = models.CharField(max_length=50, choices=[('Issue', 'Issue'), ('Receive', 'Receive')])
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    pcs = models.IntegerField()
    ct = models.DecimalField(max_digits=10, decimal_places=3)
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    loss = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    packet = models.ForeignKey(Packet, on_delete=models.SET_NULL, null=True)
    metal_purity = models.ForeignKey(PurityMaster, on_delete=models.SET_NULL, null=True)
    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)
    class Meta:
        db_table = "stock_journal_detail"


# ── Stock Transfer ─────────────────────────────────────────────────────────────

class StockTransfer(models.Model):
    date1 = models.DateField()
    billno = models.CharField(max_length=50)
    sent_status = models.BooleanField(default=False)   # True = sender has dispatched; barcodes in transit
    rec_status = models.BooleanField(default=False)    # True = receiver has accepted; barcodes in receiver's stock
    to_rt_code = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, related_name='to_rt_code')
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)
    retail = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "stock_transfer"


class StockTransferMain(models.Model):
    sl_no = models.IntegerField()
    barcode = models.ForeignKey(BarcodeMain, on_delete=models.CASCADE)
    rec_status = models.BooleanField(default=False)
    billno = models.ForeignKey(StockTransfer, on_delete=models.CASCADE)

    class Meta:
        db_table = "stock_transfer_main"


# ── Inter-Retail Raw-Material / Stone Transfer ────────────────────────────────
# Distinct from the barcode-level StockTransfer above: this voucher transfers
# raw materials (gold, stones, diamonds) and snapshots the source retail's
# weighted-average rate at transfer date so historical valuation is reproducible.

class InterRetailTransferVoucher(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_IN_TRANSIT = "in_transit"
    STATUS_RECEIVED = "received"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_IN_TRANSIT, "In Transit"),
        (STATUS_RECEIVED, "Received"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    voucher_no = models.CharField(max_length=20)
    transfer_date = models.DateField()
    from_retail = models.ForeignKey(
        "mastersconfig.RetailMaster",
        on_delete=models.PROTECT,
        related_name="inter_retail_transfers_out",
    )
    to_retail = models.ForeignKey(
        "mastersconfig.RetailMaster",
        on_delete=models.PROTECT,
        related_name="inter_retail_transfers_in",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    narration = models.TextField(blank=True, default="")
    fiscal_year = models.ForeignKey(
        "mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "inter_retail_transfer_voucher"
        indexes = [
            models.Index(fields=["from_retail", "transfer_date"], name="idx_irtv_from_date"),
            models.Index(fields=["to_retail", "transfer_date"], name="idx_irtv_to_date"),
            models.Index(fields=["status", "transfer_date"], name="idx_irtv_status_date"),
        ]

    def __str__(self):
        return f"{self.voucher_no} ({self.from_retail_id}->{self.to_retail_id})"


class InterRetailTransferItem(models.Model):
    voucher = models.ForeignKey(
        InterRetailTransferVoucher, on_delete=models.CASCADE, related_name="items"
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    purity = models.ForeignKey(PurityMaster, on_delete=models.PROTECT, null=True, blank=True)
    qty_pcs = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    qty_gw = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    qty_ct = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    # Primary qty = gw for M/R items, ct for S items. Populated on save.
    primary_qty = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    # Snapshotted from source retail's weighted-average rate at transfer_date at save.
    # Never recomputed — preserves historical reproducibility.
    source_avg_rate = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    transfer_value = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    # Optional physical-ownership links — when a specific barcode/unbarcoded/packet is transferred,
    # its retail FK is updated to voucher.to_retail on receive.
    barcode = models.ForeignKey(BarcodeMain, on_delete=models.PROTECT, null=True, blank=True)
    unbarcoded_ref = models.ForeignKey(UnBarcodedMain, on_delete=models.PROTECT, null=True, blank=True)
    packet = models.ForeignKey(Packet, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        db_table = "inter_retail_transfer_item"
        indexes = [
            models.Index(fields=["voucher", "item"], name="idx_irti_voucher_item"),
            models.Index(fields=["item"], name="idx_irti_item"),
        ]


class BarcodeOrderReleaseLog(models.Model):
    MODE_CANCEL = "cancel_order"
    MODE_REASSIGN = "reassign"
    MODE_CHOICES = [
        (MODE_CANCEL, "Cancel original order"),
        (MODE_REASSIGN, "Release - order stays open"),
    ]

    barcode = models.ForeignKey(BarcodeMain, on_delete=models.CASCADE, related_name="order_release_logs")
    original_order = models.ForeignKey(CustomerOrder, on_delete=models.SET_NULL, null=True, blank=True)
    original_order_no = models.CharField(max_length=50, blank=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    remarks = models.TextField(blank=True)
    released_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    released_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "barcode_order_release_log"
        ordering = ["-released_at"]