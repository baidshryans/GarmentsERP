from accounting.models import Account
from django.core.management.base import BaseCommand
# Function to create an account group
def create_account(name, code, parent=None):
    account, created = Account.objects.get_or_create(name=name, code=code, parent=parent)
    return account
# Super Parent Groups

class Command(BaseCommand):
    help = 'Import Colors data from CSV file'

   

    def handle(self, *args, **kwargs):
        income = create_account("Income", "1000")
        expenditure = create_account("Expenditure", "2000")
        assets = create_account("Assets", "3000")
        liabilities = create_account("Liabilities", "4000")
        # Income Subgroups
        direct_income = create_account("Direct Income", "1100", parent=income)
        sales_account = create_account("Sales Account", "1110", parent=direct_income)
        indirect_income = create_account("Indirect Income", "1200", parent=income)
        making_charge_received = create_account("Making Charge Received", "1120", parent=direct_income)
        # Expenditure Subgroups
        direct_expenses = create_account("Direct Expenses", "2100", parent=expenditure)
        indirect_expenses = create_account("Indirect Expenses", "2200", parent=expenditure)
        # Expenditure Sub-subgroups
        purchase_account = create_account("Purchase Account", "2110", parent=direct_expenses)
        making_charge_paid = create_account("Making Charge Paid", "2120", parent=direct_expenses)
        staff_salary = create_account("Staff Salary", "2210", parent=indirect_expenses)
        bank_charges_commission = create_account("Bank Charges & Commission", "2220", parent=indirect_expenses)
        # Assets Subgroups
        current_assets = create_account("Current Assets", "3100", parent=assets)
        fixed_assets = create_account("Fixed Assets", "3200", parent=assets)
        investments = create_account("Investments", "3300", parent=assets)
        misc_expenses_asset = create_account("Misc Expenses (Asset)", "3400", parent=assets)
        opening_stock = create_account("Opening Stock", "3500", parent=assets)
        closing_stock = create_account("Closing Stock", "3600", parent=assets)
        staff_advances = create_account("Staff Advances", "3700", parent=assets)
        # Current Assets Subgroups
        bank_accounts = create_account("Bank Accounts", "3110", parent=current_assets)
        cash_in_hand = create_account("Cash in Hand", "3120", parent=current_assets)
        deposits = create_account("Deposits (Asset)", "3130", parent=current_assets)
        loans_advances_asset = create_account("Loans & Advances (Asset)", "3140", parent=current_assets)
        stock_in_hand = create_account("Stock in Hand", "3150", parent=current_assets)
        sundry_debtors = create_account("Sundry Debtors", "3160", parent=current_assets)
        credit_card = create_account("Credit Card", "3170", parent=current_assets)
        prepaid_expenses = create_account("Prepaid Expenses", "3180", parent=current_assets)
        # Fixed Assets Subgroups
        furniture_fixture = create_account("Furniture & Fixture", "3210", parent=fixed_assets)
        plant_machinery = create_account("Plant & Machinery", "3220", parent=fixed_assets)
        computer = create_account("Computer", "3230", parent=fixed_assets)
        capital_work_in_progress = create_account("Capital Work In Progress", "3250", parent=fixed_assets)
        building = create_account("Building", "3240", parent=fixed_assets)
        # Liabilities Subgroups
        current_liabilities = create_account("Current Liabilities", "4100", parent=liabilities)
        loans_liability = create_account("Loans (Liability)", "4200", parent=liabilities)
        suspense_account = create_account("Suspense Account", "4300", parent=liabilities)
        capital = create_account("Capital", "4400", parent=liabilities)
        expense_payable = create_account("Expense Payable", "4500", parent=liabilities)
        # Current Liabilities Subgroups
        duties_taxes = create_account("Duties & Taxes", "4110", parent=current_liabilities)
        provisions = create_account("Provisions", "4120", parent=current_liabilities)
        sundry_creditors = create_account("Sundry Creditors", "4130", parent=current_liabilities)
        liabilities_for_statutory_dues = create_account("Liabilities For Statutory Dues", "4140", parent=current_liabilities)
        color_stone = create_account("Color Stone", "4150", parent=current_liabilities)
        sundry_dealer = create_account("Sundry Dealer", "4160", parent=current_liabilities)
        sundry_karigar = create_account("Sundry Karigar", "4170", parent=current_liabilities)
        creditor_for_expenses = create_account("Creditor For Expenses", "4180", parent=current_liabilities)
        creditor_for_others = create_account("Creditors For Others", "4190", parent=current_liabilities)
        # Loans (Liability) Subgroups
        bank_od = create_account("Bank OD", "4210", parent=loans_liability)
        secured_loans = create_account("Secured Loans", "4220", parent=loans_liability)
        unsecured_loans = create_account("Unsecured Loans", "4230", parent=loans_liability)
        # Capital Subgroups
        reserves_surplus = create_account("Reserves & Surplus", "4410", parent=capital)
        print("Account structure with 4-digit codes successfully created!")


