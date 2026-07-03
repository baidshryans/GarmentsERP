"""
Seed the database with realistic demo data for a jewellery ERP.

Usage:
    python manage.py seed_demo_data
    python manage.py seed_demo_data --reset   # clear existing demo data first

Idempotent: safe to re-run without creating duplicates.
"""
import decimal
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction


D = decimal.Decimal


# ─────────────────────────────────────────────────────────────────────────────
# Static demo data definitions
# ─────────────────────────────────────────────────────────────────────────────

COMPANY = {
    "company_name": "Zorii Diamonds Pvt. Ltd.",
    "pan": "AABCZ1234A",
    "tan": "CALC12345A",
    "gstin": "27AABCZ1234A1Z5",
    "cin": "U74999MH2010PTC123456",
    "phone": "02222334455",
    "email": "info@zoriidiamonds.com",
    "address": "101, Diamond Arcade, Opera House",
    "city": "Mumbai",
    "pincode": "400004",
    "website": "www.zoriidiamonds.com",
}

BRANCH = {
    "branch_name": "Head Office",
    "branch_code": "HO",
    "description": "Corporate head office and main showroom",
}

GSTIN = {
    "gstin": "27AABCZ1234A1Z5",
    "legal_name": "Zorii Diamonds Pvt. Ltd.",
}

RETAIL = {
    "retail_name": "Zorii Diamonds - Opera House",
    "retail_code": "MAIN",
    "email": "main@zoriidiamonds.com",
    "address_line1": "101, Diamond Arcade, Opera House",
    "city": "Mumbai",
    "pincode": "400004",
    "phone": "02222334455",
}

FISCAL_YEARS = [
    {"fy_code": "25-26", "fy_start": date(2025, 4, 1), "fy_end": date(2026, 3, 31)},
    {"fy_code": "26-27", "fy_start": date(2026, 4, 1), "fy_end": date(2027, 3, 31)},
]
ACTIVE_FY_CODE = "26-27"

PURITIES = [
    {"purity": "24K",      "gw_per": D("100.00")},
    {"purity": "22K",      "gw_per": D("91.67")},
    {"purity": "18K",      "gw_per": D("75.00")},
    {"purity": "14K",      "gw_per": D("58.33")},
    {"purity": "9K",       "gw_per": D("37.50")},
    {"purity": "Platinum", "gw_per": D("95.00")},
    {"purity": "Silver",   "gw_per": D("92.50")},
]

HSN_CODES = [
    {"hsn_no": "7113", "hsn_type": "GD", "cgst": D("1.5"), "sgst": D("1.5"), "igst": D("3.0"),
     "description": "Articles of Jewellery of precious metal"},
    {"hsn_no": "7108", "hsn_type": "GD", "cgst": D("0.0"), "sgst": D("0.0"), "igst": D("0.0"),
     "description": "Gold (including gold plated with platinum)"},
    {"hsn_no": "7102", "hsn_type": "GD", "cgst": D("0.0"), "sgst": D("0.0"), "igst": D("0.0"),
     "description": "Diamonds (whether or not worked)"},
    {"hsn_no": "7116", "hsn_type": "GD", "cgst": D("1.5"), "sgst": D("1.5"), "igst": D("3.0"),
     "description": "Articles of natural or cultured pearls, precious stones"},
    {"hsn_no": "9983", "hsn_type": "SR", "cgst": D("9.0"), "sgst": D("9.0"), "igst": D("18.0"),
     "description": "Making / Repair Services (Job Work)"},
]

ITEM_GROUPS = [
    {"item_group_name": "Gold Jewellery",    "short_code": "GJ"},
    {"item_group_name": "Diamond Jewellery", "short_code": "DJ"},
    {"item_group_name": "Silver Jewellery",  "short_code": "SJ"},
    {"item_group_name": "Loose Diamonds",    "short_code": "LD"},
    {"item_group_name": "Loose Gold",        "short_code": "LG"},
    {"item_group_name": "Making Charge",     "short_code": "MC"},
]

ITEMS = [
    # (short_code, item_name, item_type, uom, group, hsn_no, default_purity)
    ("GR22",  "Gold Ring 22K",          "M", "Gm",  "Gold Jewellery",    "7113", "22K"),
    ("GN22",  "Gold Necklace 22K",      "M", "Gm",  "Gold Jewellery",    "7113", "22K"),
    ("GE22",  "Gold Earrings 22K",      "M", "Gm",  "Gold Jewellery",    "7113", "22K"),
    ("GB22",  "Gold Bracelet 22K",      "M", "Gm",  "Gold Jewellery",    "7113", "22K"),
    ("GBN22", "Gold Bangle 22K",        "M", "Gm",  "Gold Jewellery",    "7113", "22K"),
    ("DR18",  "Diamond Ring 18K",       "M", "Gm",  "Diamond Jewellery", "7113", "18K"),
    ("DN18",  "Diamond Necklace 18K",   "M", "Gm",  "Diamond Jewellery", "7113", "18K"),
    ("DE18",  "Diamond Earrings 18K",   "M", "Gm",  "Diamond Jewellery", "7113", "18K"),
    ("SR925", "Silver Ring",            "M", "Gm",  "Silver Jewellery",  "7113", "Silver"),
    ("GOLD",  "Raw Gold",               "R", "Gm",  "Loose Gold",        "7108", "22K"),
    ("DIAM",  "Loose Diamond",          "S", "Ct",  "Loose Diamonds",    "7102", "18K"),
    ("STDBAR","Standard Gold Bar",      "R", "Gm",  "Loose Gold",        "7108", "24K"),
    ("MKCHG", "Making Charge",          "O", "Pcs", "Making Charge",     "9983", "22K"),
]

SHAPES = [
    {"shape_name": "Round",    "shape_code": "RND"},
    {"shape_name": "Oval",     "shape_code": "OVL"},
    {"shape_name": "Pear",     "shape_code": "PER"},
    {"shape_name": "Princess", "shape_code": "PRS"},
    {"shape_name": "Cushion",  "shape_code": "CSH"},
    {"shape_name": "Marquise", "shape_code": "MRQ"},
    {"shape_name": "Emerald",  "shape_code": "EMR"},
    {"shape_name": "Heart",    "shape_code": "HRT"},
]

COLORS = [
    {"color_name": "D"},
    {"color_name": "E"},
    {"color_name": "F"},
    {"color_name": "G"},
    {"color_name": "H"},
    {"color_name": "White Gold"},
    {"color_name": "Yellow Gold"},
    {"color_name": "Rose Gold"},
]

PACKET_GROUPS = [
    {"packet_group_name": "Round Brilliants"},
    {"packet_group_name": "Fancy Shapes"},
    {"packet_group_name": "Solitaires"},
    {"packet_group_name": "Melee"},
]

# (pckt_no, packet_group, stone_item, color, shape, is_solitaire, clarity,
#  seives, rate_for_retail, rate_for_wholesale)
PACKETS = [
    ("PKT001", "Melee",           "Loose Diamond", "F", "Round",    False, "VS1",  "8/8",  D("30000"), D("28000")),
    ("PKT002", "Melee",           "Loose Diamond", "G", "Round",    False, "VS2",  "8/8",  D("25000"), D("23000")),
    ("PKT003", "Round Brilliants","Loose Diamond", "E", "Round",    False, "VVS1", "11/8", D("50000"), D("47000")),
    ("PKT004", "Fancy Shapes",    "Loose Diamond", "F", "Princess", False, "VS1",  "7/7",  D("35000"), D("32000")),
    ("PKT005", "Solitaires",      "Loose Diamond", "D", "Round",    True,  "IF",   "6/4",  D("80000"), D("75000")),
]

# Customers: (ac_name, mobile, city, pan, b2b)
CUSTOMERS = [
    ("Rahul Mehta",      "9820112233", "Mumbai",     "ABCPM1234D", False),
    ("Priya Sharma",     "9833445566", "Pune",       "BCDPS5678E", False),
    ("Vikram Traders",   "2223456789", "Mumbai",     "CDEVT9012F", True),
    ("Sunita Joshi",     "9867890123", "Thane",      "DFJSJ3456G", False),
    ("Arjun Kapoor",     "9811223344", "Navi Mumbai","EFKAK7890H", False),
]

# Vendors/Suppliers: (ac_name, mobile, city, gst, pan)
VENDORS = [
    ("Mumbai Gold Refiners Pvt. Ltd.", "2226543210", "Mumbai", "27AABCM5678B1Z3", "AABCM5678B"),
    ("Surat Diamond House",            "2612345678", "Surat",  "24AABCS9012C1Z7", "AABCS9012C"),
    ("National Bullion Corp",          "2223344556", "Mumbai", "27AAACN3456D1Z1", "AAACN3456D"),
]

# Karigars: (ac_name, mobile, city)
KARIGARS = [
    ("Ramesh Sonar",  "9870001122", "Mumbai"),
    ("Dinesh Goldsmith", "9870003344", "Dharavi"),
]

# Banks: (ac_name, account_no, bank_name, branch)
BANKS = [
    ("HDFC Bank - Current A/c",   "50100123456789", "HDFC Bank", "Fort Branch"),
    ("Kotak Mahindra - OD A/c",   "7012345678",     "Kotak Mahindra Bank", "Opera House"),
]

# Refinery / Melting / Hallmark
REFINERIES   = [("National Refinery Mumbai", "2225556677")]
MELT_HOUSES  = [("Dharavi Melting Centre",   "9870005566")]
HM_CENTRES   = [("BIS Hallmark Centre",      "2223337788")]

SALESPERSONS = [
    # (name, commission_rate, commission_on)
    ("Amit Verma",  D("2.0"), "making"),
    ("Sneha Patil", D("1.5"), "overall"),
]

# Gold rates per purity (rate per gram for last 30 days ending today)
BASE_GOLD_RATE_22K = D("6500")   # Rs. per gram
BASE_BUYING_RATE   = D("6450")
BASE_SELLING_RATE  = D("6550")

# Barcodes to create
# (barcode, item_short, purity, gw, nw, pcs, making, making_type, design_code, metal_color)
BARCODES = [
    ("7800010000001", "GR22",  "22K", D("5.200"),  D("5.000"),  1, D("150"), "PG", "DR-001", "Yellow Gold"),
    ("7800010000002", "GR22",  "22K", D("6.400"),  D("6.100"),  1, D("180"), "PG", "DR-002", "Yellow Gold"),
    ("7800010000003", "GN22",  "22K", D("22.500"), D("21.800"), 1, D("100"), "PG", "NCK-001","Yellow Gold"),
    ("7800010000004", "GE22",  "22K", D("4.800"),  D("4.600"),  2, D("120"), "PG", "ER-001", "Yellow Gold"),
    ("7800010000005", "GB22",  "22K", D("12.300"), D("11.900"), 1, D("130"), "PG", "BR-001", "Yellow Gold"),
    ("7800010000006", "GBN22", "22K", D("28.000"), D("27.200"), 2, D("90"),  "PG", "BNG-001","Yellow Gold"),
    ("7800010000007", "DR18",  "18K", D("4.600"),  D("4.200"),  1, D("250"), "PG", "DMR-001","White Gold"),
    ("7800010000008", "DR18",  "18K", D("5.800"),  D("5.300"),  1, D("300"), "PG", "DMR-002","White Gold"),
    ("7800010000009", "DN18",  "18K", D("8.400"),  D("7.900"),  1, D("200"), "PG", "DMN-001","White Gold"),
    ("7800010000010", "DE18",  "18K", D("3.200"),  D("2.900"),  2, D("220"), "PG", "DME-001","White Gold"),
    ("7800010000011", "SR925", "Silver", D("15.500"), D("15.000"), 1, D("50"), "PG", "SR-001","Silver"),
    ("7800010000012", "GBN22", "22K", D("32.000"), D("31.000"), 2, D("85"),  "PG", "BNG-002","Yellow Gold"),
]

# Barcode stone details: (barcode, packet_no, pcs, ct, gw, rate, amt)
BARCODE_DETAILS = [
    ("7800010000007", "PKT001", 8,  D("0.48"), D("0.50"), D("30000"), D("14400")),
    ("7800010000007", "PKT005", 1,  D("0.50"), D("0.00"), D("80000"), D("40000")),
    ("7800010000008", "PKT003", 10, D("0.60"), D("0.62"), D("50000"), D("30000")),
    ("7800010000009", "PKT001", 22, D("1.32"), D("1.38"), D("30000"), D("39600")),
    ("7800010000010", "PKT002", 12, D("0.72"), D("0.76"), D("25000"), D("18000")),
]

# Purchase vouchers: (vendor_ac_name, date_offset_days, ref_no, items)
# items: (item_short, purity, pcs, gw, rate, making, making_type)
PURCHASE_VOUCHERS = [
    {
        "vendor": "Mumbai Gold Refiners Pvt. Ltd.",
        "date": date.today() - timedelta(days=25),
        "ref_no": "MGR/2026/001",
        "narration": "Gold purchase - standard bars",
        "items": [
            ("STDBAR", "24K", 1, D("100.000"), D("7200"), D("0"), "PG"),
            ("STDBAR", "24K", 1, D("100.000"), D("7200"), D("0"), "PG"),
        ],
    },
    {
        "vendor": "Surat Diamond House",
        "date": date.today() - timedelta(days=15),
        "ref_no": "SDH/2026/045",
        "narration": "Diamond purchase - melee and solitaire",
        "items": [
            ("DIAM", "18K", 30, D("1.80"),  D("30000"), D("0"), "PG"),
            ("DIAM", "18K", 5,  D("2.50"),  D("50000"), D("0"), "PG"),
        ],
    },
]

# Sales vouchers: (customer, date_offset, items, mode)
# items: (barcode, pcs, gw, making, making_type)
SALES_VOUCHERS = [
    {
        "customer": "Rahul Mehta",
        "date": date.today() - timedelta(days=12),
        "narration": "Sale of gold jewellery",
        "salesperson": "Amit Verma",
        "barcodes": ["7800010000001", "7800010000004"],
        "cash": D("0"),
        "mode": "Bank",
    },
    {
        "customer": "Priya Sharma",
        "date": date.today() - timedelta(days=8),
        "narration": "Sale of diamond ring",
        "salesperson": "Sneha Patil",
        "barcodes": ["7800010000007"],
        "cash": D("50000"),
        "mode": "Mixed",
    },
    {
        "customer": "Sunita Joshi",
        "date": date.today() - timedelta(days=3),
        "narration": "Sale of gold necklace and bangles",
        "salesperson": "Amit Verma",
        "barcodes": ["7800010000003", "7800010000006"],
        "cash": D("0"),
        "mode": "Bank",
    },
]

# Employees: (code, name, designation, department, dob, doj, gender, basic, hra, special)
EMPLOYEES = [
    {
        "employee_code": "EMP001",
        "username": "amit.verma",
        "full_name": "Amit Verma",
        "designation": "Senior Sales Executive",
        "department": "Sales",
        "date_of_birth": date(1988, 5, 15),
        "date_of_joining": date(2018, 7, 1),
        "gender": "M",
        "basic": D("25000"),
        "hra": D("10000"),
        "da": D("2500"),
        "conveyance_allowance": D("1600"),
        "medical_allowance": D("1250"),
        "special_allowance": D("4650"),
    },
    {
        "employee_code": "EMP002",
        "username": "sneha.patil",
        "full_name": "Sneha Patil",
        "designation": "Sales Executive",
        "department": "Sales",
        "date_of_birth": date(1993, 11, 22),
        "date_of_joining": date(2021, 3, 15),
        "gender": "F",
        "basic": D("20000"),
        "hra": D("8000"),
        "da": D("2000"),
        "conveyance_allowance": D("1600"),
        "medical_allowance": D("1250"),
        "special_allowance": D("3150"),
    },
    {
        "employee_code": "EMP003",
        "username": "rajan.nair",
        "full_name": "Rajan Nair",
        "designation": "Store Manager",
        "department": "Operations",
        "date_of_birth": date(1982, 3, 8),
        "date_of_joining": date(2015, 1, 10),
        "gender": "M",
        "basic": D("40000"),
        "hra": D("16000"),
        "da": D("4000"),
        "conveyance_allowance": D("1600"),
        "medical_allowance": D("1250"),
        "special_allowance": D("12150"),
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Management command
# ─────────────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Seed the database with realistic demo data for a jewellery ERP (idempotent)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear all previously seeded demo data before re-seeding",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset()

        with transaction.atomic():
            self._phase("1/9", "Infrastructure (accounts, states, TDS)")
            self._setup_infrastructure()

            self._phase("2/9", "Company, Branch, GSTIN, Retail, Fiscal Year")
            retail, fy = self._setup_org()

            self._phase("3/9", "Item Masters (purities, HSN, items, groups, stones)")
            self._setup_item_masters()

            self._phase("4/9", "Ledgers (customers, vendors, karigars, banks)")
            self._setup_ledgers(retail)

            self._phase("5/9", "Salespersons & Karigar Making")
            self._setup_salespersons_and_karigars(retail)

            self._phase("6/9", "Gold Rates (last 30 days)")
            self._setup_gold_rates()

            self._phase("7/9", "Barcodes & Opening Inventory")
            self._setup_inventory(retail, fy)

            self._phase("8/9", "Purchase & Sales Vouchers")
            self._setup_vouchers(retail, fy)

            self._phase("9/9", "HR - Employees, Salary Structures, Salary Slips")
            self._setup_hr(retail, fy)

        self.stdout.write(self.style.SUCCESS("\n[OK] Demo data seeded successfully!\n"))

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _phase(self, tag, label):
        self.stdout.write(self.style.HTTP_INFO(f"\n  [{tag}] {label}"))

    def _ok(self, msg):
        self.stdout.write(f"        + {msg}")

    def _skip(self, msg):
        self.stdout.write(f"        . {msg} (already exists)")

    def _reset(self):
        self.stdout.write(self.style.WARNING("  Resetting demo data…"))
        from mastersconfig.models import (
            CompanyMaster, BranchMaster, GSTINMaster, RetailMaster,
            FiscalYearMaster, SalesPersonMaster,
        )
        from contacts.models import Ledger
        from goldrates.models import GoldRates
        from inventory.models import BarcodeMain, BarcodeDetails
        from hr.models import Employee, SalaryStructure, SalarySlip

        SalarySlip.objects.all().delete()
        SalaryStructure.objects.all().delete()
        Employee.objects.all().delete()
        BarcodeDetails.objects.all().delete()
        BarcodeMain.objects.all().delete()
        GoldRates.objects.all().delete()
        SalesPersonMaster.objects.all().delete()
        FiscalYearMaster.objects.all().delete()
        Ledger.objects.filter(is_system=False).delete()
        RetailMaster.objects.all().delete()
        GSTINMaster.objects.all().delete()
        BranchMaster.objects.all().delete()
        CompanyMaster.objects.all().delete()
        self.stdout.write(self.style.WARNING("  Reset complete.\n"))

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 1 - Infrastructure
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_infrastructure(self):
        call_command("setup_account_groups", verbosity=0)
        self._ok("Chart of accounts")

        call_command("setup_states", verbosity=0)
        self._ok("Indian states")

        call_command("setup_tds_initial_data", verbosity=0)
        self._ok("TDS / TCS sections")

        call_command("seed_app_registry", verbosity=0)
        self._ok("App / licensing registry")

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 2 - Organisation
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_org(self):
        from mastersconfig.models import (
            State, CompanyMaster, BranchMaster, GSTINMaster,
            RetailMaster, FiscalYearMaster,
        )
        from accounting.models import Account

        mh_state = State.objects.filter(code="27").first() or State.objects.first()

        # Company — reuse any existing company to avoid duplicates
        existing = CompanyMaster.objects.first()
        if existing:
            company = existing
            self._skip(f"Company: {company.company_name} (reusing existing)")
        else:
            company = CompanyMaster.objects.create(**{**COMPANY, "state": mh_state})
            self._ok(f"Company: {company.company_name}")

        # Branch
        branch, created = BranchMaster.objects.get_or_create(
            branch_code=BRANCH["branch_code"],
            defaults={**BRANCH, "company": company, "state": mh_state},
        )
        if created:
            self._ok(f"Branch: {branch.branch_name}")
        else:
            self._skip(f"Branch: {branch.branch_name}")

        # GSTIN (signal creates 12 GST register ledgers)
        gstin, created = GSTINMaster.objects.get_or_create(
            gstin=GSTIN["gstin"],
            defaults={**GSTIN, "branch": branch, "state": mh_state},
        )
        if created:
            self._ok(f"GSTIN: {gstin.gstin}  (+ 12 GST register ledgers)")
        else:
            self._skip(f"GSTIN: {gstin.gstin}")

        # Retail (signal creates cash ledger + TDS/TCS payable ledgers)
        retail, created = RetailMaster.objects.get_or_create(
            retail_code=RETAIL["retail_code"],
            defaults={
                **RETAIL,
                "state": mh_state,
                "gstin_master": gstin,
                "branch": branch,
            },
        )
        if created:
            self._ok(f"Retail: {retail.retail_name}  (+ cash ledger)")
        else:
            self._skip(f"Retail: {retail.retail_name}")

        # Fiscal Years
        active_fy = None
        for fy_data in FISCAL_YEARS:
            fy, created = FiscalYearMaster.objects.get_or_create(
                fy_code=fy_data["fy_code"],
                defaults={**fy_data},
            )
            if created:
                self._ok(f"Fiscal Year: {fy.fy_code}")
            else:
                self._skip(f"Fiscal Year: {fy.fy_code}")
            if fy_data["fy_code"] == ACTIVE_FY_CODE:
                active_fy = fy

        # Set company-wide active FY
        from mastersconfig.models import SystemSettings
        if SystemSettings.get().active_fy_id != active_fy.pk:
            SystemSettings.set_company_active_fy(active_fy)
            self._ok(f"Active FY set to {active_fy.fy_code}")

        return retail, active_fy

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 3 - Item Masters
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_item_masters(self):
        from mastersconfig.models import (
            ItemGroupMaster, Hsn, Item,
            Shapes, Colors, PacketGroup, Packet,
        )
        from goldrates.models import PurityMaster
        from accounting.models import Account

        # Purities
        purity_map = {}
        for p in PURITIES:
            obj, created = PurityMaster.objects.get_or_create(
                purity=p["purity"], defaults=p
            )
            purity_map[p["purity"]] = obj
            if created:
                self._ok(f"Purity: {obj.purity}")

        # HSN codes
        hsn_map = {}
        for h in HSN_CODES:
            obj, created = Hsn.objects.get_or_create(
                hsn_no=h["hsn_no"], defaults=h
            )
            hsn_map[h["hsn_no"]] = obj
            if created:
                self._ok(f"HSN: {obj.hsn_no} - {obj.description[:40]}")

        # Item groups
        grp_map = {}
        for g in ITEM_GROUPS:
            obj, created = ItemGroupMaster.objects.get_or_create(
                short_code=g["short_code"], defaults=g
            )
            grp_map[g["item_group_name"]] = obj
            if created:
                self._ok(f"Item Group: {obj.item_group_name}")

        # Find auto-created trading ledgers from CompanyMaster signal
        from contacts.models import Ledger as LedgerModel
        gold_pur_ldgr = LedgerModel.objects.filter(ac_name="Gold Purchase", is_system=True).first()
        gold_sal_ldgr = LedgerModel.objects.filter(ac_name="Gold Sales",    is_system=True).first()
        diam_pur_ldgr = LedgerModel.objects.filter(ac_name="Diamond Purchase", is_system=True).first()
        diam_sal_ldgr = LedgerModel.objects.filter(ac_name="Diamond Sales",    is_system=True).first()

        sale_ldgr_map = {
            "Gold Jewellery":    gold_sal_ldgr,
            "Diamond Jewellery": diam_sal_ldgr,
            "Silver Jewellery":  gold_sal_ldgr,
            "Loose Diamonds":    diam_sal_ldgr,
            "Loose Gold":        gold_sal_ldgr,
            "Making Charge":     gold_sal_ldgr,
        }
        pur_ldgr_map = {
            "Gold Jewellery":    gold_pur_ldgr,
            "Diamond Jewellery": diam_pur_ldgr,
            "Silver Jewellery":  gold_pur_ldgr,
            "Loose Diamonds":    diam_pur_ldgr,
            "Loose Gold":        gold_pur_ldgr,
            "Making Charge":     gold_pur_ldgr,
        }

        # Items
        item_map = {}
        for (sc, name, itype, uom, grp_name, hsn_no, purity_code) in ITEMS:
            obj, created = Item.objects.get_or_create(
                short_code=sc,
                defaults={
                    "item_name": name,
                    "item_type": itype,
                    "uom": uom,
                    "grp": grp_map.get(grp_name),
                    "hsn_no": hsn_map.get(hsn_no),
                    "default_purity": purity_map.get(purity_code),
                    "purchase_ledger": pur_ldgr_map.get(grp_name),
                    "sale_ledger":     sale_ldgr_map.get(grp_name),
                    "show_in_pcs_report": False,
                },
            )
            item_map[sc] = obj
            if created:
                self._ok(f"Item: {obj.short_code} - {obj.item_name}")

        # Shapes
        shape_map = {}
        for s in SHAPES:
            obj, created = Shapes.objects.get_or_create(
                shape_code=s["shape_code"], defaults=s
            )
            shape_map[s["shape_name"]] = obj
            if created:
                self._ok(f"Shape: {obj.shape_name}")

        # Colors
        color_map = {}
        for c in COLORS:
            obj, created = Colors.objects.get_or_create(
                color_name=c["color_name"], defaults=c
            )
            color_map[c["color_name"]] = obj
            if created:
                self._ok(f"Color: {obj.color_name}")

        # Packet Groups
        pg_map = {}
        for pg in PACKET_GROUPS:
            obj, created = PacketGroup.objects.get_or_create(
                packet_group_name=pg["packet_group_name"], defaults=pg
            )
            pg_map[pg["packet_group_name"]] = obj
            if created:
                self._ok(f"Packet Group: {obj.packet_group_name}")

        # Packets
        diam_item = item_map.get("DIAM")
        for (pno, pg_name, item_name, color_name, shape_name,
             is_sol, clarity, seives, rate_r, rate_w) in PACKETS:
            obj, created = Packet.objects.get_or_create(
                pckt_no=pno,
                defaults={
                    "packet_group": pg_map.get(pg_name),
                    "stone_item_id": diam_item,
                    "color": color_map.get(color_name),
                    "shape": shape_map.get(shape_name),
                    "is_solitaire": is_sol,
                    "is_customer_stone": False,
                    "clarity": clarity,
                    "seives": seives,
                    "rate_for_retail": rate_r,
                    "rate_for_wholesale": rate_w,
                },
            )
            if created:
                self._ok(f"Packet: {obj.pckt_no} ({pg_name})")

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 4 - Ledgers
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_ledgers(self, retail):
        from mastersconfig.models import State
        from accounting.models import Account
        from contacts.models import Ledger, LedgerRole

        mh_state = State.objects.filter(code="27").first()

        def _make_ledger(ac_name, ac_group_code, role_code, **kwargs):
            ac_group = Account.objects.filter(code=ac_group_code).first()
            ldgr, created = Ledger.objects.get_or_create(
                ac_name=ac_name,
                retail_code=retail,
                defaults={
                    "display_name": ac_name,
                    "ac_group": ac_group,
                    "retail_code": retail,
                    **kwargs,
                },
            )
            if created:
                LedgerRole.objects.get_or_create(
                    ledger=ldgr, role=role_code, defaults={"is_primary": True}
                )
                self._ok(f"Ledger [{role_code}]: {ac_name}")
            else:
                self._skip(f"Ledger [{role_code}]: {ac_name}")
            return ldgr

        # Customers
        for name, mobile, city, pan, b2b in CUSTOMERS:
            _make_ledger(name, "CA-SD", "CO",
                         mobile1=mobile, city=city, pan=pan, b2b=b2b,
                         state=mh_state)

        # Vendors / Suppliers
        for name, mobile, city, gst, pan in VENDORS:
            _make_ledger(name, "CL-SC", "VD",
                         mobile1=mobile, city=city, gst=gst, pan=pan,
                         b2b=True, state=mh_state)

        # Karigars
        for name, mobile, city in KARIGARS:
            _make_ledger(name, "CL-SC", "KR",
                         mobile1=mobile, city=city, state=mh_state)

        # Banks
        for name, _, _, _ in BANKS:
            _make_ledger(name, "CA-BNK", "BA")

        # Refinery
        for name, mobile in REFINERIES:
            _make_ledger(name, "CL-SC", "REF", mobile1=mobile)

        # Melting Houses
        for name, mobile in MELT_HOUSES:
            _make_ledger(name, "CL-SC", "MLT", mobile1=mobile)

        # Hallmark Centres
        for name, mobile in HM_CENTRES:
            _make_ledger(name, "CL-SC", "HM", mobile1=mobile)

        # Capital account
        _make_ledger("Owner's Capital Account", "CAP-OWN", "OTH")

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 5 - Salespersons & Karigar Making
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_salespersons_and_karigars(self, retail):
        from mastersconfig.models import SalesPersonMaster, Item
        from manufacturing.models import KarigarMaster
        from contacts.models import Ledger
        from goldrates.models import PurityMaster

        # Salesperson commission ledger (Indirect Income)
        from accounting.models import Account
        from contacts.models import LedgerRole

        comm_ac = Account.objects.filter(code="INC-IND").first()
        sp_map = {}
        for sp_name, rate, comm_on in SALESPERSONS:
            # create a payable ledger for salesperson commissions
            comm_ldgr, _ = Ledger.objects.get_or_create(
                ac_name=f"Commission Payable - {sp_name}",
                retail_code=retail,
                defaults={
                    "display_name": f"Commission Payable - {sp_name}",
                    "ac_group": comm_ac,
                    "retail_code": retail,
                },
            )
            if not comm_ldgr.roles.exists():
                LedgerRole.objects.create(ledger=comm_ldgr, role="OTH", is_primary=True)

            sp, created = SalesPersonMaster.objects.get_or_create(
                salesperson_name=sp_name,
                retail=retail,
                defaults={
                    "commission_rate": rate,
                    "commission_on": comm_on,
                    "ledger": comm_ldgr,
                    "deduct_discount": False,
                },
            )
            sp_map[sp_name] = sp
            if created:
                self._ok(f"Salesperson: {sp.salesperson_name}")
            else:
                self._skip(f"Salesperson: {sp.salesperson_name}")

        # Karigar Making
        karigar_ldgrs = Ledger.objects.filter(
            retail_code=retail,
            roles__role="KR",
        )
        items_for_making = Item.objects.filter(
            short_code__in=["GR22", "GN22", "GE22", "GB22", "GBN22",
                            "DR18", "DN18", "DE18"]
        )
        purity_22k = PurityMaster.objects.filter(purity="22K").first()
        purity_18k = PurityMaster.objects.filter(purity="18K").first()

        making_data = [
            # (item_short, purity, per_gm, per_pc, loss_rate)
            ("GR22",  purity_22k, D("35"), D("0"),   D("1.5")),
            ("GN22",  purity_22k, D("30"), D("0"),   D("1.5")),
            ("GE22",  purity_22k, D("40"), D("0"),   D("1.2")),
            ("GB22",  purity_22k, D("32"), D("0"),   D("1.3")),
            ("GBN22", purity_22k, D("28"), D("0"),   D("1.4")),
            ("DR18",  purity_18k, D("50"), D("0"),   D("1.8")),
            ("DN18",  purity_18k, D("45"), D("0"),   D("1.6")),
            ("DE18",  purity_18k, D("55"), D("0"),   D("1.5")),
        ]

        for karigar_ldgr in karigar_ldgrs:
            for (sc, purity, pgm, ppc, loss) in making_data:
                if purity is None:
                    continue
                item = Item.objects.filter(short_code=sc).first()
                if not item:
                    continue
                _, created = KarigarMaster.objects.get_or_create(
                    karigar=karigar_ldgr,
                    item=item,
                    purity=purity,
                    retail=retail,
                    defaults={
                        "making_per_gm": pgm,
                        "making_per_pc": ppc,
                        "loss_rate": loss,
                    },
                )
                if created:
                    self._ok(f"Karigar Making: {karigar_ldgr.ac_name} × {sc} × {purity.purity}")

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 6 - Gold Rates
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_gold_rates(self):
        from goldrates.models import GoldRates, PurityMaster

        purities = PurityMaster.objects.all()
        if not purities.exists():
            return

        purity_multipliers = {
            "24K": D("1.0"),
            "22K": D("0.9167"),
            "18K": D("0.75"),
            "14K": D("0.5833"),
            "9K":  D("0.375"),
            "Silver": D("0.085"),
            "Platinum": D("1.35"),
        }

        today = date.today()
        created_count = 0
        for i in range(30):
            rate_date = today - timedelta(days=29 - i)
            # Slight daily variation (±0.5%)
            variation = D("1") + D(str(round(0.005 * ((i % 7) - 3) / 3, 4)))
            for purity in purities:
                mult = purity_multipliers.get(purity.purity, D("1.0"))
                base = BASE_GOLD_RATE_22K * mult * variation
                buy  = BASE_BUYING_RATE  * mult * variation
                sell = BASE_SELLING_RATE * mult * variation

                _, created = GoldRates.objects.get_or_create(
                    purity=purity,
                    date1=rate_date,
                    defaults={
                        "rate": base.quantize(D("0.01")),
                        "buying_rate": buy.quantize(D("0.01")),
                        "selling_rate": sell.quantize(D("0.01")),
                    },
                )
                if created:
                    created_count += 1

        self._ok(f"Gold rate entries created: {created_count}")

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 7 - Barcodes & Opening Inventory
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_inventory(self, retail, fy):
        from mastersconfig.models import Item, Packet
        from goldrates.models import PurityMaster
        from inventory.models import BarcodeMain, BarcodeDetails
        from contacts.models import Ledger

        item_map   = {i.short_code: i for i in Item.objects.all()}
        purity_map = {p.purity: p for p in PurityMaster.objects.all()}
        packet_map = {p.pckt_no: p for p in Packet.objects.all()}

        # Find a karigar to assign as kr_code
        karigar = Ledger.objects.filter(
            retail_code=retail, roles__role="KR"
        ).first()

        for (bc_no, item_sc, purity_code, gw, nw, pcs,
             making, making_type, design_code, metal_color) in BARCODES:

            item   = item_map.get(item_sc)
            purity = purity_map.get(purity_code)
            if not item or not purity:
                continue

            bc, created = BarcodeMain.objects.get_or_create(
                barcode=bc_no,
                defaults={
                    "item": item,
                    "purity": purity,
                    "pcs": pcs,
                    "gw": gw,
                    "nw": nw,
                    "making_val": making,
                    "making_type": making_type,
                    "design_code": design_code,
                    "metal_color": metal_color,
                    "stk_status": True,
                    "retail": retail,
                    "kr_code": karigar,
                    "huid": f"HUID{bc_no[-6:]}",
                },
            )
            if created:
                self._ok(f"Barcode: {bc_no} - {item.item_name}")

        # Barcode stone details
        for (bc_no, pckt_no, pcs, ct, gw, rate, amt) in BARCODE_DETAILS:
            bc     = BarcodeMain.objects.filter(barcode=bc_no).first()
            packet = packet_map.get(pckt_no)
            if not bc or not packet:
                continue
            _, created = BarcodeDetails.objects.get_or_create(
                barcode=bc,
                item=packet.stone_item_id,
                packet=packet,
                defaults={"pcs": pcs, "ct": ct, "gw": gw, "rate": rate, "amt": amt},
            )
            if created:
                self._ok(f"  Stone detail: {bc_no} + {pckt_no}")

        # Opening inventory for loose gold and diamond items
        from inventory.models import RawMaterialInventory
        raw_items = [
            ("GOLD",  "22K", 0, D("0"),    D("500.000")),   # pcs, ct, gw
            ("STDBAR","24K", 0, D("0"),    D("200.000")),
            ("DIAM",  "18K", 50, D("3.0"), D("0")),
        ]
        for (sc, purity_code, pcs, ct, gw) in raw_items:
            item   = item_map.get(sc)
            purity = purity_map.get(purity_code)
            if not item or not purity:
                continue
            _, created = RawMaterialInventory.objects.get_or_create(
                item=item, purity=purity, retail=retail,
                defaults={"pcs": pcs, "ct": ct, "gw": gw, "packet": None},
            )
            if created:
                self._ok(f"Raw material inventory: {sc} ({purity_code})")

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 8 - Purchase & Sales Vouchers
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_vouchers(self, retail, fy):
        self._setup_purchases(retail, fy)
        self._setup_sales(retail, fy)
        self._setup_journal_entries(retail, fy)

    def _next_voucher_no(self, retail, fy, prefix):
        from mastersconfig.models import BillNumberSequence
        seq, _ = BillNumberSequence.objects.get_or_create(
            retail=retail, fiscal_year=fy, prefix=prefix,
            defaults={"last_number": 0},
        )
        seq.last_number += 1
        seq.save(update_fields=["last_number"])
        return f"{prefix}/{retail.retail_code}/{fy.fy_code}/{seq.last_number:04d}"

    def _setup_purchases(self, retail, fy):
        from purchase.models import PurchaseVoucher, PurchaseVoucherItems
        from contacts.models import Ledger
        from mastersconfig.models import Item, GSTINMaster
        from goldrates.models import PurityMaster
        from accounting.models import VoucherMain, VoucherDetail

        gstin = GSTINMaster.objects.filter(gstin=COMPANY["gstin"]).first()

        for i, pv_data in enumerate(PURCHASE_VOUCHERS, start=1):
            vendor = Ledger.objects.filter(
                ac_name=pv_data["vendor"], retail_code=retail
            ).first()
            if not vendor:
                self.stdout.write(self.style.WARNING(
                    f"        ! Vendor not found: {pv_data['vendor']}"
                ))
                continue

            billno = self._next_voucher_no(retail, fy, "PV")

            # Check idempotency by ref_no
            if PurchaseVoucher.objects.filter(
                retail=retail, ref_no=pv_data["ref_no"]
            ).exists():
                self._skip(f"Purchase Voucher: {pv_data['ref_no']}")
                continue

            # Calculate totals
            item_map = {i.short_code: i for i in Item.objects.all()}
            purity_map = {p.purity: p for p in PurityMaster.objects.all()}
            pur_ac = vendor.ac_group

            item_total = D("0")
            item_rows = []
            for (sc, purity_code, pcs, gw, rate, making, making_type) in pv_data["items"]:
                item  = item_map.get(sc)
                pur   = purity_map.get(purity_code)
                value = (gw * rate).quantize(D("0.01"))
                item_total += value
                item_rows.append((item, pur, pcs, gw, rate, making, making_type, value))

            bill_value = item_total

            # Accounting voucher (Journal - Cr vendor, Dr purchases)
            pur_expense_ac = Ledger.objects.filter(
                ac_name="Gold Purchase", retail_code=None
            ).first()

            vou_no = self._next_voucher_no(retail, fy, "JV")
            ac_vou = VoucherMain.objects.create(
                date=pv_data["date"],
                voucher_no=vou_no,
                narration=pv_data["narration"],
                amount=bill_value,
                voucher_type="JRNL",
                status="posted",
                retail=retail,
                fiscal_year=fy,
                gstin_ref=gstin,
                branch_ref=retail.branch,
            )
            # Dr Stock/Purchase, Cr Vendor
            if pur_expense_ac:
                VoucherDetail.objects.create(
                    voucher_main=ac_vou,
                    account=pur_expense_ac,
                    debit=bill_value,
                    credit=D("0"),
                    voucher_type="JRNL",
                    voucher_no=vou_no,
                )
            VoucherDetail.objects.create(
                voucher_main=ac_vou,
                account=vendor,
                debit=D("0"),
                credit=bill_value,
                voucher_type="JRNL",
                voucher_no=vou_no,
            )

            pv = PurchaseVoucher.objects.create(
                date1=pv_data["date"],
                billno=billno,
                ref_no=pv_data["ref_no"],
                ref_date=pv_data["date"],
                item_total=item_total,
                bill_value=bill_value,
                due_amt=bill_value,
                narration=pv_data["narration"],
                ldgr=vendor,
                ac_voucher=ac_vou,
                retail=retail,
                fiscal_year=fy,
                gstin_ref=gstin,
                branch_ref=retail.branch,
            )

            for j, (item, purity, pcs, gw, rate, making, making_type, value) in enumerate(item_rows, 1):
                if item:
                    PurchaseVoucherItems.objects.create(
                        billno=pv,
                        item=item,
                        purity=purity,
                        sl_no=j,
                        pcs=pcs,
                        gw=gw,
                        making_type=making_type,
                        making=making,
                        making_value=D("0"),
                        item_value=value,
                        retail=retail,
                    )

            self._ok(f"Purchase Voucher: {billno} - {pv_data['vendor']} - Rs.{bill_value:,.0f}")

    def _setup_sales(self, retail, fy):
        from sales.models import SalesVou, SalesVouItem
        from contacts.models import Ledger
        from mastersconfig.models import SalesPersonMaster, GSTINMaster
        from inventory.models import BarcodeMain
        from accounting.models import VoucherMain, VoucherDetail

        gstin = GSTINMaster.objects.filter(gstin=COMPANY["gstin"]).first()

        for sv_data in SALES_VOUCHERS:
            customer = Ledger.objects.filter(
                ac_name=sv_data["customer"], retail_code=retail
            ).first()
            if not customer:
                continue

            # Idempotency: check by customer + date + first barcode
            first_bc = sv_data["barcodes"][0] if sv_data["barcodes"] else None
            if first_bc and SalesVouItem.objects.filter(
                barcode__barcode=first_bc, billno__retail=retail
            ).exists():
                self._skip(f"Sales Voucher: {sv_data['customer']} × {first_bc}")
                continue

            billno = self._next_voucher_no(retail, fy, "SV")
            gst_billno = f"{retail.retail_code}/{fy.fy_code}/{billno.split('/')[-1]}"

            # Collect barcodes and compute totals
            bc_objects = []
            for bc_no in sv_data["barcodes"]:
                bc = BarcodeMain.objects.filter(barcode=bc_no, retail=retail).first()
                if bc:
                    bc_objects.append(bc)

            if not bc_objects:
                continue

            # Item total = sum of (gw × current 22K rate ≈ 6500 + making)
            item_total = D("0")
            for bc in bc_objects:
                rate_22k = D("6500")
                metal_val = (bc.gw * rate_22k).quantize(D("0.01"))
                making_val = bc.making_val or D("0")
                item_total += metal_val + making_val

            taxable_value = item_total
            cgst_per = D("1.5")
            sgst_per = D("1.5")
            cgst_amt = (taxable_value * cgst_per / 100).quantize(D("0.01"))
            sgst_amt = (taxable_value * sgst_per / 100).quantize(D("0.01"))
            total_bill = taxable_value + cgst_amt + sgst_amt

            sp = SalesPersonMaster.objects.filter(
                salesperson_name=sv_data["salesperson"], retail=retail
            ).first()

            # Receipt voucher
            bank_ldgr = Ledger.objects.filter(
                retail_code=retail, roles__role="BA"
            ).first()
            cash_ldgr = retail.cash_ldgr

            vou_no = self._next_voucher_no(retail, fy, "RCPT")
            ac_vou = VoucherMain.objects.create(
                date=sv_data["date"],
                voucher_no=vou_no,
                narration=f"Receipt against {billno}",
                amount=total_bill,
                voucher_type="RCPT",
                status="posted",
                retail=retail,
                fiscal_year=fy,
                gstin_ref=gstin,
                branch_ref=retail.branch,
            )

            recv_ac = bank_ldgr or cash_ldgr
            if recv_ac:
                VoucherDetail.objects.create(
                    voucher_main=ac_vou,
                    account=recv_ac,
                    debit=total_bill,
                    credit=D("0"),
                    voucher_type="RCPT",
                    voucher_no=vou_no,
                )
            VoucherDetail.objects.create(
                voucher_main=ac_vou,
                account=customer,
                debit=D("0"),
                credit=total_bill,
                voucher_type="RCPT",
                voucher_no=vou_no,
            )

            sv = SalesVou.objects.create(
                date1=sv_data["date"],
                billno=billno,
                gst_billno=gst_billno,
                place_of_supply="27",
                ldgr=customer,
                sales_person=sp,
                sales_person2=sp,
                cgst_per=cgst_per,
                sgst_per=sgst_per,
                igst_per=D("0"),
                round_off=D("0"),
                discount=D("0"),
                cash=sv_data["cash"],
                due_amt=D("0"),
                ac_voucher=ac_vou,
                retail=retail,
                gstin_ref=gstin,
                branch_ref=retail.branch,
                fiscal_year=fy,
            )

            for bc in bc_objects:
                rate_22k = D("6500")
                metal_val = (bc.gw * rate_22k).quantize(D("0.01"))
                making_val = bc.making_val or D("0")
                SalesVouItem.objects.create(
                    billno=sv,
                    barcode=bc,
                    item=bc.item,
                    pcs=bc.pcs,
                    gw=bc.gw,
                    making=making_val,
                    making_type=bc.making_type or "PG",
                    purity=int(bc.purity.gw_per * 10),
                    amount=int((metal_val + making_val).quantize(D("1"))),
                    retail=retail,
                )
                # Mark barcode as sold
                bc.stk_status = False
                bc.save(update_fields=["stk_status"])

            self._ok(
                f"Sales Voucher: {billno} - {sv_data['customer']} - "
                f"Rs.{total_bill:,.0f}  ({len(bc_objects)} items)"
            )

    def _setup_journal_entries(self, retail, fy):
        from accounting.models import VoucherMain, VoucherDetail, LedgerOpenBalance
        from contacts.models import Ledger

        # Opening balances for customers (Sundry Debtors)
        opening_balances = [
            ("Rahul Mehta",      D("125000"), D("0")),
            ("Vikram Traders",   D("85000"),  D("0")),
            ("Owner's Capital Account", D("0"), D("5000000")),
        ]

        for (ac_name, debit, credit) in opening_balances:
            ldgr = Ledger.objects.filter(
                ac_name=ac_name, retail_code=retail
            ).first()
            if not ldgr:
                continue
            _, created = LedgerOpenBalance.objects.get_or_create(
                ldgr=ldgr, retail=retail,
                defaults={"debit": debit, "credit": credit, "acc_year": fy.fy_code},
            )
            if created:
                self._ok(f"Opening Balance: {ac_name}  Dr {debit}  Cr {credit}")

        # Payment voucher: rent payment
        rent_ldgr = Ledger.objects.filter(ac_name__icontains="Rent", is_system=True).first()
        bank_ldgr = Ledger.objects.filter(
            retail_code=retail, roles__role="BA"
        ).first()

        if bank_ldgr:
            vou_no = self._next_voucher_no(retail, fy, "PMNT")
            if not VoucherMain.objects.filter(voucher_no=vou_no).exists():
                vou = VoucherMain.objects.create(
                    date=date.today() - timedelta(days=20),
                    voucher_no=vou_no,
                    narration="Office rent - April 2026",
                    amount=D("75000"),
                    voucher_type="PMNT",
                    status="posted",
                    retail=retail,
                    fiscal_year=fy,
                )
                VoucherDetail.objects.create(
                    voucher_main=vou, account=bank_ldgr,
                    debit=D("0"), credit=D("75000"),
                    voucher_type="PMNT", voucher_no=vou_no,
                )
                self._ok("Payment Voucher: Office Rent Rs.75,000")

        # Contra voucher: cash deposit to bank
        cash_ldgr = retail.cash_ldgr
        if cash_ldgr and bank_ldgr:
            vou_no = self._next_voucher_no(retail, fy, "CONTRA")
            if not VoucherMain.objects.filter(voucher_no=vou_no).exists():
                vou = VoucherMain.objects.create(
                    date=date.today() - timedelta(days=10),
                    voucher_no=vou_no,
                    narration="Cash deposit to bank",
                    amount=D("200000"),
                    voucher_type="CONTRA",
                    status="posted",
                    retail=retail,
                    fiscal_year=fy,
                )
                VoucherDetail.objects.create(
                    voucher_main=vou, account=bank_ldgr,
                    debit=D("200000"), credit=D("0"),
                    voucher_type="CONTRA", voucher_no=vou_no,
                )
                VoucherDetail.objects.create(
                    voucher_main=vou, account=cash_ldgr,
                    debit=D("0"), credit=D("200000"),
                    voucher_type="CONTRA", voucher_no=vou_no,
                )
                self._ok("Contra Voucher: Cash Deposit Rs.2,00,000")

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 9 - HR
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_hr(self, retail, fy):
        from hr.models import Employee, SalaryStructure, PayrollDeductionConfig, SalarySlip
        from mastersconfig.models import State

        mh_state = State.objects.filter(code="27").first()

        for emp_data in EMPLOYEES:
            from django.contrib.auth import get_user_model
            UserModel = get_user_model()
            user, _ = UserModel.objects.get_or_create(
                username=emp_data["username"],
                defaults={"first_name": emp_data["full_name"].split()[0],
                          "last_name": " ".join(emp_data["full_name"].split()[1:]),
                          "is_active": True},
            )

            emp, created = Employee.objects.get_or_create(
                employee_code=emp_data["employee_code"],
                defaults={
                    "user":             user,
                    "full_name":        emp_data["full_name"],
                    "designation":      emp_data["designation"],
                    "department":       emp_data["department"],
                    "date_of_joining":  emp_data["date_of_joining"],
                    "date_of_birth":    emp_data["date_of_birth"],
                    "gender":           emp_data["gender"],
                    "is_active":        True,
                    "retail":           retail,
                    "state":            mh_state,
                },
            )
            if created:
                self._ok(f"Employee: {emp.employee_code} - {emp.full_name}")
            else:
                self._skip(f"Employee: {emp.employee_code} - {emp.full_name}")

            # Salary structure
            ss, ss_created = SalaryStructure.objects.get_or_create(
                employee=emp,
                effective_from=emp_data["date_of_joining"],
                defaults={
                    "is_active":             True,
                    "basic":                 emp_data["basic"],
                    "hra":                   emp_data["hra"],
                    "da":                    emp_data["da"],
                    "conveyance_allowance":  emp_data["conveyance_allowance"],
                    "medical_allowance":     emp_data["medical_allowance"],
                    "special_allowance":     emp_data["special_allowance"],
                },
            )
            if ss_created:
                self._ok(f"  Salary Structure: gross Rs.{ss.gross_ctc:,.0f}/month")

            # Deduction config
            PayrollDeductionConfig.objects.get_or_create(
                employee=emp,
                defaults={
                    "pf_applicable":    True,
                    "esi_applicable":   False,
                    "pt_applicable":    True,
                    "tds_monthly":      D("0"),
                    "advance_recovery": D("0"),
                },
            )

            # One salary slip (April 2026)
            SalarySlip.objects.get_or_create(
                employee=emp,
                month=4,
                year=2026,
                defaults={
                    "retail":           retail,
                    "fiscal_year":      fy,
                    "working_days":     26,
                    "days_worked":      26,
                    "basic_earned":     emp_data["basic"],
                    "hra_earned":       emp_data["hra"],
                    "da_earned":        emp_data["da"],
                    "conveyance_earned":emp_data["conveyance_allowance"],
                    "medical_earned":   emp_data["medical_allowance"],
                    "special_allowance_earned": emp_data["special_allowance"],
                    "gross_salary":     ss.gross_ctc,
                    "pf_employee":      min(emp_data["basic"] * D("0.12"), D("1800")).quantize(D("0.01")),
                    "pf_employer":      min(emp_data["basic"] * D("0.12"), D("1800")).quantize(D("0.01")),
                    "esi_employee":     D("0"),
                    "esi_employer":     D("0"),
                    "professional_tax": D("200"),
                    "tds_deducted":     D("0"),
                    "advance_recovery": D("0"),
                    "total_deductions": min(emp_data["basic"] * D("0.12"), D("1800")).quantize(D("0.01")) + D("200"),
                    "net_salary":       (ss.gross_ctc - min(emp_data["basic"] * D("0.12"), D("1800")).quantize(D("0.01")) - D("200")).quantize(D("0.01")),
                    "status":           "APPROVED",
                },
            )
            self._ok(f"  Salary Slip: {emp.full_name} - April 2026")
