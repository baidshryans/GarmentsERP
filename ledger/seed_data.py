"""Chart of accounts seeded by the setup wizard (SYS-02, SYS-03, PRD E1.2, E1.3).

This is only the starting point: seeding copies it into the database, where everything
is editable (SYS-05). Re-running the seeder adds anything missing and never overwrites.
"""

A, L, I, E = "asset", "liability", "income", "expense"
BS, PL = "bs", "pl"

# (name, parent name or None, nature, statement)
GROUPS = [
    ("Capital", None, L, BS),
    ("Reserves", None, L, BS),
    ("Secured Loans", None, L, BS),
    ("Unsecured Loans", None, L, BS),
    ("Current Liabilities", None, L, BS),
    ("Duties and Taxes", "Current Liabilities", L, BS),
    ("Sundry Creditors", "Current Liabilities", L, BS),
    ("Provisions", "Current Liabilities", L, BS),
    ("Fixed Assets", None, A, BS),
    ("Investments", None, A, BS),
    ("Current Assets", None, A, BS),
    ("Stock-in-hand", "Current Assets", A, BS),
    ("Sundry Debtors", "Current Assets", A, BS),
    ("Cash-in-hand", "Current Assets", A, BS),
    ("Bank Accounts", "Current Assets", A, BS),
    ("Loans and Advances", "Current Assets", A, BS),
    ("Sales", None, I, PL),
    ("Purchases", None, E, PL),
    ("Direct Incomes", None, I, PL),
    ("Indirect Incomes", None, I, PL),
    ("Direct Expenses", None, E, PL),
    ("Indirect Expenses", None, E, PL),
]

# (name, group, system_key, bill_wise)
LEDGERS = [
    # PRD E1.3 - cash, taxes
    ("Cash", "Cash-in-hand", "cash", False),
    ("CGST Input", "Duties and Taxes", "cgst_input", False),
    ("SGST Input", "Duties and Taxes", "sgst_input", False),
    ("IGST Input", "Duties and Taxes", "igst_input", False),
    ("CGST Output", "Duties and Taxes", "cgst_output", False),
    ("SGST Output", "Duties and Taxes", "sgst_output", False),
    ("IGST Output", "Duties and Taxes", "igst_output", False),
    ("TDS Payable", "Duties and Taxes", "tds_payable", False),
    ("TCS Payable", "Duties and Taxes", "tcs_payable", False),
    ("Round Off", "Indirect Expenses", "round_off", False),
    # PRD E1.3 - garment-unit expenses
    ("Job Work Charges", "Direct Expenses", "job_work_charges", False),
    ("Embroidery Charges", "Direct Expenses", "embroidery_charges", False),
    ("Printing Charges", "Direct Expenses", "printing_charges", False),
    ("Washing Charges", "Direct Expenses", "washing_charges", False),
    ("Wages", "Direct Expenses", "wages", False),
    ("Power and Fuel", "Direct Expenses", "power_fuel", False),
    ("Factory Rent", "Direct Expenses", "factory_rent", False),
    ("Freight Inward", "Direct Expenses", "freight_inward", False),
    ("Packing Material", "Direct Expenses", "packing_material", False),
    ("Salaries", "Indirect Expenses", "salaries", False),
    ("Freight Outward", "Indirect Expenses", "freight_outward", False),
    ("Repairs and Maintenance", "Indirect Expenses", "repairs", False),
    ("Staff Welfare", "Indirect Expenses", "staff_welfare", False),
    ("Office Expenses", "Indirect Expenses", "office_expenses", False),
    ("Telephone and Internet", "Indirect Expenses", "telephone", False),
    ("Bank Charges", "Indirect Expenses", "bank_charges", False),
    ("Interest", "Indirect Expenses", "interest", False),
    ("Depreciation", "Indirect Expenses", "depreciation", False),
    # Additions the posting, stock and year-end engines need (not in the PRD list)
    ("Raw Material Stock", "Stock-in-hand", "stock_raw_material", False),
    ("Work-in-Progress Stock", "Stock-in-hand", "stock_wip", False),
    ("Stock with Fabricators", "Stock-in-hand", "stock_with_fabricators", False),
    ("Finished Goods Stock", "Stock-in-hand", "stock_finished", False),
    ("Rejects and Remnants Stock", "Stock-in-hand", "stock_rejects", False),
    ("Sales - Ready Stock", "Sales", "sales_stock", False),
    ("Sales - Made to Order", "Sales", "sales_mto", False),
    ("Sales Returns", "Sales", "sales_returns", False),
    ("Purchases - Fabric", "Purchases", "purchases_fabric", False),
    ("Purchases - Trims", "Purchases", "purchases_trims", False),
    ("Purchases - Finished Goods", "Purchases", "purchases_finished", False),
    ("Purchases - Packing Material", "Purchases", "purchases_packing", False),
    ("Purchase Returns", "Purchases", "purchase_returns", False),
    ("Job Work Income", "Direct Incomes", "job_work_income", False),
    ("Scrap and Remnant Sales", "Direct Incomes", "scrap_sales", False),
    ("Discount Received", "Indirect Incomes", "discount_received", False),
    ("Discount Allowed", "Indirect Expenses", "discount_allowed", False),
    ("Goods Received Not Billed", "Current Liabilities", "grni", False),
    ("Rejected Goods Recoverable", "Loans and Advances", "rejected_recoverable", False),
    ("CGST RCM Payable", "Duties and Taxes", "cgst_rcm", False),
    ("SGST RCM Payable", "Duties and Taxes", "sgst_rcm", False),
    ("IGST RCM Payable", "Duties and Taxes", "igst_rcm", False),
    ("Inter-Factory Receivable", "Loans and Advances", "interfactory_receivable", False),
    ("Inter-Factory Payable", "Current Liabilities", "interfactory_payable", False),
    ("Labour Absorbed (WIP)", "Direct Expenses", "labour_absorbed", False),
    ("WIP Written Off", "Direct Expenses", "wip_written_off", False),
    ("Profit & Loss A/c", "Reserves", "profit_loss", False),
    ("Opening Balance Difference", "Capital", "opening_difference", False),
]
