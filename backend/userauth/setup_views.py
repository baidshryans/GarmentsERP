"""
ERP Setup & Reset API views.

Endpoints:
  GET  /userauth/api/setup/status/          — is the ERP set up?
  POST /userauth/api/setup/seed-accounts/   — seed account groups
  POST /userauth/api/setup/seed-tds-tcs/    — seed TDS & TCS sections + ledgers
  POST /userauth/api/setup/reset-erp/       — truncate all non-user tables
"""
from django.apps import apps
from django.contrib.auth import authenticate
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from accounting.models import Account
from mastersconfig.models import (
    RetailMaster,
    CompanyMaster,
    BranchMaster,
    GSTINMaster,
    State,
)


# ── Tables that must NEVER be truncated ────────────────────────────────────────
PROTECTED_TABLES = {
    # Django internals
    'django_migrations',
    'django_content_type',
    'django_session',
    'django_admin_log',
    # Auth / users
    'auth_user',
    'auth_group',
    'auth_permission',
    'auth_group_permissions',
    'auth_user_groups',
    'auth_user_user_permissions',
    'authtoken_token',
    # Custom RBAC
    'userauth_role',
    'userauth_permission',
    'userauth_userrole',
    # User-location mapping
    'contacts_userlocation',
    'contacts_userlocation_location',
    # Easy-audit
    'easyaudit_crudevent',
    'easyaudit_loginevent',
    'easyaudit_requestevent',
    # SQLite internals
    'sqlite_sequence',
}


def _safe_count(model):
    """Count model rows; return 0 if the table doesn't exist yet."""
    try:
        return model.objects.count()
    except Exception:
        return 0


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def setup_status(request):
    """Return current setup state so the wizard knows which steps are done."""
    states_count = _safe_count(State)
    account_groups_count = _safe_count(Account)
    retails_count = _safe_count(RetailMaster)
    company_count = _safe_count(CompanyMaster)
    branch_count = _safe_count(BranchMaster)
    gstin_count = _safe_count(GSTINMaster)

    from mastersconfig.models import TDSSectionMaster, TCSSectionMaster
    tds_count = _safe_count(TDSSectionMaster)
    tcs_count = _safe_count(TCSSectionMaster)

    from mastersconfig.models import Hsn, Item, FiscalYearMaster
    hsn_count = _safe_count(Hsn)
    item_count = _safe_count(Item)
    fy_count = _safe_count(FiscalYearMaster)

    return Response({
        'states_seeded': states_count >= 35,
        'states_count': states_count,
        'company_created': company_count > 0,
        'company_count': company_count,
        'branch_created': branch_count > 0,
        'branch_count': branch_count,
        'gstin_created': gstin_count > 0,
        'gstin_count': gstin_count,
        'account_groups_seeded': account_groups_count > 5,
        'account_groups_count': account_groups_count,
        'retails_created': retails_count > 0,
        'retails_count': retails_count,
        'tds_tcs_seeded': tds_count > 0 and tcs_count > 0,
        'tds_count': tds_count,
        'tcs_count': tcs_count,
        'fiscal_years_created': fy_count > 0,
        'fiscal_years_count': fy_count,
        'masters_uploaded': hsn_count > 0 or item_count > 0,
        'hsn_count': hsn_count,
        'item_count': item_count,
        'is_setup_complete': (
            company_count > 0
            and branch_count > 0
            and gstin_count > 0
            and account_groups_count > 5
            and retails_count > 0
            and tds_count > 0
            and fy_count > 0
        ),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_user_retails(request):
    """
    Ensure the requesting user has a UserLocation record covering all existing
    retails.  Called by the setup wizard Finish step so the retail selector is
    populated immediately after setup.
    """
    from mastersconfig.models import RetailMaster
    from contacts.models import UserLocation

    retails = list(RetailMaster.objects.all())
    if not retails:
        return Response({'detail': 'No retails found.', 'synced': 0})

    ul, _ = UserLocation.objects.get_or_create(user=request.user)
    for retail in retails:
        ul.location.add(retail)
    if ul.default_location is None:
        ul.default_location = retails[0]
        ul.save(update_fields=['default_location'])

    return Response({'detail': f'Synced {len(retails)} retail(s).', 'synced': len(retails)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def seed_states(request):
    """Run the setup_states management command to populate all Indian states/UTs."""
    from django.core.management import call_command
    from io import StringIO

    try:
        out = StringIO()
        call_command('setup_states', stdout=out)
        return Response({'detail': out.getvalue(), 'success': True})
    except Exception as e:
        return Response(
            {'detail': str(e), 'success': False},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def seed_account_groups(request):
    """Run the setup_account_groups management command."""
    from django.core.management import call_command
    from io import StringIO

    out = StringIO()
    call_command('setup_account_groups', stdout=out)
    return Response({'detail': out.getvalue(), 'success': True})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def seed_tds_tcs(request):
    """Run the setup_tds_initial_data management command and seed default purities."""
    from django.core.management import call_command
    from io import StringIO

    out = StringIO()
    call_command('setup_tds_initial_data', stdout=out)

    # Seed default purity masters (idempotent)
    from goldrates.models import PurityMaster
    DEFAULT_PURITIES = [
        {'purity': '99.99', 'gw_per': 99.99},
        {'purity': '99.9',  'gw_per': 99.90},
        {'purity': '99.5',  'gw_per': 99.50},
        {'purity': '22K',   'gw_per': 91.60},
        {'purity': '18K',   'gw_per': 75.00},
        {'purity': '14K',   'gw_per': 58.50},
    ]
    for p in DEFAULT_PURITIES:
        PurityMaster.objects.get_or_create(purity=p['purity'], defaults={'gw_per': p['gw_per']})

    # Seed default HSN master (idempotent)
    from mastersconfig.models import Hsn
    DEFAULT_HSNS = [
        {'hsn_no': '711319',   'description': 'Jewellery Plain or Studded',      'cgst': 1.500, 'sgst': 1.500, 'igst': 3.000},
        {'hsn_no': '710110',   'description': 'Pearls in Loose Form',            'cgst': 1.500, 'sgst': 1.500, 'igst': 3.000},
        {'hsn_no': '71023910', 'description': 'Cut & Polished Diamonds',         'cgst': 0.750, 'sgst': 0.750, 'igst': 1.500},
        {'hsn_no': '710490',   'description': 'Colored Gem Stone',               'cgst': 1.500, 'sgst': 1.500, 'igst': 3.000},
        {'hsn_no': '710692',   'description': 'Silver Bar & Coins',              'cgst': 1.500, 'sgst': 1.500, 'igst': 3.000},
        {'hsn_no': '71081300', 'description': 'Gold Bullion & Coins',            'cgst': 1.500, 'sgst': 1.500, 'igst': 3.000},
        {'hsn_no': '711411',   'description': 'Gold & Silver Articles',          'cgst': 1.500, 'sgst': 1.500, 'igst': 3.000},
        {'hsn_no': '71189000', 'description': 'Gold Coin',                       'cgst': 1.500, 'sgst': 1.500, 'igst': 3.000},
        {'hsn_no': '710310',   'description': 'Precious, semi precious stones',  'cgst': 1.500, 'sgst': 1.500, 'igst': 3.000},
        {'hsn_no': '71031041', 'description': 'Ruby',                            'cgst': 1.500, 'sgst': 1.500, 'igst': 3.000},
        {'hsn_no': '71031031', 'description': 'Emerald',                         'cgst': 1.500, 'sgst': 1.500, 'igst': 3.000},
        {'hsn_no': '71049120', 'description': 'Synthetic stone',                 'cgst': 1.500, 'sgst': 1.500, 'igst': 3.000},
    ]
    for h in DEFAULT_HSNS:
        Hsn.objects.get_or_create(
            hsn_no=h['hsn_no'],
            defaults={
                'description': h['description'],
                'hsn_type': 'GD',
                'cgst': h['cgst'],
                'sgst': h['sgst'],
                'igst': h['igst'],
            },
        )

    return Response({'detail': out.getvalue(), 'success': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def setup_rollback(request):
    """
    Wipe all setup data when a user abandons the wizard before completion.

    Truncates every application table (except protected user/auth/migration tables)
    AND the easyaudit_* tables so the audit trail of the failed setup is also cleared.
    Refuses to run if setup is already complete.
    """
    # Refuse if setup is already complete
    if (
        CompanyMaster.objects.exists()
        and BranchMaster.objects.exists()
        and GSTINMaster.objects.exists()
        and RetailMaster.objects.exists()
    ):
        from mastersconfig.models import FiscalYearMaster
        if (
            FiscalYearMaster.objects.exists()
            and Account.objects.count() > 5
        ):
            return Response(
                {'error': 'Setup is already complete; rollback not allowed.'},
                status=status.HTTP_403_FORBIDDEN,
            )

    # Easy-audit tables MUST be truncated as part of rollback
    rollback_protected = PROTECTED_TABLES - {
        'easyaudit_crudevent',
        'easyaudit_loginevent',
        'easyaudit_requestevent',
    }

    all_tables = set(connection.introspection.table_names())
    tables_to_truncate = sorted(all_tables - rollback_protected)

    truncated = []
    errors = []

    with connection.cursor() as cursor:
        if connection.vendor == 'sqlite':
            cursor.execute('PRAGMA foreign_keys = OFF;')
        elif connection.vendor == 'postgresql':
            cursor.execute('SET session_replication_role = replica;')

        for table in tables_to_truncate:
            try:
                if connection.vendor == 'sqlite':
                    cursor.execute(f'DELETE FROM "{table}";')
                    cursor.execute(
                        f"DELETE FROM sqlite_sequence WHERE name='{table}';"
                    )
                else:
                    cursor.execute(f'TRUNCATE TABLE "{table}" CASCADE;')
                truncated.append(table)
            except Exception as e:
                errors.append(f'{table}: {str(e)}')

        if connection.vendor == 'sqlite':
            cursor.execute('PRAGMA foreign_keys = ON;')
        elif connection.vendor == 'postgresql':
            cursor.execute('SET session_replication_role = DEFAULT;')

    return Response({
        'success': True,
        'truncated_count': len(truncated),
        'truncated': truncated,
        'errors': errors,
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def reset_erp(request):
    """
    Truncate every application table except user/auth/migration tables.
    Requires the current user's password in the request body for confirmation.
    """
    password = request.data.get('password')
    if not password:
        return Response(
            {'error': 'Password is required to reset the ERP.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(username=request.user.username, password=password)
    if user is None:
        return Response(
            {'error': 'Incorrect password.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Collect all application tables
    all_tables = set(connection.introspection.table_names())
    tables_to_truncate = sorted(all_tables - PROTECTED_TABLES)

    truncated = []
    errors = []

    with connection.cursor() as cursor:
        # Disable FK checks for the duration
        if connection.vendor == 'sqlite':
            cursor.execute('PRAGMA foreign_keys = OFF;')
        elif connection.vendor == 'postgresql':
            cursor.execute('SET session_replication_role = replica;')

        for table in tables_to_truncate:
            try:
                if connection.vendor == 'sqlite':
                    cursor.execute(f'DELETE FROM "{table}";')
                    # Reset auto-increment
                    cursor.execute(
                        f"DELETE FROM sqlite_sequence WHERE name='{table}';"
                    )
                else:
                    cursor.execute(f'TRUNCATE TABLE "{table}" CASCADE;')
                truncated.append(table)
            except Exception as e:
                errors.append(f'{table}: {str(e)}')

        # Re-enable FK checks
        if connection.vendor == 'sqlite':
            cursor.execute('PRAGMA foreign_keys = ON;')
        elif connection.vendor == 'postgresql':
            cursor.execute('SET session_replication_role = DEFAULT;')

    return Response({
        'success': True,
        'truncated_count': len(truncated),
        'truncated': truncated,
        'errors': errors,
    })
