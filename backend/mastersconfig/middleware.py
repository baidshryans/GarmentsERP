from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from .models import RetailMaster, ExhibitionProfile
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


RETAIL_EXEMPT_PREFIXES = (
    '/userauth/api/setup/',
    '/userauth/api-token-auth/',
    '/userauth/api/token-auth/',
    '/admin/',
)

class RetailMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Skip retail validation entirely for setup/auth endpoints
        if request.path.startswith(RETAIL_EXEMPT_PREFIXES):
            request.retail = None
            request.fiscal_year = None
            request.exhibition = None
            return None

        # Manual Token Authentication
        auth = TokenAuthentication()
        try:
            user_auth_tuple = auth.authenticate(request)
            if user_auth_tuple:
                request.user, request.auth = user_auth_tuple
            else:
                pass
        except AuthenticationFailed:
            pass

        model_id = request.headers.get("X-RETAIL-ID")
        if model_id:
            # Cache RetailMaster lookup (5-min TTL)
            cache_key = f"retail_{model_id}"
            retail = cache.get(cache_key)
            if retail is None:
                try:
                    retail = RetailMaster.objects.select_related('state', 'active_fy').get(retail_code=model_id)
                    cache.set(cache_key, retail, timeout=300)
                except RetailMaster.DoesNotExist:
                    return JsonResponse(
                        {"error": f"Retail location '{model_id}' not found. Check the X-RETAIL-ID header."},
                        status=400,
                    )
            request.retail = retail
            request.fiscal_year = getattr(retail, 'active_fy', None)

            # Resolve active exhibition for this retail (no cache — must be live)
            request.exhibition = ExhibitionProfile.objects.filter(
                retail=retail, is_active=True
            ).select_related('state').first()

            # Cache user-location access check (5-min TTL)
            if hasattr(request, 'user') and request.user.is_authenticated:
                access_key = f"user_access_{request.user.id}_{retail.id}"
                has_access = cache.get(access_key)
                if has_access is None:
                    try:
                        has_access = request.user.userlocation.location.filter(id=retail.id).exists()
                    except Exception:
                        # Superuser or user without a UserLocation record can access all retails
                        has_access = request.user.is_staff
                    cache.set(access_key, has_access, timeout=300)
                if not has_access:
                    return JsonResponse({"error": "Unauthorized access"}, status=401)
        else:
            request.retail = None
            request.fiscal_year = None
            request.exhibition = None
