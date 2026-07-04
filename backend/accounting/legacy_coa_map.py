"""Single source of truth mapping the legacy migrated chart of accounts
(codes MG-*/GM-*/SG-* imported by importaccs) onto the canonical standard
chart of accounts seeded by setup_account_groups.

Keyed by legacy Account.code. Values are standard Account.code strings.
Non-obvious rows are commented. See
docs/superpowers/specs/2026-07-04-chart-of-accounts-consolidation-design.md
"""

LEGACY_TO_STANDARD = {
    # Roots
    "MG-1": "LIA",   # Liabilities
    "MG-2": "AS",    # Assets
    "MG-3": "INC",   # Income
    "MG-4": "EXP",   # Expenditure -> Expenses
    # Group masters (GM-*)
    "GM-1": "CAP",           # Capital
    "GM-3": "LL",            # Loans (Liability)
    "GM-4": "CA",            # Current Assets
    "GM-7": "EXP-DIR",       # Direct Expenses
    "GM-8": "INC-DIR",       # Direct Income
    "GM-9": "FA",            # Fixed Assets
    "GM-10": "INV",          # Investments
    "GM-12": "EXP-DIR-PUR",  # Purchase Account
    "GM-13": "INC-DIR-SAL",  # Sales Account
    "GM-14": "CL",           # Suspense Account -> Current Liabilities (no std suspense)
    "GM-15": "CL",           # Current Liabilities
    "GM-16": "INC-IND",      # Indirect Income
    "GM-17": "EXP-IND",      # Indirect Expenses
    "GM-18": "CA-STK",       # Opening Stock -> Stock-in-Hand
    "GM-19": "EXP-DIR-MKG",  # Making Charge Paid -> Making Charges
    "GM-20": "INC-DIR",      # Making Charge Received -> Direct Income
    "GM-21": "CA-STK",       # Closing Stock -> Stock-in-Hand
    "GM-23": "CA-LA",        # Staff Advances -> Loans & Advances (Asset)
    # Sub-groups (SG-*)
    "SG-2": "CA-BNK",        # Bank Accounts
    "SG-3": "CA-BNK-OD",     # Bank OD
    "SG-4": "CA-CSH",        # Cash in Hand
    "SG-5": "CA-DEP",        # Deposits (Asset)
    "SG-7": "CA-LA",         # Loans & Advances (Asset)
    "SG-9": "LL-SEC",        # Secured Loans
    "SG-10": "CA-STK",       # Stock in Hand
    "SG-12": "CA-SD",        # Sundry Debtors
    "SG-13": "LL-USEC",      # Unsecured Loans
    "SG-14": "CL-SC",        # Sundry Creditors
    "SG-15": "CL-PRV",       # Provisions
    "SG-16": "CL-DT",        # Liabilities For Statutory Dues -> Duties & Taxes
    "SG-17": "CL-DT",        # Duties & Taxes
    "SG-18": "CAP-RES",      # Reserves & Surplus
    "SG-19": "CA-LA",        # Prepaid Expenses -> Loans & Advances (Asset)
    "SG-20": "FA-PM",        # Plant & Machinery
    "SG-21": "FA-FF",        # Furniture & Fixture
    "SG-23": "FA",           # Capital Work In Progress -> Fixed Assets
    "SG-24": "EXP-IND-FIN",  # Bank Charges & Commission
    "SG-25": "FA-LB",        # Building -> Land & Building
    "SG-32": "CL-HR-SAL",    # Staff Salary Payable
    "SG-33": "CL-DT",        # Tax Payable -> Duties & Taxes
    "SG-34": "CAP-OWN",      # Equity Share Capital -> Owner's Capital
    "SG-35": "CA",           # Current Tax Assets -> Current Assets
    "SG-36": "CL-SC",        # Creditor For Expenses -> Sundry Creditors
    "SG-37": "FA-CE",        # Office Equipment
    "SG-38": "EXP-IND-HR",   # Staff Salary -> Employee & HR Expenses
}


def is_legacy_code(code):
    """True if `code` is a legacy migrated group code (MG-/GM-/SG-)."""
    return bool(code) and code.split("-")[0] in ("MG", "GM", "SG")


def resolve_standard_group(legacy_code):
    """Return the standard Account for a legacy code, or None if unmapped.

    Looks up LEGACY_TO_STANDARD then fetches the standard Account by code.
    Returns None (never raises) so callers can decide how to handle gaps.
    """
    from accounting.models import Account
    std_code = LEGACY_TO_STANDARD.get(legacy_code)
    if not std_code:
        return None
    return Account.objects.filter(code=std_code).first()
