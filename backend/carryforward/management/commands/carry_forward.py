"""
Database Carry-Forward Management Command
==========================================
Creates a fresh SQLite database, copies master data + opening balances +
live/pending records, then swaps the database files. The old database is
renamed as a backup on disk (not accessible through the application).

Usage:
    python manage.py carry_forward --cutoff-date 2025-10-15
    python manage.py carry_forward --cutoff-date 2025-10-15 --dry-run
    python manage.py carry_forward --cutoff-date 2025-10-15 --retail-id 3
"""

import logging
import os
import re
import shutil

logger = logging.getLogger(__name__)
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User, Group, Permission as AuthPermission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, models, transaction
from django.db.models import Sum, F
from django.utils import timezone


# ---------------------------------------------------------------------------
# Model import helper — import lazily inside execute() to avoid AppRegistry
# issues, but define the groupings here for clarity.
# ---------------------------------------------------------------------------


def _get_master_models():
    """Models whose ENTIRE contents are copied to the new DB."""
    from accounting.models import Account, FixedAssetSettings
    from contacts.models import Ledger, LedgerRole, Documents, UserLocation
    from goldrates.models import PurityMaster
    from hr.models import Employee, SalaryStructure, PayrollDeductionConfig, HRSettings
    from inventory.models import AssetType, DesignMain, DesignDocument, DesignDetails
    from licensing.models import AppRegistry, CompanySubscription, AppLicense
    from manufacturing.models import KarigarMaster
    from mastersconfig.models import (
        State, CompanyMaster, BranchMaster, GSTINMaster, RetailMaster,
        Hsn, ItemGroupMaster, SalesPersonMaster, Item, Shapes, Colors,
        PacketGroup, Packet, ExhibitionProfile, SystemSettings,
        B2BPricelist, B2BPricelistTunch, B2BPricelistMaking,
        B2BPricelistStoneOverride, RetailDiscountPricelist,
        RetailDiscountPricelistRule, SalesOffer, SalesOfferRule,
        TDSSectionMaster, TCSSectionMaster, CRMSettings,
    )
    from goldscheme.models import SchemeMaster, SchemeBenefitTier, CustomerPortalCredential
    from userauth.models import Role, Permission, UserRole

    # Order matters: parents before children (FK dependencies)
    return [
        # Django internals (handled separately via raw copy)
        # -- ContentType, Group, AuthPermission, User are copied first --

        # Org structure
        State,
        CompanyMaster,
        BranchMaster,
        GSTINMaster,
        RetailMaster,

        # Account groups (parent → child self-FK)
        Account,

        # Contacts
        Ledger,
        LedgerRole,
        Documents,

        # Products
        ItemGroupMaster,
        Shapes,
        Colors,
        PacketGroup,
        Hsn,
        Item,
        Packet,

        # Purity
        PurityMaster,

        # Tax
        TDSSectionMaster,
        TCSSectionMaster,

        # Pricing
        B2BPricelist,
        B2BPricelistTunch,
        B2BPricelistMaking,
        B2BPricelistStoneOverride,
        RetailDiscountPricelist,
        RetailDiscountPricelistRule,
        SalesOffer,
        SalesOfferRule,

        # Sales
        SalesPersonMaster,

        # Config / Settings
        ExhibitionProfile,
        SystemSettings,
        CRMSettings,

        # Design masters
        AssetType,
        DesignMain,
        DesignDocument,
        DesignDetails,

        # Licensing
        AppRegistry,
        CompanySubscription,
        AppLicense,

        # HR masters
        HRSettings,
        Employee,
        SalaryStructure,
        PayrollDeductionConfig,

        # Scheme masters
        SchemeMaster,
        SchemeBenefitTier,
        CustomerPortalCredential,

        # Manufacturing masters
        KarigarMaster,

        # Auth/Access
        UserLocation,
        Role,
        Permission,
        UserRole,
    ]


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = 'Carry forward essential data to a fresh database, discarding old transactions.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cutoff-date', required=True,
            help='Cutoff date in YYYY-MM-DD format. Data before this date is archived.',
        )
        parser.add_argument(
            '--retail-id', type=int, default=None,
            help='Carry forward only this retail (by PK). Default: all retails.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Preview what would be carried/discarded without making changes.',
        )

    def handle(self, *args, **options):
        try:
            cutoff = datetime.strptime(options['cutoff_date'], '%Y-%m-%d').date()
        except ValueError:
            raise CommandError("Invalid date format. Use YYYY-MM-DD.")

        dry_run = options['dry_run']
        retail_id = options.get('retail_id')

        self.stdout.write(self.style.NOTICE(
            f"\n{'=' * 60}\n"
            f"  DATABASE CARRY-FORWARD {'(DRY RUN)' if dry_run else ''}\n"
            f"  Cutoff date: {cutoff}\n"
            f"  Retail: {'ALL' if not retail_id else retail_id}\n"
            f"{'=' * 60}\n"
        ))

        from mastersconfig.models import FiscalYearMaster, RetailMaster

        # ── Validate ──────────────────────────────────────────────
        retails = self._get_retails(retail_id)
        self._validate_preconditions(retails, cutoff)

        # ── Dry-run report ────────────────────────────────────────
        stats = self._compute_stats(retails, cutoff)
        self._print_stats(stats)

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\nDry run complete. No changes made."))
            return

        # ── Execute ───────────────────────────────────────────────
        self.stdout.write(self.style.WARNING("\nProceeding with carry-forward..."))

        old_db_path = settings.DATABASES['default']['NAME']
        base_dir = Path(old_db_path).parent
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"db_backup_{cutoff}_{timestamp}.sqlite3"
        backup_path = base_dir / backup_filename
        new_db_path = base_dir / 'db_new.sqlite3'

        try:
            # Step 1: Backup
            self.stdout.write("  [1/10] Creating backup...")
            shutil.copy2(str(old_db_path), str(backup_path))
            self.stdout.write(f"         → {backup_filename}")

            # Step 2: Create new DB and migrate
            self.stdout.write("  [2/10] Creating new database and running migrations...")
            self._setup_new_db(str(new_db_path))

            # Step 3: Copy Django internals
            self.stdout.write("  [3/10] Copying Django internals (users, groups, permissions)...")
            n_django = self._copy_django_internals()

            # Step 4: Copy master data
            self.stdout.write("  [4/10] Copying master data...")
            n_master = self._copy_master_data()

            # Step 5: Copy old FY as hard-closed + create new FY
            self.stdout.write("  [5/10] Setting up fiscal years...")
            new_fy_codes = self._setup_fiscal_years(retails, cutoff)

            # Step 6: Compute and write opening balances
            self.stdout.write("  [6/10] Computing and writing opening balances...")
            n_ob = self._compute_opening_balances(retails, cutoff, new_fy_codes)

            # Step 7: Copy live/pending data
            self.stdout.write("  [7/10] Copying live/pending data...")
            n_live = self._copy_live_data(retails, cutoff)

            # Step 8: Create synthetic advance vouchers
            self.stdout.write("  [8/10] Creating synthetic advance vouchers...")
            n_adv = self._create_synthetic_advances(retails, cutoff, new_fy_codes)

            # Step 9: Write carry-forward log
            self.stdout.write("  [9/10] Writing carry-forward log...")
            self._write_log(retails, cutoff, backup_filename, new_fy_codes, n_master, n_live, n_ob)

            # Step 10: Verify
            self.stdout.write("  [10/10] Running verification checks...")
            self._verify(retails)

            # ── Swap ──────────────────────────────────────────────
            self.stdout.write("\n  Swapping databases...")
            connections['carry_forward_target'].close()
            connections['default'].close()

            # Rename: old → backup, new → current
            os.replace(str(old_db_path), str(backup_path))
            os.replace(str(new_db_path), str(old_db_path))

            self.stdout.write(self.style.SUCCESS(
                f"\n{'=' * 60}\n"
                f"  CARRY-FORWARD COMPLETE\n"
                f"  New database is now active.\n"
                f"  Backup saved as: {backup_filename}\n"
                f"  Master rows: {n_django + n_master}\n"
                f"  Live/pending rows: {n_live}\n"
                f"  Ledgers with opening balance: {n_ob}\n"
                f"  Synthetic advance vouchers: {n_adv}\n"
                f"{'=' * 60}\n"
            ))

        except Exception as e:
            # Cleanup: remove partial new DB if it exists
            if new_db_path.exists():
                try:
                    connections['carry_forward_target'].close()
                except (KeyError, AttributeError):
                    pass  # connection may not have been opened
                os.remove(str(new_db_path))
            # Remove the temp DB alias
            if 'carry_forward_target' in settings.DATABASES:
                del settings.DATABASES['carry_forward_target']
            raise CommandError(f"Carry-forward failed: {e}")

    # ===================================================================
    # Validation
    # ===================================================================

    def _get_retails(self, retail_id):
        from mastersconfig.models import RetailMaster
        if retail_id:
            try:
                return [RetailMaster.objects.get(pk=retail_id)]
            except RetailMaster.DoesNotExist:
                raise CommandError(f"Retail with PK={retail_id} not found.")
        return list(RetailMaster.objects.all())

    def _validate_preconditions(self, retails, cutoff):
        from mastersconfig.models import FiscalYearMaster
        for retail in retails:
            # FY is company-global; the current FY is the same for every retail.
            fy = FiscalYearMaster.objects.filter(
                fy_start__lte=cutoff, fy_end__gte=cutoff
            ).first()
            if not fy:
                raise CommandError(
                    f"No fiscal year covers cutoff date {cutoff} for retail {retail.retail_code}. "
                    f"Create one first."
                )

    # ===================================================================
    # Dry-run stats
    # ===================================================================

    def _compute_stats(self, retails, cutoff):
        from accounting.models import VoucherMain, LedgerOpenBalance
        from contacts.models import Ledger
        from goldscheme.models import SchemeEnrollment
        from inventory.models import BarcodeMain, UnBarcodedMain, RawMaterialInventory
        from manufacturing.models import KarigarIssue
        from purchase.models import PurchaseOrder
        from sales.models import CustomerOrder

        stats = {}
        for retail in retails:
            r = retail.retail_code
            stats[r] = {
                'master_models': len(_get_master_models()),
                'ledgers': Ledger.objects.filter(retail_code=retail).count(),
                'in_stock_barcodes': BarcodeMain.objects.filter(retail=retail, stk_status=True).count(),
                'in_stock_unbarcoded': UnBarcodedMain.objects.filter(retail=retail, stk_status=True).count(),
                'raw_material_rows': RawMaterialInventory.objects.filter(retail=retail).count(),
                'open_customer_orders': CustomerOrder.objects.filter(
                    retail=retail
                ).exclude(delivery_status='delivered').exclude(delivery_status='cancelled').count(),
                'open_purchase_orders': PurchaseOrder.objects.filter(retail=retail).filter(
                    purchaseorderitems__rec_status=False
                ).distinct().count(),
                'open_karigar_jobs': KarigarIssue.objects.filter(retail=retail).filter(
                    items__rec_status=False
                ).distinct().count(),
                'active_schemes': SchemeEnrollment.objects.filter(
                    retail=retail, status__in=['ACTIVE', 'MATURED']
                ).count(),
                'vouchers_to_discard': VoucherMain.objects.filter(retail=retail).count(),
            }
        return stats

    def _print_stats(self, stats):
        for retail_code, s in stats.items():
            self.stdout.write(f"\n  Retail: {retail_code}")
            self.stdout.write(f"    CARRY FORWARD:")
            self.stdout.write(f"      Master model types:    {s['master_models']}")
            self.stdout.write(f"      Ledgers:               {s['ledgers']}")
            self.stdout.write(f"      In-stock barcodes:     {s['in_stock_barcodes']}")
            self.stdout.write(f"      In-stock unbarcoded:   {s['in_stock_unbarcoded']}")
            self.stdout.write(f"      Raw material rows:     {s['raw_material_rows']}")
            self.stdout.write(f"      Open customer orders:  {s['open_customer_orders']}")
            self.stdout.write(f"      Open purchase orders:  {s['open_purchase_orders']}")
            self.stdout.write(f"      Open karigar jobs:     {s['open_karigar_jobs']}")
            self.stdout.write(f"      Active scheme enrolls: {s['active_schemes']}")
            self.stdout.write(f"    DISCARD:")
            self.stdout.write(f"      Accounting vouchers:   {s['vouchers_to_discard']}")

    # ===================================================================
    # New DB setup
    # ===================================================================

    def _setup_new_db(self, new_db_path):
        """Create the new DB file, register it as a Django DB alias, and migrate."""
        settings.DATABASES['carry_forward_target'] = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': new_db_path,
            'OPTIONS': {'timeout': 30},
        }
        # Force Django to create a new connection
        if 'carry_forward_target' in connections:
            connections['carry_forward_target'].close()
        # Ensure the connection object is created for the new alias
        connections['carry_forward_target'].ensure_connection()
        call_command('migrate', database='carry_forward_target', verbosity=0)

    # ===================================================================
    # Copy helpers
    # ===================================================================

    def _bulk_copy(self, model, queryset=None, nullify_fields=None):
        """
        Copy rows from default DB to carry_forward_target, preserving PKs.
        Returns count of rows copied.
        """
        db_alias = 'carry_forward_target'
        if queryset is None:
            queryset = model.objects.using('default').all()

        rows = list(queryset)
        if not rows:
            return 0

        if nullify_fields:
            for row in rows:
                for field in nullify_fields:
                    setattr(row, field, None)

        # Preserve PKs by setting _state.adding = True
        for row in rows:
            row._state.db = db_alias
            row._state.adding = True

        model.objects.using(db_alias).bulk_create(rows, ignore_conflicts=False)

        # Reset sqlite_sequence for this table
        db_table = model._meta.db_table
        with connections[db_alias].cursor() as cursor:
            cursor.execute(
                f"UPDATE sqlite_sequence SET seq = (SELECT MAX(rowid) FROM \"{db_table}\") "
                f"WHERE name = %s", [db_table]
            )

        return len(rows)

    def _bulk_copy_m2m(self, model, field_name):
        """Copy M2M through-table rows."""
        db_alias = 'carry_forward_target'
        field = model._meta.get_field(field_name)
        through_model = field.remote_field.through

        rows = list(through_model.objects.using('default').all())
        if not rows:
            return 0

        for row in rows:
            row._state.db = db_alias
            row._state.adding = True

        through_model.objects.using(db_alias).bulk_create(rows, ignore_conflicts=False)
        return len(rows)

    # ===================================================================
    # Step 3: Django internals
    # ===================================================================

    def _copy_django_internals(self):
        count = 0
        # ContentType
        count += self._bulk_copy(ContentType)
        # Groups
        count += self._bulk_copy(Group)
        # Auth Permissions
        count += self._bulk_copy(AuthPermission)
        # Group-Permission M2M
        count += self._bulk_copy_m2m(Group, 'permissions')
        # Users
        count += self._bulk_copy(User)
        # User-Group M2M
        count += self._bulk_copy_m2m(User, 'groups')
        # User-Permission M2M
        count += self._bulk_copy_m2m(User, 'user_permissions')
        # Auth tokens
        try:
            Token = apps.get_model('authtoken', 'Token')
            count += self._bulk_copy(Token)
        except LookupError:
            pass
        self.stdout.write(f"         → {count} rows")
        return count

    # ===================================================================
    # Step 4: Master data
    # ===================================================================

    def _copy_master_data(self):
        count = 0
        master_models = _get_master_models()
        for model in master_models:
            n = self._bulk_copy(model)
            count += n

        # M2M fields on master models
        from licensing.models import AppRegistry
        try:
            count += self._bulk_copy_m2m(AppRegistry, 'depends_on')
        except Exception as e:
            logger.exception("carry_forward: failed to copy AppRegistry.depends_on M2M: %s", e)

        # UserLocation M2M (location)
        from contacts.models import UserLocation
        try:
            count += self._bulk_copy_m2m(UserLocation, 'location')
        except Exception as e:
            logger.exception("carry_forward: failed to copy UserLocation.location M2M: %s", e)

        self.stdout.write(f"         → {count} rows")
        return count

    # ===================================================================
    # Step 5: Fiscal years
    # ===================================================================

    def _setup_fiscal_years(self, retails, cutoff):
        """Copy existing FYs as hard-closed, create one company-wide next-year FY."""
        from mastersconfig.models import FiscalYearMaster
        db = 'carry_forward_target'
        new_fy_codes = {}  # retail_pk → fy_code

        # Copy ALL existing FiscalYearMaster rows (hard-close them)
        all_fys = list(FiscalYearMaster.objects.using('default').all())
        for fy in all_fys:
            fy.is_closed = True
            fy.is_hard_closed = True
            fy.hard_closed_at = timezone.now()
            fy._state.db = db
            fy._state.adding = True
        if all_fys:
            FiscalYearMaster.objects.using(db).bulk_create(all_fys)
            # Reset sequence
            with connections[db].cursor() as cursor:
                cursor.execute(
                    "UPDATE sqlite_sequence SET seq = (SELECT MAX(rowid) FROM \"fiscal_year_master\") "
                    "WHERE name = 'fiscal_year_master'"
                )

        # FY is company-global: determine the current FY once, no retail filter
        current_fy = FiscalYearMaster.objects.using('default').filter(
            fy_start__lte=cutoff, fy_end__gte=cutoff
        ).order_by('-fy_start').first()
        if not current_fy:
            return {retail.pk: '' for retail in retails}

        # Check if cutoff is at FY boundary (within 1 day of fy_end)
        is_fy_boundary = (cutoff >= current_fy.fy_end - timedelta(days=1))

        if is_fy_boundary:
            # Natural FY transition: e.g., 25-26 → 26-27
            end_year = current_fy.fy_end.year
            new_code = f"{str(end_year % 100).zfill(2)}-{str((end_year + 1) % 100).zfill(2)}"
            new_start = current_fy.fy_end + timedelta(days=1)
            new_end = date(end_year + 1, current_fy.fy_end.month, current_fy.fy_end.day)
        else:
            # Mid-FY carry-forward: e.g., 25-26 → 25-26-II
            base_code = current_fy.fy_code
            # Find existing suffixed FYs to determine next suffix
            existing = FiscalYearMaster.objects.using(db).filter(
                fy_code__startswith=base_code
            ).count()
            suffix_num = existing  # e.g., "25-26" exists → suffix_num=1 → "-II"
            roman = ['', '-II', '-III', '-IV', '-V'][min(suffix_num, 4)]
            new_code = f"{base_code}{roman}"
            new_start = cutoff
            new_end = current_fy.fy_end

        new_fy = FiscalYearMaster(
            fy_code=new_code,
            fy_start=new_start,
            fy_end=new_end,
            is_closed=False,
            is_hard_closed=False,
        )
        new_fy._state.db = db
        new_fy._state.adding = True
        new_fy.save(using=db)

        # Set the company-wide active FY in the target DB
        from mastersconfig.models import SystemSettings
        ss, _ = SystemSettings.objects.using(db).get_or_create(
            pk=1, defaults={'attachment_storage_path': ''})
        ss.active_fy = new_fy
        ss.save(using=db, update_fields=['active_fy'])

        self.stdout.write(f"         → company FY {new_code} ({new_start} to {new_end})")
        return {retail.pk: new_code for retail in retails}

    # ===================================================================
    # Step 6: Opening balances
    # ===================================================================

    def _compute_opening_balances(self, retails, cutoff, new_fy_codes):
        """Compute closing balances from old DB, write as opening in new DB."""
        from accounting.models import LedgerOpenBalance, VoucherDetail
        from mastersconfig.models import FiscalYearMaster
        db = 'carry_forward_target'
        total_ob = 0

        for retail in retails:
            # Find the FY covering the cutoff in the OLD DB
            fy = FiscalYearMaster.objects.using('default').filter(
                fy_start__lte=cutoff, fy_end__gte=cutoff
            ).first()
            if not fy:
                continue

            new_fy_code = new_fy_codes.get(retail.pk, '')

            # Step 1: Opening balance of THIS FY
            ob_qs = (
                LedgerOpenBalance.objects.using('default')
                .filter(retail=retail, acc_year=fy.fy_code)
                .values('ldgr')
                .annotate(ob=Sum(F('debit') - F('credit')))
            )
            ob_dict = {row['ldgr']: Decimal(str(row['ob'] or 0)) for row in ob_qs}

            # Step 2: All transactions up to cutoff date
            txn_qs = (
                VoucherDetail.objects.using('default')
                .filter(
                    voucher_main__retail=retail,
                    voucher_main__date__gte=fy.fy_start,
                    voucher_main__date__lte=cutoff,
                )
                .values('account')
                .annotate(total=Sum(F('debit') - F('credit')))
            )
            txn_dict = {row['account']: Decimal(str(row['total'] or 0)) for row in txn_qs}

            # Step 3: Compute closing balance per ledger
            all_ids = set(ob_dict.keys()) | set(txn_dict.keys())
            new_rows = []
            for ldgr_id in all_ids:
                closing = ob_dict.get(ldgr_id, Decimal(0)) + txn_dict.get(ldgr_id, Decimal(0))
                if closing == 0:
                    continue
                if closing > 0:
                    new_rows.append(LedgerOpenBalance(
                        ldgr_id=ldgr_id, retail=retail,
                        acc_year=new_fy_code,
                        debit=float(closing), credit=0.0,
                    ))
                else:
                    new_rows.append(LedgerOpenBalance(
                        ldgr_id=ldgr_id, retail=retail,
                        acc_year=new_fy_code,
                        debit=0.0, credit=float(abs(closing)),
                    ))

            if new_rows:
                for row in new_rows:
                    row._state.db = db
                    row._state.adding = True
                LedgerOpenBalance.objects.using(db).bulk_create(new_rows)

            total_ob += len(new_rows)
            self.stdout.write(f"         → {retail.retail_code}: {len(new_rows)} ledger balances")

        return total_ob

    # ===================================================================
    # Step 7: Live/pending data
    # ===================================================================

    def _copy_live_data(self, retails, cutoff):
        """Copy all live/pending records to the new DB."""
        count = 0

        for retail in retails:
            self.stdout.write(f"         [{retail.retail_code}]")

            # ── In-stock barcodes ─────────────────────────────────
            bc_qs = self._get_model('inventory', 'BarcodeMain').objects.filter(
                retail=retail, stk_status=True
            )
            n = self._bulk_copy(
                self._get_model('inventory', 'BarcodeMain'),
                bc_qs,
                nullify_fields=['pur_voucher', 'rec_item']
            )
            count += n
            self.stdout.write(f"           Barcodes (in-stock):    {n}")

            # BarcodeDetails for in-stock barcodes
            bc_ids = list(bc_qs.values_list('pk', flat=True))
            if bc_ids:
                bd_qs = self._get_model('inventory', 'BarcodeDetails').objects.filter(
                    barcode_id__in=bc_ids
                )
                count += self._bulk_copy(self._get_model('inventory', 'BarcodeDetails'), bd_qs)

            # BarcodeImage for in-stock barcodes
            if bc_ids:
                bi_qs = self._get_model('inventory', 'BarcodeImage').objects.filter(
                    barcode_id__in=bc_ids
                )
                count += self._bulk_copy(self._get_model('inventory', 'BarcodeImage'), bi_qs)

            # ── In-stock unbarcoded ───────────────────────────────
            ub_qs = self._get_model('inventory', 'UnBarcodedMain').objects.filter(
                retail=retail, stk_status=True
            )
            n = self._bulk_copy(self._get_model('inventory', 'UnBarcodedMain'), ub_qs)
            count += n
            self.stdout.write(f"           Unbarcoded (in-stock):  {n}")

            ub_ids = list(ub_qs.values_list('pk', flat=True))
            if ub_ids:
                ubd_qs = self._get_model('inventory', 'UnBarcodedDetails').objects.filter(
                    main_item_id__in=ub_ids
                )
                count += self._bulk_copy(self._get_model('inventory', 'UnBarcodedDetails'), ubd_qs)

            # ── Raw material inventory ────────────────────────────
            rm_qs = self._get_model('inventory', 'RawMaterialInventory').objects.filter(retail=retail)
            n = self._bulk_copy(self._get_model('inventory', 'RawMaterialInventory'), rm_qs)
            count += n
            self.stdout.write(f"           Raw material rows:      {n}")

            # ── Open customer orders ──────────────────────────────
            co_qs = self._get_model('sales', 'CustomerOrder').objects.filter(
                retail=retail
            ).exclude(delivery_status='delivered').exclude(delivery_status='cancelled')
            n = self._bulk_copy(self._get_model('sales', 'CustomerOrder'), co_qs)
            count += n
            self.stdout.write(f"           Open customer orders:   {n}")

            co_ids = list(co_qs.values_list('pk', flat=True))
            if co_ids:
                coi_qs = self._get_model('sales', 'CustomerOrderItems').objects.filter(
                    order_no_id__in=co_ids
                )
                count += self._bulk_copy(self._get_model('sales', 'CustomerOrderItems'), coi_qs)

            # ── Open purchase orders ──────────────────────────────
            PurchaseOrder = self._get_model('purchase', 'PurchaseOrder')
            PurchaseOrderItems = self._get_model('purchase', 'PurchaseOrderItems')
            # POs with at least one unfinished item
            open_po_ids = list(
                PurchaseOrderItems.objects.filter(
                    retail=retail, rec_status=False
                ).values_list('po_slip_id', flat=True).distinct()
            )
            if open_po_ids:
                po_qs = PurchaseOrder.objects.filter(pk__in=open_po_ids)
                n = self._bulk_copy(PurchaseOrder, po_qs)
                count += n
                self.stdout.write(f"           Open purchase orders:   {n}")

                poi_qs = PurchaseOrderItems.objects.filter(po_slip_id__in=open_po_ids)
                count += self._bulk_copy(PurchaseOrderItems, poi_qs)

            # ── Open karigar jobs (full chain) ────────────────────
            count += self._copy_open_karigar_jobs(retail)

            # ── Open hallmark/refinery/melting issues ───────
            count += self._copy_open_processing_slips(retail)

            # ── Open repair job cards ─────────────────────────────
            count += self._copy_open_repairs(retail)

            # ── In-transit stock transfers ────────────────────────
            StockTransfer = self._get_model('inventory', 'StockTransfer')
            StockTransferMain = self._get_model('inventory', 'StockTransferMain')
            st_qs = StockTransfer.objects.filter(retail=retail, rec_status=False)
            n = self._bulk_copy(StockTransfer, st_qs)
            count += n
            if n:
                self.stdout.write(f"           In-transit transfers:   {n}")
                st_ids = list(st_qs.values_list('pk', flat=True))
                stm_qs = StockTransferMain.objects.filter(billno_id__in=st_ids)
                count += self._bulk_copy(StockTransferMain, stm_qs)

            # ── Active scheme enrollments + payments ──────────────
            SchemeEnrollment = self._get_model('goldscheme', 'SchemeEnrollment')
            SchemePayment = self._get_model('goldscheme', 'SchemePayment')
            SchemeNominee = self._get_model('goldscheme', 'SchemeNominee')
            se_qs = SchemeEnrollment.objects.filter(
                retail=retail, status__in=['ACTIVE', 'MATURED']
            )
            n = self._bulk_copy(SchemeEnrollment, se_qs)
            count += n
            if n:
                self.stdout.write(f"           Active enrollments:     {n}")
                se_ids = list(se_qs.values_list('pk', flat=True))
                sp_qs = SchemePayment.objects.filter(enrollment_id__in=se_ids)
                n2 = self._bulk_copy(SchemePayment, sp_qs, nullify_fields=['voucher'])
                count += n2
                self.stdout.write(f"           Scheme payments:        {n2}")

                # Nominee (one per enrollment) — carry KYC forward with the enrollment
                nom_qs = SchemeNominee.objects.filter(enrollment_id__in=se_ids)
                n3 = self._bulk_copy(SchemeNominee, nom_qs)
                count += n3
                if n3:
                    self.stdout.write(f"           Scheme nominees:        {n3}")

            # ── Active fixed assets ───────────────────────────────
            FixedAsset = self._get_model('accounting', 'FixedAsset')
            fa_qs = FixedAsset.objects.filter(retail=retail, status='ACTIVE')
            n = self._bulk_copy(FixedAsset, fa_qs)
            count += n
            if n:
                self.stdout.write(f"           Active fixed assets:    {n}")

            # ── Leave balances (current year) ─────────────────────
            LeaveBalance = self._get_model('hr', 'LeaveBalance')
            lb_qs = LeaveBalance.objects.filter(
                employee__retail=retail, year=cutoff.year
            )
            count += self._bulk_copy(LeaveBalance, lb_qs)

        self.stdout.write(f"         → Total live rows: {count}")
        return count

    def _copy_open_karigar_jobs(self, retail):
        """Copy the full chain for karigar jobs that are not fully received."""
        KarigarIssue = self._get_model('manufacturing', 'KarigarIssue')
        KarigarIssueItem = self._get_model('manufacturing', 'KarigarIssueItem')
        KarigarGoldIssueHeader = self._get_model('manufacturing', 'KarigarGoldIssueHeader')
        KarigarGoldIssue = self._get_model('manufacturing', 'KarigarGoldIssue')
        KarigarStoneIssueHeader = self._get_model('manufacturing', 'KarigarStoneIssueHeader')
        KarigarStoneIssue = self._get_model('manufacturing', 'KarigarStoneIssue')
        KarigarStoneReceiveHeader = self._get_model('manufacturing', 'KarigarStoneReceiveHeader')
        KarigarStoneReceive = self._get_model('manufacturing', 'KarigarStoneReceive')
        KarigarReceive = self._get_model('manufacturing', 'KarigarReceive')
        KarigarReceiveItem = self._get_model('manufacturing', 'KarigarReceiveItem')
        KarigarReceiveItemDetails = self._get_model('manufacturing', 'KarigarReceiveItemDetails')

        count = 0

        # Find open job issues — those with at least one item not fully received
        open_issue_ids = list(
            KarigarIssueItem.objects.filter(
                retail=retail
            ).exclude(rec_status='received').values_list(
                'issue_slip_id', flat=True
            ).distinct()
        )

        if not open_issue_ids:
            return 0

        # Copy issue headers + items
        n = self._bulk_copy(KarigarIssue, KarigarIssue.objects.filter(pk__in=open_issue_ids))
        count += n
        self.stdout.write(f"           Open karigar jobs:      {n}")

        ki_items = KarigarIssueItem.objects.filter(issue_slip_id__in=open_issue_ids)
        count += self._bulk_copy(KarigarIssueItem, ki_items)

        # Copy gold issues for open jobs (uses GenericFK: ref_job_content_type + ref_job_object_id)
        from django.contrib.contenttypes.models import ContentType as CT
        ki_ct = CT.objects.get_for_model(KarigarIssue)

        gold_header_ids = list(
            KarigarGoldIssueHeader.objects.filter(retail=retail).values_list('pk', flat=True)
        )
        if gold_header_ids:
            open_gold_issues = KarigarGoldIssue.objects.filter(
                header_id__in=gold_header_ids,
                ref_job_content_type=ki_ct, ref_job_object_id__in=open_issue_ids
            )
            open_gold_header_ids = list(open_gold_issues.values_list('header_id', flat=True).distinct())
            if open_gold_header_ids:
                count += self._bulk_copy(
                    KarigarGoldIssueHeader,
                    KarigarGoldIssueHeader.objects.filter(pk__in=open_gold_header_ids)
                )
                count += self._bulk_copy(
                    KarigarGoldIssue,
                    KarigarGoldIssue.objects.filter(header_id__in=open_gold_header_ids)
                )

        # Copy stone issues for open jobs (same GenericFK pattern)
        stone_header_ids = list(
            KarigarStoneIssueHeader.objects.filter(retail=retail).values_list('pk', flat=True)
        )
        if stone_header_ids:
            open_stone_issues = KarigarStoneIssue.objects.filter(
                header_id__in=stone_header_ids,
                ref_job_content_type=ki_ct, ref_job_object_id__in=open_issue_ids
            )
            open_stone_header_ids = list(open_stone_issues.values_list('header_id', flat=True).distinct())
            if open_stone_header_ids:
                count += self._bulk_copy(
                    KarigarStoneIssueHeader,
                    KarigarStoneIssueHeader.objects.filter(pk__in=open_stone_header_ids)
                )
                count += self._bulk_copy(
                    KarigarStoneIssue,
                    KarigarStoneIssue.objects.filter(header_id__in=open_stone_header_ids)
                )

        # Copy stone receives for open jobs
        stone_recv_header_ids = list(
            KarigarStoneReceiveHeader.objects.filter(retail=retail).values_list('pk', flat=True)
        )
        if stone_recv_header_ids:
            open_stone_recvs = KarigarStoneReceive.objects.filter(
                header_id__in=stone_recv_header_ids,
                ref_job_content_type=ki_ct, ref_job_object_id__in=open_issue_ids
            )
            open_stone_recv_header_ids = list(open_stone_recvs.values_list('header_id', flat=True).distinct())
            if open_stone_recv_header_ids:
                count += self._bulk_copy(
                    KarigarStoneReceiveHeader,
                    KarigarStoneReceiveHeader.objects.filter(pk__in=open_stone_recv_header_ids)
                )
                count += self._bulk_copy(
                    KarigarStoneReceive,
                    KarigarStoneReceive.objects.filter(header_id__in=open_stone_recv_header_ids)
                )

        # Copy receive headers/items for partially received jobs
        recv_ids_with_open_items = list(
            KarigarReceiveItem.objects.filter(
                receive_slip_no__retail=retail,
                ref_job_no_id__in=open_issue_ids,
            ).values_list('receive_slip_no_id', flat=True).distinct()
        )
        if recv_ids_with_open_items:
            count += self._bulk_copy(
                KarigarReceive,
                KarigarReceive.objects.filter(pk__in=recv_ids_with_open_items)
            )
            recv_items = KarigarReceiveItem.objects.filter(
                receive_slip_no_id__in=recv_ids_with_open_items
            )
            count += self._bulk_copy(KarigarReceiveItem, recv_items)

            # Copy receive item details
            recv_item_ids = list(recv_items.values_list('pk', flat=True))
            if recv_item_ids:
                count += self._bulk_copy(
                    KarigarReceiveItemDetails,
                    KarigarReceiveItemDetails.objects.filter(main_sl_no_id__in=recv_item_ids)
                )

        return count

    def _copy_open_processing_slips(self, retail):
        """Copy open hallmark/refinery/melting issues and their items."""
        count = 0

        # Refinery issues (has rec_status field)
        for header_name, detail_name, header_fk in [
            ('RefinaryIssue', 'RefinaryIssueDetail', 'billno'),
            ('MeltingIssue', 'MeltingIssueDetail', 'billno'),
        ]:
            Header = self._get_model('manufacturing', header_name)
            Detail = self._get_model('manufacturing', detail_name)
            open_qs = Header.objects.filter(retail=retail, rec_status=False)
            n = self._bulk_copy(Header, open_qs)
            count += n
            if n:
                open_ids = list(open_qs.values_list('pk', flat=True))
                detail_qs = Detail.objects.filter(**{f'{header_fk}_id__in': open_ids})
                count += self._bulk_copy(Detail, detail_qs)

        # Also copy matching receive records for partial receives
        for recv_name, recv_detail_name, recv_fk in [
            ('RefinaryReceive', 'RefinaryReceiveDetail', 'billno'),
            ('MeltingReceive', 'MeltingReceiveDetail', 'billno'),
        ]:
            # These don't have rec_status — they're receive records that exist for open issues
            # Copy all for this retail (they're small in number)
            Recv = self._get_model('manufacturing', recv_name)
            RecvDetail = self._get_model('manufacturing', recv_detail_name)
            recv_qs = Recv.objects.filter(retail=retail)
            n = self._bulk_copy(Recv, recv_qs)
            count += n
            if n:
                recv_ids = list(recv_qs.values_list('pk', flat=True))
                count += self._bulk_copy(RecvDetail, RecvDetail.objects.filter(**{f'{recv_fk}_id__in': recv_ids}))

        # Hallmark issues (no rec_status — use HallmarkIssueItem.rec_status)
        HallmarkIssue = self._get_model('manufacturing', 'HallmarkIssue')
        HallmarkIssueItem = self._get_model('manufacturing', 'HallmarkIssueItem')
        HallmarkIssueDetails = self._get_model('manufacturing', 'HallmarkIssueDetails')
        open_hm_item_issue_ids = list(
            HallmarkIssueItem.objects.filter(
                issue_slip_no__retail=retail
            ).exclude(rec_status=True).values_list('issue_slip_no_id', flat=True).distinct()
        )
        if open_hm_item_issue_ids:
            n = self._bulk_copy(HallmarkIssue, HallmarkIssue.objects.filter(pk__in=open_hm_item_issue_ids))
            count += n
            items = HallmarkIssueItem.objects.filter(issue_slip_no_id__in=open_hm_item_issue_ids)
            count += self._bulk_copy(HallmarkIssueItem, items)
            item_ids = list(items.values_list('pk', flat=True))
            if item_ids:
                count += self._bulk_copy(
                    HallmarkIssueDetails,
                    HallmarkIssueDetails.objects.filter(issue_item_id__in=item_ids)
                )

        # Hallmark receives for those issues
        HallmarkReceive = self._get_model('manufacturing', 'HallmarkReceive')
        HallmarkReceiveItem = self._get_model('manufacturing', 'HallmarkReceiveItem')
        HallmarkReceiveDetails = self._get_model('manufacturing', 'HallmarkReceiveDetails')
        hr_qs = HallmarkReceive.objects.filter(retail=retail)
        if hr_qs.exists():
            n = self._bulk_copy(HallmarkReceive, hr_qs)
            count += n
            hr_ids = list(hr_qs.values_list('pk', flat=True))
            hr_items = HallmarkReceiveItem.objects.filter(receive_slip_no_id__in=hr_ids)
            count += self._bulk_copy(HallmarkReceiveItem, hr_items)
            hr_item_ids = list(hr_items.values_list('pk', flat=True))
            if hr_item_ids:
                count += self._bulk_copy(
                    HallmarkReceiveDetails,
                    HallmarkReceiveDetails.objects.filter(receive_item_id__in=hr_item_ids)
                )

        return count

    def _copy_open_repairs(self, retail):
        """Copy repair job cards not yet delivered."""
        RepairJobCard = self._get_model('manufacturing', 'RepairJobCard')
        RepairStone = self._get_model('manufacturing', 'RepairStone')
        RepairLoss = self._get_model('manufacturing', 'RepairLoss')
        RepairKarigarLink = self._get_model('manufacturing', 'RepairKarigarLink')

        count = 0
        open_qs = RepairJobCard.objects.filter(retail=retail).exclude(status='DLV')
        n = self._bulk_copy(RepairJobCard, open_qs)
        count += n
        if n:
            self.stdout.write(f"           Open repairs:           {n}")
            rjc_ids = list(open_qs.values_list('pk', flat=True))
            count += self._bulk_copy(RepairStone, RepairStone.objects.filter(job_card_id__in=rjc_ids))
            count += self._bulk_copy(RepairLoss, RepairLoss.objects.filter(job_card_id__in=rjc_ids))
            count += self._bulk_copy(RepairKarigarLink, RepairKarigarLink.objects.filter(job_card_id__in=rjc_ids))
        return count

    # ===================================================================
    # Step 8: Synthetic advance vouchers
    # ===================================================================

    def _create_synthetic_advances(self, retails, cutoff, new_fy_codes):
        """Create RCPT vouchers for open customer orders with remaining advance."""
        from accounting.models import VoucherMain
        from sales.models import CustomerOrder
        from mastersconfig.models import FiscalYearMaster
        db = 'carry_forward_target'
        count = 0

        for retail in retails:
            new_fy_code = new_fy_codes.get(retail.pk, '')
            new_fy = FiscalYearMaster.objects.using(db).filter(
                fy_code=new_fy_code
            ).first()

            open_orders = CustomerOrder.objects.using('default').filter(
                retail=retail
            ).exclude(delivery_status='delivered').exclude(delivery_status='cancelled')

            for order in open_orders:
                # Compute advance_available from the OLD DB
                advance_amt = order.advance_amt  # reads from default DB
                advance_reconciled = order.advance_reconciled  # reads from default DB
                advance_available = advance_amt - advance_reconciled

                if advance_available <= 0:
                    continue

                # Create synthetic RCPT voucher in new DB
                voucher = VoucherMain(
                    date=cutoff,
                    voucher_no=f"CF-ADV/{retail.retail_code}/{order.order_no}",
                    narration=f"Opening advance carried forward from order {order.order_no}",
                    amount=advance_available,
                    voucher_type='RCPT',
                    status='posted',
                    retail=retail,
                    fiscal_year=new_fy,
                    customer_order=order,
                )
                voucher._state.db = db
                voucher._state.adding = True
                voucher.save(using=db)
                count += 1

        if count:
            self.stdout.write(f"         → {count} synthetic advance vouchers created")
        return count

    # ===================================================================
    # Step 9: Write log
    # ===================================================================

    def _write_log(self, retails, cutoff, backup_filename, new_fy_codes, n_master, n_live, n_ob):
        from carryforward.models import CarryForwardLog
        db = 'carry_forward_target'

        for retail in retails:
            log = CarryForwardLog(
                retail=retail,
                cutoff_date=cutoff,
                old_db_filename=backup_filename,
                new_fy_code=new_fy_codes.get(retail.pk, ''),
                status='success',
                master_rows_copied=n_master,
                live_rows_copied=n_live,
                ledgers_with_opening=n_ob,
                notes=f"Carry-forward completed at {timezone.now().isoformat()}",
            )
            log._state.db = db
            log._state.adding = True
            log.save(using=db)

    # ===================================================================
    # Step 10: Verification
    # ===================================================================

    def _verify(self, retails):
        """Post-copy verification checks."""
        db = 'carry_forward_target'
        from accounting.models import LedgerOpenBalance
        from inventory.models import BarcodeMain
        errors = []

        for retail in retails:
            # 1. Check accounting equation: sum(debit) == sum(credit) for opening balances
            agg = LedgerOpenBalance.objects.using(db).filter(retail=retail).aggregate(
                total_dr=Sum('debit'), total_cr=Sum('credit')
            )
            dr = Decimal(str(agg['total_dr'] or 0))
            cr = Decimal(str(agg['total_cr'] or 0))
            diff = abs(dr - cr)
            if diff > Decimal('0.01'):
                errors.append(
                    f"  [{retail.retail_code}] OB imbalance: DR={dr}, CR={cr}, diff={diff}"
                )
            else:
                self.stdout.write(f"         [{retail.retail_code}] OB balanced: DR={dr}, CR={cr} ✓")

            # 2. Check in-stock barcodes match
            old_count = BarcodeMain.objects.using('default').filter(
                retail=retail, stk_status=True
            ).count()
            new_count = BarcodeMain.objects.using(db).filter(
                retail=retail, stk_status=True
            ).count()
            if old_count != new_count:
                errors.append(
                    f"  [{retail.retail_code}] Barcode mismatch: old={old_count}, new={new_count}"
                )
            else:
                self.stdout.write(f"         [{retail.retail_code}] Barcodes: {new_count} ✓")

        if errors:
            self.stdout.write(self.style.ERROR("\n  VERIFICATION WARNINGS:"))
            for e in errors:
                self.stdout.write(self.style.ERROR(e))
        else:
            self.stdout.write(self.style.SUCCESS("         All checks passed ✓"))

    # ===================================================================
    # Utility
    # ===================================================================

    def _get_model(self, app_label, model_name):
        return apps.get_model(app_label, model_name)
