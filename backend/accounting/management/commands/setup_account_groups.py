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
    ("CA-CHQ", "Cheques in Hand", "CA"),
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
    ("FA-AD", "Accumulated Depreciation", "FA"),  # Contra-asset: reduces total FA

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
    ("CL-HR", "HR & Payroll Liabilities", "CL"),
    ("CL-HR-SAL", "Salary Payable", "CL-HR"),
    ("CL-HR-PF",  "PF Payable", "CL-HR"),
    ("CL-HR-ESI", "ESI Payable", "CL-HR"),
    ("CL-HR-PT",  "Professional Tax Payable", "CL-HR"),

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
    ("EXP-IND-ADM", "Administrative Expenses", "EXP-IND"),
    ("EXP-IND-SND", "Selling & Distribution Expenses", "EXP-IND"),
    ("EXP-IND-MKT", "Marketing & Advertisement Expenses", "EXP-IND"),
    ("EXP-IND-SHW", "Showroom / Retail Expenses", "EXP-IND"),
    ("EXP-IND-HR",  "Employee & HR Expenses", "EXP-IND"),
    ("EXP-IND-RPM", "Repairs & Maintenance", "EXP-IND"),
    ("EXP-IND-TRV", "Travel & Conveyance", "EXP-IND"),
    ("EXP-IND-FIN", "Bank Charges and Commission", "EXP-IND"),
    ("EXP-IND-CMP", "Compliance & Regulatory Expenses", "EXP-IND"),
    ("EXP-IND-INS", "Insurance Expenses", "EXP-IND"),
    ("EXP-IND-IT",  "IT & Technology Expenses", "EXP-IND"),
    ("EXP-IND-MSC", "Miscellaneous Expenses", "EXP-IND"),
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

        # ── Remove account groups no longer in ACCOUNT_TREE ──────────────────
        # Move any ledgers that were under a removed group up to its parent,
        # then delete the obsolete group.
        valid_codes = {code for code, _, _ in ACCOUNT_TREE}
        removed_count = 0
        for acc in list(Account.objects.exclude(code__in=valid_codes)):
            from contacts.models import Ledger
            # Re-point ledgers to the closest ancestor still in the tree
            ancestor = acc.parent
            while ancestor is not None and ancestor.code not in valid_codes:
                ancestor = ancestor.parent
            moved = Ledger.objects.filter(ac_group=acc).update(ac_group=ancestor)
            # Re-point child account groups to the same ancestor
            Account.objects.filter(parent=acc).update(parent=ancestor)
            if moved:
                self.stdout.write(self.style.WARNING(
                    f"  Moved {moved} ledger(s) from '{acc.code}' to '{ancestor.code if ancestor else 'None'}'"
                ))
            acc.delete()
            self.stdout.write(self.style.WARNING(f"Removed obsolete group: {acc.code} - {acc.name}"))
            removed_count += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. Created {created_count}, already existed {existing_count}, "
            f"removed {removed_count}. "
            f"Total account groups: {Account.objects.count()}"
        ))
