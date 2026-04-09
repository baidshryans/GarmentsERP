"""
Scheme reports — summary, maturity calendar, overdue payments.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum, Count, Q, F

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
