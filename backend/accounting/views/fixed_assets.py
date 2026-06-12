from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from rest_framework import serializers, status
from rest_framework.decorators import permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from contacts.models import Ledger
from global_vars import VoucherType
from userauth.views import RetailBaseViewset

from ..models import *
from ..models import Account, VoucherDetail
from ..utils import *

import datetime as _dt
from userauth.permissions import RBACPermission
from ..models import (
    FixedAsset, FixedAssetSettings, IT_BLOCK_RATES,
)
from ..serializers import (
    FixedAssetSerializer, FixedAssetSettingsSerializer,
)
from ..fa_services import generate_suggestion_lines


# Maps IT block category → FA account group code
_IT_BLOCK_TO_AC_GROUP = {
    'BLDG_RES':  'FA-LB',
    'BLDG_COM':  'FA-LB',
    'FURN':      'FA-FF',
    'PLANT':     'FA-PM',
    'VEHICLE':   'FA-VH',
    'COMPUTER':  'FA-CE',
    'BOOKS':     'FA-PM',
    'INTANG':    'FA-PM',
}
_DEFAULT_FA_GROUP = 'FA-PM'


class FixedAssetViewSet(RetailBaseViewset):
    queryset         = FixedAsset.objects.all()
    serializer_class = FixedAssetSerializer
    permission_classes = [RBACPermission]

    def get_queryset(self):
        retail = getattr(self.request, 'retail', None)
        qs = FixedAsset.objects.filter(retail=retail).select_related('retail', 'asset_ledger')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_create(self, serializer):
        retail = self.request.retail
        asset = serializer.save(retail=retail)

        # Auto-create a matching ledger under the correct FA account group
        group_code = _IT_BLOCK_TO_AC_GROUP.get(asset.it_block_category or '', _DEFAULT_FA_GROUP)
        try:
            ac_group = Account.objects.get(code=group_code)
        except Account.DoesNotExist:
            ac_group = None

        ledger = Ledger.objects.create(
            ac_name=asset.asset_name,
            display_name=asset.asset_name,
            ac_group=ac_group,
            retail_code=retail,
            is_system=True,  # prevents independent edit/delete from ledger master
        )
        asset.asset_ledger = ledger
        asset.save(update_fields=['asset_ledger'])


class GenerateDepreciationSuggestionView(APIView):
    """
    Compute depreciation for all active assets over a date range.
    Stateless — returns suggested lines without persisting anything.
    The frontend keeps the worksheet in local state and POSTs back to
    PostDepreciationView to actually create the journal entry.
    """
    permission_classes = [RBACPermission]

    def post(self, request):
        retail = getattr(request, 'retail', None)

        period_from_str = request.data.get('period_from')
        period_to_str   = request.data.get('period_to')
        label           = request.data.get('label', '').strip()

        if not all([period_from_str, period_to_str, label]):
            return Response({'detail': 'period_from, period_to, and label are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            period_from = _dt.date.fromisoformat(period_from_str)
            period_to   = _dt.date.fromisoformat(period_to_str)
        except ValueError:
            return Response({'detail': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        if period_from > period_to:
            return Response({'detail': 'period_from must be before period_to.'}, status=status.HTTP_400_BAD_REQUEST)

        lines_data = generate_suggestion_lines(retail, period_from, period_to)
        if not lines_data:
            return Response({'detail': 'No active fixed assets found for this retail.'}, status=status.HTTP_400_BAD_REQUEST)

        lines = [{
            'asset_id':           d['asset'].id,
            'asset_code':         d['asset'].asset_code,
            'asset_name':         d['asset'].asset_name,
            'asset_method':       d['asset'].depreciation_method,
            'asset_rate_or_life': str(d['asset'].rate_or_life),
            'purchase_cost':      str(d['asset'].purchase_cost),
            'opening_wdv':        str(d['opening_wdv']),
            'calculated_amount':  str(d['calculated_amount']),
            'approved_amount':    str(d['approved_amount']),
            'narration':          d['narration'],
        } for d in lines_data]

        total = sum(Decimal(l['calculated_amount']) for l in lines)

        return Response({
            'label':        label,
            'period_from':  period_from_str,
            'period_to':    period_to_str,
            'total_amount': str(total),
            'lines':        lines,
        })


class PostDepreciationView(APIView):
    """
    Take the edited worksheet from the frontend and post the depreciation
    journal entry. No suggestion record is persisted — only the voucher
    and the per-asset accumulated_depreciation are updated.

    Payload:
        {
          "label": "FY 24-25 Annual Depreciation",
          "period_to": "2026-03-31",
          "lines": [{"asset_id": 1, "approved_amount": "1234.56"}, ...]
        }
    """
    permission_classes = [RBACPermission]

    def post(self, request):
        retail      = getattr(request, 'retail', None)
        fiscal_year = getattr(request, 'fiscal_year', None)

        label        = (request.data.get('label') or '').strip()
        period_to_str = request.data.get('period_to')
        raw_lines    = request.data.get('lines') or []
        if not label:
            return Response({'detail': 'label is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not period_to_str:
            return Response({'detail': 'period_to is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            period_to = _dt.date.fromisoformat(period_to_str)
        except ValueError:
            return Response({'detail': 'Invalid period_to. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(raw_lines, list) or not raw_lines:
            return Response({'detail': 'lines payload is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            fa_settings = retail.fa_settings
        except FixedAssetSettings.DoesNotExist:
            return Response({'detail': 'Fixed Asset Settings not configured. Set up ledgers first.'}, status=status.HTTP_400_BAD_REQUEST)

        if not fa_settings.default_depreciation_expense_ldgr or not fa_settings.default_accum_depreciation_ldgr:
            return Response(
                {'detail': 'Both Depreciation Expense and Accumulated Depreciation ledgers must be set in Fixed Asset Settings.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate + collect asset rows
        rows = []
        total_approved = Decimal('0')
        for raw in raw_lines:
            try:
                asset_id = int(raw.get('asset_id'))
                amount   = Decimal(str(raw.get('approved_amount', '0')))
            except (TypeError, ValueError, InvalidOperation):
                return Response({'detail': 'Invalid line in payload.'}, status=status.HTTP_400_BAD_REQUEST)
            if amount <= 0:
                continue
            try:
                asset = FixedAsset.objects.select_related(
                    'accum_depreciation_ledger', 'depreciation_expense_ledger'
                ).get(pk=asset_id, retail=retail)
            except FixedAsset.DoesNotExist:
                return Response({'detail': f'Asset {asset_id} not found.'}, status=status.HTTP_404_NOT_FOUND)
            rows.append((asset, amount, (raw.get('narration') or '')[:200]))
            total_approved += amount

        if total_approved <= 0:
            return Response({'detail': 'Total approved amount must be > 0.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            voucher_no = get_next_bill_number(retail, VoucherType.depreciation, fiscal_year)
            voucher = VoucherMain.objects.create(
                date=_dt.date.today(), voucher_no=voucher_no,
                narration=label[:150], amount=total_approved,
                voucher_type=VoucherType.depreciation, retail=retail, fiscal_year=fiscal_year,
            )

            vd_rows = []
            for asset, amount, _narr in rows:
                exp_ldgr   = asset.depreciation_expense_ledger or fa_settings.default_depreciation_expense_ldgr
                accum_ldgr = asset.accum_depreciation_ledger   or fa_settings.default_accum_depreciation_ldgr
                vd_rows.append(VoucherDetail(
                    voucher_main=voucher, voucher_no=voucher_no,
                    voucher_type=VoucherType.depreciation, account=exp_ldgr,
                    debit=amount, credit=Decimal('0'),
                ))
                vd_rows.append(VoucherDetail(
                    voucher_main=voucher, voucher_no=voucher_no,
                    voucher_type=VoucherType.depreciation, account=accum_ldgr,
                    debit=Decimal('0'), credit=amount,
                ))
            VoucherDetail.objects.bulk_create(vd_rows)

            for asset, amount, _narr in rows:
                asset.accumulated_depreciation += amount
                # Advance the high-water mark so this period isn't re-suggested.
                if not asset.last_depreciation_through or period_to > asset.last_depreciation_through:
                    asset.last_depreciation_through = period_to
                if asset.is_fully_depreciated:
                    asset.status = 'FULLY_DEPRECIATED'
                asset.save(update_fields=[
                    'accumulated_depreciation', 'last_depreciation_through', 'status',
                ])

        return Response({
            'detail':       'Depreciation posted.',
            'voucher_id':   voucher.id,
            'voucher_no':   voucher_no,
            'total_amount': str(total_approved),
        })


class FASettingsView(APIView):
    permission_classes = [RBACPermission]

    def get(self, request):
        retail = getattr(request, 'retail', None)
        obj, _ = FixedAssetSettings.objects.get_or_create(retail=retail)
        return Response(FixedAssetSettingsSerializer(obj).data)

    def put(self, request):
        retail = getattr(request, 'retail', None)
        obj, _ = FixedAssetSettings.objects.get_or_create(retail=retail)
        ser = FixedAssetSettingsSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class ITBlockRatesView(APIView):
    permission_classes = [RBACPermission]

    def get(self, request):
        data = [
            {'key': k, 'label': v[0], 'rate': str(v[1])}
            for k, v in IT_BLOCK_RATES.items()
        ]
        return Response(data)
