from decimal import Decimal, ROUND_HALF_UP

from .models import IT_BLOCK_RATES

TWO_PLACES = Decimal('0.01')


def calculate_asset_depreciation(asset, from_date, to_date):
    """
    Pure function — calculates depreciation for one asset over a given period.
    Returns a dict; does NOT write to the database.

    SLM (Companies Act 2013, Schedule II):
        Annual = (Cost − Residual Value) / Useful Life (years)
        Prorated proportionally to days in period.

    WDV (Income Tax Act, Section 32):
        Annual = Current WDV × Rate%
        Prorated proportionally to days in period.
        IT Act half-year rule is NOT applied here because the user may generate
        suggestions for any custom date range; they can edit the amount manually
        if they need the half-year rule for the acquisition year.
    """
    days_in_period = (to_date - from_date).days + 1
    days_in_year   = Decimal('365')
    opening_wdv    = asset.current_wdv

    if opening_wdv <= asset.residual_value:
        return {
            'opening_wdv':         opening_wdv,
            'calculated_amount':   Decimal('0'),
            'days_in_period':      days_in_period,
            'annual_depreciation': Decimal('0'),
            'method':              asset.depreciation_method,
            'reason':              'Fully depreciated (WDV \u2264 residual value)',
        }

    if asset.rate_or_life <= 0:
        return {
            'opening_wdv':         opening_wdv,
            'calculated_amount':   Decimal('0'),
            'days_in_period':      days_in_period,
            'annual_depreciation': Decimal('0'),
            'method':              asset.depreciation_method,
            'reason':              'Rate / useful life not configured (0)',
        }

    if asset.depreciation_method == 'SLM':
        annual = (asset.purchase_cost - asset.residual_value) / asset.rate_or_life
    else:  # WDV
        annual = opening_wdv * asset.rate_or_life / Decimal('100')

    calculated = (
        annual * Decimal(str(days_in_period)) / days_in_year
    ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    max_dep    = max(opening_wdv - asset.residual_value, Decimal('0'))
    calculated = min(calculated, max_dep)

    return {
        'opening_wdv':         opening_wdv,
        'calculated_amount':   calculated,
        'days_in_period':      days_in_period,
        'annual_depreciation': annual.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        'method':              asset.depreciation_method,
    }


def generate_suggestion_lines(retail, from_date, to_date):
    """
    Compute depreciation for all ACTIVE assets in a retail.
    Returns a list of dicts (not saved); caller persists after confirmation.
    """
    from .models import FixedAsset

    assets = FixedAsset.objects.filter(retail=retail, status='ACTIVE').select_related('retail')
    lines  = []
    for asset in assets:
        result = calculate_asset_depreciation(asset, from_date, to_date)
        method_label = 'WDV' if asset.depreciation_method == 'WDV' else 'SLM'
        narration = (
            f"Depreciation \u2013 {asset.asset_name} "
            f"({method_label}, {asset.rate_or_life}{'%' if asset.depreciation_method == 'WDV' else ' yrs'}) "
            f"for period {from_date} to {to_date}"
        )[:200]

        lines.append({
            'asset':             asset,
            'opening_wdv':       result['opening_wdv'],
            'calculated_amount': result['calculated_amount'],
            'approved_amount':   result['calculated_amount'],
            'overridden':        False,
            'narration':         narration,
        })

    return lines
