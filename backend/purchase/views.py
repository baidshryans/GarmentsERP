from django.shortcuts import render, redirect
from django.db.models import Prefetch
from datetime import date
from django.utils import timezone
import mimetypes
import os

from purchase.filters import PurchaseItemFilterSet
from purchase.serializer import PurchaseOrderForPostSerializer, PurchaseOrderSerializer, PurchaseReturnSerializer, PurchaseVoucherItemsSerializer, PurchaseVoucherPostSerializer, PurchaseVoucherSerializer, PurchaseVoucherToReturnSerializer
from userauth.views import RetailBaseViewset
from .models import *
import json
from rest_framework.viewsets import ModelViewSet
from django.urls import reverse
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .utils import *
from django.shortcuts import get_object_or_404
from jewel_test.utils import *
from rest_framework.generics import ListCreateAPIView,ListAPIView
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
# Create your views here.
from global_vars import STATES_OF_INDIA
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend



@api_view(['GET'])
def purchase_voucher_number_view(request):
    try:
        order_no = generate_pv_no()
        return Response({"bill_no": order_no}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
def purchase_order_number_view(request):
    try:
        order_no = generate_po_no()
        return Response({"bill_no": order_no}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
 

class PurchaseOrderView(ListCreateAPIView):
    serializer_class = PurchaseOrderSerializer
    queryset = PurchaseOrder.objects.all()


class PurchaseVoucherView(ListCreateAPIView):
    serializer_class = PurchaseVoucherSerializer
    queryset = PurchaseVoucher.objects.all()

class PurchaseReturnViewset(RetailBaseViewset):
    queryset = PurchaseReturn.objects.select_related('ldgr', 'ac_voucher', 'retail').prefetch_related(
        'purchasereturnitems_set__purchasereturndetails_set'
    ).all()
    serializer_class = PurchaseReturnSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ["billno", "ldgr__ac_name"]
    ordering = ['billno']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    def get_serializer_context(self):
        """Pass request explicitly so the serializer can access request.retail
        when creating the accounting journal entry."""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        retail = getattr(self.request, 'retail', None)
        if not retail:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"retail": "Missing or invalid X-RETAIL-ID header."})
        serializer.save(retail=retail)

    def perform_update(self, serializer):
        retail = getattr(self.request, 'retail', None)
        if not retail:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"retail": "Missing or invalid X-RETAIL-ID header."})
        serializer.save(retail=retail)

class PurchaseVoucherViewset(RetailBaseViewset):
    queryset = PurchaseVoucher.objects.select_related('ldgr', 'retail').prefetch_related(
        'purchasevoucheritems_set__purchasevoucherdetails_set'
    ).all()
    serializer_class = PurchaseVoucherPostSerializer 
    filter_backends = [DjangoFilterBackend,OrderingFilter, SearchFilter]
    filterset_fields = ['voucher_type']
    search_fields = ["billno","ldgr__ac_name"]

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['date1','ldgr__ac_name','billno',]

class PurchaseOrderViewset(RetailBaseViewset):
    queryset = PurchaseOrder.objects.select_related('ldgr', 'retail').prefetch_related(
        'purchaseorderitems_set'
    ).all()
    serializer_class = PurchaseOrderForPostSerializer 
    filter_backends=[DjangoFilterBackend,OrderingFilter,SearchFilter]

    search_fields=["po_no","ldgr__ac_name"]

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['po_no'] 



@api_view(['GET'])
def get_purchase_for_return(request, po_no):
    if not request.retail:
        return Response({"error": "Missing or invalid X-RETAIL-ID header"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        pv = PurchaseVoucher.objects.get(billno=po_no)
        serializer = PurchaseVoucherToReturnSerializer(pv)
        return Response(serializer.data)
    except PurchaseVoucher.DoesNotExist:
        try:
            pr = PurchaseReturn.objects.get(billno=po_no)
            serializer = PurchaseReturnSerializer(pr)
            return Response(serializer.data)
        except PurchaseReturn.DoesNotExist:
            return Response({"error": "No purchase voucher or return found for this bill number."}, status=404)

class PurchaseItemView(ListAPIView):
    serializer_class = PurchaseVoucherItemsSerializer
    queryset = PurchaseVoucherItems.objects.all()
    filter_backends = [DjangoFilterBackend , OrderingFilter]

    filterset_class = PurchaseItemFilterSet

@api_view(['GET'])
def get_next_pv_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response({"error": "Missing or invalid X-RETAIL-ID header"}, status=status.HTTP_400_BAD_REQUEST)
    bill_no = peek_next_bill_number(request.retail, "PV")
    return Response({"billno": bill_no})

@api_view(['GET'])
def get_next_pr_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response({"error": "Missing or invalid X-RETAIL-ID header"}, status=status.HTTP_400_BAD_REQUEST)
    bill_no = peek_next_bill_number(request.retail, "PR")
    return Response({"billno": bill_no})

@api_view(['GET'])
def get_next_po_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response({"error": "Missing or invalid X-RETAIL-ID header"}, status=status.HTTP_400_BAD_REQUEST)
    bill_no = peek_next_bill_number(request.retail, "PO")
    return Response({"billno": bill_no})


@api_view(['GET'])
def purchase_return_initial_data(request):
    """Combined initial data for the PurchaseReturn form."""
    from mastersconfig.models import Item, Packet
    from mastersconfig.serializers import ItemSerializer, PacketSerializer
    from goldrates.serializer import PurityMasterSerializer
    from contacts.models import Ledger
    from accounting.serializers import LedgerSerializer
    from goldrates.models import PurityMaster

    if not request.retail:
        return Response(
            {"error": "Missing or invalid X-RETAIL-ID header"},
            status=status.HTTP_400_BAD_REQUEST
        )

    from accounting.utils import peek_next_bill_number
    bill_no = peek_next_bill_number(request.retail, "PR")
    ledgers_qs = Ledger.objects.filter(roles__role='SC').only('id', 'ac_name', 'ac_group').distinct()
    items_qs = Item.objects.select_related('hsn_no').all()
    purity_qs = PurityMaster.objects.all()
    packets_qs = Packet.objects.select_related('stone_item_id').all()

    return Response({
        "billno": bill_no,
        "ledgers": LedgerSerializer(ledgers_qs, many=True).data,
        "items": ItemSerializer(items_qs, many=True).data,
        "purity": PurityMasterSerializer(purity_qs, many=True).data,
        "packets": PacketSerializer(packets_qs, many=True).data,
    })


class PurchaseAttachmentListCreate(ListCreateAPIView):
    from .serializer import PurchaseAttachmentSerializer
    serializer_class = PurchaseAttachmentSerializer
    from rest_framework.parsers import MultiPartParser
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        from .models import PurchaseAttachment
        purchase_id = self.request.query_params.get('purchase')
        if purchase_id:
            return PurchaseAttachment.objects.filter(purchase_id=purchase_id).order_by('-uploaded_at')
        return PurchaseAttachment.objects.none()


class PurchaseAttachmentDelete(APIView):
    def delete(self, request, pk):
        from .models import PurchaseAttachment
        try:
            att = PurchaseAttachment.objects.get(pk=pk)
            att.file.delete(save=False)
            att.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PurchaseAttachment.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def serve_attachment_file(request, name):
    """
    Stream an attachment file from the configured (dynamic) storage root.
    Authentication is intentionally not enforced here — consistent with Django's
    default MEDIA_URL behaviour for local deployments. The URL contains an
    opaque hashed name (Django's default collision-avoidance) which provides
    de-facto obscurity.
    """
    from urllib.parse import unquote
    from mastersconfig.storage import _configured_root

    # Decode percent-encoded characters and normalise separators
    name = unquote(name)
    root = _configured_root()
    abs_root = os.path.abspath(root)
    full_path = os.path.normpath(os.path.join(abs_root, name))

    # Path-traversal guard: resolved path must start with the storage root
    if not full_path.startswith(abs_root + os.sep) and full_path != abs_root:
        return Response({'error': 'Forbidden'}, status=403)

    if not os.path.isfile(full_path):
        return Response({'error': 'File not found'}, status=404)

    content_type, _ = mimetypes.guess_type(full_path)
    content_type = content_type or 'application/octet-stream'

    with open(full_path, 'rb') as f:
        from django.http import HttpResponse
        response = HttpResponse(f.read(), content_type=content_type)

    basename = os.path.basename(full_path)
    response['Content-Disposition'] = f'inline; filename="{basename}"'
    return response


@api_view(['GET'])
def tds_register(request):
    retail = request.retail
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    section = request.GET.get('section')

    qs = PurchaseVoucher.objects.filter(
        retail=retail,
        tds_amt__gt=0
    ).select_related('ldgr', 'tds_section')

    if from_date:
        qs = qs.filter(date1__gte=from_date)
    if to_date:
        qs = qs.filter(date1__lte=to_date)
    if section:
        qs = qs.filter(tds_section__section_code=section)

    data = [{
        'bill_no': v.billno,
        'date': v.date1,
        'vendor': v.ldgr.ac_name if v.ldgr else '',
        'pan': v.ldgr.pan or '' if v.ldgr else '',
        'section': v.tds_section.section_code if v.tds_section else '',
        'description': v.tds_section.description if v.tds_section else '',
        'taxable_value': float(v.tds_taxable_value),
        'tds_rate': float(v.tds_rate),
        'tds_amt': float(v.tds_amt),
    } for v in qs]

    return Response(data)






