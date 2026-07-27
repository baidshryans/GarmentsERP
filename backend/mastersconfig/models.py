from decimal import Decimal

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
    Operational ledgers (discount, round off, etc.) are company-wide and auto-created on save.
    """
    company_name = models.CharField(max_length=200)
    legal_name   = models.CharField(max_length=200, blank=True, help_text="Legal/registered name of the company (as per MCA/GST records)")
    pan          = models.CharField(max_length=10, blank=True, help_text="Permanent Account Number")
    tan          = models.CharField(max_length=10, blank=True, help_text="Tax Deduction Account Number")
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
    bis_logo     = models.ImageField(upload_to='company-logos/', blank=True, null=True,
                                     help_text="BIS Hallmark logo for printed invoices")
    company_logo = models.ImageField(upload_to='company-logos/', blank=True, null=True,
                                     help_text="Company logo for printed invoices")
    created_at   = models.DateTimeField(auto_now_add=True)

    # ── Operational Ledgers (auto-created on company creation) ───────────────
    discount_ldgr        = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_discount'
    )
    round_off_ldgr       = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_round_off'
    )
    hallmark_charge_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_hallmark_charge'
    )
    making_receive_ldgr  = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_making_receive'
    )
    gold_conversion_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_gold_conversion'
    )

    # ── Compliance Limits ─────────────────────────────────────────────────────
    enforce_cash_limits = models.BooleanField(
        default=True,
        help_text=(
            "Enable real-time enforcement of Sec 269ST (cash receipt limit) "
            "and Sec 40A(3) (cash payment limit). Disable only if you manage "
            "compliance outside the system."
        )
    )
    max_cash_receipt_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=199999,
        help_text="Maximum cash receivable from a single customer per financial year (Sec 269ST)"
    )
    max_cash_payment_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=10000,
        help_text="Maximum cash payable to a single party in a single day (Sec 40A(3))"
    )

    carriage_inward_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_carriage_inward'
    )
    making_charge_paid_14k_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_making_charge_paid_14k'
    )
    making_charge_paid_18k_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_making_charge_paid_18k'
    )
    making_charge_paid_22k_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_making_charge_paid_22k'
    )
    making_receive_14k_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_making_receive_14k'
    )
    making_receive_18k_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_making_receive_18k'
    )
    making_receive_22k_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_making_receive_22k'
    )
    sale_discount_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_sale_discount'
    )
    cheques_in_hand_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_cheques_in_hand',
        help_text="Suspense ledger cheques land in until deposited/cleared."
    )
    gold_scheme_liability_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_gold_scheme_liability',
        help_text="Current liability for money collected under gold schemes."
    )

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
    Purely organisational — GST ledgers are owned by GSTINMaster, not by branch.
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
        help_text="State this branch represents"
    )
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "branch_master"
        ordering = ['branch_name']

    def __str__(self):
        return f"{self.branch_code} – {self.branch_name}"


class GSTINMaster(models.Model):
    """
    Compliance anchor for GST. Each unique GSTIN gets one record.
    The 6 GST register ledgers (Input/Output CGST/SGST/IGST) are auto-created
    via signal when a GSTINMaster is first saved.
    Hierarchy: BranchMaster → GSTINMaster ← RetailMaster
    """
    gstin      = models.CharField(max_length=15, unique=True)
    legal_name = models.CharField(max_length=200, blank=True)
    branch     = models.ForeignKey(
        BranchMaster, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='gstins'
    )
    state      = models.ForeignKey(
        State, null=True, blank=True, on_delete=models.SET_NULL
    )

    # ── GST Register Ledgers (auto-created on first save via signal) ─────────
    input_cgst  = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gstin_input_cgst'
    )
    input_sgst  = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gstin_input_sgst'
    )
    input_igst  = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gstin_input_igst'
    )
    output_cgst = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gstin_output_cgst'
    )
    output_sgst = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gstin_output_sgst'
    )
    output_igst = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gstin_output_igst'
    )

    # ── RCM GST Register Ledgers (auto-created on first save via signal) ─────
    input_cgst_rcm  = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gstin_input_cgst_rcm'
    )
    input_sgst_rcm  = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gstin_input_sgst_rcm'
    )
    input_igst_rcm  = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gstin_input_igst_rcm'
    )
    output_cgst_rcm = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gstin_output_cgst_rcm'
    )
    output_sgst_rcm = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gstin_output_sgst_rcm'
    )
    output_igst_rcm = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gstin_output_igst_rcm'
    )

    class Meta:
        db_table = "gstin_master"

    def __str__(self):
        return self.gstin


class RetailMaster(models.Model):
    STATES = global_vars.STATES_OF_INDIA
    retail_name = models.CharField(max_length=100)
    gstin_master = models.ForeignKey(
        'GSTINMaster', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='retails'
    )
    email = models.EmailField(unique=True,null=True)
    retail_code = models.CharField(max_length=100,unique=True)
    address_line1 = models.CharField(max_length=100)
    address_line2 = models.CharField(max_length=100, blank=True)
    address_line3 = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    state = models.ForeignKey(State,null=True,on_delete=models.SET_NULL)
    phone = models.CharField(max_length=15)

    is_exhibition = models.BooleanField(default=False)

    cash_ldgr = models.OneToOneField('contacts.Ledger',null=True ,on_delete=models.SET_NULL,blank=True)
    commission_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='commission_retail_set',
        help_text="Expense ledger debited when salesperson commission journal voucher is created"
    )
    bank_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='bank_for_retail_set',
        help_text="Default bank ledger whose remittance details print on this retail's invoices"
    )
    sales_incentive_ldgr = models.ForeignKey(
        'contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sales_incentive_retail_set',
        help_text="Shared Sundry-Creditor ledger credited by salesperson commission journals"
    )
    branch = models.ForeignKey(
        'BranchMaster', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='retails'
    )

    def __str__(self):
        return self.retail_name or self.retail_code or f'Retail #{self.pk}'

    @property
    def active_fy(self):
        from mastersconfig.models import SystemSettings
        return SystemSettings.get().active_fy

    @property
    def active_fy_id(self):
        from mastersconfig.models import SystemSettings
        return SystemSettings.get().active_fy_id

    default_country_code = models.CharField(
        max_length=5, default='IN', blank=True,
        help_text="ISO 3166-1 alpha-2 code used as default dial code on mobile inputs (e.g. IN, AE, US)"
    )

    # Maps internal sequence prefix codes → display prefix strings in the bill number
    _DISPLAY_PREFIX = {
        'PVC': 'PV/C',
        'PVV': 'PV/V',
    }

    def get_bill_prefix(self, type=None, fy_code=None):
        fy = fy_code or (self.active_fy.fy_code if self.active_fy else '')
        prefix = type or ''
        display = self._DISPLAY_PREFIX.get(prefix, prefix)
        if fy:
            return f"{display}/{self.retail_code}/{fy}/"
        return f"{display}/{self.retail_code}/"






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
    # NOTE: The credit-side payable ledger for commission JVs is a single shared
    # "Sales Incentive" ledger per retail — resolved via ledger_utils
    # (get_or_create_shared_incentive_ledger). There is no per-salesperson FK.
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
    grp = models.ForeignKey(ItemGroupMaster, on_delete = models.SET_NULL, null=True, blank=True)
    sub_grp = models.CharField(max_length=20, blank=True, null=True)
    item_type = models.CharField(max_length=50,choices=ITEM_CHOICES)
    uom = models.CharField(max_length=10,choices=CHOICES)

    purchase_ledger = models.ForeignKey("contacts.Ledger", related_name='purchase_ldgrs', on_delete = models.SET_NULL, null=True, blank=True)
    sale_ledger = models.ForeignKey("contacts.Ledger", related_name='sale_ldgrs', on_delete = models.SET_NULL, null=True, blank=True)
    
    show_in_pcs_report = models.BooleanField()
    hsn_no = models.ForeignKey(Hsn, on_delete = models.SET_NULL, null=True, blank=True)
    created_date = models.DateField(default=timezone.now)

    op_wtd_avg_rate = models.DecimalField(default=0,decimal_places=3,max_digits=10)
    default_purity = models.CharField(max_length=10, blank=True, default="")

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

class PacketSubGroup(models.Model):
    packet_group = models.ForeignKey(PacketGroup, on_delete=models.CASCADE, related_name='sub_groups')
    packet_sub_group_name = models.CharField(max_length=10)

    class Meta:
        db_table = "packet_sub_group_master"
        constraints = [
            models.UniqueConstraint(fields=['packet_group', 'packet_sub_group_name'], name='uniq_subgroup_per_group'),
        ]

    def __str__(self) -> str:
        return f"{self.packet_group.packet_group_name} / {self.packet_sub_group_name}"

class FiscalYearMaster(models.Model):
    """Tracks fiscal years for the whole company (Indian FY: April–March)."""
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
        constraints = [
            models.UniqueConstraint(fields=['fy_code'], name='uniq_fy_code'),
        ]
        indexes = [
            models.Index(fields=['is_closed'], name='idx_fy_closed'),
        ]

    def __str__(self):
        return f"FY {self.fy_code}"


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
    barcode_image_storage_path = models.CharField(
        max_length=500, blank=True,
        help_text=(
            "Absolute path on this server where barcode images are stored. "
            "Leave blank to use the default media folder. "
            "Changing this path does NOT move existing files."
        )
    )
    bill_total_auto_calc = models.BooleanField(
        default=False,
        help_text="Allow entering the desired bill total and auto-calculating Discount & GST."
    )
    spell_check_enabled = models.BooleanField(
        default=True,
        help_text="Enable browser spell checking and fuzzy matching in search/picker fields."
    )
    enable_gst_bill = models.BooleanField(
        default=False,
        help_text="Enable GST bill number (auto-generated as GST/<retail_code>/<FY>/NNNNN) on sales vouchers. When enabled the field is mandatory."
    )
    mysql_sync_config = models.JSONField(
        default=dict, blank=True,
        help_text="MySQL source database connection details for master data sync."
    )
    active_fy = models.ForeignKey(
        'FiscalYearMaster', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='active_for_company',
        help_text="The single company-wide active fiscal year.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'system_settings'

    def __str__(self):
        return 'System Settings'

    @classmethod
    def get(cls):
        """Return (creating if needed) the singleton settings row.

        Pre-joins active_fy so reading it in a loop (e.g. RetailMaster.active_fy
        across branches) stays a single query. Deliberately NOT cached across
        requests: the row carries the active FY's closure state, which must stay
        fresh so a just-closed fiscal year is enforced immediately across all
        workers. The pk=1 lookup is cheap enough to read live."""
        obj, _ = cls.objects.select_related('active_fy').get_or_create(
            pk=1, defaults={'attachment_storage_path': ''}
        )
        return obj

    @classmethod
    def set_company_active_fy(cls, fy):
        """Set (or clear) the company-wide active fiscal year."""
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'attachment_storage_path': ''})
        obj.active_fy = fy
        obj.save(update_fields=['active_fy', 'updated_at'])
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
    packet_sub_group = models.ForeignKey(PacketSubGroup, on_delete=models.SET_NULL, null=True, blank=True)
    pckt_no = models.CharField(max_length=10, unique=True)
    stone_item_id = models.ForeignKey(Item, on_delete = models.CASCADE, null=True)
    cut = models.CharField(max_length=50, null=True, blank=True)
    clarity = models.CharField(max_length=10, null=True, blank=True)
    color = models.ForeignKey(Colors, on_delete = models.SET_NULL,max_length=20, null=True)
    COLOR_TONE_CHOICES = [('LB', 'LB'), ('LC', 'LC')]
    color_tone = models.CharField(max_length=2, choices=COLOR_TONE_CHOICES, null=True, blank=True)
    shape = models.ForeignKey(Shapes,on_delete=models.SET_NULL,max_length=10, null=True)
    sieve_max = models.CharField(max_length=10, null=True, blank=True)
    sieve_min = models.CharField(max_length=10, null=True, blank=True)
    ct_min = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    ct_max = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
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


# ── B2B Pricelist ────────────────────────────────────────────────────────────
# Defines pricing rules for B2B (dealer/wholesale) customers.  A pricelist is
# assigned to a Ledger via Ledger.b2b_pricelist FK.

class B2BPricelist(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'b2b_pricelist'

    def __str__(self):
        return self.name


MAKING_TYPE_CHOICES = [
    ('per_gram', 'Per Gram'),
    ('val',      'Flat Value'),
    ('tunch',    'Tunch % Markup'),
    ('per_nw',   '% of Gold Value'),
]

class B2BPricelistMaking(models.Model):
    """Making / tunch rule.  Null purity/item = default for all.

    See ``mastersconfig.b2b_pricing.resolve_b2b_making`` for the exact math each
    ``making_type`` implies.  In short:
      per_gram → making_value ₹ per gram of gold
      val      → a flat ₹ amount (overrides everything; no minimum applies)
      tunch    → making_value % added on top of the purity's base gw_per, so the
                 charge lands on the gold rate rather than the making column
      per_nw   → making_value % of the gold value
    """
    pricelist    = models.ForeignKey(B2BPricelist, on_delete=models.CASCADE, related_name='making_entries')
    purity       = models.ForeignKey('goldrates.PurityMaster', on_delete=models.CASCADE, null=True, blank=True)
    item         = models.ForeignKey(Item, on_delete=models.CASCADE, null=True, blank=True)
    making_type  = models.CharField(max_length=10, choices=MAKING_TYPE_CHOICES)
    making_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_making_grams = models.DecimalField(
        max_digits=10, decimal_places=3, default=Decimal('0'),
        help_text=("Minimum making charge expressed in grams.  The weight used for the "
                   "making computation is floored at this value: eff_wt = max(actual_wt, this). "
                   "Ignored for making_type='val'."),
    )

    class Meta:
        db_table = 'b2b_pricelist_making'
        constraints = [
            models.UniqueConstraint(
                fields=['pricelist', 'purity', 'item'],
                name='uniq_b2b_making_pricelist_purity_item',
            ),
        ]

    def __str__(self):
        base = f"{self.pricelist.name} making: {self.making_type}={self.making_value}"
        if self.min_making_grams:
            base += f" (min {self.min_making_grams}g)"
        return base


class B2BPricelistStoneOverride(models.Model):
    """Optional per-packet stone rate override.  Falls back to Packet.rate_for_wholesale."""
    pricelist = models.ForeignKey(B2BPricelist, on_delete=models.CASCADE, related_name='stone_overrides')
    packet    = models.ForeignKey(Packet, on_delete=models.CASCADE)
    rate      = models.IntegerField()

    class Meta:
        db_table = 'b2b_pricelist_stone_override'
        unique_together = ('pricelist', 'packet')

    def __str__(self):
        return f"{self.pricelist.name} / {self.packet} → ₹{self.rate}"


class RetailDiscountPricelist(models.Model):
    """Discount pricelist for retail customers — defines making & diamond discount % per purity."""
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'retail_discount_pricelist'

    def __str__(self):
        return self.name


class RetailDiscountPricelistRule(models.Model):
    """Per-purity discount percentages for making charges and diamond/stone charges."""
    pricelist            = models.ForeignKey(RetailDiscountPricelist, on_delete=models.CASCADE, related_name='rules')
    purity               = models.ForeignKey('goldrates.PurityMaster', on_delete=models.CASCADE)
    making_discount_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    diamond_discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        db_table        = 'retail_discount_pricelist_rule'
        unique_together = ('pricelist', 'purity')

    def __str__(self):
        return (
            f"{self.pricelist.name} / {self.purity} → "
            f"making={self.making_discount_pct}% diamond={self.diamond_discount_pct}%"
        )


# ── Sales Offer ───────────────────────────────────────────────────────────────

OFFER_MAKING_TYPE_CHOICES = [
    ('flat',     'Flat ₹/g'),
    ('discount', '% Discount on Making'),
]


class SalesOffer(models.Model):
    """Company-wide promotional offer: per-purity making charge rules + diamond discount."""
    name                 = models.CharField(max_length=200)
    start_date           = models.DateField(null=True, blank=True)
    end_date             = models.DateField(null=True, blank=True)
    diamond_discount_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0,
                                               help_text="% discount on all diamond/stone amounts")
    is_active            = models.BooleanField(default=False)
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sales_offer'

    def save(self, *args, **kwargs):
        # Enforce only one active offer at a time
        if self.is_active:
            SalesOffer.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class SalesOfferRule(models.Model):
    """Per-purity making charge rule within a SalesOffer."""
    offer        = models.ForeignKey(SalesOffer, on_delete=models.CASCADE, related_name='rules')
    purity       = models.CharField(max_length=20, help_text="Purity code e.g. 91.6, 75.0")
    making_type  = models.CharField(max_length=10, choices=OFFER_MAKING_TYPE_CHOICES)
    making_value = models.DecimalField(max_digits=10, decimal_places=2,
                                       help_text="₹/g if flat; % if discount")

    class Meta:
        db_table        = 'sales_offer_rule'
        unique_together = ('offer', 'purity')

    def __str__(self):
        try:
            return f"{self.offer.name} / {self.purity} → {self.making_type}={self.making_value}"
        except Exception:
            return f"SalesOfferRule {self.pk}"


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
    fiscal_year = models.ForeignKey('mastersconfig.FiscalYearMaster', on_delete=models.SET_NULL, null=True, blank=True)
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


class EmailSettings(models.Model):
    """Per-retail SMTP configuration for outbound email (OTP, bills, statements)."""
    PROVIDER_CHOICES = [
        ('gmail',       'Gmail (SMTP + app password)'),
        ('outlook',     'Outlook / Office365 (SMTP + app password)'),
        ('custom_smtp', 'Custom SMTP'),
    ]
    PRESETS = {
        'gmail':   {'host': 'smtp.gmail.com',        'port': 587, 'use_tls': True},
        'outlook': {'host': 'smtp-mail.outlook.com', 'port': 587, 'use_tls': True},
    }
    retail          = models.OneToOneField(RetailMaster, on_delete=models.CASCADE, related_name='email_settings')
    provider        = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='custom_smtp')
    host            = models.CharField(max_length=200, blank=True)
    port            = models.PositiveIntegerField(default=587)
    use_tls         = models.BooleanField(default=True)
    username        = models.CharField(max_length=200, blank=True)
    password        = models.CharField(max_length=600, blank=True, help_text="SMTP password / app password")
    from_email      = models.EmailField(blank=True)
    from_name       = models.CharField(max_length=200, blank=True)
    is_enabled      = models.BooleanField(default=False, help_text="Enable outbound email for this retail")
    auto_send_bills = models.BooleanField(default=False, help_text="Superadmin-only: email bills to customers on save")
    last_run_status = models.CharField(max_length=500, blank=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'email_settings'

    def __str__(self):
        return f"Email Settings — {self.retail.retail_name}"

    def save(self, *args, **kwargs):
        preset = self.PRESETS.get(self.provider)
        if preset:
            self.host = preset['host']
            self.port = preset['port']
            self.use_tls = preset['use_tls']
        super().save(*args, **kwargs)


class EmailSendLog(models.Model):
    """Audit log of every outbound email attempt."""
    STATUS_CHOICES  = [('sent', 'Sent'), ('failed', 'Failed'), ('skipped', 'Skipped')]
    PURPOSE_CHOICES = [('otp', 'OTP'), ('bill', 'Bill'), ('statement', 'Statement'), ('other', 'Other')]
    retail        = models.ForeignKey(RetailMaster, on_delete=models.CASCADE, related_name='email_logs')
    to_email      = models.EmailField()
    subject       = models.CharField(max_length=300)
    purpose       = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default='other')
    sent_at       = models.DateTimeField(auto_now_add=True)
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES)
    error_message = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = 'email_send_log'
        ordering = ['-sent_at']
        indexes = [models.Index(fields=['retail', '-sent_at'], name='idx_email_log_retail_date')]

    def __str__(self):
        return f"{self.to_email} | {self.purpose} | {self.status} | {self.sent_at:%Y-%m-%d}"
