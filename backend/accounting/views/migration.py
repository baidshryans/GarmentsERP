"""
Frontend-facing endpoints for the one-time legacy data migration.

Wraps the CLI management commands (import_vouchers / import_sales /
import_purchases / import_voucher_allocations) so they can be driven from the
"Import Master Data" → Transactions tab. Uploaded CSVs are written to a temp
dir, the matching command is run via call_command (always with
continue-on-error so a bad row reports instead of 500-ing), and the captured
output + any unresolved_*.csv reports are returned.
"""
import io
import os
import shutil
import tempfile

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import FileResponse, Http404
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

# repo-root/templates (settings.BASE_DIR == backend/)
TEMPLATES_DIR = os.path.join(os.path.dirname(settings.BASE_DIR), 'templates')

# kind -> (command name, {form-field: command-kwarg}, required-fields)
IMPORT_KINDS = {
    'vouchers':    ('import_vouchers',             {'main': 'main', 'details': 'details'},
                    ['main', 'details']),
    'sales':       ('import_sales',                {'header': 'header', 'items': 'items', 'details': 'details'},
                    ['header', 'items', 'details']),
    'sale_returns': ('import_sale_returns',        {'header': 'header', 'items': 'items', 'details': 'details'},
                    ['header', 'items', 'details']),
    'purchases':   ('import_purchases',            {'header': 'header', 'items': 'items', 'details': 'details'},
                    ['header', 'items', 'details']),
    'purchase_returns': ('import_purchase_returns', {'header': 'header', 'items': 'items', 'details': 'details'},
                    ['header', 'items', 'details']),
    'customer_orders': ('import_customer_orders',  {'header': 'header', 'items': 'items'},
                        ['header', 'items']),
    'ledger_opening':  ('import_ledger_opening',   {'file': 'file'},
                        ['file']),
    'opening_stock':   ('import_opening_stock',    {'file': 'file'},
                        ['file']),
    'allocations': ('import_voucher_allocations',  {'receive': 'receive', 'payment': 'payment', 'journal': 'journal'},
                    []),  # at least one (validated below)
    'barcode_transactions': ('import_barcode_transactions',
                    {'txn': 'txn_csv', 'split': 'split_csv', 'merge': 'merge_csv'},
                    []),  # at least one (command validates)
}

# download name -> template filename
TEMPLATE_FILES = {
    'voucher_main':              'legacy_voucher_main_template.csv',
    'voucher_details':           'legacy_voucher_details_template.csv',
    'sales_vou':                 'legacy_sales_vou_template.csv',
    'sales_vou_main':            'legacy_sales_vou_main_template.csv',
    'sales_vou_detail':          'legacy_sales_vou_detail_template.csv',
    'sale_return':               'legacy_sale_return_template.csv',
    'sale_return_main':          'legacy_sale_return_main_template.csv',
    'sale_return_detail':        'legacy_sale_return_detail_template.csv',
    'purchase_voucher':          'legacy_purchase_voucher_template.csv',
    'purchase_voucher_main':     'legacy_purchase_voucher_main_template.csv',
    'purchase_voucher_details':  'legacy_purchase_voucher_details_template.csv',
    'purchase_return':           'legacy_purchase_return_template.csv',
    'purchase_return_main':      'legacy_purchase_return_main_template.csv',
    'purchase_return_detail':    'legacy_purchase_return_detail_template.csv',
    'receive_amount':            'legacy_receive_amount_template.csv',
    'payment_amount':            'legacy_payment_amount_template.csv',
    'journal_amount':            'legacy_journal_amount_template.csv',
    'customer_order':            'legacy_customer_order_template.csv',
    'customer_order_main':       'legacy_customer_order_main_template.csv',
    'ldgr_open_balance':         'legacy_ldgr_open_balance_template.csv',
    'barcode_detail_rawstone':   'legacy_barcode_detail_rawstone_template.csv',
    'barcode_wise_all_transaction': 'legacy_barcode_wise_all_transaction_template.csv',
    'barcode_split':             'legacy_barcode_split_template.csv',
    'barcode_merge':             'legacy_barcode_merge_template.csv',
}


class MigrationTemplateView(APIView):
    """GET /accounting/api/migration/template/?name=voucher_main -> CSV file."""

    def get(self, request):
        name = request.query_params.get('name', '')
        fname = TEMPLATE_FILES.get(name)
        if not fname:
            raise Http404(f"unknown template {name!r}")
        path = os.path.join(TEMPLATES_DIR, fname)
        if not os.path.exists(path):
            raise Http404("template file missing on server")
        return FileResponse(open(path, 'rb'), as_attachment=True, filename=fname, content_type='text/csv')


class MigrationImportView(APIView):
    """POST /accounting/api/migration/<kind>/?apply=true  (multipart files)."""
    parser_classes = [MultiPartParser]

    def post(self, request, kind=None):
        cfg = IMPORT_KINDS.get(kind)
        if not cfg:
            return Response({'error': f"unknown import kind {kind!r}"}, status=status.HTTP_400_BAD_REQUEST)
        command, field_map, required = cfg

        provided = {f: request.FILES.get(f) for f in field_map if request.FILES.get(f)}
        missing = [f for f in required if f not in provided]
        if missing:
            return Response({'error': f"missing file(s): {', '.join(missing)}"}, status=status.HTTP_400_BAD_REQUEST)
        if not provided:
            return Response({'error': 'no files uploaded'}, status=status.HTTP_400_BAD_REQUEST)

        apply = request.query_params.get('apply', 'false').lower() == 'true'

        tmp = tempfile.mkdtemp(prefix='legacy_import_')
        try:
            kwargs = {'apply': apply, 'continue_on_error': True, 'report_dir': tmp}
            for field, f in provided.items():
                path = os.path.join(tmp, f.name or f'{field}.csv')
                with open(path, 'wb') as out:
                    for chunk in f.chunks():
                        out.write(chunk)
                kwargs[field_map[field]] = path

            buf = io.StringIO()
            try:
                call_command(command, stdout=buf, stderr=buf, **kwargs)
            except CommandError as exc:
                return Response(
                    {'error': str(exc), 'output': buf.getvalue(), 'applied': apply},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            reports = {}
            for fn in os.listdir(tmp):
                if fn.startswith('unresolved') or fn.startswith('imbalanced'):
                    with open(os.path.join(tmp, fn), encoding='utf-8') as r:
                        reports[fn] = r.read()[:20000]

            return Response({'applied': apply, 'output': buf.getvalue(), 'reports': reports})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class MigrationResetView(APIView):
    """POST /accounting/api/migration/reset/?apply=true  body: {scope: [...]}

    Clears non-system-seeded migrated data so a migration can be re-run.
    Scope keys: 'sales', 'purchases', 'gl' (legacy GL vouchers, identified by
    legacy_key), 'ledgers' (non-system ledgers + all LedgerAlias). System
    ledgers and core config are always preserved. Records still referenced by
    out-of-scope data via a PROTECT FK are skipped (kept), never force-deleted.
    Dry-run by default; ?apply=true performs the deletes in one transaction.
    """

    def post(self, request):
        import contextlib
        from django.db import models as dm, transaction
        from django.db.models.signals import pre_delete, post_delete
        from sales.models import SalesVou, CustomerOrder
        from purchase.models import PurchaseVoucher
        from accounting.models import VoucherMain, LedgerOpenBalance
        from contacts.models import Ledger, LedgerAlias

        @contextlib.contextmanager
        def _muted_delete_signals():
            # A migration teardown removes data wholesale; the per-row delete
            # side effects (stock/raw-material reversal, due_amt restore, audit)
            # are for undoing single live transactions and must not run here —
            # some also crash on legacy data quirks. Temporarily detach all
            # pre/post_delete receivers, then restore. (Reset is a deliberate
            # one-off admin action, not run concurrently with normal use.)
            saved = {}
            for sig in (pre_delete, post_delete):
                saved[sig] = sig.receivers
                sig.receivers = []
                sig.sender_receivers_cache.clear()
            try:
                yield
            finally:
                for sig, recv in saved.items():
                    sig.receivers = recv
                    sig.sender_receivers_cache.clear()

        apply = request.query_params.get('apply', 'false').lower() == 'true'
        scope = set(request.data.get('scope') or ['sales', 'purchases', 'gl', 'ledgers'])

        def protected_pks(model):
            """PKs of `model` referenced by any incoming PROTECT FK (keep these)."""
            pks = set()
            for rel in model._meta.related_objects:
                if getattr(rel, 'on_delete', None) is dm.PROTECT:
                    attn = rel.field.attname
                    pks |= set(rel.related_model.objects.exclude(**{attn: None})
                               .values_list(attn, flat=True))
            return pks

        report = {}

        def do(label, qs, model):
            # Count + skipped are computed against the live state at this point in
            # the ordered run (after prior deletes), then the delete happens. For
            # dry-run the whole run is rolled back, so the preview counts match a
            # real apply exactly.
            prot = protected_pks(model)
            target = qs.exclude(pk__in=prot)
            n = target.count()
            skipped = qs.filter(pk__in=prot).count()
            target.delete()  # cascades items/details/roles/etc.
            report[label] = {'deleted': n, 'skipped_protected': skipped}

        def run():
            # Order matters: sales before purchases (old-gold adjustments PROTECT
            # purchases), then GL, then ledgers (protections recomputed after the
            # above are gone within this transaction).
            if 'sales' in scope:
                do('sales_vouchers', SalesVou.objects.all(), SalesVou)
            if 'purchases' in scope:
                do('purchase_vouchers', PurchaseVoucher.objects.all(), PurchaseVoucher)
            if 'gl' in scope:
                do('gl_vouchers', VoucherMain.objects.filter(legacy_key__isnull=False), VoucherMain)
            if 'barcode_transactions' in scope:
                from inventory.models import BarcodeTransaction, BarcodeSplitMerge
                # Only the legacy-imported rows (legacy_key set); live-created
                # rows are preserved. op_stk is re-reconciled on the next import.
                do('barcode_transactions',
                   BarcodeTransaction.objects.filter(legacy_key__isnull=False), BarcodeTransaction)
                do('barcode_split_merge',
                   BarcodeSplitMerge.objects.filter(legacy_key__isnull=False), BarcodeSplitMerge)
            if 'customer_orders' in scope:
                do('customer_orders', CustomerOrder.objects.all(), CustomerOrder)
            if 'ledger_opening' in scope:
                do('ledger_opening', LedgerOpenBalance.objects.all(), LedgerOpenBalance)
            if 'ledgers' in scope:
                report['ledger_aliases'] = {'deleted': LedgerAlias.objects.count()}
                LedgerAlias.objects.all().delete()
                do('non_system_ledgers', Ledger.objects.filter(is_system=False), Ledger)

        class _Rollback(Exception):
            pass

        try:
            with transaction.atomic(), _muted_delete_signals():
                run()
                if not apply:
                    raise _Rollback  # discard preview deletes
        except _Rollback:
            pass

        return Response({'applied': apply, 'scope': sorted(scope), 'report': report})
