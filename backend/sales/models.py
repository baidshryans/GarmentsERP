from django.db import models
from contacts.models import Ledger
from mastersconfig.models import Item, SalesPersonMaster
from goldrates.models import PurityMaster
# Create your models here.
class CustomerOrder(models.Model):
    ldgr = models.ForeignKey(Ledger, on_delete=models.SET_NULL, null=True)
    date1 = models.DateField()
    order_no = models.CharField(max_length=14,unique=True)
    fix_gold_rate = models.BooleanField(null=True, default=False)
    gold_rate_date = models.DateField(null=True)
    rate_18kt = models.IntegerField(default=0)
    rate_22kt = models.IntegerField(default=0)
    rate_24kt = models.IntegerField(default=0)
    salesman_1 = models.ForeignKey(SalesPersonMaster, related_name = "salesman_1", on_delete = models.SET_NULL, null=True)
    salesman_2 = models.ForeignKey(SalesPersonMaster, related_name = "salesman_2", on_delete = models.SET_NULL, null=True, blank=True)
    advance_amt = models.IntegerField(null=True, default=0)
    est_amount = models.IntegerField(null=True, default=0)
    nature = models.CharField(max_length=20, default="New Booking",blank=True)
    status = models.CharField(max_length=20, default="",blank=True)
    delivery_date = models.DateField(null=True)
    remarks = models.CharField(max_length=100, null=True)

    DELIVERY_STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('ready',     'Ready for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    delivery_status      = models.CharField(
        max_length=20, choices=DELIVERY_STATUS_CHOICES,
        default='pending', blank=True
    )
    actual_delivery_date = models.DateField(
        null=True, blank=True,
        help_text="Date the order was actually handed to the customer"
    )

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    @property
    def ldgr_code_name(self):
        return self.ldgr.ac_name if self.ldgr else None

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
    gw = models.DecimalField(null=True, max_digits=10, decimal_places =2)
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
    gst_billno = models.CharField(max_length=20)
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)
    ldgr = models.ForeignKey(Ledger, on_delete=models.PROTECT)
    sales_person = models.ForeignKey(SalesPersonMaster, on_delete=models.PROTECT)
    sales_person2 = models.ForeignKey(SalesPersonMaster, on_delete=models.PROTECT, related_name='sales_person2_sales_vou')
    place_of_supply = models.CharField(max_length=100) # select from global_vars.py choices
    ret_status = models.BooleanField(default=False)
    remarks = models.CharField(max_length=30)
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

    # ── E-Way Bill transport fields ────────────────────────────────────────────
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
    ac_voucher = models.ForeignKey("accounting.VoucherMain",on_delete=models.SET_NULL,null=True,blank=True)
    ac_rec_voucher = models.ForeignKey("accounting.VoucherMain",on_delete=models.SET_NULL,null=True,blank=True,related_name="salereceipts")

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)
    exhibition_profile = models.ForeignKey(
        'mastersconfig.ExhibitionProfile', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sales_vouchers'
    )

    @property
    def taxable_value(self):
        return float(self.mrp) - float(self.discount)
    @property
    def ldgr_name(self):
        return self.ldgr.ac_name
    @property
    def sgst_amt(self):
        return (float(self.taxable_value) - float(self.discount)) * float(self.sgst_per)/100

    @property
    def cgst_amt(self):
        return (float(self.taxable_value) - float(self.discount)) * float(self.cgst_per)/100

    @property
    def igst_amt(self):
        return (float(self.taxable_value) - float(self.discount)) * float(self.igst_per)/100

    @property
    def total_bill_value(self):
        return float(self.taxable_value) + float(self.cgst_amt) + float(self.sgst_amt) + float(self.igst_amt)

    @property
    def tcs_amt(self):
        tcs_value = float(self.total_bill_value) * float(self.tcs_per)/100
        return tcs_value if tcs_value > 5000000 else 0  # Return only if greater than 5,000,000

    def clean(self):
        # Ensure that if both cgst and sgst are defined, igst should be 0
        if self.cgst_amt is not None and self.sgst_amt is not None:
            if self.igst_amt != 0:
                raise ValidationError("IGST must be 0 if both CGST and SGST are defined.")

        # You can add more conditions if needed
        # For example, you may want to ensure that if igst is defined, cgst and sgst should be None
        if self.igst_amt is not None:
            if self.cgst_amt or self.sgst_amt:
                raise ValidationError("CGST and SGST must be None if IGST is defined.")
    class Meta:
        db_table = "sales_vou"
        indexes = [
            models.Index(fields=['retail', '-billno'], name='idx_sv_retail_billno'),
            models.Index(fields=['retail', 'date1'], name='idx_sv_retail_date'),
            models.Index(fields=['ldgr'], name='idx_sv_ldgr'),
        ]

    def __str__(self):

        return self.billno

class SalesVouItem(models.Model):
    date1= models.DateField(auto_now_add=True)
    billno = models.ForeignKey(SalesVou, on_delete=models.CASCADE)
    # sl_no= models.PositiveIntegerField()
    barcode = models.ForeignKey(BarcodeMain, on_delete=models.PROTECT)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs = models.IntegerField()
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    making = models.DecimalField(max_digits=10, decimal_places=3)
    making_type = models.CharField(max_length=30,)
    making_value = models.PositiveBigIntegerField(default=0)
    purity = models.IntegerField()
    ret_status = models.BooleanField(default=False)
    amount = models.IntegerField()

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)


    class Meta:
        db_table = "sales_vou_main"

class BankDetail(models.Model):
    sales_vou = models.ForeignKey(SalesVou,on_delete=models.CASCADE,related_name='bank_details')
    amount = models.IntegerField()
    bank_name = models.CharField(max_length=255)
    chq_no = models.CharField(max_length=50, unique=True)  # Assuming chq_no should be unique
    chq_date = models.DateField()
    ledger = models.ForeignKey(Ledger, null=True, blank=True, on_delete=models.SET_NULL, related_name='bank_payment_details')

    class Meta:
        db_table = 'sale_voucher_bankdetail'

    def __str__(self):
        return f"{self.bank_name} - {self.chq_no}"


class SalesVouItemDetails(models.Model):
    date1 = models.DateField(auto_now_add=True)
    billno = models.ForeignKey(SalesVou, on_delete=models.CASCADE,related_name='salesvouitemdetails_set',null=True,blank=True)
    main_item = models.ForeignKey(SalesVouItem, on_delete=models.SET_NULL,null=True,blank=True,related_name='main_item_set') # do we need to link this to item??
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs = models.IntegerField()
    ct = models.DecimalField(max_digits=10, decimal_places=3)
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    metal_purity = models.CharField(max_length=10) # can have characters also
    tunch = models.DecimalField(max_digits=3, decimal_places=3, null=True, blank=True)
    rate = models.DecimalField(max_digits=10, decimal_places=3)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    packet = models.ForeignKey("mastersconfig.Packet", on_delete=models.SET_NULL, null=True, blank=True)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    @property
    def date(self):
        return self.main_item.billno.date1 if self.main_item else self.billno.date1
    @property
    def fine_wt(self):
        return (self.gw if self.gw else Decimal(0)) * (self.tunch if self.tunch else Decimal(0))

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

    @property
    def taxable_value(self):
        return float(self.mrp) - float(self.discount)

    @property
    def ldgr_name(self):
        return self.ldgr.ac_name
    @property
    def sgst_amt(self):
        return (float(self.taxable_value) - float(self.discount)) * float(self.sgst_per)/100

    @property
    def cgst_amt(self):
        return (float(self.taxable_value) - float(self.discount)) * float(self.cgst_per)/100

    @property
    def igst_amt(self):
        return (float(self.taxable_value) - float(self.discount)) * float(self.igst_per)/100

    @property
    def total_bill_value(self):
        return float(self.taxable_value) + float(self.cgst_amt) + float(self.sgst_amt) + float(self.igst_amt)

    @property
    def tcs_amt(self):
        tcs_value = float(self.total_bill_value) * float(self.tcs_per)/100
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
    tunch = models.DecimalField(max_digits=10, decimal_places=3)
    rate = models.DecimalField(max_digits=10, decimal_places=3)
    amount = models.DecimalField(max_digits=10, decimal_places=3)
    packet = models.ForeignKey("mastersconfig.Packet", on_delete=models.SET_NULL, null=True)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)


    @property
    def fine_wt(self):
        return self.gw * self.tunch

    class Meta:
        db_table = "sale_return_details"


class SalesApproval(models.Model):
    date1 = models.DateField()
    billno = models.CharField(max_length=30)
    ldgr = models.ForeignKey(Ledger, on_delete=models.PROTECT)
    narration = models.CharField(max_length=100)
    sales_person = models.ForeignKey(SalesPersonMaster, on_delete=models.PROTECT)
    sales_person2 = models.ForeignKey(SalesPersonMaster, on_delete=models.PROTECT, related_name='sales_person2_for_approval')
    place_of_supply = models.ForeignKey("mastersconfig.State", on_delete=models.PROTECT, null=True, blank=True)
    taxable_value = models.DecimalField(max_digits=10, decimal_places = 2)
    discount = models.DecimalField(max_digits=10, decimal_places=3)
    sgst_per = models.DecimalField(null=True, max_digits=10, decimal_places = 2)
    cgst_per = models.DecimalField(null=True, max_digits=10, decimal_places = 2)
    igst_per = models.DecimalField(null=True, max_digits=10, decimal_places = 2)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)


    def clean(self):
        # Ensure that if both cgst and sgst are defined, igst should be 0
        if self.cgst_amt is not None and self.sgst_amt is not None:
            if self.igst_amt != 0:
                raise ValidationError("IGST must be 0 if both CGST and SGST are defined.")

        # You can add more conditions if needed
        # For example, you may want to ensure that if igst is defined, cgst and sgst should be None
        if self.igst_amt is not None:
            if self.cgst_amt or self.sgst_amt:
                raise ValidationError("CGST and SGST must be None if IGST is defined.")

    @property
    def total_bill_value(self):
        return self.taxable_value + self.cgst_amt + self.sgst_amt + self.igst_amt

    @property
    def sgst_amt(self):
        return (self.taxable_value - self.discount) * self.sgst_per

    @property
    def ldgr_name(self):
        return self.ldgr.ac_name

    @property
    def cgst_amt(self):
        return (self.taxable_value - self.discount) * self.cgst_per

    @property
    def igst_amt(self):
        return (self.taxable_value - self.discount) * self.igst_per

    @property
    def total_incl_taxes(self):
        return self.taxable_value - self.discount + self.cgst_amt + self.sgst_amt + self.igst_amt

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
    gw = models.DecimalField(max_digits=10, decimal_places=2)
    # making = models.DecimalField(max_digits=10, decimal_places = 2)
    # making_type = models.DecimalField(max_digits=10, decimal_places = 2)
    purity = models.IntegerField()
    ret_status = models.BooleanField(default=False)
    amount = models.IntegerField()

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)



    class Meta:


        db_table = "sales_vou_appr_main"

class SalesApprovalItemDetails(models.Model):
    billno = models.ForeignKey(SalesApproval, on_delete=models.CASCADE,related_name='bill_set',null=True)
    main_item = models.ForeignKey(SalesApprovalItem, related_name='main_item_set',on_delete=models.CASCADE) # do we need to link this to item??
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs = models.IntegerField()
    ct = models.DecimalField(max_digits=10, decimal_places=3)
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    metal_purity = models.CharField(max_length=10) # can have characters also
    tunch = models.DecimalField(max_digits=3, decimal_places=3)
    rate = models.DecimalField(max_digits=10, decimal_places=3)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    packet = models.ForeignKey("mastersconfig.Packet", on_delete=models.SET_NULL, null=True)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)


    @property
    def fine_wt(self):
        return self.gw * self.tunch

    class Meta:
        db_table = "sales_vou_appr_detail"