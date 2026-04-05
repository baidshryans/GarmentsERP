from datetime import date
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import AppRegistry, CompanySubscription, AppLicense


def _all_apps_payload():
    """Return all active apps as licensed (used for superadmin / no subscription)."""
    all_apps = AppRegistry.objects.filter(is_active=True)
    all_codes = list(all_apps.values_list('code', flat=True))
    flat_nav = set()
    for keys in all_apps.values_list('nav_group_keys', flat=True):
        if isinstance(keys, list):
            flat_nav.update(keys)
    return all_codes, list(flat_nav)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_apps(request):
    """
    Returns the licensing info for the current user's company.
    Superadmin or no-subscription = all apps licensed (full access).
    """
    # Superadmin always gets everything
    if request.user.is_superuser:
        all_codes, all_nav = _all_apps_payload()
        return Response({
            'company': 'Superadmin',
            'status': 'active',
            'start_date': None,
            'end_date': None,
            'licensed_apps': all_codes,
            'nav_groups': all_nav,
        })

    retail = getattr(request, 'retail', None)
    if not retail:
        return Response({'error': 'No retail context'}, status=400)

    company = getattr(retail, 'branch', None)
    company = getattr(company, 'company', None) if company else None
    if not company:
        return Response({'error': 'No company found for this retail'}, status=400)

    # Build license data (cached per company, 5-min TTL)
    cache_key = f"company_license_{company.id}"
    license_data = cache.get(cache_key)
    if license_data is None:
        license_data = _build_license_data(company)
        cache.set(cache_key, license_data, timeout=300)

    return Response(license_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_apps(request):
    """
    Returns the full app catalog with licensing status for the current company.
    Superadmin or no subscription = all apps shown as installed.
    """
    is_superuser = request.user.is_superuser

    retail = getattr(request, 'retail', None)
    company = None
    if retail:
        branch = getattr(retail, 'branch', None)
        company = getattr(branch, 'company', None) if branch else None

    # Determine which apps are licensed
    licensed_codes = set()
    subscription = None
    has_subscription = False

    if company:
        try:
            sub = CompanySubscription.objects.get(company=company)
            has_subscription = True
            subscription = {
                'status': sub.status,
                'start_date': sub.start_date.isoformat(),
                'end_date': sub.end_date.isoformat(),
            }
            licensed_codes = set(
                AppLicense.objects.filter(subscription=sub, is_enabled=True)
                .values_list('app__code', flat=True)
            )
        except CompanySubscription.DoesNotExist:
            pass

    # Build full catalog
    apps = []
    for app in AppRegistry.objects.filter(is_active=True):
        # Superadmin or no subscription configured = all apps licensed
        if is_superuser or not has_subscription:
            is_licensed = True
        else:
            is_licensed = app.is_core or app.code in licensed_codes

        apps.append({
            'code': app.code,
            'name': app.name,
            'description': app.description,
            'icon': app.icon,
            'monthly_price': float(app.monthly_price),
            'is_core': app.is_core,
            'is_licensed': is_licensed,
            'nav_group_keys': app.nav_group_keys,
        })

    return Response({
        'subscription': subscription,
        'apps': apps,
    })


def _build_license_data(company):
    """Build the cached license payload for a company."""
    try:
        sub = CompanySubscription.objects.get(company=company)
        licensed_codes = set(
            AppLicense.objects.filter(subscription=sub, is_enabled=True)
            .values_list('app__code', flat=True)
        )
        core_codes = set(
            AppRegistry.objects.filter(is_core=True).values_list('code', flat=True)
        )
        all_licensed = licensed_codes | core_codes

        nav_groups = list(
            AppRegistry.objects.filter(code__in=all_licensed, is_active=True)
            .values_list('nav_group_keys', flat=True)
        )
        flat_nav = set()
        for keys in nav_groups:
            if isinstance(keys, list):
                flat_nav.update(keys)

        return {
            'company': company.company_name,
            'status': sub.status,
            'start_date': sub.start_date.isoformat(),
            'end_date': sub.end_date.isoformat(),
            'licensed_apps': list(all_licensed),
            'nav_groups': list(flat_nav),
        }
    except CompanySubscription.DoesNotExist:
        # No subscription = all apps licensed (ungated deployment)
        all_codes, all_nav = _all_apps_payload()
        return {
            'company': company.company_name,
            'status': 'active',
            'start_date': None,
            'end_date': None,
            'licensed_apps': all_codes,
            'nav_groups': all_nav,
        }
