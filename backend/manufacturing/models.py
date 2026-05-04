from django.db import models
from accounting.models import VoucherMain
from contacts.models import Ledger
from goldrates.models import PurityMaster
# from inventory.models import BarcodeMain
from mastersconfig.models import Item,Packet, RetailMaster
from sales.models import CustomerOrderItems,CustomerOrder
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
# Create your models here.


class KarigarGoldIssueHeader(models.Model):
    billno = models.CharField(max_length=30)
    date1 = models.DateField()
    slip_type = models.CharField(max_length=15)
    karigar_ldgr = models.ForeignKey(Ledger, on_delete = models.SET_NULL, null=True)
    retail       = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    fiscal_year  = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def karigar_ldgr_name(self):
        return self.karigar_ldgr.ac_name


class KarigarGoldIssue(models.Model):
    header = models.ForeignKey(KarigarGoldIssueHeader, on_delete=models.CASCADE)
    # Generic ForeignKey for ref_job_no
    ref_job_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='gold_ref_jobs')
    ref_job_object_id = models.PositiveIntegerField()
    ref_job_no = GenericForeignKey('ref_job_content_type', 'ref_job_object_id')

    job_sl_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='gold_job_sl_items')
    job_sl_object_id = models.PositiveIntegerField()
    job_sl_no = GenericForeignKey('job_sl_content_type', 'job_sl_object_id')

    sl_no = models.IntegerField()
    item = models.ForeignKey(Item, on_delete = models.SET_NULL, null=True)
    item_gw = models.DecimalField(max_digits=10, decimal_places=3)
    alloy_wt = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True)
    conv_wt = models.DecimalField(max_digits=10, decimal_places=3)
    metal_purity = models.ForeignKey(
        PurityMaster, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="issue_org_purity",
        help_text="Select a predefined purity OR leave blank and enter custom_purity_per"
    )
    custom_purity_per = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
        help_text="Free-form purity percentage (e.g. 99.2). Used when metal_purity is not in master."
    )
    conv_purity = models.ForeignKey(PurityMaster, on_delete= models.SET_NULL, null=True)
    remarks = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "karigar_gold_issue"

class KarigarIssue(models.Model):
    bill_id = models.IntegerField()
    date1 = models.DateField()
    issue_slip_type = models.CharField(max_length=20)
    issue_slip_no = models.CharField(max_length=30)
    karigar_ldgr = models.ForeignKey(Ledger, on_delete = models.CASCADE)
    gold_issue = GenericRelation(KarigarGoldIssue,        content_type_field='ref_job_content_type',  # Updated field name
        object_id_field='ref_job_object_id',  )
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)
    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)
    
    @property
    def karigar_ldgr_name(self):
        return self.karigar_ldgr.ac_name 

    
    class Meta:
        db_table="issue_to_karigar"

class KarigarIssueItem(models.Model):
    issue_slip = models.ForeignKey(KarigarIssue, on_delete=models.CASCADE,related_name="items")
    issue_sl_no = models.IntegerField()
    customer_order_item = models.ForeignKey(CustomerOrderItems, on_delete=models.SET_NULL, null=True, blank=True) 
    sketch = models.FileField(upload_to="sketch/")
    item = models.ForeignKey(Item,on_delete=models.SET_NULL, null=True)
    purity = models.ForeignKey(PurityMaster, on_delete = models.SET_NULL, null=True)
    pcs = models.IntegerField()
    approx_wt = models.DecimalField(null=True, max_digits=10, decimal_places =2)
    design_code = models.CharField(max_length=10, null=True, blank=True)
    size = models.CharField(max_length=10, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    remarks = models.CharField(max_length=50, blank=True, default="")
    stone_issue = GenericRelation("manufacturing.KarigarStoneIssue",content_type_field='job_sl_content_type',  # Updated field name
        object_id_field='job_sl_object_id',  )
    stone_receive = GenericRelation("manufacturing.KarigarStoneReceive",content_type_field='job_sl_content_type',  # Updated field name
        object_id_field='job_sl_object_id',  )
    rec_status = models.BooleanField(default=False)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    @property
    def item_name(self):
        return self.item.item_name



    class Meta:
        db_table = "issue_to_karigar_main"
        constraints = [
            models.UniqueConstraint(
                fields=['customer_order_item'],
                condition=models.Q(customer_order_item__isnull=False),
                name='uniq_karigarissue_customer_order_item',
            ),
        ]


class SampleIssue(models.Model):
    billno = models.CharField(max_length=30)
    date1 = models.DateField()
    karigar_ldgr = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name="sample_issues")
    retail = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.CharField(max_length=200, blank=True, null=True)
    due_date = models.DateField(null=True, blank=True)
    gold_issue = GenericRelation(
        KarigarGoldIssue,
        content_type_field='ref_job_content_type',
        object_id_field='ref_job_object_id',
    )

    @property
    def karigar_ldgr_name(self):
        return self.karigar_ldgr.ac_name

    class Meta:
        db_table = "sample_issue_main"


class SampleIssueItem(models.Model):
    SOURCE_KR = 'KR'
    SOURCE_PV = 'PV'
    SOURCE_BC = 'BC'
    SOURCE_CHOICES = [(SOURCE_KR, 'Karigar Receive'), (SOURCE_PV, 'Purchase Voucher'), (SOURCE_BC, 'Barcode')]

    issue = models.ForeignKey(SampleIssue, on_delete=models.CASCADE, related_name="items")
    sl_no = models.IntegerField()

    # Source traceability (one will be set depending on source_type)
    piece = models.ForeignKey(
        "inventory.UnBarcodedMain",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sample_issue_items",
    )
    barcode = models.ForeignKey(
        "inventory.BarcodeMain",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sample_issue_items",
    )
    kr_receive_item = models.ForeignKey(
        'manufacturing.KarigarReceiveItem',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sample_issue_items",
    )
    pv_item = models.ForeignKey(
        'purchase.PurchaseVoucherItems',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sample_issue_items",
    )
    source_type = models.CharField(max_length=2, choices=SOURCE_CHOICES, blank=True, null=True)

    # Stored item details
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True)
    purity = models.ForeignKey(PurityMaster, on_delete=models.SET_NULL, null=True, blank=True)
    pcs = models.IntegerField(null=True, blank=True)
    gw = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    design_code = models.CharField(max_length=50, blank=True, null=True)
    size = models.CharField(max_length=20, blank=True, null=True)
    huid = models.CharField(max_length=30, blank=True, null=True)

    remarks = models.CharField(max_length=100, blank=True, null=True)
    rec_status = models.BooleanField(default=False)
    retail = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)

    stone_issue = GenericRelation(
        "manufacturing.KarigarStoneIssue",
        content_type_field='job_sl_content_type',
        object_id_field='job_sl_object_id',
    )
    stone_receive = GenericRelation(
        "manufacturing.KarigarStoneReceive",
        content_type_field='job_sl_content_type',
        object_id_field='job_sl_object_id',
    )

    class Meta:
        db_table = "sample_issue_item"


class SampleIssueItemDetails(models.Model):
    main_item = models.ForeignKey(SampleIssueItem, on_delete=models.CASCADE, related_name="details")
    sl_no = models.IntegerField(default=1)
    sub_item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    packet = models.ForeignKey(Packet, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    pcs = models.IntegerField(null=True, blank=True, default=0)
    ct = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, default=0)
    gw = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, default=0)
    rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)

    class Meta:
        db_table = "sample_issue_item_details"


class KarigarStoneIssueHeader(models.Model):
    SLIP_TYPE_CHOICES = [('JO', 'Job Order'), ('PO', 'Purchase Order')]
    
    billno = models.CharField(max_length=25)
    date1 = models.DateField()
    karigar_ldgr = models.ForeignKey(Ledger, on_delete=models.SET_NULL, null=True)
    slip_type    = models.CharField(max_length=15)
    retail       = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    fiscal_year  = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def karigar_ldgr_name(self):
        return self.karigar_ldgr.ac_name

class KarigarStoneIssue(models.Model):
    header = models.ForeignKey(KarigarStoneIssueHeader,on_delete=models.CASCADE)

    # Generic ForeignKey for ref_job_no
    ref_job_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='ref_jobs')
    ref_job_object_id = models.PositiveIntegerField()
    ref_job_no = GenericForeignKey('ref_job_content_type', 'ref_job_object_id')

    job_sl_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='job_sl_items')
    job_sl_object_id = models.PositiveIntegerField()
    job_sl_no = GenericForeignKey('job_sl_content_type', 'job_sl_object_id')

    sl_no = models.IntegerField()

    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    
    pcs = models.IntegerField()
    ct = models.DecimalField(max_digits=10, decimal_places=3)
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    cgst = models.DecimalField(max_digits=10, decimal_places=2)
    sgst = models.DecimalField(max_digits=10, decimal_places=2)
    igst = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    taxable_value = models.DecimalField(max_digits=10, decimal_places=2)
    tot_val = models.DecimalField(max_digits=10, decimal_places=2)

    packet = models.ForeignKey(Packet, on_delete=models.SET_NULL, null=True)

    remarks = models.CharField(max_length=100, null=True, blank=True)
    place_of_supply = models.CharField(max_length=100, null=True, blank=True)

    @property
    def date(self):
        return self.header.date1

    class Meta:
        db_table = "karigar_stone_issue"

class KarigarStoneReceiveHeader(models.Model):
    billno = models.CharField(max_length=25)
    date1 = models.DateField()
    karigar_ldgr = models.ForeignKey(Ledger, on_delete=models.SET_NULL, null=True)
    retail       = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    fiscal_year  = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def karigar_ldgr_name(self):
        return self.karigar_ldgr.ac_name

class KarigarStoneReceive(models.Model):

    header = models.ForeignKey(KarigarStoneReceiveHeader,on_delete=models.CASCADE)
    # Generic ForeignKey for ref_job_no
    ref_job_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='ref_jobs_stn_rec')
    ref_job_object_id = models.PositiveIntegerField()
    ref_job_no = GenericForeignKey('ref_job_content_type', 'ref_job_object_id')
    
    #job_sl_no = models.ForeignKey(KarigarIssueItem, on_delete=models.CASCADE, null=True, blank=True)
    job_sl_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='job_sl_items_stn_rec')
    job_sl_object_id = models.PositiveIntegerField()
    job_sl_no = GenericForeignKey('job_sl_content_type', 'job_sl_object_id')
    sl_no = models.IntegerField()
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    
    return_pcs = models.IntegerField(default=0, blank=True)
    return_ct = models.DecimalField(max_digits=10, decimal_places=3)
    return_gw = models.DecimalField(max_digits=10, decimal_places=3)

    broken_pcs = models.IntegerField(default=0, blank=True)
    broken_ct = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    broken_gw = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    
    loss_pcs = models.IntegerField(default=0, blank=True)
    loss_ct = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    loss_gw = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    
    cgst = models.DecimalField(max_digits=10, decimal_places=2)
    sgst = models.DecimalField(max_digits=10, decimal_places=2)
    igst = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    taxable_value = models.DecimalField(max_digits=10, decimal_places=2)
    tot_val = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    
    packet = models.ForeignKey(Packet, on_delete=models.SET_NULL, null=True)
    place_of_supply = models.CharField(max_length=100, null=True, blank=True)
    
    @property
    def date(self):
        return self.header.date1
    @property
    def item_name(self):
        return self.item.item_name

    class Meta:
        db_table = "karigar_stone_receive"

#-------------------karigar master----------------------------------
class KarigarMaster(models.Model):
    karigar = models.ForeignKey(Ledger, on_delete = models.CASCADE)
    kr_code = models.CharField(max_length=10, null=True, blank=True)
    making_per_gm = models.DecimalField(max_digits=10, decimal_places=2)
    making_per_pc = models.DecimalField(max_digits=10, decimal_places=2)
    loss_rate = models.DecimalField(max_digits=10, decimal_places=3)
    purity = models.ForeignKey(PurityMaster, on_delete=models.PROTECT)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    class Meta:
        db_table = "karigar_master"
    @property
    def karigar_ldgr_name(self):
        return self.karigar.ac_name 

#-------------------receive from karigar----------------------------
class KarigarReceive(models.Model):
    receive_slip_no = models.CharField(max_length=30) # rec
    date1 = models.DateField()
    karigar_ldgr = models.ForeignKey(Ledger, on_delete = models.SET_NULL, null=True)
    place_of_supply=models.CharField(max_length=30)
    making_vid = models.ForeignKey(VoucherMain,on_delete=models.SET_NULL,null=True)
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)
    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True,related_name="retail_location")
    @property
    def karigar_ldgr_name(self):
        return self.karigar_ldgr.ac_name 
    
    class Meta:
        db_table = "receive_from_karigar"

class KarigarReceiveItem(models.Model):
    receive_slip_no = models.ForeignKey(KarigarReceive, on_delete=models.CASCADE) 
    date1 = models.DateField()
    sl_no = models.IntegerField()
    ref_job_no = models.ForeignKey(KarigarIssue, on_delete=models.CASCADE, null=True, blank=True)
    ref_job_sl_no = models.ForeignKey(KarigarIssueItem,on_delete=models.CASCADE, null=True, blank=True)
    ref_sample_issue = models.ForeignKey(
        SampleIssue, on_delete=models.PROTECT, null=True, blank=True,
        related_name="receives",
        help_text="Set when this receive lands against a Sample Issue (reworked / reissued piece).",
    )
    ref_sample_issue_item = models.ForeignKey(
        SampleIssueItem, on_delete=models.PROTECT, null=True, blank=True,
        related_name="receives",
    )

    item = models.ForeignKey(Item, on_delete=models.SET_NULL,  null=True)
    purity = models.ForeignKey(PurityMaster, on_delete = models.SET_NULL , null=True)
    pcs = models.IntegerField()
    gw = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    nw = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)

    ADD_FIELD_CHOICES = [
        ('RHODIUM',   'Rhodium Plating'),
        ('SETTING',   'Stone Setting'),
        ('SOLDER',    'Solder Added'),
        ('OTHER',     'Other Addition'),
    ]
    LESS_FIELD_CHOICES = [
        ('SETTING',   'Setting Loss'),
        ('FILING',    'Filing Loss'),
        ('POLISHING', 'Polishing Loss'),
        ('MELTING',   'Melting Loss'),
        ('OTHER',     'Other Loss'),
    ]
    add_field_type = models.CharField(max_length=20, null=True, blank=True, choices=ADD_FIELD_CHOICES)
    add_gw = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    less_field_type = models.CharField(null=True, blank=True, max_length=20, choices=LESS_FIELD_CHOICES)
    less_gw = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    tunch_per = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True) #only one of loss % and tunch % will be active
    fine_wt = models.DecimalField(max_digits=10, decimal_places=3)
    loss = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    main_total_wt = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    wastage = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    
    barcode = models.ForeignKey("inventory.BarcodeMain",on_delete=models.SET_NULL,null=True)
    
    finish_status = models.BooleanField()
    
    hallmark_status = models.BooleanField()
    rhodium = models.IntegerField(null=True, blank=True)
    
    making = models.IntegerField(null=True, blank=True)
    making_auto = models.BooleanField(
        default=False,
        help_text="True when `making` was auto-computed from karigar rate × incremental_gw and not user-edited.",
    )
    making_rate_applied = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, blank=True, null=True,
        help_text="The per-gram labour rate used when `making_auto` was computed.",
    )

    unbarcoded_item = models.OneToOneField("inventory.UnBarcodedMain",null=True,blank=True,on_delete=models.SET_NULL)

    remarks = models.CharField(max_length=100,blank=True,null=True)
    pending_pcs = models.IntegerField(default=0, blank=True)
    pending_gw = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    @property
    def item_name(self):
        return self.item.item_name

    @property
    def incremental_gw(self):
        """
        Net new gold the karigar added this cycle.

        Formula:
            incremental = received_nw
                          - raw_gold_supplied_to_this_job (sum of KarigarGoldIssue.conv_wt
                            linked to the parent issue slip, which is either KarigarIssue
                            or SampleIssue)
                          - sample_piece_gw (when receive lands against a SampleIssueItem,
                            the reworked piece started with this weight already)
        Negative values mean the karigar returned less gold than they received —
        the difference is captured separately on `less_gw` / `loss`.
        """
        nw = self.nw or 0
        supplied = 0
        parent = None
        if self.ref_sample_issue_id:
            parent = self.ref_sample_issue
        elif self.ref_job_no_id:
            parent = self.ref_job_no
        if parent is not None:
            supplied = sum(
                (gi.conv_wt or 0) for gi in parent.gold_issue.all()
            )
        sample_piece_gw = 0
        if self.ref_sample_issue_item_id:
            si_item = self.ref_sample_issue_item
            if si_item.piece_id:
                sample_piece_gw = si_item.piece.gw or 0
        return nw - supplied - sample_piece_gw

    class Meta:
        db_table = "receive_from_karigar_main"

class KarigarReceiveItemDetails(models.Model):
    receive_slip_no = models.ForeignKey(KarigarReceive, on_delete=models.CASCADE,null=True)
    sl_no = models.IntegerField()
    main_sl_no = models.ForeignKey(KarigarReceiveItem, on_delete = models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.SET_NULL,  null=True)
    metal_purity = models.ForeignKey(PurityMaster, on_delete = models.SET_NULL, null=True,blank=True)
    packet = models.ForeignKey(Packet, on_delete = models.SET_NULL, null=True, blank=True)
    issue_pcs = models.IntegerField()
    issue_ct = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    issue_gw = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    broken_pcs = models.IntegerField()
    broken_ct = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    broken_gw = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    return_pcs = models.IntegerField()
    return_ct = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    return_gw = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True)
    balance_pcs = models.IntegerField() #to be passed to barcode creation
    balance_ct = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True) #to be passed to barcode creation
    balance_gw = models.DecimalField(max_digits=10, decimal_places=3, default=0, blank=True, null=True) #to be passed to barcode creation
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, null=True) #to be passed to barcode creation
    amt = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, null=True) #to be passed to barcode creation

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)

    
    class Meta:
        db_table = "receive_from_karigar_details"

class HallmarkIssue(models.Model):
    issue_slip_no = models.CharField(max_length=30)
    date1 = models.DateField()
    hallmark_center = models.ForeignKey(Ledger, on_delete=models.PROTECT)
    retail          = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    fiscal_year     = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def hallmark_center_name(self):
        return self.hallmark_center.ac_name

    class Meta:
        db_table = "issue_to_hallmark"

class HallmarkIssueItem(models.Model):
    issue_slip_no = models.ForeignKey(HallmarkIssue, on_delete = models.CASCADE)
    sl_no = models.IntegerField()
    date1 = models.DateField(auto_now_add=True)
    receive_sl = models.ForeignKey(KarigarReceiveItem, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs = models.IntegerField()
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    nw = models.DecimalField(max_digits=10, decimal_places=3)
    purity = models.ForeignKey(PurityMaster, on_delete=models.PROTECT)
    remarks = models.CharField(max_length=50, blank=True, null=True)
    rec_status = models.BooleanField(default=False)
    unbarcoded_item = models.OneToOneField("inventory.UnBarcodedMain",null=True,blank=True,on_delete=models.SET_NULL)


    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)


    class Meta:
        db_table = "issue_to_hallmark_main"
    
class HallmarkIssueDetails(models.Model):
    billno = models.ForeignKey(HallmarkIssue, on_delete = models.CASCADE,null=True)
    main_item = models.ForeignKey(HallmarkIssueItem, on_delete = models.CASCADE)
    date1= models.DateField(auto_now_add=True)
    metal_purity = models.ForeignKey(PurityMaster, null=True, blank=True, on_delete=models.SET_NULL)
    packet = models.ForeignKey(Packet, on_delete=models.SET_NULL, null=True)
    pcs = models.IntegerField()
    ct = models.DecimalField(max_digits=10, decimal_places=3)
    gw = models.DecimalField(max_digits=10, decimal_places=3)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)


    class Meta:
        db_table = "issue_to_hallmark_details"


class HallmarkReceive(models.Model):
    date1 = models.DateField(auto_now_add=True)
    receive_slip_no = models.CharField(max_length=200)
    hallmark_center = models.ForeignKey(Ledger, on_delete=models.PROTECT)
    retail          = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    fiscal_year     = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def hallmark_center_name(self):
        return self.hallmark_center.ac_name

    class Meta:
        db_table = "receive_from_hallmark"

class HallmarkReceiveItem(models.Model):
    date1 = models.DateField(auto_now_add=True)
    receive_slip_no = models.ForeignKey(HallmarkReceive, on_delete=models.CASCADE)
    receive_sl = models.ForeignKey(KarigarReceiveItem, on_delete=models.SET_NULL, null=True, blank=True)
    sl_no = models.IntegerField()
    issue_slip_no = models.ForeignKey(HallmarkIssue, on_delete=models.CASCADE)
    huid = models.CharField(max_length=200,null=True, blank=True) # this should be fetched when creating a barcode
    remarks = models.CharField( max_length=200,null=True, blank=True)
    pcs = models.IntegerField()
    item = models.ForeignKey(Item,null=True,on_delete=models.SET_NULL,blank=True)
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    nw = models.DecimalField(max_digits=10, decimal_places=3)
    loss_wt = models.DecimalField(max_digits=10, decimal_places=3)
    purity = models.ForeignKey(PurityMaster, on_delete=models.PROTECT)
    rejection_status = models.BooleanField(default=False)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)


    class Meta:
        db_table = "receive_from_hallmark_main"

class HallmarkReceiveDetails(models.Model):
    date1= models.DateField(auto_now_add=True)
    main_item = models.ForeignKey(HallmarkReceiveItem, on_delete=models.CASCADE)
    receive_slip_no = models.ForeignKey(HallmarkReceive, on_delete=models.CASCADE,null=True)
    packet = models.ForeignKey(Packet, on_delete=models.SET_NULL, null=True)
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    metal_purity = models.ForeignKey(PurityMaster, on_delete=models.SET_NULL, null=True)
    pcs = models.IntegerField()
    ct = models.IntegerField()
    gw = models.DecimalField(max_digits=10, decimal_places=3)

    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)


    class Meta:
        db_table = "hallmark_receive_details"

class RefinaryIssue(models.Model):
    date1 = models.DateField()
    billno = models.CharField(max_length=30)
    ldgr        = models.ForeignKey(Ledger, on_delete=models.PROTECT)
    rec_status  = models.BooleanField(default=False)
    retail      = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def ldgr_name(self):
        return self.ldgr.ac_name

    class Meta:
        db_table = "issue_to_refinary"

class RefinaryIssueDetail(models.Model):
    billno = models.ForeignKey(RefinaryIssue, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs = models.IntegerField()
    ct = models.DecimalField(max_digits=10, decimal_places=3)
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    packet = models.ForeignKey(Packet, on_delete=models.PROTECT)
    metal_purity = models.ForeignKey(PurityMaster, on_delete=models.PROTECT)
    rec_status = models.BooleanField(default=False)
    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)
    class Meta:
        db_table = "issue_to_refinary_details"


class RefinaryReceive(models.Model):
    date1 = models.DateField()
    billno = models.CharField(max_length=30)
    ldgr        = models.ForeignKey(Ledger, on_delete=models.PROTECT)
    retail      = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "receive_from_refinary"


    @property
    def ldgr_name(self):
        return self.ldgr.ac_name 


class RefinaryReceiveDetail(models.Model):
    billno = models.ForeignKey(RefinaryReceive, on_delete=models.CASCADE)
    issue_no = models.ForeignKey(RefinaryIssue, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs = models.IntegerField()
    ct = models.DecimalField(max_digits=10, decimal_places=3)
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    loss_per = models.DecimalField(max_digits=10, decimal_places=3)
    loss_wt = models.DecimalField(max_digits=10, decimal_places=3)
    remarks = models.CharField(max_length=100)
    packet = models.ForeignKey(Packet, on_delete=models.PROTECT)
    metal_purity = models.ForeignKey(PurityMaster, on_delete=models.PROTECT)
    conv_purity = models.ForeignKey(PurityMaster, on_delete=models.PROTECT, related_name="converted_refinary_receive_set")
    conv_nw = models.DecimalField(max_digits=10, decimal_places=3)
    rec_status = models.BooleanField()
    retail = models.ForeignKey("mastersconfig.RetailMaster",on_delete=models.SET_NULL,null=True,blank=True)
    class Meta:
        db_table = "receive_from_refinary_details"


# ── Melting ──────────────────────────────────────────────────────────────────

class MeltingIssue(models.Model):
    date1       = models.DateField()
    billno      = models.CharField(max_length=30)
    ldgr        = models.ForeignKey(Ledger, on_delete=models.PROTECT)
    rec_status  = models.BooleanField(default=False)
    retail      = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def ldgr_name(self):
        return self.ldgr.ac_name

    class Meta:
        db_table = "issue_to_melting"


class MeltingIssueDetail(models.Model):
    billno       = models.ForeignKey(MeltingIssue, on_delete=models.CASCADE)
    item         = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs          = models.IntegerField()
    ct           = models.DecimalField(max_digits=10, decimal_places=3)
    gw           = models.DecimalField(max_digits=10, decimal_places=3)
    packet       = models.ForeignKey(Packet, on_delete=models.PROTECT)
    metal_purity = models.ForeignKey(PurityMaster, on_delete=models.PROTECT)
    rec_status   = models.BooleanField(default=False)
    retail       = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "issue_to_melting_details"


class MeltingReceive(models.Model):
    date1       = models.DateField()
    billno      = models.CharField(max_length=30)
    ldgr        = models.ForeignKey(Ledger, on_delete=models.PROTECT)
    retail      = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def ldgr_name(self):
        return self.ldgr.ac_name

    class Meta:
        db_table = "receive_from_melting"


class MeltingReceiveDetail(models.Model):
    billno       = models.ForeignKey(MeltingReceive, on_delete=models.CASCADE)
    issue_no     = models.ForeignKey(MeltingIssue, on_delete=models.CASCADE)
    item         = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs          = models.IntegerField()
    ct           = models.DecimalField(max_digits=10, decimal_places=3)
    gw           = models.DecimalField(max_digits=10, decimal_places=3)
    loss_per     = models.DecimalField(max_digits=10, decimal_places=3)
    loss_wt      = models.DecimalField(max_digits=10, decimal_places=3)
    remarks      = models.CharField(max_length=100, blank=True)
    packet       = models.ForeignKey(Packet, on_delete=models.PROTECT)
    metal_purity = models.ForeignKey(PurityMaster, on_delete=models.PROTECT)
    conv_purity  = models.ForeignKey(PurityMaster, on_delete=models.PROTECT, related_name="converted_melting_receive_set")
    conv_nw      = models.DecimalField(max_digits=10, decimal_places=3)
    rec_status   = models.BooleanField(default=False)
    retail       = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "receive_from_melting_details"


# ── Fire Assay ───────────────────────────────────────────────────────────────

class AssayIssue(models.Model):
    date1       = models.DateField()
    billno      = models.CharField(max_length=30)
    ldgr        = models.ForeignKey(Ledger, on_delete=models.PROTECT)
    melt_recv   = models.ForeignKey(
        "MeltingReceive", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="assay_issues",
        help_text="Source melting receive this assay sample was drawn from."
    )
    rec_status  = models.BooleanField(default=False)
    retail      = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def ldgr_name(self):
        return self.ldgr.ac_name

    @property
    def melt_recv_billno(self):
        return self.melt_recv.billno if self.melt_recv_id else None

    class Meta:
        db_table = "assay_issue"


class AssayIssueDetail(models.Model):
    billno       = models.ForeignKey(AssayIssue, on_delete=models.CASCADE)
    item         = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs          = models.IntegerField()
    ct           = models.DecimalField(max_digits=10, decimal_places=3)
    gw           = models.DecimalField(max_digits=10, decimal_places=3)
    packet       = models.ForeignKey(Packet, on_delete=models.PROTECT)
    metal_purity = models.ForeignKey(PurityMaster, on_delete=models.PROTECT)
    rec_status   = models.BooleanField(default=False)
    retail       = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "assay_issue_details"


class AssayReceive(models.Model):
    date1       = models.DateField()
    billno      = models.CharField(max_length=30)
    ldgr        = models.ForeignKey(Ledger, on_delete=models.PROTECT)
    retail      = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)
    fiscal_year = models.ForeignKey("mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def ldgr_name(self):
        return self.ldgr.ac_name

    class Meta:
        db_table = "assay_receive"


class AssayReceiveDetail(models.Model):
    billno       = models.ForeignKey(AssayReceive, on_delete=models.CASCADE)
    issue_no     = models.ForeignKey(AssayIssue, on_delete=models.CASCADE)
    item         = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs          = models.IntegerField()
    ct           = models.DecimalField(max_digits=10, decimal_places=3)
    gw           = models.DecimalField(max_digits=10, decimal_places=3)
    loss_per     = models.DecimalField(max_digits=10, decimal_places=3)
    loss_wt      = models.DecimalField(max_digits=10, decimal_places=3)
    remarks      = models.CharField(max_length=100, blank=True)
    packet       = models.ForeignKey(Packet, on_delete=models.PROTECT)
    metal_purity = models.ForeignKey(PurityMaster, on_delete=models.PROTECT)
    conv_purity  = models.ForeignKey(PurityMaster, on_delete=models.PROTECT, related_name="converted_assay_receive_set")
    conv_nw      = models.DecimalField(max_digits=10, decimal_places=3)
    is_cornet    = models.BooleanField(default=False, help_text="Flags the refined cornet row (99.5% pure). Cornet goes directly to fine-gold stock and bypasses the refinery flow.")
    rec_status   = models.BooleanField(default=False)
    retail       = models.ForeignKey("mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "assay_receive_details"




# ── Repair Job Card ────────────────────────────────────────────────────────────

class RepairJobCard(models.Model):
    STATUS_CHOICES = [
        ('RCV',  'Received from Customer'),
        ('ISS',  'Issued to Karigar'),
        ('RECV', 'Received from Karigar'),
        ('RDY',  'Ready for Delivery'),
        ('DLV',  'Delivered'),
    ]

    rjc_no                 = models.CharField(max_length=30)
    date1                  = models.DateField()
    customer               = models.ForeignKey(
        'contacts.Ledger',
        on_delete=models.PROTECT,
        related_name='repair_job_cards',
        limit_choices_to={'type': 'CO'},
    )
    status                 = models.CharField(max_length=10, choices=STATUS_CHOICES, default='RCV')
    item                   = models.ForeignKey(
        'mastersconfig.Item',
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    purity                 = models.ForeignKey(
        'goldrates.PurityMaster',
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    description            = models.TextField(blank=True)
    received_gw            = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    received_nw            = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    expected_delivery_date = models.DateField(null=True, blank=True)
    estimated_making       = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    remarks                = models.TextField(blank=True)
    fiscal_year            = models.ForeignKey(
        'mastersconfig.FiscalYearMaster',
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    retail                 = models.ForeignKey(
        'mastersconfig.RetailMaster',
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    class Meta:
        db_table = 'repair_job_card'

    def __str__(self):
        return f"{self.rjc_no} — {self.customer.ac_name}"


class RepairStone(models.Model):
    """Customer-owned stones received with the repair piece."""
    job_card    = models.ForeignKey(RepairJobCard, on_delete=models.CASCADE, related_name='stones')
    description = models.CharField(max_length=200, blank=True)
    pcs         = models.IntegerField(default=0)
    ct          = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    remarks     = models.CharField(max_length=100, blank=True)
    returned    = models.BooleanField(default=False)

    class Meta:
        db_table = 'repair_stone'


REPAIR_LOSS_TYPE_CHOICES = [
    ('POLISH',  'Polish Loss'),
    ('FILING',  'Filing Loss'),
    ('MELTING', 'Melting Loss'),
    ('STONE',   'Stone Setting Loss'),
    ('OTHER',   'Other'),
]


class RepairLoss(models.Model):
    """Named manufacturing loss entries for a repair job."""
    job_card  = models.ForeignKey(RepairJobCard, on_delete=models.CASCADE, related_name='losses')
    loss_type = models.CharField(max_length=15, choices=REPAIR_LOSS_TYPE_CHOICES)
    loss_wt   = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    remarks   = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'repair_loss'


class RepairKarigarLink(models.Model):
    """Join table linking a RepairJobCard to KarigarIssue and KarigarReceive records."""
    job_card        = models.ForeignKey(RepairJobCard, on_delete=models.CASCADE, related_name='karigar_links')
    karigar_issue   = models.ForeignKey(
        'KarigarIssue',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='repair_links',
    )
    karigar_receive = models.ForeignKey(
        'KarigarReceive',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='repair_links',
    )

    class Meta:
        db_table = 'repair_karigar_link'

