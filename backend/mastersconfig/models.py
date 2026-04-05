from django.db import models
from contacts.models import *
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
import global_vars
# Create your modes here.

    
class State(models.Model):
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10)
    tin = models.IntegerField()
    code = models.CharField(max_length=5, unique=True)

    def __str__(self):
        return self.name
    

class CompanyMaster(models.Model):
    """
    Top-level legal entity. Hierarchy: Company → Branch → Retail.
    Company details (PAN, TAN, phone, email, address) are printed on all bills.
    """
    company_name = models.CharField(max_length=200)
    pan          = models.CharField(max_length=10, blank=True, help_text="Permanent Account Number")
    tan          = models.CharField(max_length=10, blank=True, help_text="Tax Deduction Account Number")
    gstin        = models.CharField(max_length=15, blank=True, help_text="Company-level GSTIN (if any)")
    cin          = models.CharField(max_length=21, blank=True, help_text="Corporate Identification Number")
    phone        = models.CharField(max_length=20, blank=True)
    email        = models.EmailField(blank=True)
    address      = models.TextField(blank=True, help_text="Registered office address")
    city         = models.CharField(max_length=100, blank=True)
    state        = models.ForeignKey(
        State, null=True, blank=True, on_delete=models.SET_NULL, related_name='companies'
    )
    pincode      = models.CharField(max_length=10, blank=True)
    website      = models.CharField(max_length=200, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "company_master"
        ordering = ['company_name']

    def __str__(self):
        return self.company_name

    @property
    def full_address(self):
        return ', '.join(filter(None, [self.address, self.city, self.pincode]))


class BranchMaster(models.Model):
    """
    Groups retail locations under a company at the *state* level.
    All retails in the same state share one branch and therefore the same
    set of INPUT / OUTPUT GST register ledgers.
    Hierarchy: Company → Branch → Retail.
    """
    company     = models.ForeignKey(
        CompanyMaster, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='branches'
    )
    branch_name = models.CharField(max_length=100)
    branch_code = models.CharField(max_length=20, unique=True)
    state       = models.ForeignKey(
        State, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='branches',
        help_text="State this branch represents — all retails in this state share the branch's GST registers"
    )
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    # ── GST Register Ledgers (auto-created on branch creation) ───────────────
    input_cgst  = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='branch_input_cgst'
    )
    input_sgst  = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='branch_input_sgst'
    )
    input_igst  = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='branch_input_igst'
    )
    output_cgst = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='branch_output_cgst'
    )
    output_sgst = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='branch_output_sgst'
    )
    output_igst = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='branch_output_igst'
    )

    class Meta:
        db_table = "branch_master"
        ordering = ['branch_name']

    def __str__(self):
        return f"{self.branch_code} – {self.branch_name}"


class RetailMaster(models.Model):
    STATES = global_vars.STATES_OF_INDIA
    retail_name = models.CharField(max_length=100)
    gstin = models.CharField(max_length=30,unique=True,null=True)
    email = models.EmailField(unique=True,null=True)
    retail_code = models.CharField(max_length=100,unique=True)
    address_line1 = models.CharField(max_length=100)
    address_line2 = models.CharField(max_length=100, blank=True)
    address_line3 = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    state = models.ForeignKey(State,null=True,on_delete=models.SET_NULL)
    phone = models.CharField(max_length=15)
    bill_series = models.CharField(max_length=20, unique=True)

    is_exhibition = models.BooleanField(default=False)
    max_cash_receipt_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=199999,
        help_text="Maximum cash receivable from a single customer per financial year (Sec 269ST)"
    )
    max_cash_payment_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=10000,
        help_text="Maximum cash payable to a single party in a single day (Sec 40A(3))"
    )

    cash_ldgr = models.OneToOneField('contacts.Ledger',null=True ,on_delete=models.SET_NULL,blank=True)
    commission_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='commission_retail_set',
        help_text="Expense ledger debited when salesperson commission journal voucher is created"
    )
    active_fy = models.ForeignKey(
        'FiscalYearMaster', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='active_for_retail'
    )
    branch = models.ForeignKey(
        'BranchMaster', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='retails'
    )

    # ── GST Register Ledgers (auto-assigned from branch on retail creation) ──
    input_cgst  = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='retail_input_cgst'
    )
    input_sgst  = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='retail_input_sgst'
    )
    input_igst  = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='retail_input_igst'
    )
    output_cgst = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='retail_output_cgst'
    )
    output_sgst = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='retail_output_sgst'
    )
    output_igst = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='retail_output_igst'
    )

    default_country_code = models.CharField(
        max_length=5, default='IN', blank=True,
        help_text="ISO 3166-1 alpha-2 code used as default dial code on mobile inputs (e.g. IN, AE, US)"
    )

    def get_bill_prefix(self, type=None, fy_code=None):
        fy = fy_code or (self.active_fy.fy_code if self.active_fy else '')
        prefix = type or self.bill_series
        if fy:
            return f"{prefix}/{self.retail_code}/{fy}/"
        return f"{prefix}/{self.retail_code}/"







class Hsn(models.Model):
    hsn_no = models.CharField(max_length=10)
    hsn_type = models.CharField(max_length=20,choices=(("GD","Goods"),("SR","Services")))
    cgst = models.DecimalField(max_digits=6, decimal_places=3)
    sgst = models.DecimalField(max_digits=6, decimal_places=3)
    igst = models.DecimalField(max_digits=6, decimal_places=3)
    description = models.CharField(max_length = 100)



    def __str__(self) -> str:
        return self.hsn_no
    
    class Meta:
        db_table = "hsn_master"


class ItemGroupMaster(models.Model):
    item_group_name = models.CharField(max_length=20)
    short_code = models.CharField(max_length=5)



    def __str__(self) -> str:
        return self.item_group_name
    class Meta:
        db_table = "item_group_master"


class SalesPersonMaster(models.Model):
    COMMISSION_ON_CHOICES = [
        ('overall', 'Overall Bill Value (MRP − Discount)'),
        ('making',  'Making Value Only'),
        ('stone',   'Stone Value Only'),
    ]

    salesperson_name = models.CharField(max_length=100)
    retail = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)

    # ── Commission configuration ──────────────────────────────────────────────
    ledger = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='salesperson_set',
        help_text="Payable ledger for this salesperson (required to create commission JV)"
    )
    commission_rate    = models.DecimalField(max_digits=6, decimal_places=3, default=0,
                                             help_text="Commission rate in %")
    commission_on      = models.CharField(max_length=10, choices=COMMISSION_ON_CHOICES, default='overall')
    deduct_discount    = models.BooleanField(default=True,
                                             help_text="Deduct bill discount before applying commission rate")
    apply_on_b2b       = models.BooleanField(default=False,
                                             help_text="Apply commission on B2B (GST-registered) sales")

    def __str__(self) -> str:
        return self.salesperson_name

    class Meta:
        db_table = "salesperson_master"


class Item(models.Model):
    CHOICES = (("Gm","gram"),("Pcs","pieces"),("Ct","Ct"),)
    ITEM_CHOICES = (("M","Metal"),("R","Raw"),("S","Stone"),("O","Other"),("C","Coin"),)
    short_code = models.CharField(max_length=10, unique=True)
    item_name = models.CharField(max_length=50)
    grp = models.ForeignKey(ItemGroupMaster, on_delete = models.SET_NULL, null=True)
    sub_grp = models.CharField(max_length=20)
    item_type = models.CharField(max_length=50,choices=ITEM_CHOICES)
    uom = models.CharField(max_length=10,choices=CHOICES)

    purchase_ledger = models.ForeignKey("contacts.Ledger", related_name='purchase_ldgrs', on_delete = models.SET_NULL, null=True)
    sale_ledger = models.ForeignKey("contacts.Ledger", related_name='sale_ldgrs', on_delete = models.SET_NULL, null=True)
    
    show_in_pcs_report = models.BooleanField()
    hsn_no = models.ForeignKey(Hsn, on_delete = models.SET_NULL, null=True)
    created_date = models.DateField(default=timezone.now)

    op_wtd_avg_rate = models.DecimalField(default=0,decimal_places=3,max_digits=10)


    def __str__(self) -> str:
        return self.item_name

    class Meta:
        db_table = "item_master"
        


class Shapes(models.Model):
    shape_name = models.CharField(max_length=50)
    shape_code = models.CharField(max_length=50)



    def __str__(self) -> str:
        return self.shape_name
    class Meta:
        db_table = "shape_master"

class Colors(models.Model):
    color_name = models.CharField(max_length=50)


    class Meta:
        db_table = "color_master"

    def __str__(self) -> str:
        return self.color_name

class PacketGroup(models.Model):
    packet_group_name = models.CharField(max_length=10)


    class Meta:
        db_table = "packet_group_master"
    def __str__(self) -> str:
        return self.packet_group_name

class FiscalYearMaster(models.Model):
    """Tracks fiscal years per retail location (Indian FY: April–March)."""
    retail = models.ForeignKey(RetailMaster, on_delete=models.CASCADE, related_name='fiscal_years')
    fy_code = models.CharField(max_length=10)           # "24-25", "25-26"
    fy_start = models.DateField()                        # 2024-04-01
    fy_end = models.DateField()                          # 2025-03-31
    is_closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)
    # Hard-close: absolute lock — no entries of any kind allowed.
    # Can be toggled on/off multiple times (e.g. sync → hard-close → post audit adj → reopen → sync → hard-close again).
    is_hard_closed = models.BooleanField(default=False)
    hard_closed_at = models.DateTimeField(null=True, blank=True)
    # Tracks the last time opening balances of the NEXT FY were synced from this FY's closing balance.
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fiscal_year_master"
        unique_together = ('retail', 'fy_code')
        indexes = [
            models.Index(fields=['retail', 'is_closed'], name='idx_fy_retail_closed'),
        ]

    def __str__(self):
        return f"{self.retail.retail_code} / FY {self.fy_code}"


class ExhibitionProfile(models.Model):
    """Temporary exhibition venue — overrides retail GSTIN/address on invoices while active."""
    retail        = models.ForeignKey(RetailMaster, on_delete=models.CASCADE, related_name='exhibitions')
    name          = models.CharField(max_length=150)       # e.g. "Chennai Trade Fair Jan 2025"
    gstin         = models.CharField(max_length=30)        # temporary state GSTIN
    state         = models.ForeignKey(State, null=True, on_delete=models.SET_NULL)
    address_line1 = models.CharField(max_length=100)
    address_line2 = models.CharField(max_length=100, blank=True)
    address_line3 = models.CharField(max_length=100, blank=True)
    city          = models.CharField(max_length=100, blank=True)
    pincode       = models.CharField(max_length=10, blank=True)
    start_date    = models.DateField(null=True, blank=True)
    end_date      = models.DateField(null=True, blank=True)
    is_active     = models.BooleanField(default=False)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'exhibition_profile'

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"


class SystemSettings(models.Model):
    """
    Singleton table (always pk=1) for server-side ERP configuration.
    Use SystemSettings.get() to retrieve or create the single row.
    """
    attachment_storage_path = models.CharField(
        max_length=500, blank=True,
        help_text=(
            "Absolute path on this server where file attachments are stored. "
            "Leave blank to use the default media folder. "
            "Changing this path does NOT move existing files."
        )
    )
    bill_total_auto_calc = models.BooleanField(
        default=False,
        help_text="Allow entering the desired bill total and auto-calculating Discount & GST."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'system_settings'

    def __str__(self):
        return 'System Settings'

    @classmethod
    def get(cls):
        """Return (and create if needed) the singleton settings row."""
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'attachment_storage_path': ''})
        return obj


class BillNumberSequence(models.Model):
    """Tracks the last used bill number per retail location, prefix and fiscal year for O(1) voucher number generation."""
    retail = models.ForeignKey(RetailMaster, on_delete=models.CASCADE)
    prefix = models.CharField(max_length=20)  # e.g., "SV", "PV", "SR", "JRNL", "GC", "CG"
    fiscal_year = models.ForeignKey(FiscalYearMaster, on_delete=models.CASCADE, null=True, blank=True)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('retail', 'prefix', 'fiscal_year')
        db_table = 'bill_number_sequence'

    def __str__(self):
        fy = self.fiscal_year.fy_code if self.fiscal_year else 'no-fy'
        return f"{self.retail.retail_code}/{self.prefix}/{fy} → {self.last_number}"


class Packet(models.Model):
    packet_group = models.ForeignKey(PacketGroup,max_length=10, on_delete=models.CASCADE,null=True)
    pckt_no = models.CharField(max_length=10, unique=True)
    stone_item_id = models.ForeignKey(Item, on_delete = models.CASCADE, null=True)
    cut = models.CharField(max_length=50, null=True)
    clarity = models.CharField(max_length=10, null=True)
    color = models.ForeignKey(Colors, on_delete = models.SET_NULL,max_length=20, null=True)
    shape = models.ForeignKey(Shapes,on_delete=models.SET_NULL,max_length=10, null=True)
    seives = models.CharField(max_length=10, null=True)
    is_solitaire = models.BooleanField()
    rate_for_retail = models.IntegerField()
    rate_for_wholesale = models.IntegerField(blank=True, null=True)
    is_customer_stone = models.BooleanField()
    created_date = models.DateField(default=timezone.now)

    op_stock_wtd_avg_rate = models.DecimalField(default=0,decimal_places=3,max_digits=10)

    class Meta:
        db_table = "packet_master"
    def __str__(self) -> str:
        return self.pckt_no


class TDSSectionMaster(models.Model):
    """TDS (Tax Deducted at Source) sections — applies on purchases/payments."""
    section_code     = models.CharField(max_length=10, unique=True)
    description      = models.CharField(max_length=200)
    rate_individual  = models.DecimalField(max_digits=6, decimal_places=3)
    rate_company     = models.DecimalField(max_digits=6, decimal_places=3)
    rate_no_pan      = models.DecimalField(max_digits=6, decimal_places=3, default=20)
    threshold_single = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    threshold_annual = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    ledger           = models.ForeignKey('contacts.Ledger', on_delete=models.SET_NULL, null=True, blank=True, related_name='tds_section_ledger')
    is_active        = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.section_code} — {self.description}"

    class Meta:
        db_table = "tds_section_master"


class TCSSectionMaster(models.Model):
    """TCS (Tax Collected at Source) sections — applies on sales/collections."""
    section_code     = models.CharField(max_length=10, unique=True)
    description      = models.CharField(max_length=200)
    rate             = models.DecimalField(max_digits=6, decimal_places=3)
    rate_no_pan      = models.DecimalField(max_digits=6, decimal_places=3, default=1)
    threshold_annual = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    ledger           = models.ForeignKey('contacts.Ledger', on_delete=models.SET_NULL, null=True, blank=True, related_name='tcs_section_ledger')
    is_active        = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.section_code} — {self.description}"

    class Meta:
        db_table = "tcs_section_master"


class SalesPersonCommission(models.Model):
    """Tracks commission earned per salesperson per sales voucher.
    Created when the commission report 'Create JV' action is triggered."""
    sales_vou   = models.ForeignKey('sales.SalesVou', on_delete=models.CASCADE, related_name='commissions')
    salesperson = models.ForeignKey(SalesPersonMaster, on_delete=models.CASCADE, related_name='commissions')
    base_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                      help_text="The value on which commission was computed")
    rate        = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    commission_amt = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    journal_voucher = models.ForeignKey(
        'accounting.VoucherMain', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='commission_entries'
    )
    retail      = models.ForeignKey(RetailMaster, on_delete=models.CASCADE, related_name='commissions')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'salesperson_commission'
        unique_together = ('sales_vou', 'salesperson')

    def __str__(self):
        return f"{self.salesperson.salesperson_name} | {self.sales_vou.billno} | ₹{self.commission_amt}"


class SalesPersonCommissionReversal(models.Model):
    """Records a commission reversal whenever a sales return is processed.

    One row per (commission, sale_return) pair, so partial and multiple
    returns against the same original bill are all tracked individually.
    The reversal JV is created automatically when the original commission JV
    already exists; otherwise reversal_jv is left null (no JV had been posted).
    """
    commission  = models.ForeignKey(
        SalesPersonCommission, on_delete=models.CASCADE, related_name='reversals'
    )
    sale_return = models.ForeignKey(
        'sales.SaleReturn', on_delete=models.CASCADE, related_name='commission_reversals'
    )
    reversal_amt = models.DecimalField(max_digits=12, decimal_places=2)
    reversal_jv  = models.ForeignKey(
        'accounting.VoucherMain', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='commission_reversal_entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'salesperson_commission_reversal'
        unique_together = ('commission', 'sale_return')

    def __str__(self):
        return (
            f"Reversal ₹{self.reversal_amt} | {self.commission.salesperson.salesperson_name}"
            f" | return {self.sale_return.billno}"
        )


class CRMSettings(models.Model):
    """Per-retail configuration for automated WhatsApp birthday/anniversary messages."""
    PROVIDER_CHOICES = [
        ('meta',    'Meta Cloud API (official)'),
        ('wati',    'WATI'),
        ('aisensy', 'AiSensy'),
        ('webhook', 'Custom HTTP Webhook'),
    ]
    retail                   = models.OneToOneField(RetailMaster, on_delete=models.CASCADE, related_name='crm_settings')
    is_enabled               = models.BooleanField(default=False, help_text="Enable automatic sending")
    send_time                = models.TimeField(default='09:00', help_text="Time of day to send (IST)")
    provider                 = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='webhook')
    api_key                  = models.CharField(max_length=600, blank=True, help_text="Access token / API key for the provider")
    phone_number_id          = models.CharField(max_length=100, blank=True, help_text="Meta: WhatsApp Phone Number ID")
    birthday_template_name   = models.CharField(max_length=100, default='birthday_wishes', help_text="Template name registered with the provider")
    anniversary_template_name= models.CharField(max_length=100, default='anniversary_wishes')
    webhook_url              = models.CharField(max_length=500, blank=True, help_text="WATI server URL or generic webhook endpoint")
    webhook_headers          = models.JSONField(default=dict, blank=True, help_text="Extra HTTP headers as JSON object")
    # Runtime state
    last_send_date           = models.DateField(null=True, blank=True)
    last_run_status          = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = 'crm_settings'

    def __str__(self):
        return f"CRM Settings — {self.retail.retail_name}"


class CRMSendLog(models.Model):
    """Audit log of every automated WhatsApp send attempt."""
    STATUS_CHOICES = [('success', 'Success'), ('failed', 'Failed'), ('skipped', 'Skipped')]
    retail        = models.ForeignKey(RetailMaster, on_delete=models.CASCADE, related_name='crm_logs')
    ledger_id     = models.IntegerField(null=True, blank=True)
    customer_name = models.CharField(max_length=200)
    mobile        = models.CharField(max_length=20, blank=True)
    occasion      = models.CharField(max_length=20)          # birthday / anniversary
    sent_at       = models.DateTimeField(auto_now_add=True)
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES)
    error_message = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = 'crm_send_log'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['retail', '-sent_at'], name='idx_crm_log_retail_date'),
        ]

    def __str__(self):
        return f"{self.customer_name} | {self.occasion} | {self.status} | {self.sent_at:%Y-%m-%d}"
