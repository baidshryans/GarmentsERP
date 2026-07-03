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
                'account', 'retail'
            ).get(token=token_uuid)
        except CustomerPortalToken.DoesNotExist:
            raise AuthenticationFailed('Invalid or expired portal token.')

        if token.is_expired:
            token.delete()
            raise AuthenticationFailed('Portal token has expired. Please log in again.')

        request.retail = token.retail
        from mastersconfig.models import SystemSettings
        request.fiscal_year = SystemSettings.get().active_fy
        request.portal_account = token.account
        request.portal_token = token
        return (token.account, token)


class IsPortalAuthenticated(BasePermission):
    """Permission class that checks for a valid portal token."""

    def has_permission(self, request, view):
        return (
            hasattr(request, 'portal_token')
            and request.portal_token is not None
        )


def portal_ledgers(request):
    """The set of ledgers the authenticated portal account may access."""
    account = getattr(request, 'portal_account', None)
    if account is None:
        from contacts.models import Ledger
        return Ledger.objects.none()
    return account.linked_ledgers.all()
