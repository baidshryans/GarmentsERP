"""
RBAC for the Customer 360 analytics endpoints.

`userauth.permissions.RBACPermission` resolves the model from the view's
queryset, so it cannot protect the plain APIViews here — they aggregate across
several models and have no single queryset. These classes do the same
UserRole → Role → Permission lookup, but against an explicitly named model.

This matters: these endpoints expose every customer's spend, contact details and
buying history. Leaving them on bare IsAuthenticated would let any logged-in
user export the customer book.
"""

import logging

from django.contrib.contenttypes.models import ContentType
from rest_framework.permissions import BasePermission

from userauth.models import UserRole

logger = logging.getLogger(__name__)


class _ModelBackedPermission(BasePermission):
    """
    Grant access based on the caller's role permissions for `model_label`.

    Subclasses set `model_label` ('app_label.modelname') and optionally
    `require_flag` to demand a specific capability rather than inferring one
    from the HTTP method.
    """

    model_label = None
    require_flag = None

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        app_label, model_name = self.model_label.split(".")
        try:
            content_type = ContentType.objects.get(app_label=app_label, model=model_name)
        except ContentType.DoesNotExist:
            logger.error("customer_intel: content type %s missing", self.model_label)
            return False

        try:
            user_role = UserRole.objects.get(user=request.user)
        except UserRole.DoesNotExist:
            logger.warning("customer_intel: no UserRole for %s", request.user)
            return False

        permissions = user_role.role.permissions.filter(module=content_type)
        flag = self.require_flag or self._flag_for_method(request.method)
        if flag is None:
            return False
        return permissions.filter(**{flag: True}).exists()

    @staticmethod
    def _flag_for_method(method):
        return {
            "GET": "can_get",
            "HEAD": "can_get",
            "OPTIONS": "can_get",
            "POST": "can_post",
            "PUT": "can_put",
            "PATCH": "can_patch",
            "DELETE": "can_delete",
        }.get(method)


class HasIntelAccess(_ModelBackedPermission):
    """Read/write access to customer profiles and their timeline."""

    model_label = "customer_intel.customerprofilesnapshot"


class CanExportCustomerData(_ModelBackedPermission):
    """
    Bulk export of customer PII (segment CSV, Meta audience files).

    Deliberately a *separate* grant from viewing a profile: reading one
    customer's record while serving them is an everyday action; downloading the
    whole book is not. `CustomerDataExport` is a proxy model that exists purely
    to give this capability its own ContentType row, so it can be granted or
    withheld independently in the role editor.
    """

    model_label = "customer_intel.customerdataexport"
    require_flag = "can_get"
