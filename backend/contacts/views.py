from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from rest_framework.decorators import api_view
from rest_framework import status
from accounting.serializers import LedgerSerializer
from contacts.filters import LedgerFilter
from contacts.serializers import AllowedRetailSerializer
from global_vars import CUSTOMER_TYPE, STATES_OF_INDIA
from .models import *
from accounting.models import *
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from .serializers import AccountSerializer
import csv
import io
from datetime import datetime
from rest_framework.parsers import MultiPartParser
from django.db import transaction


class LocationBasedQuerysetMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        try:
            user_location = self.request.user.userlocation.location
            return queryset.filter(loc=user_location)
        except ObjectDoesNotExist:
            # Staff/superuser without a UserLocation record — return full queryset
            if getattr(self.request.user, 'is_staff', False):
                return queryset
            return queryset.none()


def _has_non_customer_role(ledger):
    """Return True if the ledger has any role that is not Customer (CO)."""
    return ledger.roles.exclude(role='CO').exists()


def _name_conflicts(ac_name, exclude_id=None):
    """
    Return True if a non-Customer ledger with this ac_name (case-insensitive)
    already exists, excluding the ledger with exclude_id.
    """
    qs = Ledger.objects.filter(ac_name__iexact=ac_name).exclude(roles__role='CO')
    # The above gets ledgers that have at least one non-CO role OR no roles at all
    # We want ledgers that are NOT purely customers
    # Ledgers with no roles yet: filter those out (they have no non-CO role either)
    qs = Ledger.objects.filter(
        ac_name__iexact=ac_name
    ).filter(
        roles__isnull=False        # has at least one role
    ).exclude(
        roles__role='CO'           # exclude pure customers (those whose only roles are CO)
    )
    # More precise: exclude ledgers where ALL roles are CO
    # Simplest: a ledger conflicts if it has any non-CO role AND its name matches
    qs = Ledger.objects.filter(ac_name__iexact=ac_name).filter(
        roles__role__in=['DL','KR','VD','CA','BA','SC','SD','REF','MLT','EXP','INC','HM','OTH']
    ).distinct()
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


@api_view(['GET'])
def check_ledger_name(request):
    """
    GET /contacts/api/ledger/check-name/?ac_name=X&exclude_id=Y
    Returns { exists: bool } — exists=true means a non-Customer ledger with
    that name already exists (conflict for non-Customer ledger types).
    """
    ac_name = request.GET.get('ac_name', '').strip()
    exclude_id = request.GET.get('exclude_id') or None
    if not ac_name:
        return Response({'exists': False})
    exists = _name_conflicts(ac_name, exclude_id=exclude_id)
    return Response({'exists': exists})


class ListCreateLedger(ListCreateAPIView):
    serializer_class = LedgerSerializer
    queryset         = Ledger.objects.select_related('ac_group').prefetch_related('roles').all()
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LedgerFilter          # supports ?type= and ?role=

    search_fields = ["ac_name", "display_name", "mobile1", "mobile2", "phone1"]

    # Optionally set default ordering
    ordering = ['ac_name']

    # FA asset account groups that are managed exclusively via the Fixed Asset Master
    FA_ASSET_GROUP_CODES = {'FA-LB', 'FA-PM', 'FA-FF', 'FA-CE', 'FA-VH'}

    # These account groups are branch-specific (each retail has its own cash/bank).
    # Every other group is treated as global (retail_code=None) so ledgers like
    # customers, suppliers, karigars, income, expense accounts are shared across
    # all retail branches.
    PER_RETAIL_GROUP_CODES = {'CA-CSH', 'CA-BNK', 'CA-BNK-OD'}

    def get_queryset(self):
        retail = getattr(self.request, 'retail', None)
        if retail is None:
            return Ledger.objects.none()
        return (
            Ledger.objects
            .filter(Q(retail_code=retail) | Q(retail_code__isnull=True))
            .select_related('ac_group')
            .prefetch_related('roles')
        )

    def perform_create(self, serializer):
        ac_group = serializer.validated_data.get('ac_group')
        if ac_group and ac_group.code in self.PER_RETAIL_GROUP_CODES:
            serializer.save(retail_code=self.request.retail)
        else:
            serializer.save(retail_code=None)  # global — visible to all branches

    def create(self, request, *args, **kwargs):
        # Block ledger creation under FA asset account groups — use Asset Master instead
        ac_group_id = request.data.get('ac_group')
        if ac_group_id:
            try:
                from accounting.models import Account
                group = Account.objects.get(pk=ac_group_id)
                if group.code in self.FA_ASSET_GROUP_CODES:
                    return Response(
                        {'ac_group': (
                            f"Ledgers under '{group.name}' are managed automatically. "
                            "Please create the asset in Fixed Assets → Asset Master instead."
                        )},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except Account.DoesNotExist:
                pass

        # requested_roles may be passed in the payload for upfront uniqueness check
        requested_roles = request.data.get('requested_roles', [])
        is_customer_only = requested_roles and all(r == 'CO' for r in requested_roles)
        ac_name = (request.data.get('ac_name') or '').strip()
        if ac_name and requested_roles and not is_customer_only:
            if _name_conflicts(ac_name):
                return Response(
                    {'ac_name': f"A ledger named '{ac_name}' already exists. Duplicate names are only allowed for Customer accounts."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return super().create(request, *args, **kwargs)


class RetrieveUpdateDestroyLedger(RetrieveUpdateDestroyAPIView):
    serializer_class = LedgerSerializer
    queryset         = Ledger.objects.all()

    def get_queryset(self):
        retail = getattr(self.request, 'retail', None)
        if retail is None:
            return Ledger.objects.none()
        return Ledger.objects.filter(Q(retail_code=retail) | Q(retail_code__isnull=True))

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_system:
            return Response(
                {'error': 'System-created ledgers cannot be edited.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        # If the ledger has non-CO roles and the name is being changed, check uniqueness
        new_name = (request.data.get('ac_name') or '').strip()
        if new_name and new_name.lower() != instance.ac_name.lower():
            if _has_non_customer_role(instance) and _name_conflicts(new_name, exclude_id=instance.pk):
                return Response(
                    {'ac_name': f"A ledger named '{new_name}' already exists. Duplicate names are only allowed for Customer accounts."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_system:
            return Response(
                {'error': 'System-created ledgers cannot be deleted.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

class AllowedRetailView(ListAPIView):
    serializer_class = AllowedRetailSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            # Superusers always see every retail — sync their UserLocation first
            from mastersconfig.models import RetailMaster
            all_retails = list(RetailMaster.objects.all())
            if all_retails:
                ul, _ = UserLocation.objects.get_or_create(user=user)
                for retail in all_retails:
                    ul.location.add(retail)
                if ul.default_location is None:
                    ul.default_location = all_retails[0]
                    ul.save(update_fields=['default_location'])
        return UserLocation.objects.filter(user=user).order_by('id')
    
@api_view(['GET'])
def get_customer_type(request):
    customer_type_dict_list = [{"code": code, "name": name} for code, name in CUSTOMER_TYPE]
    return Response(customer_type_dict_list)

@api_view(['GET'])
def get_states_of_india(request):
    states_dict_list = [{"code": code, "name": name} for code, name in STATES_OF_INDIA]
    return Response(states_dict_list)

@api_view(['POST', 'DELETE'])
def manage_ledger_role(request, pk):
    """
    POST   /api/ledger/<pk>/roles/  {"role": "CO"}  → add role
    DELETE /api/ledger/<pk>/roles/  {"role": "CO"}  → remove role
    """
    try:
        ledger = Ledger.objects.get(pk=pk)
    except Ledger.DoesNotExist:
        return Response({'error': 'Ledger not found'}, status=status.HTTP_404_NOT_FOUND)

    if ledger.is_system:
        return Response({'error': 'System-created ledgers cannot be modified.'}, status=status.HTTP_403_FORBIDDEN)

    role = request.data.get('role')
    valid_codes = {code for code, _ in TYPE_CHOICES}
    if not role or role not in valid_codes:
        return Response(
            {'error': f'Invalid role. Must be one of: {", ".join(sorted(valid_codes))}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if request.method == 'POST':
        is_first = not ledger.roles.exists()
        _, created = LedgerRole.objects.get_or_create(
            ledger=ledger, role=role,
            defaults={'is_primary': is_first},
        )
        return Response(
            {'detail': 'Role added' if created else 'Role already exists',
             'roles': list(ledger.roles.values('role', 'is_primary'))},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    if request.method == 'DELETE':
        role_obj = LedgerRole.objects.filter(ledger=ledger, role=role).first()
        if not role_obj:
            return Response({'detail': 'Role not found'}, status=status.HTTP_200_OK)
        if role_obj.is_primary:
            return Response(
                {'error': 'Cannot remove the primary role. Set another role as primary first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        role_obj.delete()
        return Response(
            {'detail': 'Role removed',
             'roles': list(ledger.roles.values('role', 'is_primary'))},
            status=status.HTTP_200_OK,
        )


@api_view(['PATCH'])
def set_primary_ledger_role(request, pk):
    """
    PATCH /api/ledger/<pk>/roles/primary/  {"role": "CO"}
    Marks the given role as primary (clears is_primary on all others).
    """
    ledger = get_object_or_404(Ledger, pk=pk)
    if ledger.is_system:
        return Response({'error': 'System-created ledgers cannot be modified.'}, status=status.HTTP_403_FORBIDDEN)
    role = request.data.get('role')
    valid_codes = {code for code, _ in TYPE_CHOICES}
    if not role or role not in valid_codes:
        return Response(
            {'error': f'Invalid role. Must be one of: {", ".join(sorted(valid_codes))}'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not LedgerRole.objects.filter(ledger=ledger, role=role).exists():
        return Response(
            {'error': f'Ledger does not have role {role}. Add the role first.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    LedgerRole.objects.filter(ledger=ledger).update(is_primary=False)
    LedgerRole.objects.filter(ledger=ledger, role=role).update(is_primary=True)
    return Response(
        {'detail': f'{role} is now the primary role.',
         'roles': list(ledger.roles.values('role', 'is_primary'))},
    )


class LedgerDocumentListCreate(ListCreateAPIView):
    from rest_framework.parsers import MultiPartParser
    parser_classes = [MultiPartParser]

    def get_serializer_class(self):
        from contacts.serializers import LedgerDocumentSerializer
        return LedgerDocumentSerializer

    def get_queryset(self):
        ldgr_id = self.request.query_params.get('ldgr')
        if ldgr_id:
            return Documents.objects.filter(ldgr_id=ldgr_id).order_by('-uploaded_at')
        return Documents.objects.none()


class LedgerDocumentDelete(APIView):
    def delete(self, request, pk):
        try:
            doc = Documents.objects.get(pk=pk)
            doc.document.delete(save=False)
            doc.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Documents.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class AccountTreeViewSet(viewsets.ViewSet):
    """
    Returns the account tree structure including child accounts and associated ledgers.
    """
    def list(self, request):
        root_accounts = Account.objects.filter(parent=None)  # Get only top-level accounts
        serializer = AccountSerializer(root_accounts, many=True)
        return Response(serializer.data)


@api_view(['GET'])
def ledger_tds_info(request, pk):
    from contacts.models import Ledger
    ledger = get_object_or_404(Ledger, pk=pk)
    if not ledger.tds_applicable or not ledger.tds_section:
        return Response({'tds_applicable': False})
    s = ledger.tds_section
    has_pan = bool(ledger.pan)
    if not has_pan:
        rate = s.rate_no_pan
    elif ledger.tds_deductor_type == 'CO':
        rate = s.rate_company
    else:
        rate = s.rate_individual
    return Response({
        'tds_applicable': True,
        'section_id': s.id,
        'section_code': s.section_code,
        'description': s.description,
        'rate': float(rate),
        'has_pan': has_pan,
        'threshold_single': float(s.threshold_single) if s.threshold_single else None,
        'threshold_annual': float(s.threshold_annual) if s.threshold_annual else None,
    })


# ── CRM — Birthday & Anniversary Occasions ────────────────────────────────────

@api_view(['GET'])
def crm_occasions(request):
    """
    Returns customers (type=CO) whose birthday (dob) or anniversary
    matches today's month/day, and those whose occasion falls in the
    next `days` days (default=30).

    Response:
      { today: [...], upcoming: [...] }
    Each row: { id, name, mobile, occasion, date_str, days_until, message, wa_url }
    """
    import urllib.parse
    from datetime import date
    from contacts.crm_utils import clean_mobile, get_mobile, days_until_this_year, build_message

    try:
        days = int(request.query_params.get('days', 30))
        days = min(max(days, 1), 365)
    except (ValueError, TypeError):
        days = 30

    retail      = getattr(request, 'retail', None)
    retail_name = retail.retail_name if retail else "Us"
    today       = date.today()

    customers = Ledger.objects.filter(
        roles__role='CO'
    ).distinct().exclude(
        dob__isnull=True, anniversary__isnull=True
    ).only('id', 'ac_name', 'salutation', 'mobile1', 'mobile2', 'mobile3', 'phone1', 'dob', 'anniversary')

    today_list    = []
    upcoming_list = []

    for ldgr in customers:
        name   = ldgr.ac_name.strip()
        mobile = get_mobile(ldgr)
        occasions_to_check = []

        if ldgr.dob:
            occasions_to_check.append(('birthday', ldgr.dob.month, ldgr.dob.day))
        if ldgr.anniversary:
            occasions_to_check.append(('anniversary', ldgr.anniversary.month, ldgr.anniversary.day))

        for occasion, month, day in occasions_to_check:
            d_until = days_until_this_year(month, day, today)
            try:
                date_str = today.replace(month=month, day=day).strftime('%d %b')
            except ValueError:
                date_str = "28 Feb"

            message = build_message(name, occasion, retail_name)
            wa_url  = None
            if mobile:
                wa_url = f"https://wa.me/91{mobile}?text={urllib.parse.quote(message)}"

            row = {
                'id':         ldgr.id,
                'name':       name,
                'mobile':     mobile,
                'occasion':   occasion,
                'date_str':   date_str,
                'days_until': d_until,
                'message':    message,
                'wa_url':     wa_url,
            }

            if d_until == 0:
                today_list.append(row)
            elif d_until <= days:
                upcoming_list.append(row)

    upcoming_list.sort(key=lambda r: r['days_until'])

    return Response({
        'today':          today_list,
        'upcoming':       upcoming_list,
        'today_count':    len(today_list),
        'upcoming_count': len(upcoming_list),
    })


# ── Ledger Master CSV Template & Upload ───────────────────────────────────────

_COMMON_COLS = [
    'ac_name', 'display_name', 'ac_group_name',
    'add1', 'add2', 'city', 'state', 'pincode',
    'phone1', 'mobile1', 'email', 'pan', 'gst', 'remarks',
]

_ROLE_COLS = ['primary_role', 'secondary_roles']

_TEMPLATE_COLS = {
    'CO':  _COMMON_COLS + ['salutation', 'dob', 'anniversary', 'mobile2', 'mobile3',
                           'aadhar', 'ship_add1', 'ship_city', 'ship_state', 'ship_pincode'] + _ROLE_COLS,
    'DL':  _COMMON_COLS + ['dob', 'anniversary', 'mobile2'] + _ROLE_COLS,
    'KR':  _COMMON_COLS + ['mobile2'] + _ROLE_COLS,
    'VD':  _COMMON_COLS + _ROLE_COLS,
    'SC':  _COMMON_COLS + _ROLE_COLS,
    'SD':  _COMMON_COLS + _ROLE_COLS,
    'BA':  _COMMON_COLS + ['cheque_no'] + _ROLE_COLS,
    'EXP': ['ac_name', 'ac_group_name', 'remarks'] + _ROLE_COLS,
    'INC': ['ac_name', 'ac_group_name', 'remarks'] + _ROLE_COLS,
    'OTH': _COMMON_COLS + _ROLE_COLS,
}

_TEMPLATE_LABELS = {
    'CO': 'customer', 'DL': 'dealer', 'KR': 'karigar',
    'VD': 'vendor',   'SC': 'supplier', 'SD': 'sundry_debtor', 'BA': 'bank',
    'EXP': 'expense', 'INC': 'income',  'OTH': 'others',
}

_SAMPLE_ROWS = {
    'CO': [
        {'ac_name': 'Ravi Kumar',   'display_name': 'Ravi K',  'ac_group_name': 'Sundry Debtors',
         'add1': '123 Main Street', 'add2': 'Near Clock Tower', 'city': 'Mumbai',
         'state': 'Maharashtra',    'pincode': '400001',        'phone1': '022-12345678',
         'mobile1': '9876543210',   'email': 'ravi@email.com',  'pan': 'ABCDE1234F',
         'gst': '27ABCDE1234F1Z5',  'remarks': 'Sample — delete before uploading',
         'salutation': 'Mr',        'dob': '15/08/1985',        'anniversary': '20/02/2010',
         'mobile2': '9876543211',   'mobile3': '',              'aadhar': '123456789012',
         'ship_add1': '456 Park Ave','ship_city': 'Mumbai',     'ship_state': 'Maharashtra',
         'ship_pincode': '400001',  'primary_role': 'CO',       'secondary_roles': ''},
        {'ac_name': 'Priya Shah',   'display_name': 'Priya S', 'ac_group_name': 'Sundry Debtors',
         'add1': '456 Park Avenue', 'add2': '',                 'city': 'Delhi',
         'state': 'Delhi',          'pincode': '110001',        'phone1': '',
         'mobile1': '9123456789',   'email': 'priya@email.com', 'pan': 'FGHIJ5678K',
         'gst': '',                 'remarks': 'Sample 2 — delete before uploading',
         'salutation': 'Mrs',       'dob': '03/04/1990',        'anniversary': '14/11/2015',
         'mobile2': '',             'mobile3': '',              'aadhar': '',
         'ship_add1': '',           'ship_city': '',            'ship_state': '',
         'ship_pincode': '',        'primary_role': 'CO',       'secondary_roles': ''},
    ],
    'DL': [
        {'ac_name': 'Mehta Jewellery', 'display_name': 'Mehta', 'ac_group_name': 'Sundry Debtors',
         'add1': '78 Diamond Street',  'add2': '',              'city': 'Jaipur',
         'state': 'Rajasthan',         'pincode': '302001',     'phone1': '0141-2345678',
         'mobile1': '9988776655',      'email': 'mehta@jwl.in', 'pan': 'UVWXY3456Z',
         'gst': '08UVWXY3456Z1Z5',     'remarks': 'Sample — delete before uploading',
         'dob': '10/05/1975',          'anniversary': '25/01/2000', 'mobile2': '',
         'primary_role': 'DL',         'secondary_roles': ''},
    ],
    'KR': [
        {'ac_name': 'Suresh Gold Works',   'display_name': 'Suresh GW', 'ac_group_name': 'Karigars',
         'add1': '45 Gold Lane',           'add2': '',                   'city': 'Surat',
         'state': 'Gujarat',              'pincode': '395001',           'phone1': '0261-2345678',
         'mobile1': '9811234567',          'email': 'suresh@gw.in',      'pan': 'PQRST9012U',
         'gst': '',                        'remarks': 'Sample — delete before uploading',
         'mobile2': '9811234568',          'primary_role': 'KR',         'secondary_roles': ''},
        {'ac_name': 'Ramesh Silversmiths', 'display_name': '',           'ac_group_name': 'Karigars',
         'add1': '67 Silver Street',       'add2': '',                   'city': 'Ahmedabad',
         'state': 'Gujarat',              'pincode': '380001',           'phone1': '',
         'mobile1': '9921234567',          'email': '',                  'pan': '',
         'gst': '',                        'remarks': 'Sample 2 — delete before uploading',
         'mobile2': '',                    'primary_role': 'KR',         'secondary_roles': ''},
    ],
    'VD': [
        {'ac_name': 'Sharma Diamond Suppliers', 'display_name': 'Sharma DS', 'ac_group_name': 'Sundry Creditors',
         'add1': '55 Gem Street',               'add2': '',                   'city': 'Surat',
         'state': 'Gujarat',                   'pincode': '395001',           'phone1': '0261-9876543',
         'mobile1': '9876543210',               'email': 'sharma@gems.in',    'pan': 'ABCVD1234Z',
         'gst': '24ABCVD1234Z1Z5',              'remarks': 'Sample — delete before uploading',
         'primary_role': 'VD',                  'secondary_roles': ''},
        {'ac_name': 'Kapoor Metal Works',       'display_name': 'Kapoor MW',  'ac_group_name': 'Sundry Creditors',
         'add1': '88 Metal Lane',               'add2': '',                   'city': 'Mumbai',
         'state': 'Maharashtra',                'pincode': '400001',           'phone1': '',
         'mobile1': '9823456789',               'email': 'kapoor@metals.in',  'pan': 'LMNVD5678Q',
         'gst': '',                             'remarks': 'Sample 2 — delete before uploading',
         'primary_role': 'VD',                  'secondary_roles': 'SC'},
    ],
    'SC': [
        {'ac_name': 'ABC Gold Suppliers',  'display_name': 'ABC Gold',   'ac_group_name': 'Sundry Creditors',
         'add1': '101 Trade Centre',       'add2': '',                   'city': 'Mumbai',
         'state': 'Maharashtra',           'pincode': '400001',          'phone1': '022-87654321',
         'mobile1': '9876543210',          'email': 'abc@gold.in',       'pan': 'MFGST1234Z',
         'gst': '27MFGST1234Z1Z5',         'remarks': 'Sample — delete before uploading',
         'primary_role': 'SC',             'secondary_roles': ''},
        {'ac_name': 'XYZ Metals Pvt Ltd',  'display_name': '',           'ac_group_name': 'Sundry Creditors',
         'add1': '202 Metal House',        'add2': '',                   'city': 'Delhi',
         'state': 'Delhi',                 'pincode': '110001',          'phone1': '',
         'mobile1': '9123456789',          'email': 'xyz@metals.in',     'pan': 'LMNOP5678Q',
         'gst': '09LMNOP5678Q1Z5',         'remarks': 'Sample 2 — delete before uploading',
         'primary_role': 'SC',             'secondary_roles': ''},
    ],
    'SD': [
        {'ac_name': 'Patel Stores',        'display_name': 'Patel',      'ac_group_name': 'Sundry Debtors',
         'add1': '33 Market Road',         'add2': '',                   'city': 'Surat',
         'state': 'Gujarat',              'pincode': '395002',           'phone1': '',
         'mobile1': '9978563412',          'email': 'patel@stores.in',   'pan': 'ABCDE5678F',
         'gst': '',                        'remarks': 'Sample — delete before uploading',
         'primary_role': 'SD',             'secondary_roles': ''},
    ],
    'BA': [
        {'ac_name': 'HDFC Current Account', 'display_name': 'HDFC CA',  'ac_group_name': 'Bank Accounts',
         'add1': 'HDFC Bank, Fort Branch',  'add2': '',                  'city': 'Mumbai',
         'state': 'Maharashtra',            'pincode': '400001',         'phone1': '1800-202-6161',
         'mobile1': '',                     'email': '',                 'pan': '',
         'gst': '',                         'remarks': 'Sample — delete before uploading',
         'cheque_no': '1234567890',         'primary_role': 'BA',        'secondary_roles': ''},
    ],
    'EXP': [
        {'ac_name': 'Office Rent',          'ac_group_name': 'Indirect Expenses', 'remarks': 'Sample — delete before uploading',         'primary_role': 'EXP', 'secondary_roles': ''},
        {'ac_name': 'Electricity Charges',  'ac_group_name': 'Indirect Expenses', 'remarks': 'Sample 2 — delete before uploading',       'primary_role': 'EXP', 'secondary_roles': ''},
    ],
    'INC': [
        {'ac_name': 'Making Charges Income','ac_group_name': 'Indirect Income',   'remarks': 'Sample — delete before uploading',         'primary_role': 'INC', 'secondary_roles': ''},
    ],
    'OTH': [
        {'ac_name': 'Tax Payable',          'display_name': '',                   'ac_group_name': 'Current Liabilities',
         'add1': '',                        'add2': '',                           'city': '',
         'state': '',                       'pincode': '',                        'phone1': '',
         'mobile1': '',                     'email': '',                          'pan': '',
         'gst': '',                         'remarks': 'Sample — delete before uploading',
         'primary_role': 'OTH',             'secondary_roles': ''},
    ],
}

_PERSONAL_TYPES = {'CO', 'DL', 'KR', 'VD', 'SC', 'SD', 'REF', 'MLT', 'HM'}

_TYPE_MAP = {
    'customer': 'CO', 'dealer': 'DL', 'karigar': 'KR',
    'vendor': 'VD', 'vendors': 'VD',
    'cash': 'CA', 'bank': 'BA',
    'sundry creditors': 'SC', 'sundrycreditors': 'SC', 'supplier': 'SC',
    'sundry debtors': 'SD', 'sundrydebtors': 'SD',
    'refinery': 'REF',
    'melting': 'MLT', 'melting house': 'MLT', 'meltinghouse': 'MLT',
    'expenses': 'EXP', 'expense': 'EXP',
    'income': 'INC',
    'hallmark': 'HM',
    'others': 'OTH', 'other': 'OTH',
    'co': 'CO', 'dl': 'DL', 'kr': 'KR', 'ca': 'CA', 'ba': 'BA',
    'vd': 'VD', 'sc': 'SC', 'sd': 'SD', 'ref': 'REF', 'mlt': 'MLT', 'exp': 'EXP',
    'inc': 'INC', 'hm': 'HM', 'oth': 'OTH', 'su': 'SC',
}

_DATE_FORMATS = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y']


def _parse_date(val):
    """Try multiple date formats; return date object or None."""
    if not val or not val.strip():
        return None
    v = val.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    return None


def _resolve_account_group(name):
    """Look up an Account by name (case-insensitive). Return instance or None."""
    if not name or not name.strip():
        return None
    return Account.objects.filter(name__iexact=name.strip()).first()


class LedgerTemplateDownloadView(APIView):
    """
    GET /contacts/api/ledger/template/?type=CO
    Returns a CSV file with correct columns and 2 sample data rows.
    """
    def get(self, request):
        ledger_type = request.query_params.get('type', 'CO').upper()
        if ledger_type not in _TEMPLATE_COLS:
            return Response({'error': f'Unknown type. Choose from: {", ".join(_TEMPLATE_COLS)}'}, status=400)

        cols      = _TEMPLATE_COLS[ledger_type]
        samples   = _SAMPLE_ROWS.get(ledger_type, [])
        type_name = _TEMPLATE_LABELS.get(ledger_type, ledger_type.lower())

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=cols, extrasaction='ignore', lineterminator='\r\n')
        writer.writeheader()
        # Write comment row to signal sample data
        writer.writerow({cols[0]: '# --- SAMPLE ROWS — delete this row and the rows below before uploading ---'})
        for row in samples:
            writer.writerow({col: row.get(col, '') for col in cols})

        csv_content = output.getvalue()
        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="ledger_template_{type_name}.csv"'
        return response


class LedgerCSVUploadView(APIView):
    """
    POST /contacts/api/ledger/csv-upload/?type=CO
    Accepts a filled-in ledger template CSV. Upserts ledgers by ac_name.
    Skips rows starting with '#'. Returns { created, updated, errors }.

    Optimised: pre-loads all lookups (account groups, existing ledgers, existing
    roles) in 3 queries, then uses bulk_update + bulk_create to avoid N+1 query
    overhead on large imports.
    """
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)

        ledger_type = (request.query_params.get('type') or '').upper()
        valid_types = set(_TEMPLATE_COLS.keys())
        if ledger_type not in valid_types:
            return Response({'error': f'Provide ?type= param. Valid: {", ".join(sorted(valid_types))}'}, status=400)

        try:
            decoded = file.read().decode('utf-8-sig')
        except Exception as e:
            return Response({'error': str(e)}, status=400)

        created_count = updated_count = 0
        errors = []
        valid_codes = {code for code, _ in TYPE_CHOICES}

        _BULK_UPDATE_FIELDS = [
            'ac_group', 'display_name', 'add1', 'add2', 'city', 'state',
            'pincode', 'phone1', 'mobile1', 'mobile2', 'mobile3', 'email',
            'pan', 'gst', 'remarks', 'cheque_no',
            'ship_add1', 'ship_city', 'ship_state', 'ship_pincode',
            'salutation', 'aadhar', 'passport', 'dl_no', 'dob', 'anniversary',
        ]

        with transaction.atomic():
            # ── Pre-load all lookup data (3 queries total, no N+1) ────────────
            # Map: lower(ac_name) → Ledger obj
            existing_map = {ldgr.ac_name.lower(): ldgr for ldgr in Ledger.objects.all()}
            # Map: ledger_id → set of assigned role codes
            roles_map = {}
            for lr in LedgerRole.objects.values('ledger_id', 'role'):
                roles_map.setdefault(lr['ledger_id'], set()).add(lr['role'])
            # Set of lower-cased names for non-CO ledgers (for conflict detection)
            non_customer_lower = {
                ldgr.ac_name.lower()
                for ldgr in existing_map.values()
                if 'CO' not in roles_map.get(ldgr.id, set())
            }
            # Map: lower(group name) → Account obj
            ag_map = {ag.name.lower(): ag for ag in Account.objects.all()}

            # ── Parse rows into two buckets ───────────────────────────────────
            to_create = []   # list of (ac_name, fields_dict, row_type, secondary_codes)
            to_update = []   # list of (ledger_obj, row_type, secondary_codes)

            try:
                reader = csv.DictReader(io.StringIO(decoded))
                for i, row in enumerate(reader, start=2):
                    try:
                        first_val = next(iter(row.values()), '') or ''
                        if first_val.strip().startswith('#'):
                            continue

                        ac_name = (row.get('ac_name') or '').strip()
                        if not ac_name:
                            continue

                        # Resolve account group from pre-loaded map
                        ag_name_raw = (row.get('ac_group_name') or '').strip()
                        ac_group = ag_map.get(ag_name_raw.lower()) if ag_name_raw else None
                        if not ac_group and ag_name_raw:
                            errors.append(
                                f"Row {i}: '{ac_name}' — group '{ag_name_raw}' "
                                f"not found in Chart of Accounts; imported with no group."
                            )

                        # Resolve primary role
                        raw_primary = (row.get('primary_role') or row.get('type') or '').strip()
                        row_type = _TYPE_MAP.get(raw_primary.lower(), raw_primary.upper())
                        if row_type not in valid_codes:
                            row_type = ledger_type

                        # Resolve secondary roles
                        raw_secondary = (row.get('secondary_roles') or '').strip()
                        secondary_codes = []
                        if raw_secondary:
                            for part in raw_secondary.split(','):
                                part = part.strip()
                                code = _TYPE_MAP.get(part.lower(), part.upper())
                                if code in valid_codes and code != row_type:
                                    secondary_codes.append(code)

                        is_personal = row_type in _PERSONAL_TYPES

                        fields = {
                            'ac_group':     ac_group,
                            'display_name': (row.get('display_name') or '').strip()[:100],
                            'add1':         (row.get('add1') or '').strip()[:200],
                            'add2':         (row.get('add2') or '').strip()[:200],
                            'city':         (row.get('city') or '').strip()[:100],
                            'state':        (row.get('state') or '').strip()[:100],
                            'pincode':      (row.get('pincode') or '').strip()[:10],
                            'phone1':       (row.get('phone1') or '').strip()[:30],
                            'mobile1':      (row.get('mobile1') or '').strip()[:20],
                            'mobile2':      (row.get('mobile2') or '').strip()[:20],
                            'mobile3':      (row.get('mobile3') or '').strip()[:20],
                            'email':        (row.get('email') or '').strip()[:100],
                            'pan':          (row.get('pan') or '').strip()[:20],
                            'gst':          (row.get('gst') or '').strip()[:20],
                            'remarks':      (row.get('remarks') or '').strip()[:200],
                            'cheque_no':    (row.get('cheque_no') or '').strip()[:30],
                            'ship_add1':    (row.get('ship_add1') or '').strip()[:200],
                            'ship_city':    (row.get('ship_city') or '').strip()[:100],
                            'ship_state':   (row.get('ship_state') or '').strip()[:100],
                            'ship_pincode': (row.get('ship_pincode') or '').strip()[:10],
                        }

                        if is_personal:
                            fields['salutation'] = (row.get('salutation') or '').strip()[:20]
                            fields['aadhar']     = (row.get('aadhar') or '').strip()[:20]
                            fields['passport']   = (row.get('passport') or '').strip()[:20]
                            fields['dl_no']      = (row.get('dl_no') or '').strip()[:30]
                            dob_raw = row.get('dob', '')
                            ann_raw = row.get('anniversary', '')
                            dob_parsed = _parse_date(dob_raw)
                            ann_parsed = _parse_date(ann_raw)
                            if dob_raw.strip() and not dob_parsed:
                                errors.append(f"Row {i}: '{ac_name}' — unrecognised dob format '{dob_raw}'; skipped.")
                            if ann_raw.strip() and not ann_parsed:
                                errors.append(f"Row {i}: '{ac_name}' — unrecognised anniversary format '{ann_raw}'; skipped.")
                            fields['dob']         = dob_parsed
                            fields['anniversary'] = ann_parsed
                        else:
                            fields.update({'salutation': '', 'aadhar': '', 'passport': '',
                                           'dl_no': '', 'dob': None, 'anniversary': None})

                        existing = existing_map.get(ac_name.lower())
                        if not existing and row_type != 'CO' and ac_name.lower() in non_customer_lower:
                            errors.append(
                                f"Row {i}: '{ac_name}' — a non-customer ledger with this name already exists. "
                                f"Duplicate names are not allowed for non-customer ledgers."
                            )
                            continue

                        if existing:
                            for k, v in fields.items():
                                setattr(existing, k, v)
                            to_update.append((existing, row_type, secondary_codes))
                        else:
                            to_create.append((ac_name, fields, row_type, secondary_codes))

                    except Exception as e:
                        errors.append(f"Row {i}: {str(e)}")

            except Exception as e:
                return Response({'error': str(e)}, status=400)

            # ── Bulk-create new ledgers ───────────────────────────────────────
            if to_create:
                new_names = [ac_name for ac_name, _, _, _ in to_create]
                new_objs  = [Ledger(ac_name=ac_name, **fields) for ac_name, fields, _, _ in to_create]
                Ledger.objects.bulk_create(new_objs)
                # Re-fetch to get DB-assigned PKs (needed for role creation)
                created_map = {
                    ldgr.ac_name.lower(): ldgr
                    for ldgr in Ledger.objects.filter(ac_name__in=new_names)
                }
                new_roles = []
                for ac_name, _, row_type, secondary_codes in to_create:
                    ldgr = created_map.get(ac_name.lower())
                    if ldgr:
                        new_roles.append(LedgerRole(ledger=ldgr, role=row_type, is_primary=True))
                        for sec in secondary_codes:
                            new_roles.append(LedgerRole(ledger=ldgr, role=sec, is_primary=False))
                if new_roles:
                    LedgerRole.objects.bulk_create(new_roles, ignore_conflicts=True)
                created_count = len(to_create)

            # ── Bulk-update existing ledgers ──────────────────────────────────
            if to_update:
                update_objs = [ldgr for ldgr, _, _ in to_update]
                Ledger.objects.bulk_update(update_objs, _BULK_UPDATE_FIELDS)
                # Add any missing roles (only inserts — never removes existing roles)
                missing_roles = []
                for ldgr, row_type, secondary_codes in to_update:
                    assigned = roles_map.get(ldgr.id, set())
                    if row_type not in assigned:
                        missing_roles.append(
                            LedgerRole(ledger=ldgr, role=row_type, is_primary=not assigned)
                        )
                    for sec in secondary_codes:
                        if sec not in assigned:
                            missing_roles.append(LedgerRole(ledger=ldgr, role=sec, is_primary=False))
                if missing_roles:
                    LedgerRole.objects.bulk_create(missing_roles, ignore_conflicts=True)
                updated_count = len(to_update)

        return Response({'created': created_count, 'updated': updated_count, 'errors': errors})