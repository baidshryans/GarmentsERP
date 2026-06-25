from decimal import Decimal, ROUND_HALF_UP


# Statutory defaults — used when a retail has no HRSettings row yet.
# These mirror the EPFO/ESIC figures and Karnataka PT slab that were previously
# hardcoded, so behaviour is unchanged for existing data.
_DEFAULTS = {
    'pf_employee_rate':  Decimal('0.12'),
    'pf_ceiling':        Decimal('15000'),
    'esi_employee_rate': Decimal('0.0075'),
    'esi_employer_rate': Decimal('0.0325'),
    'esi_ceiling':       Decimal('21000'),
    'pt_threshold':      Decimal('15000'),
    'pt_amount':         Decimal('200'),
    'working_days_basis': 26,
}


def _payroll_settings(employee):
    """
    Return the HRSettings row for the employee's retail, or None.
    Reads are tolerant: a missing row falls back to _DEFAULTS via _cfg().
    """
    from hr.models import HRSettings
    retail = getattr(employee, 'retail', None)
    if retail is None:
        return None
    return HRSettings.objects.filter(retail=retail).first()


def _cfg(settings, key):
    """Read a payroll rate/ceiling from HRSettings, falling back to defaults."""
    if settings is not None:
        val = getattr(settings, key, None)
        if val is not None:
            return val
    return _DEFAULTS[key]


def _pt_from_gross(gross, threshold, amount):
    """Two-slab Professional Tax: nil at/below threshold, flat amount above."""
    return Decimal('0') if gross <= threshold else amount


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

    hr_settings = _payroll_settings(employee)

    pay_basis = Decimal(str(_cfg(hr_settings, 'working_days_basis')))
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
        pf_ceiling = _cfg(hr_settings, 'pf_ceiling')
        pf_rate = _cfg(hr_settings, 'pf_employee_rate')
        pf_base_full = basic_earned + da_earned  # EPFO: PF is on Basic + DA
        pf_base = pf_base_full if (config and config.pf_above_ceiling) else min(pf_base_full, pf_ceiling)
        pf_employee = (pf_base * pf_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        pf_employer = pf_employee

    # ESI — only if gross ≤ ceiling. Rates/ceiling configurable per retail.
    # Default to applicable when no deduction config exists
    esi_employee = Decimal('0')
    esi_employer = Decimal('0')
    esi_applicable = config.esi_applicable if config else True
    if esi_applicable and gross_salary <= _cfg(hr_settings, 'esi_ceiling'):
        esi_employee = (gross_salary * _cfg(hr_settings, 'esi_employee_rate')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        esi_employer = (gross_salary * _cfg(hr_settings, 'esi_employer_rate')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Professional Tax
    professional_tax = Decimal('0')
    if config is None or config.pt_applicable:
        professional_tax = _pt_from_gross(
            gross_salary, _cfg(hr_settings, 'pt_threshold'), _cfg(hr_settings, 'pt_amount')
        )

    # TDS + Advance
    tds_deducted     = Decimal(str(config.tds_monthly))     if config else Decimal('0')
    advance_recovery = Decimal(str(config.advance_recovery)) if config else Decimal('0')

    total_deductions = (pf_employee + esi_employee + professional_tax +
                        tds_deducted + advance_recovery)
    net_salary = gross_salary - total_deductions

    return {
        'working_days': int(pay_basis),
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
