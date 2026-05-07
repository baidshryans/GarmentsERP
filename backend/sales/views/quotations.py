import json
import logging
logger = logging.getLogger(__name__)
from django.shortcuts import get_object_or_404, render
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.utils.timezone import make_aware
from django.utils import timezone
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from ..serializers import CustomerOrderSerializer, PortalCustomerOrderSerializer
from ..models import *
from django.contrib.auth.decorators import login_required
from userauth import views
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
#import other relevant models
from goldrates.models import PurityMaster
from contacts.models import Ledger, LedgerRole
from mastersconfig.models import Item
from ..models import *

from django.db.models import Q
from ..serializers import QuotationSerializer, QuotationListSerializer


class QuotationViewset(views.RetailBaseViewset):
    queryset = Quotation.objects.select_related(
        'ldgr', 'sales_person', 'retail'
    ).prefetch_related('items__details').all()
    serializer_class = QuotationSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['quotation_no', 'ldgr__ac_name', 'party_name']
    filterset_fields = ['status']
    ordering = ['-id']

    def get_serializer_class(self):
        if self.action == 'list':
            return QuotationListSerializer
        return QuotationSerializer

    def perform_create(self, serializer):
        from accounting.utils import peek_next_bill_number
        retail = getattr(self.request, 'retail', None)
        fiscal_year = getattr(retail, 'active_fy', None) if retail else None
        qt_no = peek_next_bill_number(retail, "QT")
        serializer.save(
            retail=retail,
            fiscal_year=fiscal_year,
            created_by=self.request.user,
            quotation_no=qt_no,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_qt_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response({"error": "Missing or invalid X-RETAIL-ID header"}, status=status.HTTP_400_BAD_REQUEST)
    bill_no = peek_next_bill_number(request.retail, "QT")
    return Response({"billno": bill_no})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def quotation_initial_data(request):
    """Combined initial data for the Quotation form."""
    from mastersconfig.models import SalesPersonMaster
    from mastersconfig.serializers import SalesPersonMasterSerializer
    from accounting.utils import peek_next_bill_number
    from accounting.serializers import LedgerLightSerializer
    from goldrates.models import PurityMaster

    if not request.retail:
        return Response({"error": "Missing or invalid X-RETAIL-ID header"}, status=status.HTTP_400_BAD_REQUEST)

    bill_no = peek_next_bill_number(request.retail, "QT")
    ledgers_qs = (Ledger.objects
                  .filter(roles__role='CO')
                  .select_related('ac_group')
                  .prefetch_related('roles')
                  .only('id', 'ac_name', 'ac_group')
                  .distinct())
    salespersons_qs = SalesPersonMaster.objects.filter(retail=request.retail)
    purities = list(PurityMaster.objects.values('purity', 'gw_per'))

    return Response({
        "billno": bill_no,
        "ledgers": LedgerLightSerializer(ledgers_qs, many=True).data,
        "salespersons": SalesPersonMasterSerializer(salespersons_qs, many=True).data,
        "purities": purities,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def quotation_print_data(request, pk):
    """Full quotation data for the print template."""
    qt = get_object_or_404(
        Quotation.objects.select_related('ldgr', 'sales_person')
        .prefetch_related('items__details'),
        pk=pk
    )
    data = QuotationSerializer(qt).data
    # Add party contact info if ledger exists
    if qt.ldgr:
        data['party_mobile'] = qt.ldgr.mobile1 or ''
        data['party_address'] = ', '.join(filter(None, [
            qt.ldgr.address1 or '', qt.ldgr.city or '', qt.ldgr.state or '',
        ]))
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quotation_duplicate(request, pk):
    """Duplicate a quotation with new number and draft status."""
    from accounting.utils import peek_next_bill_number
    from datetime import date, timedelta

    original = get_object_or_404(Quotation, pk=pk)
    retail = getattr(request, 'retail', None)
    new_no = peek_next_bill_number(retail, "QT")

    with transaction.atomic():
        new_qt = Quotation.objects.create(
            date1=date.today(),
            quotation_no=new_no,
            ldgr=original.ldgr,
            party_name=original.party_name,
            gold_rate_date=original.gold_rate_date,
            rate_18kt=original.rate_18kt,
            rate_22kt=original.rate_22kt,
            rate_24kt=original.rate_24kt,
            total_items=original.total_items,
            grand_total=original.grand_total,
            tax_percent=original.tax_percent,
            tax_amount=original.tax_amount,
            net_total=original.net_total,
            status='draft',
            valid_until=date.today() + timedelta(days=7),
            remarks=original.remarks,
            seller_info=original.seller_info,
            sales_person=original.sales_person,
            retail=retail,
            fiscal_year=getattr(retail, 'active_fy', None) if retail else None,
            created_by=request.user,
        )
        for item in original.items.all():
            new_item = QuotationItem.objects.create(
                quotation=new_qt,
                sl_no=item.sl_no,
                barcode=item.barcode,
                barcode_text=item.barcode_text,
                item=item.item,
                item_name=item.item_name,
                design_code=item.design_code,
                purity_text=item.purity_text,
                pcs=item.pcs,
                gw=item.gw,
                nw=item.nw,
                gold_rate=item.gold_rate,
                gold_amount=item.gold_amount,
                making_rate=item.making_rate,
                making_amount=item.making_amount,
                total_diamond_pcs=item.total_diamond_pcs,
                total_diamond_wt=item.total_diamond_wt,
                total_diamond_amt=item.total_diamond_amt,
                total_stone_pcs=item.total_stone_pcs,
                total_stone_wt=item.total_stone_wt,
                total_stone_amt=item.total_stone_amt,
                total_amount=item.total_amount,
                image_url=item.image_url,
            )
            for det in item.details.all():
                QuotationItemDetail.objects.create(
                    quotation_item=new_item,
                    packet=det.packet,
                    packet_name=det.packet_name,
                    item_name=det.item_name,
                    is_diamond=det.is_diamond,
                    pcs=det.pcs,
                    wt=det.wt,
                    rate=det.rate,
                    amount=det.amount,
                )
    return Response({"id": new_qt.id, "quotation_no": new_qt.quotation_no})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quotation_finalize(request, pk):
    """Finalize a quotation (draft → finalized)."""
    qt = get_object_or_404(Quotation, pk=pk)
    if qt.status != 'draft':
        return Response({"error": f"Cannot finalize quotation in '{qt.status}' status."}, status=status.HTTP_400_BAD_REQUEST)
    qt.status = 'finalized'
    qt.save(update_fields=['status'])
    return Response({"status": "finalized"})


@api_view(['GET'])
@permission_classes([])
def portal_customer_orders(request):
    """
    Portal endpoint: Customer sees their orders with status tracking.
    Only includes customer-relevant fields (order_no, delivery_status, item_count, etc.)
    Excludes vendor/karigar names for privacy.
    """
    from goldscheme.portal_auth import PortalTokenAuthentication, IsPortalAuthenticated

    auth = PortalTokenAuthentication()
    try:
        result = auth.authenticate(request)
        if result is None:
            return Response({'error': 'Portal authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)

    customer = getattr(request, 'portal_customer', None)
    if not customer:
        return Response({'error': 'Portal authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    orders = CustomerOrder.objects.filter(ldgr=customer).order_by('-date1')
    serializer = PortalCustomerOrderSerializer(orders, many=True)
    return Response(serializer.data)
