from decimal import Decimal, ROUND_HALF_UP


# Karnataka Professional Tax slabs (monthly gross)
PT_SLABS_KA = [
    (Decimal('15000'), Decimal('0')),
    (Decimal('9999999'), Decimal('200')),
]


def _pt_from_gross(gross):
    for threshold, amount in PT_SLABS_KA:
        if gross <= threshold:
            return amount
    return Decimal('200')


def generate_salary_slip(employee, month, year, days_worked=None):
    """
    Pure calculation — returns a dict of all slip fields. No DB writes.
    Raises ValueError if no active SalaryStructure exists.
    """
    from hr.models import SalaryStructure, PayrollDeductionConfig

    structure = (
        SalaryStructure.objects
        .filter(employee=employee, is_active=True)
        .order_by('-effective_from')
        .first()
    )
    if not structure:
        raise ValueError(
            f"No active salary structure found for {employee.employee_code}. "
            "Please create one before generating a payslip."
        )

    try:
        config = employee.deduction_config
    except PayrollDeductionConfig.DoesNotExist:
        config = None

    pay_basis = Decimal('26')
    dw = Decimal(str(days_worked)) if days_worked is not None else pay_basis

    def prorate(amount):
        return (Decimal(str(amount)) * dw / pay_basis).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    basic_earned  = prorate(structure.basic)
    hra_earned    = prorate(structure.hra)
    da_earned     = prorate(structure.da)
    conv_earned   = prorate(structure.conveyance_allowance)
    med_earned    = prorate(structure.medical_allowance)
    special_earned = prorate(structure.special_allowance)
    gross_salary  = basic_earned + hra_earned + da_earned + conv_earned + med_earned + special_earned

    # PF — base is Basic + DA per EPFO rules
    pf_employee = Decimal('0')
    pf_employer = Decimal('0')
    if config is None or config.pf_applicable:
        pf_ceiling = Decimal('15000')
        pf_base_full = basic_earned + da_earned  # EPFO: PF is on Basic + DA
        pf_base = pf_base_full if (config and config.pf_above_ceiling) else min(pf_base_full, pf_ceiling)
        pf_employee = (pf_base * Decimal('0.12')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        pf_employer = pf_employee

    # ESI (employee 0.75%, employer 3.25%) — only if gross ≤ 21000
    # Default to applicable when no deduction config exists
    esi_employee = Decimal('0')
    esi_employer = Decimal('0')
    esi_applicable = config.esi_applicable if config else True
    if esi_applicable and gross_salary <= Decimal('21000'):
        esi_employee = (gross_salary * Decimal('0.0075')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        esi_employer = (gross_salary * Decimal('0.0325')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Professional Tax
    professional_tax = Decimal('0')
    if config is None or config.pt_applicable:
        professional_tax = _pt_from_gross(gross_salary)

    # TDS + Advance
    tds_deducted     = Decimal(str(config.tds_monthly))     if config else Decimal('0')
    advance_recovery = Decimal(str(config.advance_recovery)) if config else Decimal('0')

    total_deductions = (pf_employee + esi_employee + professional_tax +
                        tds_deducted + advance_recovery)
    net_salary = gross_salary - total_deductions

    return {
        'working_days': 26,
        'days_worked': dw,
        'basic_earned': basic_earned,
        'hra_earned': hra_earned,
        'da_earned': da_earned,
        'conveyance_earned': conv_earned,
        'medical_earned': med_earned,
        'special_allowance_earned': special_earned,
        'gross_salary': gross_salary,
        'pf_employee': pf_employee,
        'pf_employer': pf_employer,
        'esi_employee': esi_employee,
        'esi_employer': esi_employer,
        'professional_tax': professional_tax,
        'tds_deducted': tds_deducted,
        'advance_recovery': advance_recovery,
        'total_deductions': total_deductions,
        'net_salary': net_salary,
    }
