import uuid

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission

from .models import CustomerPortalToken


class PortalTokenAuthentication(BaseAuthentication):
    """
    DRF authentication class for customer portal.
    Expects header: Authorization: PortalToken <uuid>
    """
    keyword = 'PortalToken'

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith(f'{self.keyword} '):
            return None

        token_str = auth_header[len(self.keyword) + 1:].strip()
        try:
            token_uuid = uuid.UUID(token_str)
        except (ValueError, AttributeError):
            raise AuthenticationFailed('Invalid portal token format.')

        try:
            token = CustomerPortalToken.objects.select_related(
                'ledger', 'retail', 'retail__active_fy'
            ).get(token=token_uuid)
        except CustomerPortalToken.DoesNotExist:
            raise AuthenticationFailed('Invalid or expired portal token.')

        if token.is_expired:
            token.delete()
            raise AuthenticationFailed('Portal token has expired. Please log in again.')

        # Set retail and fiscal_year on request so downstream services work
        request.retail = token.retail
        request.fiscal_year = getattr(token.retail, 'active_fy', None)
        request.portal_customer = token.ledger
        request.portal_token = token

        # DRF expects (user, auth) tuple; use ledger as the "user" stand-in
        return (token.ledger, token)


class IsPortalAuthenticated(BasePermission):
    """Permission class that checks for a valid portal token."""

    def has_permission(self, request, view):
        return (
            hasattr(request, 'portal_token')
            and request.portal_token is not None
        )
