from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import *
from ..models import VoucherDetail


class BankStatementListCreate(ListCreateAPIView):
    """
    GET  /api/bank-statement/?bank_ledger=<id>&from_date=&to_date=
    POST /api/bank-statement/   — create a single bank statement entry
    """
    from ..serializers import BankStatementSerializer

    @property
    def serializer_class(self):
        from ..serializers import BankStatementSerializer
        return BankStatementSerializer

    def get_queryset(self):
        from ..models import BankStatementEntry
        retail = self.request.retail
        qs = BankStatementEntry.objects.filter(retail=retail).select_related('bank_ledger', 'matched_entry')
        bank_ldgr = self.request.query_params.get('bank_ledger')
        from_date = self.request.query_params.get('from_date')
        to_date   = self.request.query_params.get('to_date')
        if bank_ldgr:
            qs = qs.filter(bank_ledger_id=bank_ldgr)
        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)
        return qs.order_by('date', 'id')

    def perform_create(self, serializer):
        serializer.save(retail=self.request.retail)


class BankStatementDetail(APIView):
    """DELETE /api/bank-statement/<pk>/"""
    def delete(self, request, pk):
        from ..models import BankStatementEntry
        entry = BankStatementEntry.objects.filter(pk=pk, retail=request.retail).first()
        if not entry:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        entry.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bank_statement_match(request, pk):
    """
    POST /api/bank-statement/<pk>/match/
    Body: {"voucher_detail_id": <int>}
    Links a bank statement entry to a book entry.
    """
    from ..models import BankStatementEntry
    entry = BankStatementEntry.objects.filter(pk=pk, retail=request.retail).first()
    if not entry:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    vd_id = request.data.get('voucher_detail_id')
    if vd_id:
        vd = VoucherDetail.objects.filter(pk=vd_id, voucher_main__retail=request.retail).first()
        if not vd:
            return Response({"detail": "VoucherDetail not found."}, status=status.HTTP_404_NOT_FOUND)
        entry.matched_entry = vd
    else:
        entry.matched_entry = None
    entry.save(update_fields=['matched_entry'])
    return Response({"status": "ok", "matched": bool(entry.matched_entry)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bank_book_for_recon(request):
    """
    GET /api/bank-reconciliation/book-entries/?bank_ledger=<id>&from_date=&to_date=
    Returns VoucherDetail rows for the given bank ledger (for matching).
    """
    retail = request.retail
    bank_ldgr_id = request.GET.get('bank_ledger')
    from_date    = request.GET.get('from_date')
    to_date      = request.GET.get('to_date')

    if not bank_ldgr_id:
        return Response({"detail": "bank_ledger is required."}, status=status.HTTP_400_BAD_REQUEST)

    qs = VoucherDetail.objects.filter(
        voucher_main__retail=retail,
        account_id=bank_ldgr_id,
    ).select_related('voucher_main').order_by('voucher_main__date', 'id')

    if from_date:
        qs = qs.filter(voucher_main__date__gte=from_date)
    if to_date:
        qs = qs.filter(voucher_main__date__lte=to_date)

    data = [{
        'id':         vd.id,
        'date':       str(vd.voucher_main.date),
        'voucher_no': vd.voucher_no,
        'narration':  vd.voucher_main.narration,
        'debit':      float(vd.debit),
        'credit':     float(vd.credit),
        'chq_no':     vd.chq_no or '',
        'is_matched': hasattr(vd, 'bank_statement_match'),
    } for vd in qs]

    # Annotate is_matched properly
    from ..models import BankStatementEntry
    matched_vd_ids = set(
        BankStatementEntry.objects.filter(
            retail=retail, bank_ledger_id=bank_ldgr_id, matched_entry__isnull=False
        ).values_list('matched_entry_id', flat=True)
    )
    for row in data:
        row['is_matched'] = row['id'] in matched_vd_ids

    return Response(data)
