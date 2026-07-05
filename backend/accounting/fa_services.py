from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from .models import IT_BLOCK_RATES

ASSET_CODE_PREFIX = "FA"


def generate_next_asset_code(retail):
    """
    Race-safe, retail-scoped asset code, e.g. "FA-00001". Deliberately does
    NOT reuse accounting.utils.get_next_bill_number — that helper is
    fiscal-year-scoped (requires an active FY, resets the counter every FY),
    but FixedAsset has no fiscal_year field and must number continuously
    across years.
    """
    from mastersconfig.models import BillNumberSequence
    from .models import FixedAsset

    for _ in range(5):
        with transaction.atomic():
            seq, _created = BillNumberSequence.objects.select_for_update().get_or_create(
                retail=retail, prefix=ASSET_CODE_PREFIX, fiscal_year=None,
                defaults={'last_number': 0},
            )
            # Resync against the actual max in case rows were created
            # directly or the sequence otherwise drifted.
            existing_max = 0
            codes = FixedAsset.objects.filter(
                retail=retail, asset_code__startswith=f"{ASSET_CODE_PREFIX}-",
            ).values_list('asset_code', flat=True)
            for code in codes:
                tail = code.rsplit('-', 1)[-1]
                if tail.isdigit():
                    existing_max = max(existing_max, int(tail))
            if existing_max > seq.last_number:
                seq.last_number = existing_max

            seq.last_number += 1
            seq.save(update_fields=['last_number'])
            candidate = f"{ASSET_CODE_PREFIX}-{seq.last_number:05d}"

        if not FixedAsset.objects.filter(retail=retail, asset_code=candidate).exists():
            return candidate
    raise RuntimeError("Could not generate a unique asset code — please retry.")

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
    # Clip the period to the asset's holding window: depreciation only accrues
    # from the day of purchase onward. If the asset was acquired after the
    # period ends, suggest zero — it wasn't owned during this window.
    if asset.purchase_date > to_date:
        return {
            'opening_wdv':         asset.current_wdv,
            'calculated_amount':   Decimal('0'),
            'days_in_period':      0,
            'annual_depreciation': Decimal('0'),
            'method':              asset.depreciation_method,
            'reason':              f'Asset acquired {asset.purchase_date} — after period end',
        }

    effective_from = max(from_date, asset.purchase_date)
    # Don't re-charge depreciation for a stretch that's already been posted.
    if asset.last_depreciation_through and asset.last_depreciation_through >= effective_from:
        effective_from = asset.last_depreciation_through + timedelta(days=1)
    if effective_from > to_date:
        return {
            'opening_wdv':         asset.current_wdv,
            'calculated_amount':   Decimal('0'),
            'days_in_period':      0,
            'annual_depreciation': Decimal('0'),
            'method':              asset.depreciation_method,
            'reason':              f'Already depreciated through {asset.last_depreciation_through}',
        }

    days_in_period = (to_date - effective_from).days + 1
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
        # Asset fully covered by an earlier posting — omit from the worksheet.
        if asset.last_depreciation_through and asset.last_depreciation_through >= to_date:
            continue
        # Asset not yet acquired during the period — omit.
        if asset.purchase_date > to_date:
            continue
        result = calculate_asset_depreciation(asset, from_date, to_date)
        method_label = 'WDV' if asset.depreciation_method == 'WDV' else 'SLM'
        effective_from = max(from_date, asset.purchase_date)
        period_note = (
            f"{from_date} to {to_date}"
            if effective_from == from_date
            else f"{effective_from} to {to_date} (acquired {asset.purchase_date})"
        )
        narration = (
            f"Depreciation \u2013 {asset.asset_name} "
            f"({method_label}, {asset.rate_or_life}{'%' if asset.depreciation_method == 'WDV' else ' yrs'}) "
            f"for period {period_note}"
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
