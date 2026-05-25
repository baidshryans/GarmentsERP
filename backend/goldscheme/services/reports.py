"""
Scheme reports — summary, maturity calendar, overdue payments.
"""
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Sum, Count, Q, F, Min

from goldscheme.models import SchemeEnrollment, SchemePayment, SchemeMaster


def scheme_summary(retail):
    """
    Dashboard-level KPIs for the scheme module.
    """
    active = SchemeEnrollment.objects.filter(retail=retail, status='ACTIVE')
    matured = SchemeEnrollment.objects.filter(retail=retail, status='MATURED')
    redeemed = SchemeEnrollment.objects.filter(retail=retail, status='REDEEMED')

    total_collection = SchemePayment.objects.filter(
        retail=retail
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    active_collection = SchemePayment.objects.filter(
        retail=retail, enrollment__status='ACTIVE'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    today = date.today()
    maturing_30d = SchemeEnrollment.objects.filter(
        retail=retail, status='ACTIVE',
        maturity_date__range=(today, today + timedelta(days=30))
    ).count()

    return {
        'active_enrollments': active.count(),
        'matured_enrollments': matured.count(),
        'redeemed_enrollments': redeemed.count(),
        'total_collection': float(total_collection),
        'active_scheme_balance': float(active_collection),
        'maturing_in_30_days': maturing_30d,
        'schemes_available': SchemeMaster.objects.filter(retail=retail, is_active=True).count(),
    }


def maturity_calendar(retail, from_date, to_date):
    """
    List enrollments maturing within a date range.
    """
    enrollments = SchemeEnrollment.objects.filter(
        retail=retail,
        status__in=('ACTIVE', 'MATURED'),
        maturity_date__range=(from_date, to_date),
    ).select_related('customer', 'scheme').order_by('maturity_date')

    return [
        {
            'enrollment_no': e.enrollment_no,
            'customer': e.customer.ac_name,
            'scheme': e.scheme.name,
            'maturity_date': str(e.maturity_date),
            'total_paid': float(e.total_paid),
            'gold_weight': float(e.gold_accumulated_wt),
            'status': e.status,
        }
        for e in enrollments
    ]


def overdue_payments(retail):
    """
    Find active enrollments where the expected number of payments
    (based on months elapsed) exceeds actual payments made.
    Only applies to INSTALLMENT and ACCUMULATION types.
    """
    today = date.today()
    active = SchemeEnrollment.objects.filter(
        retail=retail,
        status='ACTIVE',
        scheme__scheme_type__in=('INSTALLMENT', 'ACCUMULATION'),
    ).select_related('customer', 'scheme')

    overdue = []
    for e in active:
        expected = e.months_completed
        if expected > e.payments_made:
            overdue.append({
                'enrollment_no': e.enrollment_no,
                'customer': e.customer.ac_name,
                'scheme': e.scheme.name,
                'months_elapsed': expected,
                'payments_made': e.payments_made,
                'missed_payments': expected - e.payments_made,
                'installment_amount': float(e.installment_amount),
                'total_overdue': float(e.installment_amount * (expected - e.payments_made)),
            })

    return sorted(overdue, key=lambda x: x['missed_payments'], reverse=True)


def scheme_wise_collection(retail, from_date=None, to_date=None):
    """
    Collection totals grouped by scheme.
    """
    qs = SchemePayment.objects.filter(retail=retail)
    if from_date:
        qs = qs.filter(date__gte=from_date)
    if to_date:
        qs = qs.filter(date__lte=to_date)

    return list(
        qs.values(
            scheme_name=F('enrollment__scheme__name'),
            scheme_code=F('enrollment__scheme__scheme_code'),
        ).annotate(
            total_collection=Sum('amount'),
            payment_count=Count('id'),
            enrollment_count=Count('enrollment', distinct=True),
        ).order_by('-total_collection')
    )


def _month_end(d):
    """Last day of d's month."""
    return (d.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)


def upcoming_payment_dues(retail, window_end):
    """
    Active INSTALLMENT enrollments whose next installment is due on or before window_end.
    Next-due = start_date + (payments_made + 1) months, anchored on start_date.day.
    Includes already-overdue (next_due < today) so the dashboard can chase them too.
    """
    today = date.today()
    qs = SchemeEnrollment.objects.filter(
        retail=retail,
        status='ACTIVE',
        scheme__scheme_type='INSTALLMENT',
    ).select_related('customer', 'scheme')

    rows = []
    for e in qs:
        # Don't bill past tenure
        if e.payments_made >= e.scheme.tenure_months:
            continue
        next_due = e.start_date + relativedelta(months=e.payments_made + 1)
        if next_due > window_end:
            continue
        rows.append({
            'enrollment_no': e.enrollment_no,
            'enrollment_id': e.id,
            'customer': e.customer.ac_name,
            'phone': getattr(e.customer, 'mobile1', '') or '',
            'scheme': e.scheme.name,
            'installment_amount': float(e.installment_amount),
            'next_due_date': str(next_due),
            'days_until_due': (next_due - today).days,
            'payments_made': e.payments_made,
            'tenure_months': e.scheme.tenure_months,
        })
    return sorted(rows, key=lambda x: x['next_due_date'])


def overdue_matured(retail):
    """
    Enrollments past maturity_date that have not been redeemed.
    Includes status=MATURED (already auto-flipped) and status=ACTIVE past maturity
    (signal hasn't run yet).
    """
    today = date.today()
    qs = SchemeEnrollment.objects.filter(
        retail=retail,
        status__in=('ACTIVE', 'MATURED'),
        maturity_date__lt=today,
    ).select_related('customer', 'scheme').order_by('maturity_date')

    return [
        {
            'enrollment_no': e.enrollment_no,
            'enrollment_id': e.id,
            'customer': e.customer.ac_name,
            'scheme': e.scheme.name,
            'maturity_date': str(e.maturity_date),
            'days_overdue': (today - e.maturity_date).days,
            'total_paid': float(e.total_paid),
            'gold_weight': float(e.gold_accumulated_wt),
            'status': e.status,
        }
        for e in qs
    ]


def aged_advances(retail, days=365):
    """
    Enrollments whose earliest payment is older than `days` days and are still
    unredeemed (ACTIVE or MATURED). These are advances we cannot legally continue
    to hold.
    """
    today = date.today()
    cutoff = today - timedelta(days=days)

    qs = (
        SchemeEnrollment.objects
        .filter(retail=retail, status__in=('ACTIVE', 'MATURED'))
        .annotate(first_payment_date=Min('payments__date'))
        .filter(first_payment_date__lte=cutoff)
        .select_related('customer', 'scheme')
        .order_by('first_payment_date')
    )

    return [
        {
            'enrollment_no': e.enrollment_no,
            'enrollment_id': e.id,
            'customer': e.customer.ac_name,
            'phone': getattr(e.customer, 'mobile1', '') or '',
            'scheme': e.scheme.name,
            'first_payment_date': str(e.first_payment_date),
            'days_held': (today - e.first_payment_date).days,
            'total_collected': float(e.total_paid),
            'status': e.status,
        }
        for e in qs
    ]


def collections_by_mode(retail, from_date, to_date):
    """
    Sum of SchemePayment.amount grouped by payment_mode within [from_date, to_date].
    Returns dict keyed by mode label (Cash/Bank/UPI/Cheque/Card).
    """
    rows = (
        SchemePayment.objects
        .filter(retail=retail, date__gte=from_date, date__lte=to_date)
        .values('payment_mode')
        .annotate(total=Sum('amount'))
    )
    mode_labels = dict(SchemePayment.PAYMENT_MODES)
    out = {label: 0.0 for label in mode_labels.values()}
    for r in rows:
        label = mode_labels.get(r['payment_mode'], r['payment_mode'])
        out[label] = float(r['total'] or 0)
    return out


def scheme_dashboard_ext(retail):
    """
    Combined payload for the extended scheme dashboard. Single round-trip.
    """
    today = date.today()
    week_end = today + timedelta(days=7)
    month_end = _month_end(today)
    month_start = today.replace(day=1)

    return {
        'as_of': str(today),
        'dues_7d': upcoming_payment_dues(retail, week_end),
        'dues_month': upcoming_payment_dues(retail, month_end),
        'maturing_7d': maturity_calendar(retail, str(today), str(week_end)),
        'maturing_month': maturity_calendar(retail, str(today), str(month_end)),
        'overdue_matured': overdue_matured(retail),
        'aged_advances': aged_advances(retail, days=365),
        'collections_by_mode_month': collections_by_mode(retail, month_start, today),
    }
