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
    'purchases':   ('import_purchases',            {'header': 'header', 'items': 'items', 'details': 'details'},
                    ['header', 'items', 'details']),
    'allocations': ('import_voucher_allocations',  {'receive': 'receive', 'payment': 'payment', 'journal': 'journal'},
                    []),  # at least one (validated below)
}

# download name -> template filename
TEMPLATE_FILES = {
    'voucher_main':              'legacy_voucher_main_template.csv',
    'voucher_details':           'legacy_voucher_details_template.csv',
    'sales_vou':                 'legacy_sales_vou_template.csv',
    'sales_vou_main':            'legacy_sales_vou_main_template.csv',
    'sales_vou_detail':          'legacy_sales_vou_detail_template.csv',
    'purchase_voucher':          'legacy_purchase_voucher_template.csv',
    'purchase_voucher_main':     'legacy_purchase_voucher_main_template.csv',
    'purchase_voucher_details':  'legacy_purchase_voucher_details_template.csv',
    'receive_amount':            'legacy_receive_amount_template.csv',
    'payment_amount':            'legacy_payment_amount_template.csv',
    'journal_amount':            'legacy_journal_amount_template.csv',
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
