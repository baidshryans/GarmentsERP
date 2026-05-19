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
from django.db.models import Sum as _Sum
from django.utils import timezone as _tz
from userauth.permissions import RBACPermission
from ..models import (
    FixedAsset, DepreciationSuggestion, DepreciationSuggestionLine,
    FixedAssetSettings, IT_BLOCK_RATES,
)
from ..serializers import (
    FixedAssetSerializer, DepreciationSuggestionSerializer,
    DepreciationSuggestionLineSerializer, FixedAssetSettingsSerializer,
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


class DepreciationSuggestionViewSet(RetailBaseViewset):
    queryset         = DepreciationSuggestion.objects.all()
    serializer_class = DepreciationSuggestionSerializer
    permission_classes = [RBACPermission]

    def get_queryset(self):
        retail = getattr(self.request, 'retail', None)
        return (
            DepreciationSuggestion.objects
            .filter(retail=retail)
            .prefetch_related('lines__asset')
            .select_related('voucher', 'approved_by', 'fiscal_year')
        )

    def create(self, request, *args, **kwargs):
        return Response({'detail': 'Use /api/fa/generate-suggestion/ to create a suggestion.'}, status=405)


class GenerateDepreciationSuggestionView(APIView):
    permission_classes = [RBACPermission]

    def post(self, request):
        retail      = getattr(request, 'retail', None)
        fiscal_year = getattr(request, 'fiscal_year', None)

        period_from_str = request.data.get('period_from')
        period_to_str   = request.data.get('period_to')
        label           = request.data.get('label', '').strip()
        fy_id           = request.data.get('fiscal_year_id')

        if not all([period_from_str, period_to_str, label]):
            return Response({'detail': 'period_from, period_to, and label are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            period_from = _dt.date.fromisoformat(period_from_str)
            period_to   = _dt.date.fromisoformat(period_to_str)
        except ValueError:
            return Response({'detail': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        if period_from > period_to:
            return Response({'detail': 'period_from must be before period_to.'}, status=status.HTTP_400_BAD_REQUEST)

        if fy_id:
            from mastersconfig.models import FiscalYearMaster
            try:
                fiscal_year = FiscalYearMaster.objects.get(pk=fy_id, retail=retail)
            except FiscalYearMaster.DoesNotExist:
                return Response({'detail': 'Fiscal year not found.'}, status=status.HTTP_404_NOT_FOUND)

        overlapping = DepreciationSuggestion.objects.filter(
            retail=retail, status='PENDING',
            period_from__lte=period_to, period_to__gte=period_from,
        ).exists()
        if overlapping:
            return Response(
                {'detail': 'A pending suggestion already covers this period. Approve or reject it first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lines_data = generate_suggestion_lines(retail, period_from, period_to)
        if not lines_data:
            return Response({'detail': 'No active fixed assets found for this retail.'}, status=status.HTTP_400_BAD_REQUEST)

        total = sum(d['calculated_amount'] for d in lines_data)

        with transaction.atomic():
            suggestion = DepreciationSuggestion.objects.create(
                retail=retail, fiscal_year=fiscal_year,
                label=label, period_from=period_from, period_to=period_to,
                total_amount=total,
            )
            DepreciationSuggestionLine.objects.bulk_create([
                DepreciationSuggestionLine(
                    suggestion=suggestion, asset=d['asset'],
                    opening_wdv=d['opening_wdv'], calculated_amount=d['calculated_amount'],
                    approved_amount=d['approved_amount'], overridden=d['overridden'],
                    narration=d['narration'],
                )
                for d in lines_data
            ])

        suggestion.refresh_from_db()
        return Response(DepreciationSuggestionSerializer(suggestion).data, status=status.HTTP_201_CREATED)


class UpdateSuggestionLineView(APIView):
    permission_classes = [RBACPermission]

    def patch(self, request, pk):
        retail = getattr(request, 'retail', None)
        try:
            line = DepreciationSuggestionLine.objects.select_related('suggestion__retail').get(pk=pk)
        except DepreciationSuggestionLine.DoesNotExist:
            return Response({'detail': 'Line not found.'}, status=status.HTTP_404_NOT_FOUND)

        if line.suggestion.retail != retail:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if line.suggestion.status != 'PENDING':
            return Response({'detail': 'Only PENDING suggestions can be edited.'}, status=status.HTTP_400_BAD_REQUEST)

        new_amount = request.data.get('approved_amount')
        narration  = request.data.get('narration')

        if new_amount is not None:
            try:
                line.approved_amount = Decimal(str(new_amount))
            except (InvalidOperation, ValueError):
                return Response({'detail': 'Invalid amount.'}, status=status.HTTP_400_BAD_REQUEST)
            line.overridden = (line.approved_amount != line.calculated_amount)

        if narration is not None:
            line.narration = narration[:200]

        line.save(update_fields=['approved_amount', 'overridden', 'narration'])

        total = (
            DepreciationSuggestionLine.objects
            .filter(suggestion=line.suggestion)
            .aggregate(t=_Sum('approved_amount'))
        )['t'] or Decimal('0')
        line.suggestion.total_amount = total
        line.suggestion.save(update_fields=['total_amount'])

        return Response(DepreciationSuggestionLineSerializer(line).data)


class ApproveDepreciationSuggestionView(APIView):
    permission_classes = [RBACPermission]

    def post(self, request, pk):
        retail      = getattr(request, 'retail', None)
        fiscal_year = getattr(request, 'fiscal_year', None)

        try:
            suggestion = (
                DepreciationSuggestion.objects
                .prefetch_related('lines__asset')
                .select_related('retail', 'fiscal_year')
                .get(pk=pk, retail=retail)
            )
        except DepreciationSuggestion.DoesNotExist:
            return Response({'detail': 'Suggestion not found.'}, status=status.HTTP_404_NOT_FOUND)

        if suggestion.status != 'PENDING':
            return Response({'detail': f'Suggestion is already {suggestion.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        if suggestion.fiscal_year:
            fiscal_year = suggestion.fiscal_year

        try:
            fa_settings = retail.fa_settings
        except FixedAssetSettings.DoesNotExist:
            return Response({'detail': 'Fixed Asset Settings not configured. Set up ledgers first.'}, status=status.HTTP_400_BAD_REQUEST)

        if not fa_settings.default_depreciation_expense_ldgr or not fa_settings.default_accum_depreciation_ldgr:
            return Response(
                {'detail': 'Both Depreciation Expense and Accumulated Depreciation ledgers must be set in Fixed Asset Settings.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lines = list(suggestion.lines.select_related(
            'asset__accum_depreciation_ledger', 'asset__depreciation_expense_ledger'
        ).all())
        total_approved = sum(l.approved_amount for l in lines)

        if total_approved <= 0:
            return Response({'detail': 'Total approved amount must be > 0.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            voucher_no = get_next_bill_number(retail, VoucherType.depreciation, fiscal_year)
            voucher = VoucherMain.objects.create(
                date=_dt.date.today(), voucher_no=voucher_no,
                narration=suggestion.label[:150], amount=total_approved,
                voucher_type=VoucherType.depreciation, retail=retail, fiscal_year=fiscal_year,
            )

            vd_rows = []
            for line in lines:
                if line.approved_amount <= 0:
                    continue
                exp_ldgr   = line.asset.depreciation_expense_ledger or fa_settings.default_depreciation_expense_ldgr
                accum_ldgr = line.asset.accum_depreciation_ledger    or fa_settings.default_accum_depreciation_ldgr
                vd_rows.append(VoucherDetail(
                    voucher_main=voucher, voucher_no=voucher_no,
                    voucher_type=VoucherType.depreciation, account=exp_ldgr,
                    debit=line.approved_amount, credit=Decimal('0'),
                ))
                vd_rows.append(VoucherDetail(
                    voucher_main=voucher, voucher_no=voucher_no,
                    voucher_type=VoucherType.depreciation, account=accum_ldgr,
                    debit=Decimal('0'), credit=line.approved_amount,
                ))
            # Plain bulk_create: the custom audit app captures created rows via
            # post_save signals, so depreciation postings still land in the audit log.
            VoucherDetail.objects.bulk_create(vd_rows)

            for line in lines:
                if line.approved_amount <= 0:
                    continue
                asset = line.asset
                asset.accumulated_depreciation += line.approved_amount
                if asset.is_fully_depreciated:
                    asset.status = 'FULLY_DEPRECIATED'
                asset.save(update_fields=['accumulated_depreciation', 'status'])

            suggestion.voucher      = voucher
            suggestion.status       = 'APPROVED'
            suggestion.total_amount = total_approved
            suggestion.approved_at  = _tz.now()
            suggestion.approved_by  = request.user
            suggestion.save(update_fields=['voucher', 'status', 'total_amount', 'approved_at', 'approved_by'])

        suggestion.refresh_from_db()
        return Response(DepreciationSuggestionSerializer(suggestion).data)


class RejectDepreciationSuggestionView(APIView):
    permission_classes = [RBACPermission]

    def post(self, request, pk):
        retail = getattr(request, 'retail', None)
        try:
            suggestion = DepreciationSuggestion.objects.get(pk=pk, retail=retail)
        except DepreciationSuggestion.DoesNotExist:
            return Response({'detail': 'Suggestion not found.'}, status=status.HTTP_404_NOT_FOUND)

        if suggestion.status != 'PENDING':
            return Response({'detail': f'Suggestion is already {suggestion.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        suggestion.status = 'REJECTED'
        suggestion.save(update_fields=['status'])
        return Response({'detail': 'Suggestion rejected.', 'id': suggestion.id})


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
