from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from contacts.models import Ledger
from mastersconfig.models import *
from goldrates.models import *
from sales.models import CustomerOrder, CustomerOrderItems
from inventory.models import BarcodeMain, BarcodeDetails
def _attachment_storage():
    """Callable storage factory — resolves DynamicAttachmentStorage at access time."""
    from mastersconfig.storage import DynamicAttachmentStorage
    return DynamicAttachmentStorage()

# Create your models here.
class PurchaseVoucher(models.Model):
    VOUCHER_TYPE_CHOICES = [
        ('Customer', 'Customer'),
        ('Vendor', 'Vendor'),
    ]

    date1 = models.DateField()
    billno = models.CharField(max_length=30) #
    voucher_type = models.CharField(max_length=10, choices=VOUCHER_TYPE_CHOICES) #
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)
    hallmark_charge = models.DecimalField(null=True, max_digits=10, decimal_places =2) #
    ref_no = models.CharField(max_length=10, null=True,blank=True) #
    ref_date = models.DateField(null=True) #
    ldgr = models.ForeignKey(Ledger, on_delete=models.SET_NULL, null=True, related_name='ldgr_code') #
    item_total = models.DecimalField(null=True, max_digits=12, decimal_places=2) #
    discount_amt = models.DecimalField(default=Decimal(0.00), max_digits=10, decimal_places =2) #
    round_off = models.DecimalField(default=Decimal(0.00), max_digits=10, decimal_places =2) #
    add_chrg_cap1 = models.CharField(max_length=10, null=True,blank=True) #
    add_chrg_cap2 = models.CharField(max_length=10, null=True,blank=True) #
    add_chrg_amt1 = models.DecimalField(null=True, max_digits=10, decimal_places =2) #
    add_chrg_amt2 = models.DecimalField(null=True, max_digits=10, decimal_places =2) #
    freight_amt = models.DecimalField(null=True, max_digits=10, decimal_places =2) #
    cgst = models.DecimalField(null=True, max_digits=10, decimal_places =2) #
    sgst = models.DecimalField(null=True, max_digits=10, decimal_places =2) #
    igst = models.DecimalField(null=True, max_digits=10, decimal_places =2) #
    tcs_amt = models.DecimalField(null=True, max_digits=10, decimal_places =2) #
    tds_section       = models.ForeignKey('mastersconfig.TDSSectionMaster', on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_vouchers')
    tds_rate          = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    tds_taxable_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tds_amt           = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    narration = models.CharField(max_length=100, null=True,blank=True) #
    total_incl_gst = models.DecimalField(null=True, max_digits=10, decimal_places =2) #
    bill_value = models.DecimalField(null=True, max_digits=10, decimal_places =2) #
    due_amt = models.DecimalField(null=True, max_digits=10, decimal_places =2) 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_return = models.BooleanField(default=False)
    hsn = models.ForeignKey("mastersconfig.Hsn", on_delete=models.SET_NULL, null=True, blank=True)
    is_rcm = models.BooleanField(
        default=False,
        help_text="Reverse charge applies — old gold purchased from unregistered individual"
    )

    SOURCE_CHOICES = [
        ('standalone', 'Standalone'),
        ('sales_inline', 'Sales Inline'),
    ]
    source = models.CharField(
        max_length=20,
        default='standalone',
        choices=SOURCE_CHOICES,
        help_text="standalone: created directly; sales_inline: auto-created from a Sales Voucher and read-only here",
    )

    ac_voucher     = models.ForeignKey("accounting.VoucherMain", on_delete=models.SET_NULL, null=True, blank=True)
    tds_ac_voucher = models.ForeignKey("accounting.VoucherMain", on_delete=models.SET_NULL, null=True, blank=True, related_name='tds_purchase_vouchers')

    retail     = models.ForeignKey("mastersconfig.RetailMaster",  on_delete=models.SET_NULL, null=True, blank=True)
    gstin_ref  = models.ForeignKey("mastersconfig.GSTINMaster",  on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_vouchers')
    branch_ref = models.ForeignKey("mastersconfig.BranchMaster", on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_vouchers')

    #return tag
    @property
    def ldgr_name(self):
        return self.ldgr.ac_name
    class Meta:
        db_table="purchase_voucher"
        indexes = [
            models.Index(fields=['retail', '-billno'], name='idx_pv_retail_billno'),
            models.Index(fields=['retail', 'date1'], name='idx_pv_retail_date'),
            models.Index(fields=['ldgr'], name='idx_pv_ldgr'),
        ]

class PurchaseAttachment(models.Model):
    purchase = models.ForeignKey(PurchaseVoucher, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(
        upload_to='purchase_attachments/%Y/%m/',
        storage=_attachment_storage,
    )
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "purchase_attachment"

    def __str__(self):
        return f"{self.original_name} – {self.purchase.billno}"


class PurchaseVoucherItems(models.Model): #main item
    billno = models.ForeignKey(PurchaseVoucher, on_delete=models.CASCADE, null=True)
    date1 = models.DateField(null=True)
    po_no = models.CharField(max_length=50, null=True, blank=True)
    po_sl_no = models.IntegerField(null=True, blank=True)
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    barcode = models.ForeignKey(BarcodeMain, on_delete=models.SET_NULL, null=True)
    barcode_txt = models.CharField(max_length=20, null=True,blank=True)
    order_no = models.ForeignKey(CustomerOrder, on_delete=models.CASCADE, null=True, blank=True)
    # Line-level link for the direct CO → PV path (skipping the PO step).
    # Mutually exclusive with po_no/po_sl_no at the serializer level.
    customer_order_item = models.ForeignKey(
        'sales.CustomerOrderItems',
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    sl_no = models.IntegerField()
    pcs = models.IntegerField(null=True)
    gw = models.DecimalField(null=True, max_digits=10, decimal_places=3)
    size = models.CharField(null=True, max_length=10,blank=True)
    purity = models.ForeignKey(PurityMaster, on_delete=models.SET_NULL, null=True)
    pending_pcs = models.IntegerField(null=True, blank=True, default=0)
    pending_gw = models.DecimalField(default=0, max_digits=10, decimal_places=3)
    making_type = models.CharField(max_length=20, blank=True, default='')
    making = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    making_value = models.IntegerField(null=True)
    item_value = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    remarks = models.CharField(max_length=100, null=True,blank=True)
    is_return = models.BooleanField(default=False)
    is_finished = models.BooleanField(default=False)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)
    @property
    def date(self):
        return self.billno.date1

    class Meta:
        db_table="purchase_voucher_main"
        constraints = [
            models.UniqueConstraint(
                fields=['customer_order_item'],
                condition=models.Q(customer_order_item__isnull=False),
                name='uniq_pv_customer_order_item',
            ),
        ]
class PurchaseVoucherDetails(models.Model):
    main_item = models.ForeignKey(PurchaseVoucherItems, on_delete=models.CASCADE, null=True)
    billno = models.ForeignKey(PurchaseVoucher, on_delete=models.CASCADE, null=True)
    date1 = models.DateField(null=True)
    sub_item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    sub_pcs = models.IntegerField(null=True, blank=True, default=0)
    sub_gw = models.DecimalField(null=True, max_digits=10, decimal_places=3, blank=True, default=0)
    sub_ct = models.DecimalField(null=True, max_digits=10, decimal_places=3, blank=True, default=0)
    metal_purity = models.ForeignKey(PurityMaster, on_delete=models.SET_NULL, null=True, blank=True)
    loss = models.DecimalField(null=True, max_digits=10, decimal_places =2, blank=True, default=0)
    tunch = models.DecimalField(null=True, max_digits=10, decimal_places =2, blank=True, default=0)

    fine_wt = models.DecimalField(null=True, max_digits=10, decimal_places =2, blank=True, default=0)

    packet = models.ForeignKey(Packet, on_delete=models.SET_NULL, null=True, blank=True)
    rate = models.DecimalField(null=True, max_digits=10, decimal_places =2, blank=True, default=0)
    value = models.DecimalField(null=True, max_digits=10, decimal_places =2, blank=True, default=0)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    @property
    def date(self):
        return self.main_item.billno.date1 if self.main_item else self.billno.date1
    class Meta:
        db_table="purchase_voucher_details"


class PurchaseOrder(models.Model):
    from global_vars import STATES_OF_INDIA
    PO_TYPE_CHOICES = [('Customer Order','Customer Order'),('Stock','Stock'),('Repair','Repair')]
    date1 = models.DateField()
    po_type = models.CharField(max_length=20, choices=PO_TYPE_CHOICES)
    po_no = models.CharField(max_length=30, unique=True)
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)
    ldgr = models.ForeignKey(Ledger, on_delete = models.CASCADE)
    place_of_supply = models.CharField(max_length=100, null=True, blank=True, choices=STATES_OF_INDIA)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)
    #return tag
    @property
    def ldgr_name(self):
        return self.ldgr.ac_name

    class Meta:
        db_table="purchase_order"
        indexes = [
            models.Index(fields=['retail', '-po_no'], name='idx_po_retail_pono'),
        ]

class PurchaseOrderItems(models.Model):
    po_slip = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE)
    po_sl_no = models.IntegerField()
    
    customer_order_item = models.ForeignKey(CustomerOrderItems, on_delete=models.SET_NULL, null=True, blank=True) 
    
    item = models.ForeignKey(Item,on_delete=models.SET_NULL, null=True)
    purity = models.ForeignKey(PurityMaster, on_delete = models.SET_NULL, null=True)
    pcs = models.IntegerField()
    approx_wt = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    design_code = models.CharField(max_length=10, null=True, blank=True)
    size = models.CharField(max_length=10, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    remarks = models.CharField(max_length=50, null=True, blank=True)

    rec_status = models.BooleanField(default=False)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    
    class Meta:
        db_table = "purchase_order_main"
        constraints = [
            models.UniqueConstraint(
                fields=['customer_order_item'],
                condition=models.Q(customer_order_item__isnull=False),
                name='uniq_po_customer_order_item',
            ),
        ]

class PurchaseReturn(models.Model):
    billno = models.CharField(max_length=30)
    pv_billno=models.CharField(max_length=30,null=True, blank=True)
    # Header-level reference back to the original purchase voucher being returned
    purchase_voucher_ref = models.ForeignKey(
        PurchaseVoucher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='purchase_returns'
    )
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)
    date1 = models.DateField(auto_now_add=True)
    ldgr = models.ForeignKey(Ledger, on_delete = models.CASCADE)
    discount = models.DecimalField(max_digits=10, decimal_places=2)
    cgst_amt = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    sgst_amt = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    igst_amt = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    tcs_amt = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    narration = models.CharField(max_length=100)
    mode_of_transport = models.CharField(max_length=20)
    hallmark_charge = models.DecimalField(null=True, max_digits=10, decimal_places =2) #
    freight_amt = models.DecimalField(null=True, max_digits=10, decimal_places =2) #
    bill_value = models.DecimalField(null=True, max_digits=10, decimal_places =2) #
    round_off = models.DecimalField(null=True, max_digits=10, decimal_places =2) #
    retail     = models.ForeignKey("mastersconfig.RetailMaster",  on_delete=models.SET_NULL, null=True, blank=True)
    gstin_ref  = models.ForeignKey("mastersconfig.GSTINMaster",  on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_returns')
    branch_ref = models.ForeignKey("mastersconfig.BranchMaster", on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_returns')

    ac_voucher = models.ForeignKey("accounting.VoucherMain",on_delete=models.SET_NULL,null=True,blank=True)


    @property
    def ldgr_name(self):
        return self.ldgr.ac_name

    @property
    def total_incl_tax(self):
        return (self.bill_value or Decimal(0)) - (self.discount or Decimal(0)) + \
               (self.cgst_amt or Decimal(0)) + (self.sgst_amt or Decimal(0)) + \
               (self.igst_amt or Decimal(0)) + (self.tcs_amt or Decimal(0))

    class Meta:
        db_table = "purchase_return"
        indexes = [
            models.Index(fields=['retail', '-billno'], name='idx_pr_retail_billno'),
        ]

class PurchaseReturnItems(models.Model): #main item
    billno = models.ForeignKey(PurchaseReturn, on_delete=models.CASCADE, null=True)
    sl_no = models.IntegerField(null=True, blank=True)
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)

    pcs = models.IntegerField(null=True)
    gw = models.DecimalField(null=True, max_digits=10, decimal_places=3)
    purity = models.ForeignKey(PurityMaster, on_delete=models.SET_NULL, null=True)
    making_type = models.CharField(max_length=20, blank=True, default='')
    making_value = models.IntegerField(null=True)
    making = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    remarks = models.CharField(max_length=100, null=True, blank=True)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)
    barcode = models.ForeignKey('inventory.BarcodeMain', on_delete=models.SET_NULL, null=True, blank=True)
    barcode_txt = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table="purchase_return_main"

class PurchaseReturnDetails(models.Model): #main item
    date1 = models.DateField(auto_now_add=True,null=True,blank=True)
    main_item = models.ForeignKey(PurchaseReturnItems, on_delete=models.CASCADE, null=True)
    billno = models.ForeignKey(PurchaseReturn, on_delete=models.CASCADE, null=True)
    sub_item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    sub_pcs = models.IntegerField(null=True, blank=True, default=0)
    sub_gw = models.DecimalField(null=True, max_digits=10, decimal_places=3, blank=True, default=0)
    sub_ct = models.DecimalField(null=True, max_digits=10, decimal_places=3, blank=True, default=0)
    metal_purity = models.ForeignKey(PurityMaster, on_delete=models.SET_NULL, null=True, blank=True)
    loss = models.DecimalField(null=True, max_digits=10, decimal_places =2, blank=True, default=0)
    tunch = models.DecimalField(null=True, max_digits=10, decimal_places =2, blank=True, default=0)
    packet = models.ForeignKey(Packet, on_delete=models.SET_NULL, null=True, blank=True)
    rate = models.DecimalField(null=True, max_digits=10, decimal_places =2, blank=True, default=0)
    value = models.DecimalField(null=True, max_digits=10, decimal_places =2, blank=True, default=0)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    @property
    def date(self):
        return self.main_item.billno.date1 if self.main_item else self.billno.date1
 
    @property
    def fine_wt(self):
        # tunch is stored as a percentage (e.g. 91.6 means 91.6%)
        gw = self.sub_gw if self.sub_gw is not None else Decimal(0)
        tunch = self.tunch if self.tunch is not None else Decimal(0)
        return gw * (tunch / Decimal(100))

    class Meta:
        db_table="purchase_return_details"


