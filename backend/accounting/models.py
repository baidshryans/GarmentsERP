from django.db import models
from django.contrib.auth.models import User
from contacts.models import Ledger
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from mastersconfig.models import RetailMaster

# Create your models here.
class Account(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20,)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    can_be_deleted = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    class Meta:
        db_table = "account_groups"


class VoucherMain(models.Model):
    STATUS_CHOICES = [
        ('posted',    'Posted'),
        ('cancelled', 'Cancelled'),
    ]

    date = models.DateField()
    voucher_no = models.CharField(max_length=30, unique=True)

    narration = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    voucher_type = models.CharField(max_length=10)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='posted')
    vendor_bill = models.CharField(max_length=20, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    retail = models.ForeignKey(RetailMaster, on_delete=models.SET_NULL,null=True,related_name="retail_voucher")
    fiscal_year = models.ForeignKey('mastersconfig.FiscalYearMaster', on_delete=models.SET_NULL, null=True, blank=True)
    gstin_ref  = models.ForeignKey('mastersconfig.GSTINMaster',  null=True, blank=True, on_delete=models.SET_NULL, related_name='vouchers')
    branch_ref = models.ForeignKey('mastersconfig.BranchMaster', null=True, blank=True, on_delete=models.SET_NULL, related_name='vouchers')
    customer_order = models.ForeignKey(
        'sales.CustomerOrder',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='receipts',
        help_text="For RCPT vouchers: the customer order this advance receipt belongs to"
    )

    
    def __str__(self):
        return f"Journal Entry {self.id} - {self.date}"
    
    class Meta:
        db_table = "voucher_main"
        indexes = [
            models.Index(fields=['retail', 'voucher_type', '-voucher_no'], name='idx_vm_retail_type_vno'),
            models.Index(fields=['retail', 'date'], name='idx_vm_retail_date'),
        ]

class VoucherDetail(models.Model):

    voucher_main = models.ForeignKey(VoucherMain, on_delete=models.CASCADE, related_name='transactions')
    voucher_no = models.CharField(max_length=30)
    ref_bill_no = models.CharField(max_length=30, null=True, blank=True)
    ref_sales_vou = models.ForeignKey(
        'sales.SalesVou', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='receipt_allocations',
        help_text="Strongly-typed link to the sales invoice this line is allocated against"
    )
    ref_purchase_vou = models.ForeignKey(
        'purchase.PurchaseVoucher', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='payment_allocations',
        help_text="Strongly-typed link to the purchase invoice this line is allocated against"
    )
    voucher_type = models.CharField(max_length=10)
    account = models.ForeignKey('contacts.Ledger', on_delete=models.CASCADE) # this is the account
    status = models.CharField(max_length=20,null=True,blank=True)
    #write two function for debit entry and credit entry
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    party_bank_name = models.CharField(max_length=200,null=True,blank=True)
    chq_no = models.CharField(max_length=200,null=True,blank=True)
    chq_date = models.DateField(null=True,blank=True)
    
    def __str__(self):
        return f"Transaction for {self.account.ac_name} in Voucher Detail {self.voucher_main.id}"
    
    class Meta:
        db_table = "voucher_detail"
        indexes = [
            models.Index(fields=['voucher_main', 'account'], name='idx_vd_vmain_account'),
            models.Index(fields=['account'], name='idx_vd_account'),
        ]
        
class ReferenceBills(models.Model):
    ldgr = models.ForeignKey(Ledger, on_delete=models.CASCADE)
    voucher = models.ForeignKey(VoucherMain, on_delete = models.CASCADE)
    amount = models.DecimalField(max_digits=10,decimal_places=2)
    vendor_bill_no = models.CharField(max_length=20, null=True, blank=True)
    ref_bill = models.ForeignKey(VoucherDetail, on_delete=models.CASCADE, null=True, blank=True)
    ref_bill_txt = models.CharField(max_length=20, null=True, blank=True)
    class Meta:
        db_table = "reference_bills"


class CashGoldConversion(models.Model):
    CONVERSION_TYPES = [
        ('CG', 'CG'),
        ('GC', 'GC')
    ]
    date = models.DateField()
    ldgr = models.ForeignKey(Ledger, on_delete=models.SET_NULL,null=True)
    v_type = models.ForeignKey(VoucherMain, on_delete = models.SET_NULL,null=True)
    billno = models.CharField(max_length=100)  # generate from bill prefix
    fiscal_year = models.ForeignKey('mastersconfig.FiscalYearMaster', on_delete=models.SET_NULL, null=True, blank=True)
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    retail = models.ForeignKey(RetailMaster, on_delete=models.SET_NULL,null=True)
    conv_type = models.CharField(max_length=2, choices=CONVERSION_TYPES)

    class Meta:
        db_table = "gold_cash_conversion"
        indexes = [
            models.Index(fields=['retail', 'conv_type', '-billno'], name='idx_gc_retail_type_billno'),
        ]

    def __str__(self):
      return f"{self.billno} - {self.ldgr.ac_name}"
    
class VoucherAttachment(models.Model):
    voucher = models.ForeignKey(VoucherMain, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='voucher_attachments/%Y/%m/')
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "voucher_attachment"

    def __str__(self):
        return f"{self.original_name} – {self.voucher.voucher_no}"


class BankStatementEntry(models.Model):
    """
    A single line from a physical / downloaded bank statement.
    Can be manually entered or bulk-imported via CSV.
    Once matched to a VoucherDetail book entry, `matched_entry` is set.
    """
    retail       = models.ForeignKey(RetailMaster, on_delete=models.CASCADE, related_name='bank_statements')
    bank_ledger  = models.ForeignKey('contacts.Ledger', on_delete=models.CASCADE,
                                     related_name='statement_entries',
                                     help_text="The bank ledger this statement line belongs to")
    date         = models.DateField()
    description  = models.CharField(max_length=300)
    reference    = models.CharField(max_length=100, blank=True)  # cheque/UTR/NEFT ref
    debit        = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                       help_text="Amount withdrawn (outflow from bank)")
    credit       = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                       help_text="Amount deposited (inflow to bank)")
    # When this entry is matched to a book entry:
    matched_entry = models.OneToOneField(
        VoucherDetail, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bank_statement_match'
    )
    fiscal_year  = models.ForeignKey('mastersconfig.FiscalYearMaster', on_delete=models.SET_NULL, null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_statement_entry"
        ordering = ['-date', '-id']
        indexes = [
            models.Index(fields=['retail', 'bank_ledger', 'date'], name='idx_bse_retail_ldgr_date'),
        ]

    def __str__(self):
        return f"{self.date} | {self.description[:40]} | {'Dr' if self.debit else 'Cr'} {self.debit or self.credit}"


class CreditDebitNote(models.Model):
    NOTE_TYPES = [('CN', 'Credit Note'), ('DN', 'Debit Note')]

    note_type = models.CharField(max_length=2, choices=NOTE_TYPES)
    note_no = models.CharField(max_length=30)
    date = models.DateField()
    ldgr = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name='credit_debit_notes')
    adjustment_ldgr = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name='+',
                                         help_text="Revenue/expense ledger that absorbs the adjustment")
    ref_sales_vou = models.ForeignKey('sales.SalesVou', null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name='credit_notes')
    ref_purchase_vou = models.ForeignKey('purchase.PurchaseVoucher', null=True, blank=True,
                                          on_delete=models.SET_NULL, related_name='debit_notes')
    ref_sale_return = models.ForeignKey('sales.SaleReturn', null=True, blank=True,
                                         on_delete=models.SET_NULL, related_name='credit_note')
    ref_purchase_return = models.ForeignKey('purchase.PurchaseReturn', null=True, blank=True,
                                             on_delete=models.SET_NULL, related_name='debit_note')
    reason = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=15, decimal_places=2, help_text="Total (taxable + tax)")
    taxable_value = models.DecimalField(max_digits=15, decimal_places=2)
    cgst_per = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cgst_amt = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sgst_per = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sgst_amt = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    igst_per = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    igst_amt = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ac_voucher = models.ForeignKey(VoucherMain, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='credit_debit_note')
    retail = models.ForeignKey(RetailMaster, on_delete=models.CASCADE, related_name='credit_debit_notes')
    fiscal_year = models.ForeignKey('mastersconfig.FiscalYearMaster', on_delete=models.SET_NULL, null=True, blank=True)
    gstin_ref = models.ForeignKey('mastersconfig.GSTINMaster', null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='credit_debit_notes')
    branch_ref = models.ForeignKey('mastersconfig.BranchMaster', null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='credit_debit_notes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "credit_debit_note"
        indexes = [
            models.Index(fields=['retail', 'note_type', '-note_no'], name='idx_cdn_retail_type_no'),
        ]

    def __str__(self):
        return f"{self.get_note_type_display()} {self.note_no} – {self.ldgr.ac_name}"


class LedgerOpenBalance(models.Model):
    ldgr = models.ForeignKey(Ledger, on_delete = models.CASCADE)
    debit = models.FloatField(default=0)
    credit = models.DecimalField(max_digits=11, decimal_places=2, default=0.00)
    acc_year = models.CharField(max_length=25)
    retail= models.ForeignKey(RetailMaster, on_delete= models.CASCADE)
    def __str__(self):
        return f"Ledger {self.ldgr.ac_name}"
    class Meta:
        db_table = "ldgr_open_balance"
        indexes = [
            models.Index(fields=['ldgr'], name='idx_lob_ldgr'),
            models.Index(fields=['ldgr', 'retail'], name='idx_lob_ldgr_retail'),
        ]


class AuditMark(models.Model):
    """Records that an auditor has reviewed and approved a voucher."""
    voucher    = models.OneToOneField(VoucherMain, on_delete=models.CASCADE, related_name='audit_mark')
    audited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_marks')
    audited_at = models.DateTimeField(auto_now_add=True)
    notes      = models.CharField(max_length=300, blank=True)
    retail     = models.ForeignKey(RetailMaster, on_delete=models.CASCADE, related_name='audit_marks')

    class Meta:
        db_table = "audit_mark"
        indexes = [
            models.Index(fields=['retail', 'audited_at'], name='idx_am_retail_date'),
        ]

    def __str__(self):
        return f"Audited: {self.voucher.voucher_no} by {self.audited_by}"
