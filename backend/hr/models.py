from decimal import Decimal
from django.contrib.auth.models import User
from django.db import models
from django.core.validators import MinValueValidator


class Employee(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('O', 'Other')]

    user = models.OneToOneField(
        User, on_delete=models.PROTECT, related_name='employee_profile'
    )
    retail = models.ForeignKey(
        'mastersconfig.RetailMaster', on_delete=models.PROTECT,
        related_name='employees'
    )
    salesperson = models.OneToOneField(
        'mastersconfig.SalesPersonMaster', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='employee'
    )

    employee_code   = models.CharField(max_length=20, unique=True)
    full_name       = models.CharField(max_length=150)
    designation     = models.CharField(max_length=100, blank=True)
    department      = models.CharField(max_length=100, blank=True)
    date_of_joining = models.DateField()
    date_of_birth   = models.DateField(null=True, blank=True)
    gender          = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)

    # Address
    address_line1 = models.CharField(max_length=150, blank=True)
    address_line2 = models.CharField(max_length=150, blank=True)
    city          = models.CharField(max_length=100, blank=True)
    state         = models.ForeignKey(
        'mastersconfig.State', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employees'
    )
    pincode = models.CharField(max_length=10, blank=True)

    # Bank Details
    bank_name  = models.CharField(max_length=100, blank=True)
    account_no = models.CharField(max_length=30, blank=True)
    ifsc_code  = models.CharField(max_length=15, blank=True)

    # Compliance
    pan_number = models.CharField(max_length=10, blank=True)
    pf_number  = models.CharField(max_length=25, blank=True)
    esi_number = models.CharField(max_length=20, blank=True)

    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hr_employee'
        ordering = ['employee_code']

    def __str__(self):
        return f"{self.employee_code} — {self.full_name}"


class SalaryStructure(models.Model):
    employee       = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='salary_structures'
    )
    effective_from = models.DateField()
    is_active      = models.BooleanField(default=True)

    # Earnings (monthly)
    basic                = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    hra                  = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    da                   = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    conveyance_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    medical_allowance    = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    special_allowance    = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])

    class Meta:
        db_table = 'hr_salary_structure'
        ordering = ['-effective_from']

    def __str__(self):
        return f"{self.employee.employee_code} — structure from {self.effective_from}"

    @property
    def gross_ctc(self):
        return (self.basic + self.hra + self.da +
                self.conveyance_allowance + self.medical_allowance +
                self.special_allowance)


class PayrollDeductionConfig(models.Model):
    employee         = models.OneToOneField(
        Employee, on_delete=models.CASCADE, related_name='deduction_config'
    )
    pf_applicable    = models.BooleanField(default=True)
    pf_above_ceiling = models.BooleanField(
        default=False,
        help_text="If True, PF is on full basic. If False, PF is capped at 12% of ₹15,000."
    )
    esi_applicable   = models.BooleanField(default=False)
    pt_applicable    = models.BooleanField(default=True)
    tds_monthly      = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    advance_recovery = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])

    class Meta:
        db_table = 'hr_payroll_deduction_config'

    def __str__(self):
        return f"Deduction config for {self.employee.employee_code}"


class SalarySlip(models.Model):
    STATUS_CHOICES = [
        ('DRAFT',    'Draft'),
        ('APPROVED', 'Approved'),
        ('PAID',     'Paid'),
    ]

    employee    = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='salary_slips')
    retail      = models.ForeignKey('mastersconfig.RetailMaster', on_delete=models.PROTECT, related_name='salary_slips')
    fiscal_year = models.ForeignKey('mastersconfig.FiscalYearMaster', on_delete=models.SET_NULL, null=True, blank=True)
    month       = models.PositiveSmallIntegerField()
    year        = models.PositiveSmallIntegerField()

    working_days = models.PositiveSmallIntegerField(default=26)
    days_worked  = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal('26'))

    # Earnings
    basic_earned             = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hra_earned               = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    da_earned                = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    conveyance_earned        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medical_earned           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    special_allowance_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gross_salary             = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Deductions
    pf_employee      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pf_employer      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    esi_employee     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    esi_employer     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    professional_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tds_deducted     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance_recovery = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary       = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    voucher    = models.ForeignKey(
        'accounting.VoucherMain', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='salary_slips'
    )
    status     = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hr_salary_slip'
        unique_together = ('employee', 'month', 'year')
        ordering = ['-year', '-month']

    def __str__(self):
        import calendar
        return f"{self.employee.full_name} — {calendar.month_name[self.month]} {self.year}"


class LeaveBalance(models.Model):
    employee             = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_balances')
    year                 = models.PositiveSmallIntegerField()
    earned_leave_balance = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    casual_leave_balance = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    sick_leave_balance   = models.DecimalField(max_digits=5, decimal_places=1, default=0)

    class Meta:
        db_table = 'hr_leave_balance'
        unique_together = ('employee', 'year')

    def __str__(self):
        return f"{self.employee.employee_code} leave balance {self.year}"


class HRSettings(models.Model):
    """Per-retail singleton — stores ledger FKs for salary accounting vouchers."""
    retail                = models.OneToOneField(
        'mastersconfig.RetailMaster', on_delete=models.CASCADE, related_name='hr_settings'
    )
    salary_expense_ldgr   = models.ForeignKey('contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL, related_name='hr_salary_expense')
    employee_payable_ldgr = models.ForeignKey('contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL, related_name='hr_employee_payable')
    pf_payable_ldgr       = models.ForeignKey('contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL, related_name='hr_pf_payable')
    esi_payable_ldgr      = models.ForeignKey('contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL, related_name='hr_esi_payable')
    pt_payable_ldgr       = models.ForeignKey('contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL, related_name='hr_pt_payable')
    tds_payable_ldgr      = models.ForeignKey('contacts.Ledger', null=True, blank=True, on_delete=models.SET_NULL, related_name='hr_tds_payable')

    # ── Statutory payroll rates / ceilings (configurable per retail) ──────────
    # Defaults match the EPFO/ESIC figures and Karnataka PT slab in force at the
    # time of writing; update here when the government revises rates rather than
    # editing the payroll calculation code.
    pf_employee_rate  = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.12'),
                                            help_text='Employee PF contribution rate (e.g. 0.12 = 12%)')
    pf_ceiling        = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('15000'),
                                            help_text='EPFO wage ceiling for PF base (Basic + DA)')
    esi_employee_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0075'),
                                            help_text='Employee ESI contribution rate (e.g. 0.0075 = 0.75%)')
    esi_employer_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0325'),
                                            help_text='Employer ESI contribution rate (e.g. 0.0325 = 3.25%)')
    esi_ceiling       = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('21000'),
                                            help_text='Gross salary ceiling above which ESI does not apply')
    pt_threshold      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('15000'),
                                            help_text='Monthly gross at or below which Professional Tax is nil')
    pt_amount         = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('200'),
                                            help_text='Professional Tax charged when gross exceeds the threshold')
    working_days_basis = models.PositiveSmallIntegerField(default=26,
                                            help_text='Days-per-month basis used to prorate salary (e.g. 26, 30)')

    class Meta:
        db_table = 'hr_settings'

    def __str__(self):
        return f"HR Settings — {self.retail}"
