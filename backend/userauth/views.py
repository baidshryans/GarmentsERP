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
    def get_queryset(self):
        retail = getattr(self.request, "retail", None)
        return super().get_queryset().filter(retail=retail)
    def perform_create(self, serializer):
        retail = getattr(self.request, "retail", None)

        serializer.save(retail=retail)

class UserLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
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
    backup_filename = f'jewel_erp_backup_{timestamp}.sqlite3'

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

    Backed by django-simple-history. Iterates every model that registered a
    TenantHistoricalRecords field, scoped to the active retail, sorts the
    union by date and paginates in memory. Output shape stays identical to
    the old easy-audit response so AuditLog.jsx renders unchanged.
    """
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)

    from common.history_query import query_history

    retail     = getattr(request, 'retail', None)
    user_id    = request.GET.get('user')
    model_name = request.GET.get('model', '').strip()
    from_date  = request.GET.get('from_date') or None
    to_date    = request.GET.get('to_date') or None

    rows = query_history(
        retail=retail,
        from_date=from_date,
        to_date=to_date,
        model_name=model_name,
        user_id=user_id,
    )

    page      = max(int(request.GET.get('page', 1)), 1)
    page_size = 50
    offset    = (page - 1) * page_size
    total     = len(rows)
    page_rows = rows[offset: offset + page_size]

    return Response({
        'count':     total,
        'page':      page,
        'page_size': page_size,
        'num_pages': max(1, (total + page_size - 1) // page_size),
        'results':   page_rows,
    })


# ── Audit Reversal & Restore (admin only) ───────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reverse_transaction_view(request):
    """POST /userauth/api/audit-log/reverse-transaction/

    Body: { history_transaction_id, dry_run? }
    Undoes every change written during one HTTP request (rows that share
    the same history_transaction_id). Use dry_run=true to preview.
    """
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)

    from common.restore import reverse_transaction

    txn_id = request.data.get('history_transaction_id')
    if not txn_id:
        return Response({'detail': 'history_transaction_id is required.'}, status=400)

    dry_run = bool(request.data.get('dry_run', False))

    try:
        summary = reverse_transaction(txn_id, dry_run=dry_run)
    except Exception as exc:
        return Response({'detail': f'Reversal failed: {exc}'}, status=500)

    return Response({
        'dry_run':  dry_run,
        'summary':  summary.as_dict(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def restore_to_point_view(request):
    """POST /userauth/api/audit-log/restore-to-point/

    Body: { timestamp (ISO 8601), retail_id?, dry_run? }
    Roll all tracked rows back to the state that was current at `timestamp`.
    """
    if not _is_admin(request):
        return Response({'detail': 'Admin access required.'}, status=403)

    from common.restore import restore_to_point
    from mastersconfig.models import RetailMaster
    from django.utils.dateparse import parse_datetime
    from django.utils.timezone import make_aware, is_aware

    raw_ts = request.data.get('timestamp')
    if not raw_ts:
        return Response({'detail': 'timestamp is required.'}, status=400)

    ts = parse_datetime(raw_ts)
    if ts is None:
        return Response({'detail': 'timestamp must be ISO 8601.'}, status=400)
    if not is_aware(ts):
        ts = make_aware(ts)

    retail_id = request.data.get('retail_id')
    retail = None
    if retail_id:
        try:
            retail = RetailMaster.objects.get(pk=retail_id)
        except RetailMaster.DoesNotExist:
            return Response({'detail': f'Retail {retail_id} not found.'}, status=404)
    else:
        retail = getattr(request, 'retail', None)

    dry_run = bool(request.data.get('dry_run', False))

    try:
        summary = restore_to_point(ts, retail=retail, dry_run=dry_run)
    except Exception as exc:
        return Response({'detail': f'Restore failed: {exc}'}, status=500)

    return Response({
        'dry_run':  dry_run,
        'timestamp': ts.isoformat(),
        'retail':    retail.retail_code if retail else None,
        'summary':   summary.as_dict(),
    })


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
