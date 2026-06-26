from django.shortcuts import render, redirect
from django.http import HttpResponse
import os, sqlite3, tempfile
from datetime import datetime
from django.conf import settings as django_settings
from django.core.exceptions import ObjectDoesNotExist

from userauth.permissions import RBACPermission
from .models import *
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from contacts.views import *
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework import status
from rest_framework.permissions import AllowAny
# Create your views here.


class RetailBaseViewset(viewsets.ModelViewSet):
    permission_classes = [RBACPermission]
    # Subclasses may set this False to opt a fiscal_year-bearing model OUT of
    # automatic fiscal-year scoping (e.g. scheme enrollments that span years).
    fy_scoped = True

    def _model_has_fiscal_year(self):
        model = None
        if getattr(self, "queryset", None) is not None:
            model = self.queryset.model
        else:
            try:
                model = self.get_serializer_class().Meta.model
            except Exception:
                return False
        return any(f.name == "fiscal_year" for f in model._meta.get_fields())

    def get_queryset(self):
        retail = getattr(self.request, "retail", None)
        qs = super().get_queryset().filter(retail=retail)
        if (
            getattr(self, "action", None) == "list"
            and self.fy_scoped
            and self.request.query_params.get("all_fy", "").lower() not in ("1", "true")
            and retail is not None
            and getattr(retail, "active_fy_id", None)
            and self._model_has_fiscal_year()
        ):
            qs = qs.filter(fiscal_year_id=retail.active_fy_id)
        return qs

    def perform_create(self, serializer):
        retail = getattr(self.request, "retail", None)

        serializer.save(retail=retail)

def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class UserLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        from userauth.models import LoginLog
        username = request.data.get("username")
        password = request.data.get("password")
        ip       = _get_client_ip(request)
        ua       = request.META.get('HTTP_USER_AGENT', '')[:500]
        retail   = getattr(request, 'retail', None)

        user = authenticate(username=username, password=password)
        if user is not None:
            token, created = Token.objects.get_or_create(user=user)
            # Resolve role name and flags for the frontend
            role_name = None
            can_view_customer_data = True
            try:
                user_role_obj = UserRole.objects.select_related('role').get(user=user)
                role_name = user_role_obj.role.name
                can_view_customer_data = user_role_obj.role.can_view_customer_data
            except UserRole.DoesNotExist:
                pass

            LoginLog.objects.create(
                user=user, username_attempted=username,
                action='login', success=True,
                ip_address=ip, user_agent=ua, retail=retail,
            )

            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_superuser": user.is_superuser,
                "role": role_name,
                "can_view_customer_data": can_view_customer_data,
            }
            return Response({"token": token.key, "user": user_data}, status=status.HTTP_200_OK)

        # Failed login — log without a user FK (username may not exist)
        LoginLog.objects.create(
            user=None, username_attempted=username or '',
            action='login', success=False,
            ip_address=ip, user_agent=ua, retail=retail,
        )
        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


# ── User Management (admin/superuser only) ────────────────────────────────────
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from contacts.models import UserLocation
from mastersconfig.models import RetailMaster


def _is_admin(request):
    return request.user.is_staff or request.user.is_superuser


def _user_to_dict(user):
    try:
        ul = user.userlocation
        locations = [{'id': r.id, 'retail_name': r.retail_name, 'retail_code': r.retail_code}
                     for r in ul.location.all()]
        default_loc = {
            'id': ul.default_location.id,
            'retail_name': ul.default_location.retail_name,
        } if ul.default_location else None
    except ObjectDoesNotExist:
        locations = []
        default_loc = None
    try:
        ur = user.userrole
        role = {'id': ur.role.id, 'name': ur.role.name}
    except ObjectDoesNotExist:
        role = None
    return {
        'id':               user.id,
        'username':         user.username,
        'email':            user.email,
        'first_name':       user.first_name,
        'last_name':        user.last_name,
        'is_staff':         user.is_staff,
        'is_active':        user.is_active,
        'date_joined':      str(user.date_joined.date()),
        'locations':        locations,
        'default_location': default_loc,
        'role':             role,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_users(request):
    """GET /userauth/api/users/  — list all users with their retail assignments."""
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)
    users = User.objects.all().order_by('username')
    return Response([_user_to_dict(u) for u in users])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_user(request):
    """POST /userauth/api/users/create/  — create a new user."""
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)

    username   = request.data.get('username', '').strip()
    password   = request.data.get('password', '')
    email      = request.data.get('email', '')
    first_name = request.data.get('first_name', '')
    last_name  = request.data.get('last_name', '')
    is_staff   = request.data.get('is_staff', False)

    if not username or not password:
        return Response({'detail': 'username and password are required.'}, status=400)
    if User.objects.filter(username=username).exists():
        return Response({'detail': f"Username '{username}' already exists."}, status=400)

    user = User.objects.create_user(
        username=username, password=password, email=email,
        first_name=first_name, last_name=last_name, is_staff=is_staff,
    )
    # Create empty UserLocation
    UserLocation.objects.create(user=user)
    return Response(_user_to_dict(user), status=201)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_user(request, pk):
    """PATCH /userauth/api/users/<pk>/  — update name/email/is_staff/is_active."""
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    for field in ('email', 'first_name', 'last_name', 'is_staff', 'is_active'):
        if field in request.data:
            setattr(user, field, request.data[field])
    if 'password' in request.data and request.data['password']:
        user.set_password(request.data['password'])
    user.save()
    return Response(_user_to_dict(user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """POST /userauth/api/users/change-password/ — self-service password change."""
    old_password = request.data.get('old_password', '')
    new_password = request.data.get('new_password', '')

    if not old_password or not new_password:
        return Response({'detail': 'old_password and new_password are required.'}, status=400)
    if not request.user.check_password(old_password):
        return Response({'detail': 'Current password is incorrect.'}, status=400)
    min_len = next(
        (v.get('OPTIONS', {}).get('min_length', 8)
         for v in django_settings.AUTH_PASSWORD_VALIDATORS
         if 'MinimumLength' in v.get('NAME', '')),
        8,
    )
    if len(new_password) < min_len:
        return Response({'detail': f'New password must be at least {min_len} characters.'}, status=400)
    if new_password == old_password:
        return Response({'detail': 'New password must be different from the current password.'}, status=400)

    request.user.set_password(new_password)
    request.user.save()

    # Rotate auth token so the new password takes effect immediately on next call.
    from rest_framework.authtoken.models import Token
    Token.objects.filter(user=request.user).delete()
    new_token = Token.objects.create(user=request.user)
    return Response({'detail': 'Password changed.', 'token': new_token.key})


# ── Roles & Permissions API ───────────────────────────────────────────────────

RELEVANT_APPS = {
    'accounting':    'Financial Accounting',
    'sales':         'Sales',
    'purchase':      'Purchase',
    'inventory':     'Inventory',
    'manufacturing': 'Manufacturing',
    'contacts':      'Contacts & Ledgers',
    'mastersconfig': 'Masters & Config',
    'goldrates':     'Gold Rates',
    'hr':            'Human Resources',
    'goldscheme':    'Gold Schemes',
}

# Models that inherit permissions from a parent — skip in UI (they get access automatically)
INLINE_MODELS = {
    'accounting.voucherdetail', 'accounting.referencebills', 'accounting.voucherattachment',
    'purchase.purchasevoucherdetails', 'purchase.purchasevoucheritems',
    'purchase.purchaseorderitems', 'purchase.purchasereturndetails', 'purchase.purchasereturnitems',
    'sales.salesvouitem', 'sales.salesvouitemdetails', 'sales.bankdetail',
    'sales.salereturnitem', 'sales.salereturndetails',
    'sales.salesapprovalitem', 'sales.salesapprovalitemdetails', 'sales.customerorderitems',
    'inventory.barcodedetails', 'inventory.designdetails', 'inventory.designdocument',
    'inventory.unbarcodeddetails', 'inventory.stockjournaldetail',
    'manufacturing.jobworkissuedetail', 'manufacturing.jobworkreceivedetail',
}

MODEL_DISPLAY_NAMES = {
    # Accounting
    'accounting.vouchermain':       'Journal Voucher',
    'accounting.ledgeropenbalance': 'Opening Balance',
    'accounting.bankstatemententry':'Bank Statement Entry',
    # Sales
    'sales.salesvou':               'Sales Voucher',
    'sales.salereturn':             'Sales Return',
    'sales.salesapproval':          'Sales Approval',
    'sales.customerorder':          'Customer Order',
    # Purchase
    'purchase.purchasevoucher':     'Purchase Voucher',
    'purchase.purchaseorder':       'Purchase Order',
    'purchase.purchasereturn':      'Purchase Return',
    # Inventory
    'inventory.barcodemain':        'Barcode (Stock Item)',
    'inventory.stockjournal':       'Stock Journal',
    'inventory.design':             'Design',
    # Manufacturing
    'manufacturing.jobworkissue':   'Job Work Issue',
    'manufacturing.jobworkreceive': 'Job Work Receive',
    'manufacturing.hallmarkissue':  'Hallmark Issue',
    'manufacturing.hallmarkreceive':'Hallmark Receive',
    'manufacturing.stoneissue':     'Stone Issue',
    'manufacturing.goldissue':      'Gold Issue',
    'manufacturing.repairjobcard':  'Repair Job Card',
    # Contacts
    'contacts.ledger':              'Ledger / Party',
    'contacts.userlocation':        'User Location',
    # Masters
    'mastersconfig.retailmaster':   'Retail Master',
    'mastersconfig.item':           'Item Master',
    'mastersconfig.packet':         'Packet Master',
    'mastersconfig.companymaster':  'Company Master',
    'mastersconfig.branchmaster':   'Branch Master',
    'mastersconfig.fiscalyear':     'Fiscal Year',
    # Gold
    'goldrates.puritymaster':       'Purity Master',
    'goldrates.goldrates':          'Gold Rates',
}


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def list_create_roles(request):
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)
    if request.method == 'GET':
        roles = Role.objects.prefetch_related('permissions').order_by('name')
        data = []
        for r in roles:
            user_count = UserRole.objects.filter(role=r).count()
            data.append({'id': r.id, 'name': r.name, 'user_count': user_count, 'can_view_customer_data': r.can_view_customer_data})
        return Response(data)
    name = request.data.get('name', '').strip()
    if not name:
        return Response({'detail': 'name is required.'}, status=400)
    if Role.objects.filter(name__iexact=name).exists():
        return Response({'detail': f"Role '{name}' already exists."}, status=400)
    role = Role.objects.create(name=name)
    return Response({'id': role.id, 'name': role.name, 'user_count': 0, 'can_view_customer_data': role.can_view_customer_data}, status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def role_detail(request, pk):
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)
    try:
        role = Role.objects.get(pk=pk)
    except Role.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)
    if request.method == 'DELETE':
        if UserRole.objects.filter(role=role).exists():
            return Response({'detail': 'Cannot delete a role that is assigned to users.'}, status=400)
        role.delete()
        return Response(status=204)
    name = request.data.get('name', '').strip()
    if name:
        role.name = name
    if 'can_view_customer_data' in request.data:
        role.can_view_customer_data = bool(request.data['can_view_customer_data'])
    role.save()
    return Response({'id': role.id, 'name': role.name, 'can_view_customer_data': role.can_view_customer_data})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def role_permissions(request, pk):
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)
    try:
        role = Role.objects.get(pk=pk)
    except Role.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    from django.contrib.contenttypes.models import ContentType

    if request.method == 'GET':
        perms = Permission.objects.filter(role=role).select_related('module')
        return Response([{
            'module_id': p.module_id,
            'can_list':   p.can_list,
            'can_get':    p.can_get,
            'can_post':   p.can_post,
            'can_put':    p.can_put,
            'can_patch':  p.can_patch,
            'can_delete': p.can_delete,
        } for p in perms])

    # POST — bulk replace all permissions for this role
    items = request.data
    if not isinstance(items, list):
        return Response({'detail': 'Expected a list.'}, status=400)

    Permission.objects.filter(role=role).delete()
    to_create = []
    for item in items:
        try:
            ct = ContentType.objects.get(pk=item['module_id'])
        except (ContentType.DoesNotExist, KeyError):
            continue
        to_create.append(Permission(
            role=role, module=ct,
            can_list=bool(item.get('can_list')),
            can_get=bool(item.get('can_get')),
            can_post=bool(item.get('can_post')),
            can_put=bool(item.get('can_put')),
            can_patch=bool(item.get('can_patch')),
            can_delete=bool(item.get('can_delete')),
        ))
    Permission.objects.bulk_create(to_create)
    return Response({'saved': len(to_create)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_modules(request):
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)
    from django.contrib.contenttypes.models import ContentType
    cts = ContentType.objects.filter(app_label__in=RELEVANT_APPS.keys()).order_by('app_label', 'model')
    result = []
    for ct in cts:
        label = f"{ct.app_label}.{ct.model}"
        if label in INLINE_MODELS:
            continue
        display = MODEL_DISPLAY_NAMES.get(label) or ct.model.replace('_', ' ').title()
        result.append({
            'id':          ct.id,
            'app_label':   ct.app_label,
            'app_display': RELEVANT_APPS.get(ct.app_label, ct.app_label.title()),
            'model':       ct.model,
            'model_display': display,
        })
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_permissions(request):
    """Effective module→verb permission map for the calling user.

    Mirrors RBACPermission: superusers get everything, inline child models
    inherit their parent's verbs. Used by the frontend to hide menu items and
    dashboard tiles the user cannot access.
    """
    from userauth.permissions import INLINE_MODEL_MAP

    user = request.user
    if user.is_superuser:
        return Response({'is_superuser': True, 'modules': {}})

    try:
        user_role = UserRole.objects.select_related('role').get(user=user)
    except UserRole.DoesNotExist:
        return Response({'is_superuser': False, 'modules': {}})

    modules = {}
    for p in user_role.role.permissions.select_related('module').all():
        ct = p.module
        label = f"{ct.app_label}.{ct.model}"
        modules[label] = {
            'list':   p.can_list,
            'get':    p.can_get,
            'post':   p.can_post,
            'put':    p.can_put,
            'patch':  p.can_patch,
            'delete': p.can_delete,
        }

    # Inline children inherit the parent's verbs (matches RBACPermission fallback).
    for child_label, parent_label in INLINE_MODEL_MAP.items():
        if parent_label in modules and child_label not in modules:
            modules[child_label] = modules[parent_label]

    return Response({'is_superuser': False, 'modules': modules})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_user_role(request, pk):
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)
    role_id = request.data.get('role_id')
    if role_id is None:
        UserRole.objects.filter(user=user).delete()
        return Response(_user_to_dict(user))
    try:
        role = Role.objects.get(pk=role_id)
    except Role.DoesNotExist:
        return Response({'detail': 'Role not found.'}, status=404)
    UserRole.objects.update_or_create(user=user, defaults={'role': role})
    return Response(_user_to_dict(user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_retail(request, pk):
    """
    POST /userauth/api/users/<pk>/assign-retail/
    Body: { "retail_ids": [1, 2], "default_retail_id": 1 }
    Replaces the user's retail assignments.
    """
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    retail_ids       = request.data.get('retail_ids', [])
    default_retail_id = request.data.get('default_retail_id')

    ul, _ = UserLocation.objects.get_or_create(user=user)
    ul.location.set(RetailMaster.objects.filter(id__in=retail_ids))
    if default_retail_id:
        try:
            ul.default_location = RetailMaster.objects.get(id=default_retail_id)
        except RetailMaster.DoesNotExist:
            pass
    else:
        ul.default_location = None
    ul.save()
    return Response(_user_to_dict(user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def backup_database(request):
    """
    POST /userauth/api/backup-database/
    Body (optional): { "path": "C:\\Backups\\ERP\\" }

    - With path: saves backup file to that server-side folder, returns JSON.
    - Without path: streams the backup file as an HTTP download.
    """
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)

    db_path = str(django_settings.DATABASES['default']['NAME'])
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    app_name = getattr(django_settings, 'APP_NAME', 'jewel_erp')
    backup_filename = f'{app_name}_backup_{timestamp}.sqlite3'

    # Create a safe online backup using sqlite3.backup()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.sqlite3')
    tmp.close()
    try:
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(tmp.name)
        src.backup(dst)
        dst.close()
        src.close()
    except Exception as e:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        return Response({'detail': f'Backup failed: {e}'}, status=500)

    custom_path = (request.data.get('path') or '').strip()

    if custom_path:
        # Validate backup path: must be under the project's BASE_DIR/backups or an
        # explicit BACKUP_ROOT defined in settings (prevents arbitrary path writes).
        backup_root = getattr(django_settings, 'BACKUP_ROOT', None) or \
            os.path.join(str(django_settings.BASE_DIR), 'backups')
        abs_backup_root = os.path.abspath(backup_root)
        abs_custom = os.path.abspath(custom_path)
        if not abs_custom.startswith(abs_backup_root + os.sep) and abs_custom != abs_backup_root:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
            return Response(
                {'detail': f'Backup path must be within {abs_backup_root}. '
                           f'Set BACKUP_ROOT in settings to allow a different location.'},
                status=400,
            )
        # Save to the validated server-side folder
        try:
            os.makedirs(abs_custom, exist_ok=True)
            dest = os.path.join(abs_custom, backup_filename)
            os.replace(tmp.name, dest)
            return Response({'success': True, 'saved_to': dest, 'filename': backup_filename})
        except Exception as e:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
            return Response({'detail': f'Could not save to path: {e}'}, status=500)
    else:
        # Stream as a file download
        with open(tmp.name, 'rb') as f:
            data = f.read()
        os.unlink(tmp.name)
        response = HttpResponse(data, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{backup_filename}"'
        return response


# ── Audit Log ────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_log(request):
    """GET /userauth/api/audit-log/ — paginated audit trail (admin only).

    Backed by the new `audit.AuditEvent` table (one universal event log
    that auto-tracks every model, groups parent + child rows under a
    correlation_id, and records login/logout events). Response shape
    is unchanged so AuditLog.jsx renders without modification.
    """
    from audit.views import _log_list_impl
    return _log_list_impl(request)


# ── Audit Reversal & Restore (admin only) ───────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reverse_transaction_view(request):
    """POST /userauth/api/audit-log/reverse-transaction/

    Body: { history_transaction_id (== correlation_id), reason? }
    Destructively reverts every row touched in the correlation group and
    deletes any child rows created during it. Replaces the old
    simple-history-based reverse_transaction.
    """
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)

    from audit.restore import restore_correlation

    txn_id = request.data.get('history_transaction_id') or request.data.get('correlation_id')
    if not txn_id:
        return Response({'detail': 'history_transaction_id is required.'}, status=400)
    reason = request.data.get('reason') or ''

    try:
        summary = restore_correlation(txn_id, user=request.user, reason=reason)
    except Exception as exc:
        return Response({'detail': f'Reversal failed: {exc}'}, status=500)

    return Response({'summary': summary.as_dict()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def restore_to_point_view(request):
    """POST /userauth/api/audit-log/restore-to-point/

    Body: { model_label, object_pk, timestamp (ISO 8601), reason? }
    Restores ONE row to its state at the given timestamp by replaying
    CREATE snapshot + UPDATE diffs forward from the AuditEvent log.
    System-wide point-in-time restore is no longer supported — use this
    endpoint per row, or the /audit/api/log/reverse/ endpoint to roll
    back one correlation group.
    """
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)

    from audit.restore import restore_row
    from django.utils.dateparse import parse_datetime
    from django.utils.timezone import make_aware, is_aware

    model_label = request.data.get('model_label')
    object_pk   = request.data.get('object_pk')
    raw_ts      = request.data.get('timestamp') or request.data.get('at_timestamp')
    reason      = request.data.get('reason') or ''
    if not (model_label and object_pk and raw_ts):
        return Response({
            'detail': 'model_label, object_pk, and timestamp are required.',
        }, status=400)

    ts = parse_datetime(raw_ts)
    if ts is None:
        return Response({'detail': 'timestamp must be ISO 8601.'}, status=400)
    if not is_aware(ts):
        ts = make_aware(ts)

    try:
        summary = restore_row(model_label, object_pk, ts,
                              user=request.user, reason=reason)
    except Exception as exc:
        return Response({'detail': f'Restore failed: {exc}'}, status=500)

    return Response({
        'timestamp': ts.isoformat(),
        'summary':   summary.as_dict(),
    })


# ── Logout ───────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """POST /userauth/api/logout/ — delete the auth token and write a logout log."""
    from userauth.models import LoginLog
    from rest_framework.authtoken.models import Token

    ip     = _get_client_ip(request)
    ua     = request.META.get('HTTP_USER_AGENT', '')[:500]
    retail = getattr(request, 'retail', None)

    LoginLog.objects.create(
        user=request.user,
        username_attempted=request.user.username,
        action='logout', success=True,
        ip_address=ip, user_agent=ua, retail=retail,
    )
    # Invalidate the token so it can no longer be used
    Token.objects.filter(user=request.user).delete()
    return Response({'detail': 'Logged out.'})


# ── Login Log ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def login_log(request):
    """GET /userauth/api/login-log/ — paginated login/logout history (admin only)."""
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)

    from userauth.models import LoginLog

    qs = LoginLog.objects.select_related('user', 'retail').order_by('-timestamp')

    from_date  = request.GET.get('from_date')
    to_date    = request.GET.get('to_date')
    action     = request.GET.get('action', '').strip()   # 'login' | 'logout'
    username   = request.GET.get('username', '').strip()

    if from_date:
        qs = qs.filter(timestamp__date__gte=from_date)
    if to_date:
        qs = qs.filter(timestamp__date__lte=to_date)
    if action:
        qs = qs.filter(action=action)
    if username:
        qs = qs.filter(username_attempted__icontains=username)

    page      = max(int(request.GET.get('page', 1)), 1)
    page_size = getattr(django_settings, 'LOG_PAGE_SIZE', 50)
    total     = qs.count()
    rows      = qs[(page - 1) * page_size: page * page_size]

    from django.utils.timezone import localtime

    results = []
    for log in rows:
        results.append({
            'id':         log.id,
            'timestamp':  localtime(log.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            'user':       log.user.username if log.user else None,
            'username_attempted': log.username_attempted,
            'action':     log.action,
            'success':    log.success,
            'ip_address': log.ip_address,
            'user_agent': log.user_agent,
            'retail':     log.retail.retail_name if log.retail else None,
        })

    return Response({
        'count':     total,
        'page':      page,
        'page_size': page_size,
        'num_pages': max(1, (total + page_size - 1) // page_size),
        'results':   results,
    })


# ── Audit Log Detail (field-level diff) ───────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_log_detail(request):
    """GET /userauth/api/audit-log/detail/?id=<app.model:history_id>

    Returns the old→new diff for a single UPDATE history record.
    For CREATE rows the old values will be null; for DELETE the new values.
    """
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)

    from audit.views import _log_detail_impl
    return _log_detail_impl(request)


# ── Dashboard Summary ────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """GET /userauth/api/dashboard-summary/ — today's KPIs for the active retail."""
    retail = getattr(request, 'retail', None)

    from datetime import date
    from django.db.models import Sum, Count

    today          = date.today()
    first_of_month = today.replace(day=1)

    from sales.models import SalesVou
    from purchase.models import PurchaseVoucher, PurchaseOrder

    # ── Today's sales ──────────────────────────────────────────
    sales_today = SalesVou.objects.filter(retail=retail, date1=today, ret_status=False)
    sales_today_count = sales_today.count()
    sales_today_value = sum(
        (float(v.mrp or 0) - float(v.discount or 0)) for v in sales_today
    )

    # ── This month's sales ──────────────────────────────────────
    sales_month_value = sum(
        (float(v.mrp or 0) - float(v.discount or 0))
        for v in SalesVou.objects.filter(retail=retail, date1__gte=first_of_month, ret_status=False)
    )

    # ── Today's purchases ──────────────────────────────────────
    purch_today_agg = PurchaseVoucher.objects.filter(
        retail=retail, date1=today, is_return=False
    ).aggregate(total=Sum('item_total'))
    purch_today_value = float(purch_today_agg['total'] or 0)

    # ── Pending purchase orders ────────────────────────────────
    pending_po = PurchaseOrder.objects.filter(retail=retail).count()

    # ── Outstanding receivable (due_amt on sales vouchers) ────
    outstanding = float(
        SalesVou.objects.filter(retail=retail, ret_status=False)
        .aggregate(total=Sum('due_amt'))['total'] or 0
    )

    # ── Total sales bills this month ───────────────────────────
    sales_month_count = SalesVou.objects.filter(
        retail=retail, date1__gte=first_of_month, ret_status=False
    ).count()

    return Response({
        'sales_today_count':    sales_today_count,
        'sales_today_value':    round(sales_today_value, 2),
        'sales_month_count':    sales_month_count,
        'sales_month_value':    round(sales_month_value, 2),
        'purchases_today_value': round(purch_today_value, 2),
        'pending_po':           pending_po,
        'outstanding_receivable': round(outstanding, 2),
    })
