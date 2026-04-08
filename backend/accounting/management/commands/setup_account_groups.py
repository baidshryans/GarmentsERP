from django.core.management.base import BaseCommand
from accounting.models import Account


# Standard Indian Chart of Accounts (Tally-compatible)
# Structure: (code, name, parent_code_or_None)
# Level 1 = Primary groups (root), Level 2 = Groups, Level 3 = Sub-groups

ACCOUNT_TREE = [
    # ──────────────────────────── ASSETS ────────────────────────────
    ("AS", "Assets", None),

    # Current Assets
    ("CA", "Current Assets", "AS"),
    ("CA-CSH", "Cash-in-Hand", "CA"),
    ("CA-BNK", "Bank Accounts", "CA"),
    ("CA-BNK-OD", "Bank OD Accounts", "CA-BNK"),
    ("CA-STK", "Stock-in-Hand", "CA"),
    ("CA-SD", "Sundry Debtors", "CA"),
    ("CA-GST", "GST Receivable (Input)", "CA"),
    ("CA-DEP", "Deposits (Asset)", "CA"),
    ("CA-LA", "Loans & Advances (Asset)", "CA"),

    # Fixed Assets
    ("FA", "Fixed Assets", "AS"),
    ("FA-LB", "Land & Building", "FA"),
    ("FA-PM", "Plant & Machinery", "FA"),
    ("FA-FF", "Furniture & Fixtures", "FA"),
    ("FA-CE", "Office Equipment", "FA"),
    ("FA-VH", "Vehicles", "FA"),

    # Investments
    ("INV", "Investments", "AS"),

    # ──────────────────────────── LIABILITIES ────────────────────────────
    ("LIA", "Liabilities", None),

    # Current Liabilities
    ("CL", "Current Liabilities", "LIA"),
    ("CL-SC", "Sundry Creditors", "CL"),
    ("CL-DT", "Duties & Taxes", "CL"),
    ("CL-DT-GST", "GST Payable", "CL-DT"),
    ("CL-DT-TDS", "TDS Payable", "CL-DT"),
    ("CL-DT-TCS", "TCS Payable", "CL-DT"),
    ("CL-PRV", "Provisions", "CL"),

    # Loans (Liability)
    ("LL", "Loans (Liability)", "LIA"),
    ("LL-SEC", "Secured Loans", "LL"),
    ("LL-USEC", "Unsecured Loans", "LL"),

    # ──────────────────────────── CAPITAL ────────────────────────────
    ("CAP", "Capital Account", None),
    ("CAP-OWN", "Owner's Capital", "CAP"),
    ("CAP-RES", "Reserves & Surplus", "CAP"),

    # ──────────────────────────── INCOME ────────────────────────────
    ("INC", "Income", None),

    # Direct Income
    ("INC-DIR", "Direct Income", "INC"),
    ("INC-DIR-SAL", "Sales Account", "INC-DIR"),

    # Indirect Income
    ("INC-IND", "Indirect Income", "INC"),

    # ──────────────────────────── EXPENSES ────────────────────────────
    ("EXP", "Expenses", None),

    # Direct Expenses
    ("EXP-DIR", "Direct Expenses", "EXP"),
    ("EXP-DIR-PUR", "Purchase Account", "EXP-DIR"),
    ("EXP-DIR-MFG", "Manufacturing Expenses", "EXP-DIR"),
    ("EXP-DIR-MKG", "Making Charges", "EXP-DIR"),
    ("EXP-DIR-STN", "Stone Expenses", "EXP-DIR"),
    ("EXP-DIR-FRT", "Freight & Carriage", "EXP-DIR"),

    # Indirect Expenses
    ("EXP-IND", "Indirect Expenses", "EXP"),
    ("EXP-IND-SAL", "Salaries & Wages", "EXP-IND"),
    ("EXP-IND-RNT", "Rent", "EXP-IND"),
    ("EXP-IND-ELC", "Electricity & Power", "EXP-IND"),
    ("EXP-IND-TEL", "Telephone & Internet", "EXP-IND"),
    ("EXP-IND-PRN", "Printing & Stationery", "EXP-IND"),
    ("EXP-IND-ADV", "Advertisement & Publicity", "EXP-IND"),
    ("EXP-IND-TRV", "Travel & Conveyance", "EXP-IND"),
    ("EXP-IND-INS", "Insurance", "EXP-IND"),
    ("EXP-IND-REP", "Repairs & Maintenance", "EXP-IND"),
    ("EXP-IND-AUD", "Audit Fees", "EXP-IND"),
    ("EXP-IND-LEG", "Legal & Professional Fees", "EXP-IND"),
    ("EXP-IND-BNK", "Bank Charges", "EXP-IND"),
    ("EXP-IND-DEP", "Depreciation", "EXP-IND"),
    ("EXP-IND-MSC", "Miscellaneous Expenses", "EXP-IND"),
    ("EXP-IND-ROF", "Rounding Off", "EXP-IND"),
]


class Command(BaseCommand):
    help = "Seed the standard Indian chart of account groups (idempotent)"

    def handle(self, *args, **options):
        created_count = 0
        existing_count = 0
        cache = {}  # code -> Account instance

        # Pre-load all existing accounts by code
        for acc in Account.objects.all():
            cache[acc.code] = acc

        for code, name, parent_code in ACCOUNT_TREE:
            parent = cache.get(parent_code) if parent_code else None

            if code in cache:
                acc = cache[code]
                # Update name/parent if they drifted
                changed = False
                if acc.name != name:
                    acc.name = name
                    changed = True
                if acc.parent != parent:
                    acc.parent = parent
                    changed = True
                if changed:
                    acc.save(update_fields=["name", "parent"])
                    self.stdout.write(self.style.WARNING(f"Updated: {code} - {name}"))
                existing_count += 1
            else:
                acc = Account.objects.create(code=code, name=name, parent=parent)
                cache[code] = acc
                self.stdout.write(self.style.SUCCESS(f"Created: {code} - {name}"))
                created_count += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. Created {created_count}, already existed {existing_count}. "
            f"Total account groups: {Account.objects.count()}"
        ))
