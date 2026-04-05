from datetime import date
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from .models import AppRegistry, CompanySubscription, AppLicense


class LicenseMiddleware(MiddlewareMixin):
    """
    Placed after RetailMiddleware. Checks that:
    1. The company's subscription is active and not expired
    2. The requested app/module is licensed for this company

    Attaches request.company and request.licensed_apps for downstream use.
    """

    # URL prefixes that are always allowed (no license check)
    EXEMPT_PREFIXES = (
        '/admin/',
        '/userauth/',
        '/licensing/',
    )

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Skip for exempt paths
        if any(request.path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return None

        # Skip for superusers (vendor admin)
        if getattr(request.user, 'is_superuser', False):
            return None

        # Skip for unauthenticated requests (auth middleware will handle)
        if not getattr(request.user, 'is_authenticated', False):
            return None

        # Resolve company from retail → branch → company
        retail = getattr(request, 'retail', None)
        if not retail:
            return None  # No retail context — let RetailMiddleware handle

        branch = getattr(retail, 'branch', None)
        company = getattr(branch, 'company', None) if branch else None
        if not company:
            return None

        # Get cached license data
        cache_key = f"company_license_{company.id}"
        license_data = cache.get(cache_key)
        if license_data is None:
            license_data = self._build_license_data(company)
            cache.set(cache_key, license_data, timeout=300)

        # Check subscription validity
        status = license_data.get('status', 'expired')
        if status not in ('active', 'trial'):
            return JsonResponse({
                'error': 'Subscription inactive or suspended. Please contact the vendor.',
                'code': 'SUBSCRIPTION_INACTIVE',
            }, status=403)

        end_date_str = license_data.get('end_date')
        if end_date_str:
            end_date = date.fromisoformat(end_date_str)
            if end_date < date.today():
                return JsonResponse({
                    'error': 'Subscription has expired. Please contact the vendor.',
                    'code': 'SUBSCRIPTION_EXPIRED',
                }, status=403)

        # Resolve which app this request belongs to
        app_label = self._get_app_label(view_func)
        licensed_apps = set(license_data.get('licensed_app_labels', []))
        if app_label and app_label not in licensed_apps:
            return JsonResponse({
                'error': 'This module is not licensed for your company.',
                'code': 'APP_NOT_LICENSED',
            }, status=403)

        # Attach to request for downstream use
        request.company = company
        request.licensed_apps = license_data.get('licensed_apps', [])
        return None

    def _get_app_label(self, view_func):
        """Extract Django app_label from the view's module path."""
        module = getattr(view_func, '__module__', '')
        if module:
            return module.split('.')[0]
        return None

    def _build_license_data(self, company):
        """Build and return the license payload for caching."""
        try:
            sub = CompanySubscription.objects.get(company=company)
            licensed_codes = set(
                AppLicense.objects.filter(subscription=sub, is_enabled=True)
                .values_list('app__code', flat=True)
            )
            core_codes = set(
                AppRegistry.objects.filter(is_core=True).values_list('code', flat=True)
            )
            all_codes = licensed_codes | core_codes

            # Get the django_app_labels for licensed apps (for URL-level gating)
            licensed_labels = set(
                AppRegistry.objects.filter(code__in=all_codes, is_active=True)
                .values_list('django_app_label', flat=True)
            )

            return {
                'status': sub.status,
                'end_date': sub.end_date.isoformat(),
                'licensed_apps': list(all_codes),
                'licensed_app_labels': list(licensed_labels),
            }
        except CompanySubscription.DoesNotExist:
            # No subscription configured = ungated (all apps allowed)
            all_labels = list(
                AppRegistry.objects.filter(is_active=True).values_list('django_app_label', flat=True)
            )
            all_codes = list(
                AppRegistry.objects.filter(is_active=True).values_list('code', flat=True)
            )
            return {
                'status': 'active',
                'end_date': None,
                'licensed_apps': all_codes,
                'licensed_app_labels': all_labels,
            }
