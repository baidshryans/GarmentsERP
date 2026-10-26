from rest_framework.permissions import BasePermission
from .models import UserRole
from django.contrib.contenttypes.models import ContentType
import logging

logger = logging.getLogger(__name__)

# Mapping: child (inline) model label -> parent model label
# Format: 'app_label.model' -> 'app_label.model'
# When a user has access to the parent, they automatically get access to the child.
INLINE_MODEL_MAP = {
    # Accounting
    'accounting.voucherdetail': 'accounting.vouchermain',
    'accounting.referencebills': 'accounting.vouchermain',
    'accounting.voucherattachment': 'accounting.vouchermain',
    # Purchase
    'purchase.purchasevoucherdetails': 'purchase.purchasevoucher',
    'purchase.purchasevoucheritems': 'purchase.purchasevoucher',
    'purchase.purchaseattachment': 'purchase.purchasevoucher',
    'purchase.purchaseorderitems': 'purchase.purchaseorder',
    'purchase.purchasereturndetails': 'purchase.purchasereturn',
    'purchase.purchasereturnitems': 'purchase.purchasereturn',
    # Sales
    'sales.salesvouitem': 'sales.salesvou',
    'sales.salesvouitemdetails': 'sales.salesvou',
    'sales.bankdetail': 'sales.salesvou',
    'sales.salereturnitem': 'sales.salereturn',
    'sales.salereturndetails': 'sales.salereturn',
    'sales.salesapprovalitem': 'sales.salesapproval',
    'sales.salesapprovalitemdetails': 'sales.salesapproval',
    'sales.customerorderitems': 'sales.customerorder',
    # Inventory
    'inventory.barcodedetails': 'inventory.barcodemain',
    'inventory.barcodeimage': 'inventory.barcodemain',
    'inventory.designdetails': 'inventory.designmain',
    'inventory.designdocument': 'inventory.designmain',
    'inventory.designimage': 'inventory.designmain',
    'inventory.unbarcodeddetails': 'inventory.unbarcodedmain',
    'inventory.stockjournaldetail': 'inventory.stockjournal',
    # Manufacturing
    'manufacturing.karigarissueitem': 'manufacturing.karigarissue',
    'manufacturing.karigarreceiveitem': 'manufacturing.karigarreceive',
    'manufacturing.karigarreceiveitemdetails': 'manufacturing.karigarreceive',
    'manufacturing.repairstone': 'manufacturing.repairjobcard',
    'manufacturing.repairloss': 'manufacturing.repairjobcard',
    'manufacturing.repairkarigarlink': 'manufacturing.repairjobcard',
}


class RBACPermission(BasePermission):
    def has_permission(self, request, view):
        # Unauthenticated (anonymous) users never have any permission
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        method = request.method
        if hasattr(view, 'get_queryset'):
            model = getattr(view.get_queryset(), 'model', None)
        else:
            model = getattr(view.queryset, 'model', None)

        if model is None:
            logger.error("The view does not have a valid queryset or get_queryset with a model.")
            return False

        try:
            content_type = ContentType.objects.get_for_model(model)
        except ContentType.DoesNotExist:
            logger.error(f"Content type for model {model} does not exist.")
            return False

        try:
            user_role = UserRole.objects.get(user=request.user)
        except UserRole.DoesNotExist:
            logger.warning(f"UserRole not found for user {request.user}")
            return False

        # Check permission on the model itself first
        if self._check_model_permission(user_role, content_type, method, view):
            return True

        # If not found, check if this is an inline model and fall back to parent
        model_label = f"{content_type.app_label}.{content_type.model}"
        parent_label = INLINE_MODEL_MAP.get(model_label)
        if parent_label:
            app_label, model_name = parent_label.split('.')
            try:
                parent_ct = ContentType.objects.get(app_label=app_label, model=model_name)
                if self._check_model_permission(user_role, parent_ct, method, view):
                    return True
            except ContentType.DoesNotExist:
                logger.warning(f"Parent content type {parent_label} not found for inline {model_label}")

        return False

    @staticmethod
    def _check_model_permission(user_role, content_type, method, view):
        permissions = user_role.role.permissions.filter(module=content_type)
        if method == 'GET':
            if hasattr(view, 'action') and view.action == 'list':
                return permissions.filter(can_list=True).exists()
            return permissions.filter(can_get=True).exists()
        elif method == 'POST':
            return permissions.filter(can_post=True).exists()
        elif method == 'OPTIONS':
            return permissions.filter(can_post=True).exists()
        elif method == 'PUT':
            return permissions.filter(can_put=True).exists()
        elif method == 'PATCH':
            return permissions.filter(can_patch=True).exists()
        elif method == 'DELETE':
            return permissions.filter(can_delete=True).exists()
        return False
