from django.db import models
from contacts.models import Ledger
from mastersconfig.models import Item, SalesPersonMaster
from goldrates.models import PurityMaster
from common.audit import TenantHistoricalRecords
# Create your models here.
class CustomerOrder(models.Model):
    ldgr = models.ForeignKey(Ledger, on_delete=models.SET_NULL, null=True)
    date1 = models.DateField()
    order_no = models.CharField(max_length=30, unique=True)
    fix_gold_rate = models.BooleanField(null=True, default=False)
    gold_rate_date = models.DateField(null=True)
    rate_14kt = models.IntegerField(default=0)
    rate_18kt = models.IntegerField(default=0)
    rate_22kt = models.IntegerField(default=0)
    salesman_1 = models.ForeignKey(SalesPersonMaster, related_name = "salesman_1", on_delete = models.SET_NULL, null=True)
    salesman_2 = models.ForeignKey(SalesPersonMaster, related_name = "salesman_2", on_delete = models.SET_NULL, null=True, blank=True)
    est_amount = models.IntegerField(null=True, default=0)
    nature = models.CharField(max_length=20, default="New Booking",blank=True)
    status = models.CharField(max_length=20, default="",blank=True)
    delivery_date = models.DateField(null=True)
    remarks = models.CharField(max_length=100, null=True, blank=True)

    DELIVERY_STATUS_CHOICES = [
        ('pending',        'Pending'),
        ('ready',          'Ready for Delivery'),
        ('delivered',      'Delivered'),
        ('returned',       'Returned'),
        ('partial_return', 'Partial Return'),
        ('cancelled',      'Cancelled'),
    ]
    delivery_status      = models.CharField(
        max_length=20, choices=DELIVERY_STATUS_CHOICES,
        default='pending', blank=True
    )
    actual_delivery_date = models.DateField(
        null=True, blank=True,
        help_text="Date the order was actually handed to the customer"
    )

    retail       = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    fiscal_year  = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def ldgr_code_name(self):
        return self.ldgr.ac_name if self.ldgr else None

    @property
    def advance_amt(self):
        """
        Total advance received on this order, derived from linked RCPT vouchers.
        Single source of truth: accounting.VoucherMain.customer_order FK.
        """
        from decimal import Decimal
        from django.db.models import Sum
        total = self.receipts.filter(
            voucher_type__in=['RCPT', 'RCPT-SALE'],
            status='posted',
        ).aggregate(s=Sum('amount'))['s']
        return Decimal(total) if total else Decimal('0')

    @property
    def advance_reconciled(self):
        """Total of this order's advance already applied to sales bills."""
        from decimal import Decimal
        from django.db.models import Sum
        total = self.linked_vouchers.aggregate(s=Sum('advance_deducted'))['s']
        return Decimal(total) if total else Decimal('0')

    @property
    def advance_available(self):
        """Advance received on the order that is not yet applied to any bill."""
        return self.advance_amt - self.advance_reconciled

    class Meta:
        db_table="customer_order"
        indexes = [
            models.Index(fields=['retail', '-order_no'], name='idx_co_retail_orderno'),
        ]

    def __str__(self):
        return self.order_no

class CustomerOrderItems(models.Model):
    item_id = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    sl_no = models.IntegerField()
    order_no = models.ForeignKey(CustomerOrder, on_delete=models.CASCADE, related_name="items")
    pcs = models.IntegerField(null=True)
    gw = models.DecimalField(null=True, max_digits=10, decimal_places=3)
    size = models.CharField(null=True, max_length=10,blank=True)
    purity = models.ForeignKey(PurityMaster, on_delete=models.SET_NULL, null=True)
    making_type = models.CharField(max_length=20)
    making_amt = models.IntegerField(null=True)
    other_chg = models.IntegerField(null=True,blank=True)
    iss_status = models.BooleanField(default=False)
    rec_status = models.BooleanField(default=False)
    del_status = models.BooleanField(default=False) # Delivery from Karigar 
    sale_status = models.BooleanField(default=False)
    remarks = models.CharField(max_length=100,null=True,blank=True)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    class Meta:
        db_table="customer_order_main"


# ============= Sales Voucher Models (formerly in sale_voucher app) =============

from decimal import Decimal
from django.forms import ValidationError
from inventory.models import BarcodeMain

class SalesVou(models.Model):

    date1 = models.DateField()
    billno = models.CharField(max_length=30)
    gst_billno = models.CharField(max_length=20, blank=True, default='')
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)
    ldgr = models.ForeignKey(Ledger, on_delete=models.PROTECT)
    sales_person = models.ForeignKey(SalesPersonMaster, on_delete=models.PROTECT)
    sales_person2 = models.ForeignKey(SalesPersonMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_person2_sales_vou')
    place_of_supply = models.CharField(max_length=100) # select from global_vars.py choices
    ret_status = models.BooleanField(default=False)
    remarks = models.CharField(max_length=200, null=True, blank=True, default='')
    freight_charge = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    other_charge = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    mrp = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    discount = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    round_off = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    # taxable_value = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    sgst_per = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    cgst_per = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    igst_per = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    tcs_per = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    tcs_section = models.ForeignKey('mastersconfig.TCSSectionMaster', on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_vouchers')
    mode_of_transport = models.CharField(max_length=200, null=True, blank=True)

    # â”€â”€ E-Way Bill transport fields â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    vehicle_no       = models.CharField(max_length=20,  blank=True, default='', help_text="Vehicle registration number")
    transporter_name = models.CharField(max_length=100, blank=True, default='')
    transporter_id   = models.CharField(max_length=20,  blank=True, default='', help_text="Transporter GSTIN/ID")
    trans_distance   = models.IntegerField(default=0, help_text="Approximate distance in KM")
    trans_doc_no     = models.CharField(max_length=30,  blank=True, default='', help_text="LR/RR/Airway Bill number")
    trans_doc_date   = models.DateField(null=True, blank=True, help_text="Transport document date")

    cash = models.IntegerField(default=0)
    due_amt = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_deducted = models.DecimalField(max_digits=12, decimal_places=2, default=0,
        help_text="Advance amount deducted from CustomerOrder.advance_amt at time of billing")
    customer_order = models.ForeignKey(
        'CustomerOrder', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='linked_vouchers',
        help_text="The customer order whose advance is being reconciled in this bill"
    )
    old_gold_purchase = models.ForeignKey(
        'purchase.PurchaseVoucher', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='linked_sales_vouchers',
        help_text="Customer purchase (old gold) adjusted against this sale"
    )
    old_gold_adjusted = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Old gold value adjusted from the linked customer purchase"
    )
    ac_voucher = models.ForeignKey("accounting.VoucherMain",on_delete=models.SET_NULL,null=True,blank=True)
    ac_rec_voucher = models.ForeignKey("accounting.VoucherMain",on_delete=models.SET_NULL,null=True,blank=True,related_name="salereceipts")

    retail     = models.ForeignKey("mastersconfig.RetailMaster",  on_delete=models.SET_NULL, null=True, blank=True)
    gstin_ref  = models.ForeignKey("mastersconfig.GSTINMaster",  on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_vouchers')
    branch_ref = models.ForeignKey("mastersconfig.BranchMaster", on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_vouchers')
    exhibition_profile = models.ForeignKey(
        'mastersconfig.ExhibitionProfile', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sales_vouchers'
    )

    @property
    def taxable_value(self):
        return float(self.mrp or 0) - float(self.discount or 0)

    @property
    def ldgr_name(self):
        return self.ldgr.ac_name if self.ldgr else None

    @property
    def sgst_amt(self):
        # taxable_value already = mrp - discount, so use it directly
        return float(self.taxable_value) * float(self.sgst_per or 0) / 100

    @property
    def cgst_amt(self):
        return float(self.taxable_value) * float(self.cgst_per or 0) / 100

    @property
    def igst_amt(self):
        return float(self.taxable_value) * float(self.igst_per or 0) / 100

    @property
    def total_bill_value(self):
        return float(self.taxable_value) + float(self.cgst_amt) + float(self.sgst_amt) + float(self.igst_amt)

    @property
    def tcs_amt(self):
        tcs_value = float(self.total_bill_value) * float(self.tcs_per or 0) / 100
        return tcs_value if tcs_value > 5000000 else 0  # Return only if greater than 5,000,000

    def clean(self):
        # Validate on percentage fields (actual DB columns), not computed properties
        if self.cgst_per and self.sgst_per and self.igst_per:
            raise ValidationError("IGST must be 0 if both CGST and SGST are defined.")
        if self.igst_per and (self.cgst_per or self.sgst_per):
            raise ValidationError("CGST and SGST must be 0 if IGST is defined.")

    history = TenantHistoricalRecords()

    class Meta:
        db_table = "sales_vou"
        indexes = [
            models.Index(fields=['retail', '-billno'], name='idx_sv_retail_billno'),
            models.Index(fields=['retail', 'date1'], name='idx_sv_retail_date'),
            models.Index(fields=['ldgr'], name='idx_sv_ldgr'),
        ]

    def __str__(self):

        return self.billno

class SaleOldGoldAdjustment(models.Model):
    """Tracks each old-gold purchase voucher adjusted against a single sale — supports N:1."""
    sale     = models.ForeignKey('SalesVou', on_delete=models.CASCADE, related_name='old_gold_adjustments')
    purchase = models.ForeignKey('purchase.PurchaseVoucher', on_delete=models.PROTECT, related_name='sale_adjustments')
    amount   = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = [('sale', 'purchase')]

    def __str__(self):
        return f"{self.sale.billno} ← {self.purchase.billno} ₹{self.amount}"


class SalesVouItem(models.Model):
    date1= models.DateField(auto_now_add=True)
    billno = models.ForeignKey(SalesVou, on_delete=models.CASCADE)
    # sl_no= models.PositiveIntegerField()
    barcode = models.ForeignKey(BarcodeMain, on_delete=models.PROTECT)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs = models.IntegerField(null=True, blank=True, default=1)
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    making = models.DecimalField(max_digits=10, decimal_places=3)
    making_type = models.CharField(max_length=30,)
    making_value = models.PositiveBigIntegerField(default=0)
    purity = models.IntegerField()
    ret_status = models.BooleanField(default=False)
    amount = models.IntegerField()

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    history = TenantHistoricalRecords()

    class Meta:
        db_table = "sales_vou_main"

class BankDetail(models.Model):
    PAYMENT_MODE_CHOICES = [
        ('NEFT',   'NEFT / IMPS / RTGS'),
        ('UPI',    'UPI'),
        ('CHEQUE', 'Cheque'),
        ('CARD',   'Card'),
    ]
    CHEQUE_STATUS_CHOICES = [
        ('PENDING',   'Pending'),
        ('DEPOSITED', 'Deposited'),
        ('BOUNCED',   'Bounced'),
    ]

    sales_vou    = models.ForeignKey(SalesVou, on_delete=models.CASCADE, related_name='bank_details')
    amount       = models.IntegerField()
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODE_CHOICES, default='NEFT')
    bank_name    = models.CharField(max_length=255)
    # For CHEQUE: cheque number; for UPI/NEFT: UTR / transaction reference (optional)
    chq_no   = models.CharField(max_length=50, null=True, blank=True)
    chq_date = models.DateField(null=True, blank=True)
    # Bank account ledger: for non-cheque â†’ the account credited directly;
    # for cheque â†’ the bank account the cheque will eventually be deposited into
    ledger = models.ForeignKey(Ledger, null=True, blank=True, on_delete=models.SET_NULL, related_name='bank_payment_details')

    # Cheque clearing fields (only relevant when payment_mode = 'CHEQUE')
    cheque_status   = models.CharField(max_length=10, choices=CHEQUE_STATUS_CHOICES, default='PENDING')
    deposit_date    = models.DateField(null=True, blank=True)
    deposit_voucher = models.ForeignKey(
        'accounting.VoucherMain', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='cheque_deposits',
    )

    history = TenantHistoricalRecords()

    class Meta:
        db_table = 'sale_voucher_bankdetail'

    def __str__(self):
        return f"{self.payment_mode} - {self.bank_name} - {self.chq_no or ''}"


class SalesVouItemDetails(models.Model):
    date1 = models.DateField(auto_now_add=True)
    billno = models.ForeignKey(SalesVou, on_delete=models.CASCADE,related_name='salesvouitemdetails_set',null=True,blank=True)
    main_item = models.ForeignKey(SalesVouItem, on_delete=models.SET_NULL,null=True,blank=True,related_name='main_item_set') # do we need to link this to item??
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs = models.IntegerField()
    ct = models.DecimalField(max_digits=10, decimal_places=3)
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    metal_purity = models.CharField(max_length=10, blank=True, null=True) # can have characters also
    tunch = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    rate = models.DecimalField(max_digits=10, decimal_places=3)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    packet = models.ForeignKey("mastersconfig.Packet", on_delete=models.SET_NULL, null=True, blank=True)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    @property
    def date(self):
        return self.main_item.billno.date1 if self.main_item else self.billno.date1
    @property
    def fine_wt(self):
        # tunch is stored as a percentage (e.g. 101 means 101%)
        return (self.gw if self.gw else Decimal(0)) * ((self.tunch / Decimal('100')) if self.tunch else Decimal(0))

    history = TenantHistoricalRecords()

    class Meta:
        db_table = "sales_vou_detail"


class SaleReturn(models.Model):
    date1 = models.DateField()
    billno = models.CharField(max_length=30)
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)
    ldgr = models.ForeignKey(Ledger, on_delete=models.PROTECT)
    mrp = models.DecimalField(max_digits=10, decimal_places=3)
    discount = models.DecimalField(max_digits=10, decimal_places=3)
    cgst_per = models.DecimalField(max_digits=10, decimal_places=3)
    sgst_per = models.DecimalField(max_digits=10, decimal_places=3)
    igst_per = models.DecimalField(max_digits=10, decimal_places=3)
    tcs_per = models.DecimalField(max_digits=10, decimal_places=3)
    ac_voucher = models.ForeignKey("accounting.VoucherMain",on_delete=models.SET_NULL,null=True,blank=True)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)
    # Header-level reference back to the original sales voucher being returned
    sales_voucher_ref = models.ForeignKey(
        SalesVou, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sale_returns'
    )
    # GST bill number of the original invoice â€” stored for credit note printing
    original_sale_gst_billno = models.CharField(max_length=20, blank=True, default='')

    @property
    def taxable_value(self):
        return float(self.mrp or 0) - float(self.discount or 0)

    @property
    def ldgr_name(self):
        return self.ldgr.ac_name if self.ldgr else None

    @property
    def sgst_amt(self):
        # taxable_value already = mrp - discount, so use it directly
        return float(self.taxable_value) * float(self.sgst_per or 0) / 100

    @property
    def cgst_amt(self):
        return float(self.taxable_value) * float(self.cgst_per or 0) / 100

    @property
    def igst_amt(self):
        return float(self.taxable_value) * float(self.igst_per or 0) / 100

    @property
    def total_bill_value(self):
        return float(self.taxable_value) + float(self.cgst_amt) + float(self.sgst_amt) + float(self.igst_amt)

    @property
    def tcs_amt(self):
        tcs_value = float(self.total_bill_value) * float(self.tcs_per or 0) / 100
        return tcs_value if tcs_value > 5000000 else 0  # Return only if greater than 5,000,000


    class Meta:
        db_table = "sale_return"
        indexes = [
            models.Index(fields=['retail', '-billno'], name='idx_sr_retail_billno'),
        ]

class SaleReturnItem(models.Model):
    date1 = models.DateField(auto_now_add=True)
    sale_billno = models.ForeignKey(SalesVou, on_delete=models.SET_NULL, null=True, blank=True)
    billno = models.ForeignKey(SaleReturn, on_delete=models.CASCADE)
    barcode = models.ForeignKey(BarcodeMain, on_delete=models.SET_NULL, null=True, blank=True)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs = models.IntegerField()
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    purity = models.ForeignKey(PurityMaster, on_delete=models.SET_NULL, null=True, blank=True)
    making = models.DecimalField(max_digits=10, decimal_places=3)
    making_type = models.CharField(max_length=10)
    making_value = models.DecimalField(max_digits=10, decimal_places=3)
    remarks = models.CharField(max_length=200,null=True,blank=True)
    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)
    class Meta:
        db_table = "sale_return_main"


class SaleReturnDetails(models.Model):
    date1 = models.DateField(auto_now_add=True)
    main_item = models.ForeignKey(SaleReturnItem, on_delete=models.CASCADE)
    metal_purity = models.ForeignKey(PurityMaster, on_delete=models.SET_NULL, null=True, blank=True)
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    pcs = models.IntegerField()
    ct = models.DecimalField(max_digits=10, decimal_places=3)
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    tunch = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    rate = models.DecimalField(max_digits=10, decimal_places=3)
    amount = models.DecimalField(max_digits=10, decimal_places=3)
    packet = models.ForeignKey("mastersconfig.Packet", on_delete=models.SET_NULL, null=True)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)


    @property
    def fine_wt(self):
        # tunch is stored as a percentage (e.g. 101 means 101%)
        return (self.gw if self.gw else Decimal(0)) * ((self.tunch / Decimal('100')) if self.tunch else Decimal(0))

    class Meta:
        db_table = "sale_return_details"


class SalesApproval(models.Model):
    date1 = models.DateField()
    billno = models.CharField(max_length=30)
    ldgr = models.ForeignKey(Ledger, on_delete=models.PROTECT)
    narration = models.CharField(max_length=100)
    sales_person = models.ForeignKey(SalesPersonMaster, on_delete=models.PROTECT)
    sales_person2 = models.ForeignKey(SalesPersonMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_person2_for_approval')
    place_of_supply = models.ForeignKey("mastersconfig.State", on_delete=models.PROTECT, null=True, blank=True)
    taxable_value = models.DecimalField(max_digits=10, decimal_places = 2)
    discount = models.DecimalField(max_digits=10, decimal_places=3)
    sgst_per = models.DecimalField(null=True, max_digits=10, decimal_places = 2)
    cgst_per = models.DecimalField(null=True, max_digits=10, decimal_places = 2)
    igst_per = models.DecimalField(null=True, max_digits=10, decimal_places = 2)

    retail      = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)

    def clean(self):
        # Validate on percentage fields (actual DB columns), not computed properties
        if self.cgst_per and self.sgst_per and self.igst_per:
            raise ValidationError("IGST must be 0 if both CGST and SGST are defined.")
        if self.igst_per and (self.cgst_per or self.sgst_per):
            raise ValidationError("CGST and SGST must be 0 if IGST is defined.")

    @property
    def net_taxable(self):
        """Taxable value after discount â€” base for GST calculation."""
        return (self.taxable_value or Decimal(0)) - (self.discount or Decimal(0))

    @property
    def total_bill_value(self):
        return self.net_taxable + self.cgst_amt + self.sgst_amt + self.igst_amt

    @property
    def sgst_amt(self):
        return self.net_taxable * (self.sgst_per or Decimal(0)) / Decimal(100)

    @property
    def ldgr_name(self):
        return self.ldgr.ac_name

    @property
    def cgst_amt(self):
        return self.net_taxable * (self.cgst_per or Decimal(0)) / Decimal(100)

    @property
    def igst_amt(self):
        return self.net_taxable * (self.igst_per or Decimal(0)) / Decimal(100)

    @property
    def total_incl_taxes(self):
        return self.net_taxable + self.cgst_amt + self.sgst_amt + self.igst_amt

    # â”€â”€ E-Way Bill transport fields â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    vehicle_no       = models.CharField(max_length=20,  blank=True, default='')
    transporter_name = models.CharField(max_length=100, blank=True, default='')
    transporter_id   = models.CharField(max_length=20,  blank=True, default='')
    trans_distance   = models.IntegerField(default=0)
    trans_doc_no     = models.CharField(max_length=30,  blank=True, default='')
    trans_doc_date   = models.DateField(null=True, blank=True)
    mode_of_transport = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table = "sales_vou_appr"
        indexes = [
            models.Index(fields=['retail', '-billno'], name='idx_sa_retail_billno'),
        ]


class SalesApprovalItem(models.Model):
    billno = models.ForeignKey(SalesApproval, on_delete=models.CASCADE,related_name='items')
    # sl_no = models.IntegerField()
    barcode = models.ForeignKey(BarcodeMain, on_delete=models.PROTECT)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs = models.IntegerField()
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    # making = models.DecimalField(max_digits=10, decimal_places = 2)
    # making_type = models.DecimalField(max_digits=10, decimal_places = 2)
    purity = models.IntegerField()
    ret_status = models.BooleanField(default=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)



    class Meta:


        db_table = "sales_vou_appr_main"

class SalesApprovalItemDetails(models.Model):
    billno = models.ForeignKey(SalesApproval, on_delete=models.CASCADE,related_name='bill_set',null=True)
    main_item = models.ForeignKey(SalesApprovalItem, related_name='main_item_set',on_delete=models.CASCADE) # do we need to link this to item??
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs = models.IntegerField()
    ct = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, default=0)
    gw = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, default=0)
    metal_purity = models.CharField(max_length=10, blank=True, null=True) # can have characters also
    rate = models.DecimalField(max_digits=10, decimal_places=3)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    packet = models.ForeignKey("mastersconfig.Packet", on_delete=models.SET_NULL, null=True)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    class Meta:
        db_table = "sales_vou_appr_detail"


# ============= E-Way Bill Model =============

class EWayBill(models.Model):
    STATUS_CHOICES = [('GENERATED', 'Generated'), ('CANCELLED', 'Cancelled')]

    sales_vou = models.ForeignKey(
        SalesVou, null=True, blank=True, on_delete=models.SET_NULL, related_name='eway_bills',
    )
    sales_approval = models.ForeignKey(
        SalesApproval, null=True, blank=True, on_delete=models.SET_NULL, related_name='eway_bills',
    )
    eway_bill_no = models.CharField(
        max_length=30, blank=True, default='',
        help_text="EBN from NIC portal (user enters after upload)",
    )
    generated_date = models.DateTimeField(auto_now_add=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='GENERATED')
    cancelled_date = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=200, blank=True, default='')
    # Snapshot fields (copied from voucher at generation time)
    party_name = models.CharField(max_length=200, blank=True, default='')
    source_billno = models.CharField(max_length=30, blank=True, default='')
    # Transport snapshot
    vehicle_no = models.CharField(max_length=20, blank=True, default='')
    transporter_name = models.CharField(max_length=100, blank=True, default='')
    transporter_id = models.CharField(max_length=20, blank=True, default='')
    trans_distance = models.IntegerField(default=0)
    mode_of_transport = models.CharField(max_length=20, blank=True, default='Road')
    # JSON payload stored for reference
    json_payload = models.TextField(blank=True, default='', help_text="Generated JSON sent to NIC")

    retail = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.CASCADE, related_name='eway_bills')
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "eway_bill"
        ordering = ['-generated_date']

    def __str__(self):
        source = self.sales_vou.billno if self.sales_vou else (self.sales_approval.billno if self.sales_approval else 'â€”')
        return f"EWB-{self.id} ({source})"


# â”€â”€ Quotation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Quotation(models.Model):
    STATUS_CHOICES = [
        ('draft',     'Draft'),
        ('finalized', 'Finalized'),
        ('expired',   'Expired'),
        ('converted', 'Converted to Sale'),
    ]

    date1          = models.DateField()
    quotation_no   = models.CharField(max_length=30)
    ldgr           = models.ForeignKey(Ledger, on_delete=models.SET_NULL, null=True, blank=True)
    party_name     = models.CharField(max_length=200, blank=True, default='')

    # Gold rate snapshot
    gold_rate_date = models.DateField(null=True, blank=True)
    rate_18kt      = models.IntegerField(default=0)
    rate_22kt      = models.IntegerField(default=0)
    rate_24kt      = models.IntegerField(default=0)

    # Totals
    total_items    = models.IntegerField(default=0)
    grand_total    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_percent    = models.DecimalField(max_digits=5, decimal_places=2, default=3)
    tax_amount     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_total      = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Status & validity
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    valid_until    = models.DateField(null=True, blank=True)

    # Metadata
    remarks        = models.CharField(max_length=200, blank=True, default='')
    seller_info    = models.CharField(max_length=200, blank=True, default='')
    sales_person   = models.ForeignKey(SalesPersonMaster, on_delete=models.SET_NULL, null=True, blank=True)
    converted_to   = models.ForeignKey(SalesVou, on_delete=models.SET_NULL, null=True, blank=True)

    # Multi-tenant
    retail         = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.CASCADE, null=True, blank=True, related_name='quotations')
    fiscal_year    = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    created_by     = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "quotation"
        ordering = ['-id']

    def __str__(self):
        return f"{self.quotation_no} â€” {self.party_name or (self.ldgr.ac_name if self.ldgr else 'Walk-in')}"

    @property
    def ldgr_name(self):
        if self.ldgr:
            return self.ldgr.ac_name
        return self.party_name or ''


class QuotationItem(models.Model):
    quotation      = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')
    sl_no          = models.IntegerField()
    barcode        = models.ForeignKey("inventory.BarcodeMain", on_delete=models.SET_NULL, null=True, blank=True)
    barcode_text   = models.CharField(max_length=20, blank=True, default='')
    item           = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True)
    item_name      = models.CharField(max_length=100, blank=True, default='')
    design_code    = models.CharField(max_length=50, blank=True, default='')
    purity_text    = models.CharField(max_length=10, blank=True, default='')
    pcs            = models.IntegerField(default=1)
    gw             = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    nw             = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    gold_rate      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gold_amount    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fine_wt        = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    making_rate    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    making_amount  = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    total_diamond_pcs = models.IntegerField(default=0)
    total_diamond_wt  = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    total_diamond_amt = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    total_stone_pcs   = models.IntegerField(default=0)
    total_stone_wt    = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    total_stone_amt   = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    total_amount   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    image_url      = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        db_table = "quotation_item"
        ordering = ['sl_no']

    def __str__(self):
        return f"#{self.sl_no} {self.design_code} ({self.barcode_text})"


class QuotationItemDetail(models.Model):
    quotation_item = models.ForeignKey(QuotationItem, on_delete=models.CASCADE, related_name='details')
    packet         = models.ForeignKey("mastersconfig.Packet", on_delete=models.SET_NULL, null=True, blank=True)
    packet_name    = models.CharField(max_length=30, blank=True, default='')
    item_name      = models.CharField(max_length=50, blank=True, default='')
    is_diamond     = models.BooleanField(default=False)
    pcs            = models.IntegerField(default=0)
    wt             = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    rate           = models.IntegerField(default=0)
    amount         = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = "quotation_item_detail"

    def __str__(self):
        return f"{self.packet_name} â€” {self.pcs}pcs / {self.wt}ct"
