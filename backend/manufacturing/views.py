import io
import csv
from decimal import InvalidOperation
from rest_framework import viewsets
from rest_framework.parsers import MultiPartParser
from rest_framework.views import APIView
from inventory.models import OpeningInventory
from manufacturing.filters import JobCompletedFilter, KarigarReceiveItemFilter
from manufacturing.serializer import HallmarkIssueForPostSerializer, HallmarkReceiveForPostSerializer, KarigarGoldIssueSerializer, KarigarIssueForPostSerializer, KarigarIssueFullReportSerializer, KarigarIssueItemforJobStatusSerializer, KarigarIssueSerializer, KarigarMasterSerializer , KarigarIssueforJobsSerializer, KarigarReceiveForPostSerializer, KarigarReceiveItemForGetSerializer, KarigarReceiveSerializer, KarigarReceiveforNoSerializer, KarigarStoneIssueGetSerializer, KarigarStoneIssueReportSerializer,KarigarStoneIssueSerializer, KarigarStoneReceiveSerializer, LedgerReceiveReportSerializer, LedgerReportSerializer, HallmarkIssueReportSerializer, RefinaryIssueSerializer, RefinaryReceiveSerializer, MeltingIssueSerializer, MeltingReceiveSerializer, AssayIssueSerializer, AssayReceiveSerializer
from mastersconfig.serializers import PacketSerializer, PacketWithTotalSerializer
from userauth.permissions import RBACPermission
from .models import *
from .utils import *
from goldrates.models import *
from purchase.models import *
from decimal import Decimal
from django.db.models import Sum, F
from django.shortcuts import render,redirect
from accounting.utils import peek_next_bill_number
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from collections import defaultdict
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.db import transaction
#from django.utils.timezone import make_aware
from django.utils import timezone
from userauth import views
from django.utils.dateparse import parse_date
from django.contrib.contenttypes.models import ContentType
from datetime import datetime
from rest_framework.generics import ListAPIView,ListCreateAPIView,RetrieveUpdateDestroyAPIView
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q,Prefetch

# Create your views here.
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_slip_no(request):
    try:
        bill_no = peek_next_bill_number(request.retail, 'IV')
        return Response({"next_slip_no": bill_no})
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_karigar_issue(request):
    data = request.data
    serializer = KarigarIssueForPostSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    instance = serializer.save(retail=request.retail)

    # ── Duplicate-issue warning check ─────────────────────────────────────────
    # For each item in the new issue, check if the same customer_order_item
    # is already out with another karigar (rec_status=False).
    warnings = []
    for item in instance.items.all():
        if item.customer_order_item_id:
            conflict = KarigarIssueItem.objects.filter(
                customer_order_item_id=item.customer_order_item_id,
                rec_status=False,
            ).exclude(pk=item.pk).select_related('issue_slip__karigar_ldgr')
            for c in conflict:
                warnings.append(
                    f"Item sl#{item.issue_sl_no} ({item.item_id}) is already issued to "
                    f"'{c.issue_slip.karigar_ldgr.ac_name}' (slip: {c.issue_slip.issue_slip_no}) "
                    f"and not yet received back."
                )

    response_data = serializer.data
    if warnings:
        response_data = dict(response_data) if not isinstance(response_data, dict) else response_data
        response_data['warnings'] = warnings
    return Response(data=response_data, status=status.HTTP_201_CREATED)

class SampleIssueViewSet(views.RetailBaseViewset):
    from .serializer import SampleIssueSerializer as _SIS
    from .models import SampleIssue as _SI
    serializer_class = _SIS
    queryset = _SI.objects.select_related('karigar_ldgr').prefetch_related(
        'items__piece__item', 'items__piece__purity',
    ).all()
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['billno', 'karigar_ldgr__ac_name']
    ordering = ['-date1', '-id']


def sample_issue_next_billno(request):
    """Return next billno for Sample Issue: SI/<FY>/<n>."""
    from django.http import JsonResponse
    from .models import SampleIssue
    retail_id = request.GET.get('retail')
    fy_id = request.GET.get('fiscal_year')
    qs = SampleIssue.objects.all()
    if retail_id:
        qs = qs.filter(retail_id=retail_id)
    if fy_id:
        qs = qs.filter(fiscal_year_id=fy_id)
    last = qs.order_by('-id').first()
    n = 1
    if last and last.billno:
        try:
            n = int(last.billno.split('/')[-1]) + 1
        except (ValueError, AttributeError):
            n = qs.count() + 1
    prefix = f"SI/{fy_id or 'X'}/"
    return JsonResponse({'next_billno': f"{prefix}{n}"})


class UnbarcodedForPickerView(APIView):
    """
    List UnBarcodedMain rows eligible for Sample Issue:
      stk_status=True AND (kr_code IS NULL OR kr_code=<karigar>)
    Query: ?karigar=<ledger_id>  (optional filter)
    """
    def get(self, request):
        from inventory.models import UnBarcodedMain
        from django.db.models import Q
        karigar = request.query_params.get('karigar')
        qs = UnBarcodedMain.objects.filter(stk_status=True).select_related('item', 'purity', 'kr_code')
        if karigar:
            qs = qs.filter(Q(kr_code__isnull=True) | Q(kr_code_id=karigar))
        else:
            qs = qs.filter(kr_code__isnull=True)
        data = [{
            'id': p.id,
            'label': f"{p.item.item_name if p.item else ''} — {p.gw}g — {p.design_code or ''}",
            'item': p.item.item_name if p.item else '',
            'item_id': p.item_id,
            'purity': p.purity.purity if p.purity else '',
            'purity_id': p.purity_id,
            'pcs': p.pcs,
            'gw': float(p.gw or 0),
            'design_code': p.design_code or '',
            'huid': getattr(p, 'huid', '') or '',
            'with_karigar': p.kr_code.ac_name if p.kr_code else None,
        } for p in qs.order_by('-id')[:500]]
        return Response(data)


class KarigarIssueViewSet(views.RetailBaseViewset):
    serializer_class = KarigarIssueForPostSerializer
    queryset = KarigarIssue.objects.select_related('karigar_ldgr').prefetch_related(
        'items__item',
        'items__purity',
    ).all()
    filter_backends=[DjangoFilterBackend,OrderingFilter,SearchFilter]

    search_fields=['issue_slip_no','karigar_ldgr__ac_name']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['issue_slip_no'] 


class ListKarigarIssueView(ListAPIView):
    serializer_class = KarigarIssueSerializer
    permission_classes = [RBACPermission]
    queryset = KarigarIssue.objects.all()
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    
    
    search_fields = ["issue_slip_no"]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(retail=self.request.retail)


class ListKarigarStoneIssue(ListAPIView):
    serializer_class = KarigarStoneIssueSerializer
    queryset = KarigarStoneIssue.objects.all()
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    
    
    search_fields = ["issue_slip_no"]

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hallmark_issue_billno_view(request):
    try:
        bill_no = peek_next_bill_number(request.retail, 'HMIS')
        return Response({"bill_no": bill_no}, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hallmark_receive_billno_view(request):
    try:
        bill_no = peek_next_bill_number(request.retail, 'HM/RE')
        return Response({"bill_no": bill_no}, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def refinery_issue_billno_view(request):
    try:
        bill_no = peek_next_bill_number(request.retail, 'REF/ISS')
        return Response({"bill_no": bill_no}, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def refinery_receive_billno_view(request):
    try:
        bill_no = peek_next_bill_number(request.retail, 'REF/REC')
        return Response({"bill_no": bill_no}, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def melting_issue_billno_view(request):
    try:
        bill_no = peek_next_bill_number(request.retail, 'MLT/ISS')
        return Response({"bill_no": bill_no}, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def melting_receive_billno_view(request):
    try:
        bill_no = peek_next_bill_number(request.retail, 'MLT/REC')
        return Response({"bill_no": bill_no}, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def assay_issue_billno_view(request):
    try:
        bill_no = peek_next_bill_number(request.retail, 'ASY/ISS')
        return Response({"bill_no": bill_no}, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def assay_receive_billno_view(request):
    try:
        bill_no = peek_next_bill_number(request.retail, 'ASY/REC')
        return Response({"bill_no": bill_no}, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gold_issue_billno_view(request):
    try:
        bill_no = peek_next_bill_number(request.retail, 'IV/GL')
        return Response({"bill_no": bill_no}, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_karigar_gold_issue(request):
    with transaction.atomic():

        serializer = KarigarGoldIssueSerializer(data=request.data,many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(data=serializer.data)





@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stone_issue_billno_view(request):
    try:
        bill_no = peek_next_bill_number(request.retail, 'IV/STN')
        return Response({"bill_no": bill_no}, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stone_receive_billno_view(request):
    try:
        bill_no = peek_next_bill_number(request.retail, 'REC/STN')
        return Response({"bill_no": bill_no}, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def receiver_slip_no_view(request):
    try:
        bill_no = peek_next_bill_number(request.retail, 'RS')
        return Response({"receive_slip_no": bill_no}, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def get_pojo_list(request):
    slip_type = request.GET.get('slip_type')
    if slip_type == 'Job Order':
        job_list = KarigarIssue.objects.all()
        job_data = [{'id': job.id, 'name': job.issue_slip_no} for job in job_list]
    else:
        job_list = PurchaseOrder.objects.all()
        job_data = [{'id': job.id, 'name': job.po_no} for job in job_list]
    return JsonResponse({'results': job_data})

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_karigar_stone_issue(request):
    with transaction.atomic():
        serializer = KarigarStoneIssueSerializer(data=request.data,many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(data=serializer.data)


def filter_job_items(request):
    job_id = request.GET.get('job_id')  # Match this with the key used in the JS fetch call
    slip_type = request.GET.get('slip_type')
    if slip_type == 'Job Order' or slip_type == None:
        job_item_list = KarigarIssueItem.objects.filter(issue_slip_id=job_id)
        job_items = [{ 'job_id':item.issue_slip.id,'id':item.id,'item_id': item.item_id, 'job_sl_no': item.issue_sl_no} for item in job_item_list]  # Assuming sl_no is the correct field
    else:
        job_item_list = PurchaseOrderItems.objects.filter(po_slip_id=job_id)
        job_items = [{'job_id':item.po_slip.id,'id':item.id,'item_id': item.item_id, 'job_sl_no': item.po_sl_no} for item in job_item_list]  # Assuming sl_no is the correct field
    
    #print(job_items)
    return JsonResponse({'job_items': job_items})


#--------------------------Stone receive--------------------------------------------------------
from django.db.models import Sum, OuterRef, Subquery, Value, IntegerField, DecimalField
from django.db.models.functions import Coalesce
@api_view()
@permission_classes([IsAuthenticated])
def fetch_receive_packets(request):
    ref_job_no = request.GET.get('ref_job_no')
    slip_type = request.GET.get('slip_type')
    
    job_sl_no = request.GET.get('ref_job_sl_no')
    if slip_type=="Job Order":
        ref_job_instance = KarigarIssue.objects.get(id = ref_job_no)
        job_sl_no_instance = KarigarIssueItem.objects.get(id = job_sl_no)
        packets = KarigarStoneIssue.objects.filter(ref_job_object_id=ref_job_instance.id, job_sl_object_id=job_sl_no_instance.id)
        # received_packets = KarigarStoneReceive.objects.filter(ref_job_object_id=ref_job_instance.id, job_sl_object_id=job_sl_no_instance.id)
        # # packets_data = [{'id': packet.packet.id, 'pckt_no':packet.packet.pckt_no} for packet in packets] 
        # packets_data = Packet.objects.filter(karigarstoneissue__in=packets).distinct()
        # return JsonResponse({'packets': PacketSerializer(packets_data,many=True).data})
    
        # Subqueries for issued and received pcs for each packet
        issued_pcs_subquery = KarigarStoneIssue.objects.filter(
        packet=OuterRef('id'),
        ref_job_object_id=ref_job_instance.id,
        job_sl_object_id=job_sl_no_instance.id
        ).values('packet').annotate(
            total_issued_pcs=Sum('pcs'),
            total_issued_ct=Sum('ct'),
            total_issued_gw=Sum('gw')
        ).values('total_issued_pcs', 'total_issued_ct', 'total_issued_gw')

        received_pcs_subquery = KarigarStoneReceive.objects.filter(
            packet=OuterRef('id'),
            ref_job_object_id=ref_job_instance.id,
            job_sl_object_id=job_sl_no_instance.id
        ).values('packet').annotate(
            total_returned_pcs=Sum('return_pcs'),
            total_returned_ct=Sum('return_ct'),
            total_returned_gw=Sum('return_gw'),

            total_broken_pcs=Sum('broken_pcs'),
            total_broken_ct=Sum('broken_ct'),
            total_broken_gw=Sum('broken_gw'),

            total_loss_pcs=Sum('loss_pcs'),
            total_loss_ct=Sum('loss_ct'),
            total_loss_gw=Sum('loss_gw'),
        ).values(
            'total_returned_pcs', 'total_returned_ct', 'total_returned_gw',
            'total_broken_pcs', 'total_broken_ct', 'total_broken_gw',
            'total_loss_pcs', 'total_loss_ct', 'total_loss_gw',
        )

        # Annotate packets_data with totals
        packets_data = Packet.objects.filter(karigarstoneissue__in=packets).distinct().annotate(
            total_issued_pcs=Coalesce(Subquery(issued_pcs_subquery.values('total_issued_pcs')), Value(0), output_field=IntegerField()),
            total_issued_ct=Coalesce(Subquery(issued_pcs_subquery.values('total_issued_ct')), Value(0), output_field=DecimalField()),
            total_issued_gw=Coalesce(Subquery(issued_pcs_subquery.values('total_issued_gw')), Value(0), output_field=DecimalField()),

            total_returned_pcs=Coalesce(Subquery(received_pcs_subquery.values('total_returned_pcs')), Value(0), output_field=IntegerField()),
            total_returned_ct=Coalesce(Subquery(received_pcs_subquery.values('total_returned_ct')), Value(0), output_field=DecimalField()),
            total_returned_gw=Coalesce(Subquery(received_pcs_subquery.values('total_returned_gw')), Value(0), output_field=DecimalField()),

            total_broken_pcs=Coalesce(Subquery(received_pcs_subquery.values('total_broken_pcs')), Value(0), output_field=IntegerField()),
            total_broken_ct=Coalesce(Subquery(received_pcs_subquery.values('total_broken_ct')), Value(0), output_field=DecimalField()),
            total_broken_gw=Coalesce(Subquery(received_pcs_subquery.values('total_broken_gw')), Value(0), output_field=DecimalField()),

            total_loss_pcs=Coalesce(Subquery(received_pcs_subquery.values('total_loss_pcs')), Value(0), output_field=IntegerField()),
            total_loss_ct=Coalesce(Subquery(received_pcs_subquery.values('total_loss_ct')), Value(0), output_field=DecimalField()),
            total_loss_gw=Coalesce(Subquery(received_pcs_subquery.values('total_loss_gw')), Value(0), output_field=DecimalField()),

            total_receivable_pcs=F('total_issued_pcs') - (F('total_returned_pcs') + F('total_broken_pcs') + F('total_loss_pcs')),
            total_receivable_ct=F('total_issued_ct') - (F('total_returned_ct') + F('total_broken_ct') + F('total_loss_ct')),
            total_receivable_gw=F('total_issued_gw') - (F('total_returned_gw') + F('total_broken_gw') + F('total_loss_gw'))
        )
        # # # Add net_pcs in Python logic
        # response_data = [
        #     {
        #         'id': packet.id,
        #         'pckt_no': packet.pckt_no,
        #         'total_issued': packet.total_issued or 0,
        #         'total_received': packet.total_received or 0,
        #         'net_pcs': (packet.total_issued or 0) - (packet.total_received or 0),
        #     }
        #     for packet in packets_data
        # ]

        return Response(data=PacketWithTotalSerializer(packets_data,many=True).data) 
                # return JsonResponse({'packets': []})
    
    elif slip_type=="Purchase Order":
        ref_job_instance = PurchaseOrder.objects.get(po_no=ref_job_no)
        job_sl_no_instance = PurchaseOrderItems.objects.get(po_slip_id = ref_job_instance.id, po_sl_no=job_sl_no)
        packets = KarigarStoneIssue.objects.filter(ref_job_object_id=ref_job_instance.id, job_sl_object_id=job_sl_no_instance.id)
        # packets_data = [{'id': packet.packet.id, 'pckt_no':packet.packet.pckt_no} for packet in packets] 
        packets_data = KarigarStoneIssueSerializer(packets,many=True).data
        return JsonResponse({'packets': packets_data})
    else:
        return JsonResponse({'packets': []})






@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_karigar_stone_receive(request):
    with transaction.atomic():

        data = [dict(item) for item in request.data]
        for item in data:
            item["retail"] = request.retail.id
        serializer = KarigarStoneReceiveSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(data=serializer.data)

#-----------------------------------------------KR receive-----------------------------------------


def fetch_main_item_id(request):
    packet = request.GET.get('packet')
    packet_instance = Packet.objects.get(pckt_no=packet)

    packet_data = {
        'id': packet_instance.id,
        'stone_item_id': packet_instance.stone_item_id.id,  # Assuming stone_item_id is a foreign key
        'stone_item_name': packet_instance.stone_item_id.item_name,  # Access item_name from the related model
        'shape_name': packet_instance.shape.shape_name,  # Assuming shape is a foreign key
        'uom': packet_instance.stone_item_id.uom,  # Assuming shape is a foreign key
    }

    return JsonResponse(packet_data)


def fetch_main_details(request):
    job_sl_no = request.GET.get('job_sl_no')
    ref_job_no = request.GET.get('ref_job_no')

    # Fetch the issue slip instance
    karigar_issue_instance = KarigarIssue.objects.get(issue_slip_no=ref_job_no)
    
    # Fetch the issued item
    issued_item = KarigarIssueItem.objects.get(issue_sl_no=job_sl_no, issue_slip=karigar_issue_instance)

    # Query for stone issues
    stone_issue = KarigarStoneIssue.objects.filter(ref_job_object_id=karigar_issue_instance.id , job_sl_object_id=issued_item.id) \
        .values('packet__pckt_no', 'packet', 'packet__shape__shape_name', 'packet__stone_item_id__short_code', 
                'packet__stone_item_id__item_name', 'packet__stone_item_id', 'packet__rate_for_retail', 
                'packet__stone_item_id__uom') \
        .annotate(
            pcs=Sum('pcs'),
            gw=Sum('gw'),
            ct=Sum('ct')
        )
    
    # Query for stone receives
    stone_receive = KarigarStoneReceive.objects.filter(ref_job_object_id=karigar_issue_instance.id, job_sl_object_id=issued_item.id) \
        .values('packet__pckt_no', 'packet', 'packet__shape__shape_name', 'packet__stone_item_id__short_code', 
                'packet__stone_item_id__item_name', 'packet__stone_item_id', 'packet__rate_for_retail', 
                'packet__stone_item_id__uom') \
        .annotate(
            return_pcs=Sum('return_pcs'),
            return_gw=Sum('return_gw'),
            return_ct=Sum('return_ct'),
            broken_pcs=Sum('broken_pcs'),
            broken_gw=Sum('broken_gw'),
            broken_ct=Sum('broken_ct'),
            loss_pcs=Sum('loss_pcs'),
            loss_gw=Sum('loss_gw'),
            loss_ct=Sum('loss_ct')
        )

    # Convert querysets to dictionaries based on packet number
    stone_issue_dict = {issue['packet__pckt_no']: issue for issue in stone_issue}
    stone_receive_dict = {recv['packet__pckt_no']: recv for recv in stone_receive}

    combined_data = []

    for pckt_no, issue_data in stone_issue_dict.items():
        uom = issue_data.get('packet__stone_item_id__uom', 'ct')  # Default UOM to 'ct'

        combined_entry = {
            'packet_item_id': issue_data.get('packet__stone_item_id'),
            'packet_id': issue_data.get('packet'),
            'packet': pckt_no,
            'rate':issue_data.get('packet__rate_for_retail'),
            'item': issue_data.get('packet__stone_item_id__short_code'),
            'item_name': issue_data.get('packet__stone_item_id__item_name'),
            'shape': issue_data.get('packet__shape__shape_name', ''),
            'issue_pcs': issue_data.get('pcs', 0),
            'issue_gw': issue_data.get('gw', 0),
            'issue_ct': issue_data.get('ct', 0),
            'uom': uom,
            'return_pcs': 0,
            'return_gw': 0,
            'return_ct': 0,
            'broken_pcs': 0,
            'broken_gw': 0,
            'broken_ct': 0,
            'loss_pcs': 0,
            'loss_gw': 0,
            'loss_ct': 0,
            'balance_ct':issue_data.get('ct', 0),
            'balance_gw':issue_data.get('gw', 0),
            'balance_pcs':issue_data.get('pcs', 0),

            'remaining_value': 0,  # Placeholder for value used in jewellery
            'weighted_avg_rate': 0  # Placeholder for weighted average rate
        }

        # If there's corresponding data in stone receive, merge it
        if pckt_no in stone_receive_dict:
            recv_data = stone_receive_dict[pckt_no]
            issued_pcs = combined_entry["issue_pcs"]
            issued_gw = combined_entry["issue_gw"]
            issued_ct = combined_entry["issue_ct"]
            combined_entry.update({
                'return_pcs': recv_data.get('return_pcs', 0),
                'return_gw': recv_data.get('return_gw', 0),
                'return_ct': recv_data.get('return_ct', 0),
                'broken_pcs': recv_data.get('broken_pcs', 0) + recv_data.get('loss_pcs', 0) ,
                'broken_gw': recv_data.get('broken_gw', 0) + recv_data.get('loss_gw', 0),
                'broken_ct': recv_data.get('broken_ct', 0) + recv_data.get('loss_ct', 0),
                
                'balance_ct':issued_ct - recv_data.get('return_ct', 0)-recv_data.get('broken_ct', 0)-recv_data.get('loss_ct', 0),
                'balance_gw':issued_gw - recv_data.get('return_gw', 0)-recv_data.get('broken_gw', 0)-recv_data.get('loss_gw', 0),
                'balance_pcs':issued_pcs - recv_data.get('return_pcs', 0)-recv_data.get('broken_pcs', 0)-recv_data.get('loss_pcs', 0), 
            })
        
        # Calculate issue and receive weight/quantity values based on UOM
        issue_weight = issue_data.get(uom, 0)
        receive_weight = (
            recv_data.get(f'return_{uom}', 0) + recv_data.get(f'broken_{uom}', 0) + recv_data.get(f'loss_{uom}', 0)
            if pckt_no in stone_receive_dict else 0
        )

        # Calculate weighted average value and rate
        issue_value = issue_weight * issue_data.get('packet__rate_for_retail', 0)
        receive_value = receive_weight * recv_data.get('packet__rate_for_retail', 0) if pckt_no in stone_receive_dict else 0
        remaining_value = issue_value - receive_value
        remaining_wt = issue_weight - receive_weight

        # Ensure total weight is not zero before dividing
        if remaining_wt != 0:
            weighted_avg_rate = remaining_value / remaining_wt
        else:
            weighted_avg_rate = 0

        combined_entry.update({
            'remaining_value': remaining_value,
            'weighted_avg_rate': weighted_avg_rate
        })

        # Add the combined entry to the final list
        combined_data.append(combined_entry)
    
    # Initialize nw variable
    nw = Decimal('0.0')

    # Calculate the net weight (nw) using the combined data
    for entry in combined_data:
        issue_ct = entry.get('ct', 0)
        return_ct = entry.get('return_ct', 0)
        broken_ct = entry.get('broken_ct', 0)
        loss_ct = entry.get('loss_ct', 0)

        # Perform the net weight calculation 
        nw += Decimal(issued_item.approx_wt) - (issue_ct / Decimal('5.0')) + ((return_ct + broken_ct + loss_ct) / Decimal('5.0'))
    
    # Prepare the data to be sent as JSON
    # data = {
    #     'item_id': issued_item.item.id,
    #     'short_code': issued_item.item.short_code,
    #     'item_name': issued_item.item.item_name,
    #     'purity_id': issued_item.purity.id,
    #     'purity': issued_item.purity.purity,
    #     'pcs': issued_item.pcs,
    #     'gw': issued_item.approx_wt,
    #     'nw': nw,
    #     'design_code': issued_item.design_code,
    #     'stone_data': combined_data  # Single combined list of stone issue and receive data
    # }
    short_code = issued_item.item.short_code
    data_n = KarigarReceiveItemForGetSerializer({
        "ref_job_no":issued_item.issue_slip.id,
        "ref_job_sl_no":issued_item.id,
        "item":issued_item.item,
        "purity":issued_item.purity,
        "pcs":issued_item.pcs,
        "gw":issued_item.approx_wt,
        "finish_status":False,
        "hallmark_status":False,
        # "nw":nw,
        "details":combined_data
                                        }).data

    return JsonResponse(data_n)



class KarigarJobReceiveListCreateView(ListAPIView):
    serializer_class = KarigarReceiveSerializer
    queryset = KarigarReceive.objects.all()
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    
    
    search_fields = ["receive_slip_no"]


class KarigarReceiveViewSet(views.RetailBaseViewset):
    queryset = KarigarReceive.objects.select_related('karigar_ldgr').prefetch_related(
        'karigarreceiveitem_set__item',
        'karigarreceiveitem_set__purity',
        'karigarreceiveitem_set__karigarreceiveitemdetails_set__item',
        'karigarreceiveitem_set__karigarreceiveitemdetails_set__metal_purity',
        'karigarreceiveitem_set__karigarreceiveitemdetails_set__packet',
    ).all()
    serializer_class = KarigarReceiveForPostSerializer
    filter_backends=[DjangoFilterBackend,OrderingFilter,SearchFilter]

    search_fields=['receive_slip_no','karigar_ldgr__ac_name']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['receive_slip_no'] 



class KarigarJobsView(ListCreateAPIView):
    serializer_class = KarigarIssueSerializer
    queryset = KarigarIssue.objects.all()

class KarigarMasterView(ListCreateAPIView):
    serializer_class = KarigarMasterSerializer

    def get_queryset(self):
        retail = getattr(self.request, 'retail', None)
        qs = KarigarMaster.objects.select_related('karigar', 'item', 'purity', 'retail')
        if retail:
            qs = qs.filter(retail=retail)
        return qs.order_by('karigar__ac_name', 'item__item_name', 'purity__purity')

    def perform_create(self, serializer):
        retail = getattr(self.request, 'retail', None)
        serializer.save(retail=retail)


class KarigarMasterDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = KarigarMasterSerializer

    def get_queryset(self):
        retail = getattr(self.request, 'retail', None)
        qs = KarigarMaster.objects.select_related('karigar', 'item', 'purity', 'retail')
        if retail:
            qs = qs.filter(retail=retail)
        return qs


class KarigarMakingCSVUploadView(APIView):
    """
    POST multipart/form-data with field 'file' (CSV).
    Upserts KarigarMaster records for the current retail.

    Expected columns (case-insensitive, flexible aliases):
        karigar_name | karigar    – Ledger ac_name (type KR)
        kr_code                   – Optional karigar code
        item_code | item          – Item.short_code
        purity | purity_name      – PurityMaster.purity
        making_per_gm             – Making charge per gram (₹)
        making_per_pc             – Making charge per piece (₹)
        loss_rate                 – Melting / wastage % (3 dp)
    """
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)

        retail = getattr(request, 'retail', None)
        created = updated = 0
        errors = []

        try:
            import csv as csv_module
            decoded = file.read().decode('utf-8-sig')
            reader = csv_module.DictReader(io.StringIO(decoded))

            # Normalise header names
            def col(row, *aliases):
                for a in aliases:
                    v = row.get(a, row.get(a.lower(), '')).strip()
                    if v:
                        return v
                return ''

            with transaction.atomic():
                for i, row in enumerate(reader, start=2):
                    try:
                        karigar_name = col(row, 'karigar_name', 'karigar')
                        item_code    = col(row, 'item_code', 'item')
                        purity_name  = col(row, 'purity', 'purity_name')

                        if not karigar_name or not item_code or not purity_name:
                            errors.append(f"Row {i}: karigar_name, item_code, and purity are required")
                            continue

                        # Resolve FK objects
                        from contacts.models import Ledger
                        from mastersconfig.models import Item as ItemModel
                        from goldrates.models import PurityMaster

                        karigar_obj = Ledger.objects.filter(ac_name__iexact=karigar_name).first()
                        if not karigar_obj:
                            errors.append(f"Row {i}: karigar '{karigar_name}' not found in ledger")
                            continue

                        item_obj = ItemModel.objects.filter(short_code__iexact=item_code).first()
                        if not item_obj:
                            errors.append(f"Row {i}: item '{item_code}' not found")
                            continue

                        purity_obj = PurityMaster.objects.filter(purity__iexact=purity_name).first()
                        if not purity_obj:
                            errors.append(f"Row {i}: purity '{purity_name}' not found")
                            continue

                        def to_dec(v, default='0'):
                            try:
                                return Decimal(v.strip() or default)
                            except (InvalidOperation, ValueError):
                                return Decimal(default)

                        defaults = {
                            'kr_code':      col(row, 'kr_code') or '',
                            'making_per_gm': to_dec(col(row, 'making_per_gm'), '0'),
                            'making_per_pc': to_dec(col(row, 'making_per_pc'), '0'),
                            'loss_rate':     to_dec(col(row, 'loss_rate'),     '0'),
                        }
                        if retail:
                            defaults['retail'] = retail

                        obj, flag = KarigarMaster.objects.update_or_create(
                            karigar=karigar_obj,
                            item=item_obj,
                            purity=purity_obj,
                            **(({'retail': retail} if retail else {})),
                            defaults=defaults,
                        )
                        if flag:
                            created += 1
                        else:
                            updated += 1

                    except Exception as e:
                        errors.append(f"Row {i}: {str(e)}")

        except Exception as e:
            return Response({'error': str(e)}, status=400)

        return Response({'created': created, 'updated': updated, 'errors': errors})


from rest_framework.views import APIView
from django_filters import rest_framework as filters

class HallMarkReceiveViewSet(views.RetailBaseViewset):
    queryset = HallmarkReceive.objects.all()
    serializer_class = HallmarkReceiveForPostSerializer
    filter_backends=[DjangoFilterBackend,OrderingFilter,SearchFilter]

    search_fields=['receive_slip_no','hallmark_center__ac_name']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['receive_slip_no'] 


class HallMarkIssueViewSet(views.RetailBaseViewset):
    queryset = HallmarkIssue.objects.all()
    serializer_class = HallmarkIssueForPostSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter,SearchFilter]
    # filterset_fields = ['issue_slip_no']
    
    search_fields=['issue_slip_no','hallmark_center__ac_name']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['issue_slip_no'] 


class KarigarReceiveforNoView(APIView):
    def get(self, request):
        """
        Returns all KarigarReceive along with related KarigarReceiveItem and KarigarReceiveItemDetails.
        """
        receive_slip_no = request.query_params.get('receive_slip_no', None)

        if receive_slip_no:
            try:
                karigar_receive = KarigarReceive.objects.filter(receive_slip_no=receive_slip_no).prefetch_related(
                    'karigarreceiveitem_set',
                    'karigarreceiveitem_set__details'
                )
                serializer = KarigarReceiveforNoSerializer(karigar_receive, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except KarigarReceive.DoesNotExist:
                return Response({"error": "Receive Slip No not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            karigar_receives = KarigarReceive.objects.all().prefetch_related(
                'karigarreceiveitem_set__karigarreceiveitemdetails_set'
            )
            serializer = KarigarReceiveforNoSerializer(karigar_receives, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
class JobStatusView(ListAPIView):
    serializer_class = KarigarIssueItemforJobStatusSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = JobCompletedFilter
    search_fields = ['issue_slip__issue_slip_no', 'item__item_name', 'item__short_code']
    ordering_fields = ['due_date', 'issue_slip__date1']
    ordering = ['due_date']

    def get_queryset(self):
        return KarigarIssueItem.objects.select_related(
            'issue_slip__karigar_ldgr',
            'item', 'purity',
            'customer_order_item__order_no',
            'retail',
        ).prefetch_related(
            'karigarreceiveitem_set',   # all receives against this issue item
        ).filter(retail=self.request.retail)

class RefineryIssueViewset(views.RetailBaseViewset):
    queryset = RefinaryIssue.objects.all()
    serializer_class = RefinaryIssueSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter,SearchFilter]

    search_fields=['billno']
    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['billno'] 

class RefineryReceiveViewset(views.RetailBaseViewset):
    queryset = RefinaryReceive.objects.all()
    serializer_class = RefinaryReceiveSerializer
    filter_backends=[DjangoFilterBackend,OrderingFilter,SearchFilter]

    search_fields=['billno']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['billno']


class MeltingIssueViewset(views.RetailBaseViewset):
    queryset = MeltingIssue.objects.all()
    serializer_class = MeltingIssueSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['billno']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    ordering = ['billno']


class MeltingReceiveViewset(views.RetailBaseViewset):
    queryset = MeltingReceive.objects.all()
    serializer_class = MeltingReceiveSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['billno']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    ordering = ['billno']


class AssayIssueViewset(views.RetailBaseViewset):
    queryset = AssayIssue.objects.all()
    serializer_class = AssayIssueSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['billno']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    ordering = ['billno']


class AssayReceiveViewset(views.RetailBaseViewset):
    queryset = AssayReceive.objects.all()
    serializer_class = AssayReceiveSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['billno']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    ordering = ['billno']


class AvailableMeltingReceivesView(APIView):
    """
    Returns MeltingReceive vouchers available to be referenced by a new (or edited) AssayIssue.

    A receive is "available" if it has no AssayIssue linked to it yet.
    In edit mode pass ?exclude_assay_issue=<id> so the currently-linked receive is
    also included (otherwise it would vanish from the picker on edit).
    """
    def get(self, request):
        exclude_id = request.query_params.get("exclude_assay_issue")
        retail = getattr(request, "retail", None)

        # Receives that are still unclaimed
        available_qs = MeltingReceive.objects.filter(
            retail=retail, assay_issues__isnull=True
        )

        if exclude_id:
            # Also include the receive that is already linked to the assay issue being edited
            try:
                current_issue = AssayIssue.objects.get(pk=exclude_id)
                if current_issue.melt_recv_id:
                    already_linked = MeltingReceive.objects.filter(
                        pk=current_issue.melt_recv_id, retail=retail
                    )
                    from django.db.models import QuerySet
                    available_qs = (available_qs | already_linked).distinct()
            except AssayIssue.DoesNotExist:
                pass

        available_qs = available_qs.prefetch_related("meltingreceivedetail_set").order_by("-date1")
        serializer = MeltingReceiveSerializer(available_qs, many=True)
        return Response({"results": serializer.data})


class HallmarkIssueReportView(APIView):
    def get(self, request):
        today = datetime.today().date()
        retail = getattr(request, 'retail', None)
        active_fy = getattr(retail, 'active_fy', None) if retail else None
        default_start = active_fy.fy_start if active_fy else datetime(today.year if today.month >= 4 else today.year - 1, 4, 1).date()
        start_date = request.query_params.get("start_date") or str(default_start)
        end_date = request.query_params.get("end_date") or str(today)
        item_status = request.query_params.get("item_status")  # Optional: rec_status filter
        purity_id = request.query_params.get("purity_id")  # Optional: Filter by purity
        ledger_ids = request.query_params.get("ledger_ids").split(',') if request.query_params.get("ledger_ids") else None   # Optional: Ledger ID list

        # Ensure both start_date and end_date are provided
        if not start_date or not end_date:
            return Response({"error": "start_date and end_date are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        filtered_issues = HallmarkIssue.objects.filter(date1__range=(start_date, end_date))

        filtered_items = HallmarkIssueItem.objects.filter(issue_slip_no__in=filtered_issues)

        if item_status is not None:
            filtered_items = filtered_items.filter(rec_status=item_status.lower() == "true")

        if purity_id:
            filtered_items = filtered_items.filter(purity_id=purity_id)

        # Step 3: Remove empty HallmarkIssue entries (must have at least one matching HallmarkIssueItem)
        filtered_issues = filtered_issues.filter(id__in=filtered_items.values("issue_slip_no_id"))

        # Step 4: Filter Ledgers that have at least one matching HallmarkIssue
        filtered_ledgers = Ledger.objects.filter(
            id__in=filtered_issues.values("hallmark_center_id")
        )

        # Apply Ledger ID filter (if provided)
        if ledger_ids:
            filtered_ledgers = filtered_ledgers.filter(id__in=ledger_ids)

        # Step 5: Prefetch related objects for optimization
        filtered_ledgers = filtered_ledgers.prefetch_related(
            Prefetch(
                "hallmarkissue_set",
                queryset=filtered_issues
            )
        )
        # Serialize and return data
        
        ## they are throw attribute error so, i command ledgerreportserializer.

        # serializer = LedgerReportSerializer(filtered_ledgers, many=True)
        serializer = HallmarkIssueReportSerializer(filtered_issues, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class HallmarkReceiveReportView(APIView):
    def get(self, request):
        # Extract query parameters
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        item_status = request.query_params.get("item_status")  # Optional: rec_status filter
        purity_id = request.query_params.get("purity_id")  # Optional: Filter by purity
        ledger_ids = request.query_params.getlist("ledger_ids")  # Optional: Ledger ID list

        # Ensure both start_date and end_date are provided
        if not start_date or not end_date:
            return Response({"error": "start_date and end_date are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate and parse dates
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        # Step 1: Filter HallmarkIssue based on date range
        filtered_issues = HallmarkReceive.objects.filter(date1__range=(start_date, end_date))

        # Step 2: Filter HallmarkIssueItem based on additional filters
        filtered_items = HallmarkReceiveItem.objects.filter(receive_slip_no__in=filtered_issues)

        if item_status is not None:
            filtered_items = filtered_items.filter(rec_status=item_status.lower() == "true")

        if purity_id:
            filtered_items = filtered_items.filter(purity_id=purity_id)

        # Step 3: Remove empty HallmarkIssue entries (must have at least one matching HallmarkIssueItem)
        filtered_issues = filtered_issues.filter(id__in=filtered_items.values("receive_slip_no_id"))

        # Step 4: Filter Ledgers that have at least one matching HallmarkIssue
        # filtered_ledgers = Ledger.objects.filter(type="HM").filter(
        #     id__in=filtered_issues.values("hallmark_center_id")
        # )
        filtered_ledgers = Ledger.objects.filter(
            id__in=filtered_issues.values("hallmark_center_id")
        )

        # Apply Ledger ID filter (if provided)
        if ledger_ids:
            filtered_ledgers = filtered_ledgers.filter(id__in=ledger_ids)

        # Step 5: Prefetch related objects for optimization
        filtered_ledgers = filtered_ledgers.prefetch_related(
            Prefetch(
                "hallmarkreceive_set",
                queryset=filtered_issues.prefetch_related(
                    Prefetch("hallmarkreceiveitem_set", queryset=filtered_items)
                ),
            )
        )

        # Serialize and return data
        serializer = LedgerReceiveReportSerializer(filtered_ledgers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



    # Then update the view to use filterset_class:

class KarigarStoneReceiveViewset(views.RetailBaseViewset):
    queryset = KarigarStoneReceiveHeader.objects.all()
    serializer_class = KarigarStoneReceiveSerializer
    filter_backends=[DjangoFilterBackend,OrderingFilter,SearchFilter]

    search_fields=['billno','karigar_ldgr__ac_name']
    filterset_fields = ['karigar_ldgr']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['-date1', '-billno']

    def get_queryset(self):
        qs = super().get_queryset()
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(date1__gte=date_from)
        if date_to:
            qs = qs.filter(date1__lte=date_to)
        return qs



class KarigarStoneIssueViewset(views.RetailBaseViewset):
    queryset = KarigarStoneIssueHeader.objects.all()
    serializer_class = KarigarStoneIssueSerializer
    filter_backends=[DjangoFilterBackend,OrderingFilter,SearchFilter]

    search_fields=['billno','karigar_ldgr__ac_name']
    filterset_fields = ['karigar_ldgr']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['-date1', '-billno']

    def get_queryset(self):
        qs = super().get_queryset()
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(date1__gte=date_from)
        if date_to:
            qs = qs.filter(date1__lte=date_to)
        return qs

class KarigarGoldIssueViewset(views.RetailBaseViewset):
    queryset = KarigarGoldIssueHeader.objects.all()
    serializer_class = KarigarGoldIssueSerializer
    filter_backends=[DjangoFilterBackend,OrderingFilter,SearchFilter]

    search_fields=['billno']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    # Optionally set default ordering
    ordering = ['billno'] 

class KarigarReceiveItemView(ListAPIView):
    serializer_class = KarigarReceiveItemForGetSerializer
    queryset = KarigarReceiveItem.objects.select_related(
        'item', 'purity', 'receive_slip_no__karigar_ldgr',
    ).prefetch_related('sample_issued_items').all()
    filter_backends = [DjangoFilterBackend , OrderingFilter]

    filterset_class = KarigarReceiveItemFilter


class KarigarStoneIssueReportView(APIView):
    def get(self,request):

        # Get query parameters
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date') 
        packet_group = request.query_params.get('packet_group')
        krid = request.query_params.get('krid')

        # Validate required parameters
        if not all([from_date, to_date, packet_group, krid]):
            return Response(
            {"error": "Missing required parameters: from_date, to_date, packet_group, krid"}, 
            status=status.HTTP_400_BAD_REQUEST
            )

        # Convert string dates to datetime
        try:
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
            to_date = datetime.strptime(to_date, '%Y-%m-%d').date()
        except ValueError:
            return Response(
            {"error": "Invalid date format. Use YYYY-MM-DD"}, 
            status=status.HTTP_400_BAD_REQUEST
            )

        stn_iss = KarigarStoneIssue.objects.filter(
            date1__range=[from_date,to_date],
            packet__packet_group=packet_group,
            karigar_ldgr__id=krid
        )
        
        krjob_content_type = ContentType.objects.get_for_model(KarigarReceiveItem)
        
        kr_iss_item = KarigarIssueItem.objects.filter(
            id__in = stn_iss.values('job_sl_object_id'),
            job_sl_content_type=krjob_content_type
        ).prefetch_related(
            Prefetch('stone_issue',queryset=stn_iss)
        )

        ser = KarigarStoneIssueReportSerializer(kr_iss_item)

        return Response(ser.data)

class KarigarStoneReceiveReportView(APIView):
    def get(self,request):

        # Get query parameters
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date') 
        packet_group = request.query_params.get('packet_group')
        krid = request.query_params.get('krid')

        # Validate required parameters
        if not all([from_date, to_date, packet_group, krid]):
            return Response(
            {"error": "Missing required parameters: from_date, to_date, packet_group, krid"}, 
            status=status.HTTP_400_BAD_REQUEST
            )

        # Convert string dates to datetime
        try:
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
            to_date = datetime.strptime(to_date, '%Y-%m-%d').date()
        except ValueError:
            return Response(
            {"error": "Invalid date format. Use YYYY-MM-DD"}, 
            status=status.HTTP_400_BAD_REQUEST
            )

        stn_iss = KarigarStoneReceive.objects.filter(
            date1__range=[from_date,to_date],
            packet__packet_group=packet_group,
            karigar_ldgr__id=krid
        )
        
        krjob_content_type = ContentType.objects.get_for_model(KarigarReceiveItem)
        
        kr_iss_item = KarigarIssueItem.objects.filter(
            id__in = stn_iss.values('job_sl_object_id'),
            job_sl_content_type=krjob_content_type
        ).prefetch_related(
            Prefetch('stone_receive',queryset=stn_iss)
        )

        ser = KarigarStoneIssueReportSerializer(kr_iss_item)

        return Response(ser.data)


class KarigarGoldReportView(APIView):
    def get(self,request):

        # Get query parameters
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date') 
        packet_group = request.query_params.get('packet_group')
        krid = request.query_params.get('krid')

        # Validate required parameters
        if not all([from_date, to_date, packet_group, krid]):
            return Response(
            {"error": "Missing required parameters: from_date, to_date, packet_group, krid"}, 
            status=status.HTTP_400_BAD_REQUEST
            )

        # Convert string dates to datetime
        try:
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
            to_date = datetime.strptime(to_date, '%Y-%m-%d').date()
        except ValueError:
            return Response(
            {"error": "Invalid date format. Use YYYY-MM-DD"}, 
            status=status.HTTP_400_BAD_REQUEST
            )

        stn_iss = KarigarStoneReceive.objects.filter(
            date1__range=[from_date,to_date],
            packet__packet_group=packet_group,
            karigar_ldgr__id=krid
        )
        
        krjob_content_type = ContentType.objects.get_for_model(KarigarReceiveItem)
        
        kr_iss_item = KarigarIssueItem.objects.filter(
            id__in = stn_iss.values('job_sl_object_id'),
            job_sl_content_type=krjob_content_type
        ).prefetch_related(
            Prefetch('stone_receive',queryset=stn_iss)
        )

        ser = KarigarStoneIssueReportSerializer(kr_iss_item)

        return Response(ser.data)

# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from itertools import chain
from operator import itemgetter
from datetime import datetime
from decimal import Decimal
from collections import defaultdict
from django.db.models import F, Value, DecimalField
from rest_framework.settings import api_settings
class CombinedGoldTransactionView(APIView):

    def get_combined_gold_ledger_data(self, start_date, end_date, purity_id):
        issues_qs = KarigarGoldIssue.objects.filter(
            header__date1__range=[start_date, end_date],
            conv_purity_id=purity_id
        ).annotate(
            date=F('header__date1'),
            karigar_id=F('header__karigar_ldgr_id'),
            karigar_name=F('header__karigar_ldgr__ac_name'),
            gold_wt=F('conv_wt'),
            type=Value('issue')
        ).values('date', 'karigar_id', 'karigar_name', 'gold_wt', 'type')

        receives_qs = KarigarReceiveItem.objects.filter(
            receive_slip_no__date1__range=[start_date, end_date],
            purity_id=purity_id
        ).annotate(
            date=F('receive_slip_no__date1'),
            karigar_id=F('receive_slip_no__karigar_ldgr_id'),
            karigar_name=F('receive_slip_no__karigar_ldgr__ac_name'),
            gold_wt=F('nw'),
            type=Value('receive')
        ).values('date', 'karigar_id', 'karigar_name', 'gold_wt', 'type')

        combined = sorted(
            chain(issues_qs, receives_qs),
            key=itemgetter('date')
        )
        return combined

    def get(self, request):
        start_date = request.query_params.get("start")
        end_date = request.query_params.get("end")
        purity_id = request.query_params.get("purity")

        if not (start_date and end_date and purity_id):
            return Response({"error": "Missing parameters"}, status=status.HTTP_400_BAD_REQUEST)

        data = self.get_combined_gold_ledger_data(start_date, end_date, purity_id)

        # Apply pagination manually
        paginator = getattr(self, 'pagination_class', api_settings.DEFAULT_PAGINATION_CLASS)()
        paginated_data = paginator.paginate_queryset(data, request)
        return paginator.get_paginated_response(paginated_data)
    
    
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Subquery, OuterRef, DecimalField, F, Prefetch, ExpressionWrapper
from django.db.models.functions import Coalesce, Cast
from datetime import date
from inventory.models import OpeningInventory
from contacts.models import Ledger
from .models import (
 KarigarGoldIssue,
    KarigarReceiveItem, KarigarGoldIssueHeader, KarigarReceive
)

from goldrates.models import PurityMaster as Purity
from django.core import serializers as ser


class KarigarGoldIssueSerializer(serializers.ModelSerializer):
    date = serializers.SerializerMethodField()

    class Meta:
        model = KarigarGoldIssue
        fields = ['date', 'conv_wt','conv_purity']

    def get_date(self, obj):
        return obj.header.date1

class KarigarGoldIssueHeaderSerializer(serializers.ModelSerializer):
    issues = KarigarGoldIssueSerializer(source='issue', many=True, read_only=True)

    class Meta:
        model = KarigarGoldIssueHeader
        fields = ['id', 'billno', 'date1', 'slip_type','issues']


class KarigarReceiveItemSerializer(serializers.ModelSerializer):
    date = serializers.SerializerMethodField()

    class Meta:
        model = KarigarReceiveItem
        fields = ['date', 'nw', 'add_gw', 'wastage', 'purity']

    def get_date(self, obj):
        return obj.receive_slip_no.date1

class KarigarReceiveSerializer(serializers.ModelSerializer):
    karigar_ldgr_name = serializers.CharField(read_only=True)
    items = KarigarReceiveItemSerializer(source='receive', many=True, read_only=True)

    class Meta:
        model = KarigarReceive
        fields = ['id', 'receive_slip_no', 'date1', 'karigar_ldgr', 'karigar_ldgr_name', 'place_of_supply', 'making_vid', 'retail', 'items']

class LedgerSerializer(serializers.ModelSerializer):
    per_purity = serializers.SerializerMethodField()

    class Meta:
        model = Ledger
        fields = ['id', 'ac_name', 'per_purity']

    def get_per_purity(self, obj):
        purity_data = {}
        purity_ids = self.context.get('purities')
        if purity_ids:
            purity_qs = Purity.objects.filter(id__in=purity_ids.split(','))
        else:
            purity_qs = Purity.objects.all()
        print(purity_qs)
        for purity in purity_qs:
            key = purity.purity.lower().replace(' ', '_')  # e.g., "22K" → "22k"

            # Dynamically extract annotated fields
            opening_gold_stock = getattr(obj, f'opening_gold_stock_{key}', None)
            total_issued = getattr(obj, f'total_issued_{key}', None)
            total_wastage = getattr(obj, f'total_wastage_{key}', None)
            total_add = getattr(obj, f'total_add_{key}', None)
            total_nw = getattr(obj, f'total_nw_{key}', None)

            # Transactions via prefetch_to_attr
            issues_attr = f'karigar_gold_issues_after_date_{key}'
            receives_attr = f'karigar_receive_items_after_date_{key}'

            issues = getattr(obj, issues_attr, [])
            receives = getattr(obj, receives_attr, [])

            purity_data[key] = {
                'opening_gold_stock': opening_gold_stock,
                'total_issued': total_issued,
                'total_wastage': total_wastage,
                'total_add': total_add,
                'total_nw': total_nw,
                'karigar_gold_issues_after_date': KarigarGoldIssueHeaderSerializer(issues, many=True).data,
                'karigar_receive_items_after_date': KarigarReceiveSerializer(receives, many=True).data
            }

        return purity_data


class LedgerGoldStockPerPurityView(APIView):
    def get(self, request):
        given_date = request.query_params.get('date')
        to_date = request.query_params.get('to_date') or date.today().isoformat()
        if not given_date:
            return Response({'error': 'Please provide a `date` query param (YYYY-MM-DD)'}, status=400)

        purity_ids = request.query_params.get('purity_ids')
        ledger_ids = request.query_params.get('ledger_ids')

        if purity_ids:
            purity_ids_list = [pid.strip() for pid in purity_ids.split(',') if pid.strip()]
            purity_qs = Purity.objects.filter(id__in=purity_ids_list)
        else:
            purity_qs = Purity.objects.all()


        if ledger_ids:
            ledger_ids_list = [lid.strip() for lid in ledger_ids.split(',') if lid.strip()]
            ledger_qs = Ledger.objects.filter(id__in=ledger_ids_list)
        else:
            ledger_qs = Ledger.objects.filter(roles__role='KR').distinct()

        try:
            fg_item = Item.objects.get(short_code="FG")
        except Item.DoesNotExist:
            fg_item = None

        for purity in purity_qs:
            purity_name = purity.purity.lower().replace(' ', '_')  # e.g., 22K -> 22k

            opening_inv_subq = OpeningInventory.objects.filter(
                item=fg_item,
                ldgr=OuterRef('pk'),
                purity=purity
            ).values('ldgr').annotate(
                val=Coalesce(Sum('gw'),  Cast(0, output_field=DecimalField()))
            ).values('val')

            issue_subq = KarigarGoldIssue.objects.filter(
                metal_purity=purity,
                header__karigar_ldgr=OuterRef('pk'),
                header__date1__lt=given_date
            ).values('header__karigar_ldgr').annotate(
                val=Coalesce(Sum('conv_wt'), Cast(0, output_field=DecimalField()))
            ).values('val')

            receive_filter = {
                'receive_slip_no__karigar_ldgr': OuterRef('pk'),
                'receive_slip_no__date1__lt': given_date,
                'purity': purity
            }

            wastage_subq = KarigarReceiveItem.objects.filter(**receive_filter).values(
                'receive_slip_no__karigar_ldgr'
            ).annotate(
                val=Coalesce(Sum('wastage'), Cast(0, output_field=DecimalField()))
            ).values('val')        


            add_subq = KarigarReceiveItem.objects.filter(**receive_filter).values(
                 'receive_slip_no__karigar_ldgr'
            ).annotate(
                val=Coalesce(Sum('add_gw'), Cast(0, output_field=DecimalField()))
            ).values('val')

            nw_subq = KarigarReceiveItem.objects.filter(**receive_filter).values(
                'receive_slip_no__karigar_ldgr'
            ).annotate(
                val=Coalesce(Sum('nw'), Cast(0, output_field=DecimalField()))
            ).values('val')

            ledger_qs = ledger_qs.annotate(**{
    f'opening_stock_{purity_name}': Cast(
        Coalesce(
            Cast(Subquery(opening_inv_subq), output_field=DecimalField()),
            Cast(0, output_field=DecimalField())
        ),
        output_field=DecimalField()
    ),
    f'total_issued_{purity_name}': Cast(
        Coalesce(
            Cast(Subquery(issue_subq), output_field=DecimalField()),
            Cast(0, output_field=DecimalField())
        ),
        output_field=DecimalField()
    ),
    f'total_wastage_{purity_name}': Cast(
        Coalesce(
            Cast(Subquery(wastage_subq), output_field=DecimalField()),
            Cast(0, output_field=DecimalField())
        ),
        output_field=DecimalField()
    ),
    f'total_add_{purity_name}': Cast(
        Coalesce(
            Cast(Subquery(add_subq), output_field=DecimalField()),
            Cast(0, output_field=DecimalField())
        ),
        output_field=DecimalField()
    ),
    f'total_nw_{purity_name}': Cast(
        Coalesce(
            Cast(Subquery(nw_subq), output_field=DecimalField()),
            Cast(0, output_field=DecimalField())
        ),
        output_field=DecimalField()
    ),
})

# Final arithmetic expression
            ledger_qs = ledger_qs.annotate(**{
                f'opening_gold_stock_{purity_name}': ExpressionWrapper(
                    F(f'opening_stock_{purity_name}')
                    - F(f'total_issued_{purity_name}')
                    - F(f'total_wastage_{purity_name}')
                    - F(f'total_add_{purity_name}')
                    - F(f'total_nw_{purity_name}'),
                    output_field=DecimalField()
                )
            })

            

            issue_qs_filtered = KarigarGoldIssue.objects.filter(
                conv_purity=purity,
                header__date1__range=(given_date, to_date)
            )

            glheaders = KarigarGoldIssueHeader.objects.filter(
                id__in=issue_qs_filtered.values('header__id')
            )


            receive_qs_filtered = KarigarReceiveItem.objects.filter(
                purity=purity,
                receive_slip_no__date1__range=(given_date, to_date)
            )
            rcheaders = KarigarReceive.objects.filter(
                id__in=receive_qs_filtered.values('receive_slip_no__id')
            )

            ledger_qs = ledger_qs.prefetch_related(
                Prefetch(
                    'karigargoldissueheader_set',
                    queryset=glheaders.prefetch_related(Prefetch('karigargoldissue_set',queryset=issue_qs_filtered,to_attr='issue')) ,
                    to_attr=f'karigar_gold_issues_after_date_{purity_name}'
                ),
                Prefetch(
                    'karigarreceive_set',
                    queryset=rcheaders.prefetch_related(Prefetch('karigarreceiveitem_set',queryset=receive_qs_filtered,to_attr='receive')) ,
                    
                    to_attr=f'karigar_receive_items_after_date_{purity_name}'
                )
            )


        return Response(LedgerSerializer(ledger_qs, many=True, context={'date': given_date,'purities':purity_ids}).data)

        

class KarigarWorkOrderStoneReportView(APIView):
    def get(self, request):
        given_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        if not given_date:
            return Response({'error': 'Please provide a `date` query param (YYYY-MM-DD)'}, status=400)
        
        qs = KarigarIssue.objects.filter(
            date1__range=[given_date, to_date]
        ).prefetch_related(
            Prefetch('items',queryset=KarigarIssueItem.objects.all().prefetch_related(
            Prefetch('karigarreceiveitem_set',queryset=KarigarReceiveItem.objects.all().prefetch_related('karigarreceiveitemdetails_set')),
                     ),

            
        ))

        data = KarigarIssueFullReportSerializer(qs, many=True).data
        
        return Response(data, status=status.HTTP_200_OK)

from sales.models import SalesVouItemDetails
from rest_framework.serializers import ModelSerializer
from rest_framework import serializers

class OpeningIn(ModelSerializer):
    class Meta:
        model = OpeningInventory
        fields = ['pcs',"ct","gw"]

class PurchaseVouSer(ModelSerializer):
    class Meta:
        model = PurchaseVoucherDetails
        fields = ['date','sub_pcs','sub_ct','sub_gw']

class PurchaseReturnSer(ModelSerializer):
    class Meta:
        model = PurchaseReturnDetails
        fields = ['date','sub_pcs','sub_ct','sub_gw']


class SalesVouItemDetailsSer(ModelSerializer):
    class Meta:
        model = SalesVouItemDetails
        fields = ['date','pcs',"ct","gw"]


class KarigarStoneReceiveSer(ModelSerializer):
    class Meta:
        model = KarigarStoneReceive
        fields = ['date','return_pcs',"return_ct","return_gw"]
        

class KarigarStoneIssueSer(ModelSerializer):
    class Meta:
        model = KarigarStoneIssue
        fields = ['date','pcs',"ct","gw"]


class PacketSerializer(ModelSerializer):
    purchase = PurchaseVouSer(many=True, read_only=True)
    purchase_return = PurchaseReturnSer(many=True, read_only=True)
    sales = SalesVouItemDetailsSer(many=True, read_only=True)
    stone_receive = KarigarStoneReceiveSer(many=True, read_only=True)
    stone_issue = KarigarStoneIssueSer(many=True, read_only=True)
    
    opening_quantity = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    opening_quantity_pcs = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    opening_quantity_gw = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    purchase_quantity = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    purchase_quantity_pcs = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    purchase_quantity_gw = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    purchase_return_quantity = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    purchase_return_quantity_pcs = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    purchase_return_quantity_gw = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    sales_quantity = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    sales_quantity_pcs = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    sales_quantity_gw = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    stone_receive_quantity = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    stone_receive_quantity_pcs = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    stone_receive_quantity_gw = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    stone_issue_quantity = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    stone_issue_quantity_pcs = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)
    stone_issue_quantity_gw = serializers.DecimalField(max_digits=20, decimal_places=1, read_only=True)

    class Meta:
        model = Packet
        fields = [
            'id',
            'purchase',
            'purchase_return',
            'sales',
            'stone_receive',
            'stone_issue',
            'pckt_no',
            'opening_quantity',
            'opening_quantity_pcs',
            'opening_quantity_gw',
            'purchase_quantity',
            'purchase_quantity_pcs',
            'purchase_quantity_gw',
            'purchase_return_quantity',
            'purchase_return_quantity_pcs',
            'purchase_return_quantity_gw',
            'sales_quantity',
            'sales_quantity_pcs',
            'sales_quantity_gw',
            'stone_receive_quantity',
            'stone_receive_quantity_pcs',
            'stone_receive_quantity_gw',
            'stone_issue_quantity',
            'stone_issue_quantity_pcs',
            'stone_issue_quantity_gw',
        ]


class PacketWiseLooseStoneReportView(APIView):
    def get(self, request):
        given_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        if not given_date:
            return Response({'error': 'Please provide a `date` query param (YYYY-MM-DD)'}, status=400)
        opening_sum = OpeningInventory.objects.filter(
            packet=OuterRef('pk'),
        ).values('packet').annotate(
            total=Coalesce(Sum('ct'), Value(Decimal('0.0')))
        ).values('total')[:1]
        opening_pcs = OpeningInventory.objects.filter(
            packet=OuterRef('pk'),
        ).values('packet').annotate(
            total=Coalesce(Sum('pcs'), Value(0))
        ).values('total')[:1]
        opening_gw = OpeningInventory.objects.filter(
            packet=OuterRef('pk'),
        ).values('packet').annotate(
            total=Coalesce(Sum('gw'), Value(Decimal('0.0')))
        ).values('total')[:1]


        purchase_sum = PurchaseVoucherDetails.objects.filter(
            packet=OuterRef('pk'),
            billno__isnull=False,
            main_item__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('sub_ct'), Value(Decimal('0.0')))
        ).values('total')[:1]
        purchase_sum_pcs = PurchaseVoucherDetails.objects.filter(
            packet=OuterRef('pk'),
            billno__isnull=False,
            main_item__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('sub_pcs'), Value(0))
        ).values('total')[:1]
        purchase_sum_gw = PurchaseVoucherDetails.objects.filter(
            packet=OuterRef('pk'),
            billno__isnull=False,
            main_item__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('sub_gw'), Value(Decimal('0.0')))
        ).values('total')[:1]

        purchase_return_sum = PurchaseReturnDetails.objects.filter(
            packet=OuterRef('pk'),
            billno__isnull=False,
            billno__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('sub_ct'), Value(Decimal('0.0')))
        ).values('total')[:1]
        purchase_return_sum_gw = PurchaseReturnDetails.objects.filter(
            packet=OuterRef('pk'),
            billno__isnull=False,
            billno__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('sub_gw'), Value(Decimal('0.0')))
        ).values('total')[:1]
        purchase_return_sum_pcs = PurchaseReturnDetails.objects.filter(
            packet=OuterRef('pk'),
            billno__isnull=False,
            billno__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('sub_pcs'), Value(0))
        ).values('total')[:1]

        sales_sum = SalesVouItemDetails.objects.filter(
            packet=OuterRef('pk'),
            billno__isnull=False,
            billno__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('ct'), Value(Decimal('0.0')))
        ).values('total')[:1]

        sales_sum_pcs = SalesVouItemDetails.objects.filter(
            packet=OuterRef('pk'),
            billno__isnull=False,
            billno__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('pcs'), Value(0))
        ).values('total')[:1]

        sales_sum_gw = SalesVouItemDetails.objects.filter(
            packet=OuterRef('pk'),
            billno__isnull=False,
            billno__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('gw'), Value(Decimal('0.0')))
        ).values('total')[:1]

        stone_receive_sum = KarigarStoneReceive.objects.filter(
            packet=OuterRef('pk'),
            header__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('return_ct'), Value(Decimal('0.0')))
        ).values('total')[:1]
        stone_receive_sum_pcs = KarigarStoneReceive.objects.filter(
            packet=OuterRef('pk'),
            header__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('return_pcs'), Value(0))
        ).values('total')[:1]
        stone_receive_sum_gw = KarigarStoneReceive.objects.filter(
            packet=OuterRef('pk'),
            header__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('return_gw'), Value(Decimal('0.0')))
        ).values('total')[:1]

        stone_issue_sum = KarigarStoneIssue.objects.filter(
            packet=OuterRef('pk'),
            header__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('ct'), Value(Decimal('0.0')))
        ).values('total')[:1]

        stone_issue_sum_pcs = KarigarStoneIssue.objects.filter(
            packet=OuterRef('pk'),
            header__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('pcs'), Value(0))
        ).values('total')[:1]

        stone_issue_sum_gw = KarigarStoneIssue.objects.filter(
            packet=OuterRef('pk'),
            header__date1__lt=given_date
        ).values('packet').annotate(
            total=Coalesce(Sum('gw'), Value(Decimal('0.0')))
        ).values('total')[:1]

        qs = Packet.objects.all().annotate(
    opening_quantity=Coalesce(Subquery(opening_sum, output_field=DecimalField()), Decimal('0.0')),
    opening_pcs=Coalesce(Subquery(opening_pcs, output_field=DecimalField()), Decimal('0.0')),
    opening_gw=Coalesce(Subquery(opening_gw, output_field=DecimalField()), Decimal('0.0')),
    purchase_quantity=Coalesce(Subquery(purchase_sum, output_field=DecimalField()), Decimal('0.0')),
    purchase_quantity_pcs=Coalesce(Subquery(purchase_sum_pcs, output_field=DecimalField()), Decimal('0.0')),
    purchase_quantity_gw=Coalesce(Subquery(purchase_sum_gw, output_field=DecimalField()), Decimal('0.0')),
    purchase_return_quantity=Coalesce(Subquery(purchase_return_sum, output_field=DecimalField()), Decimal('0.0')),
    purchase_return_quantity_pcs=Coalesce(Subquery(purchase_return_sum_pcs, output_field=DecimalField()), Decimal('0.0')),
    purchase_return_quantity_gw=Coalesce(Subquery(purchase_return_sum_gw, output_field=DecimalField()), Decimal('0.0')),
    sales_quantity=Coalesce(Subquery(sales_sum, output_field=DecimalField()), Decimal('0.0')),
    sales_quantity_pcs=Coalesce(Subquery(sales_sum_pcs, output_field=DecimalField()), Decimal('0.0')),
    sales_quantity_gw=Coalesce(Subquery(sales_sum_gw, output_field=DecimalField()), Decimal('0.0')),
    stone_receive_quantity=Coalesce(Subquery(stone_receive_sum, output_field=DecimalField()), Decimal('0.0')),
    stone_receive_quantity_pcs=Coalesce(Subquery(stone_receive_sum_pcs, output_field=DecimalField()), Decimal('0.0')),
    stone_receive_quantity_gw=Coalesce(Subquery(stone_receive_sum_gw, output_field=DecimalField()), Decimal('0.0')),
    stone_issue_quantity=Coalesce(Subquery(stone_issue_sum, output_field=DecimalField()), Decimal('0.0')),
    stone_issue_quantity_pcs=Coalesce(Subquery(stone_issue_sum_pcs, output_field=DecimalField()), Decimal('0.0')),
    stone_issue_quantity_gw=Coalesce(Subquery(stone_issue_sum_gw, output_field=DecimalField()), Decimal('0.0')),
        ).prefetch_related(
           
            Prefetch(
                'purchasevoucherdetails_set',
                queryset=PurchaseVoucherDetails.objects.filter(
                    billno__isnull=False,
                    packet__isnull=False,
                    billno__date1__gte=given_date,
                    billno__date1__lte=to_date
                ),
                to_attr='purchase'
            ),
            Prefetch(
                'purchasereturndetails_set',
                queryset=PurchaseReturnDetails.objects.filter(
                    billno__isnull=False,
                    packet__isnull=False,
                    billno__date1__gte=given_date,
                    billno__date1__lte=to_date
                ),
                to_attr='purchase_return'
            ),
            Prefetch(
                'salesvouitemdetails_set',
                queryset=SalesVouItemDetails.objects.filter(
                    billno__isnull=False,
                    billno__date1__gte=given_date,
                    billno__date1__lte=to_date
                ),
                to_attr='sales'
            ),
            Prefetch(
                'karigarstonereceive_set',
                queryset=KarigarStoneReceive.objects.filter(
                    header__date1__gte=given_date,
                    header__date1__lte=to_date
                ),
                to_attr='stone_receive'
            ),
            Prefetch(
                'karigarstoneissue_set',
                queryset=KarigarStoneIssue.objects.filter(
                    header__date1__gte=given_date,
                    header__date1__lte=to_date
                ),
                to_attr='stone_issue'
            ),
        )

        data = PacketSerializer(qs,many=True).data
        return Response(data)


# ── Refinery Report ────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def refinery_report(request):
    """
    Aggregated refinery report with date / refiner filters.
    Returns issues, receives, pending reconciliation, and summary stats.
    """
    from_date_str = request.query_params.get('from_date')
    to_date_str   = request.query_params.get('to_date')
    refiner_id    = request.query_params.get('refiner')
    retail        = getattr(request, 'retail', None)

    today       = datetime.today().date()
    active_fy   = getattr(retail, 'active_fy', None) if retail else None
    default_start = active_fy.fy_start if active_fy else datetime(today.year if today.month >= 4 else today.year - 1, 4, 1).date()

    try:
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date() if from_date_str else default_start
        to_date   = datetime.strptime(to_date_str,   '%Y-%m-%d').date() if to_date_str   else today
    except ValueError:
        return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

    # Base querysets scoped to retail and date range
    issue_qs = RefinaryIssue.objects.filter(retail=retail, date1__range=(from_date, to_date))
    recv_qs  = RefinaryReceive.objects.filter(retail=retail, date1__range=(from_date, to_date))

    if refiner_id:
        issue_qs = issue_qs.filter(ldgr_id=refiner_id)
        recv_qs  = recv_qs.filter(ldgr_id=refiner_id)

    issue_qs = issue_qs.select_related('ldgr').prefetch_related(
        'refinaryissuedetail_set__item',
        'refinaryissuedetail_set__metal_purity',
        'refinaryissuedetail_set__packet',
    ).order_by('-date1', 'billno')

    recv_qs = recv_qs.select_related('ldgr').prefetch_related(
        'refinaryreceivedetail_set__item',
        'refinaryreceivedetail_set__metal_purity',
        'refinaryreceivedetail_set__conv_purity',
        'refinaryreceivedetail_set__issue_no',
        'refinaryreceivedetail_set__packet',
    ).order_by('-date1', 'billno')

    # Build issue rows
    issues = []
    total_issued_gw = Decimal('0')
    for iss in issue_qs:
        detail_rows = []
        iss_gw = Decimal('0')
        for d in iss.refinaryissuedetail_set.all():
            detail_rows.append({
                'item':         d.item.short_code if d.item else '',
                'pcs':          d.pcs,
                'ct':           float(d.ct),
                'gw':           float(d.gw),
                'metal_purity': d.metal_purity.purity if d.metal_purity else '',
                'packet':       str(d.packet.pckt_no) if d.packet else '',
                'rec_status':   d.rec_status,
            })
            iss_gw += d.gw
        total_issued_gw += iss_gw
        issues.append({
            'id':         iss.id,
            'billno':     iss.billno,
            'date':       str(iss.date1),
            'refiner':    iss.ldgr.ac_name,
            'refiner_id': iss.ldgr_id,
            'rec_status': iss.rec_status,
            'total_gw':   float(iss_gw),
            'details':    detail_rows,
        })

    # Build receive rows
    receives = []
    total_recv_gw = Decimal('0')
    total_loss_gw = Decimal('0')
    for rec in recv_qs:
        detail_rows = []
        rec_gw  = Decimal('0')
        loss_gw = Decimal('0')
        for d in rec.refinaryreceivedetail_set.all():
            detail_rows.append({
                'issue_billno': d.issue_no.billno if d.issue_no else '',
                'item':         d.item.short_code if d.item else '',
                'pcs':          d.pcs,
                'gw':           float(d.gw),
                'loss_per':     float(d.loss_per),
                'loss_wt':      float(d.loss_wt),
                'metal_purity': d.metal_purity.purity if d.metal_purity else '',
                'conv_purity':  d.conv_purity.purity  if d.conv_purity  else '',
                'conv_nw':      float(d.conv_nw),
                'remarks':      d.remarks,
                'packet':       str(d.packet.pckt_no) if d.packet else '',
                'rec_status':   d.rec_status,
            })
            rec_gw  += d.gw
            loss_gw += d.loss_wt
        total_recv_gw += rec_gw
        total_loss_gw += loss_gw
        receives.append({
            'id':            rec.id,
            'billno':        rec.billno,
            'date':          str(rec.date1),
            'refiner':       rec.ldgr.ac_name,
            'refiner_id':    rec.ldgr_id,
            'total_gw':      float(rec_gw),
            'total_loss_gw': float(loss_gw),
            'details':       detail_rows,
        })

    # Pending issues = those where rec_status is False
    pending_issues = [i for i in issues if not i['rec_status']]
    pending_gw     = sum(i['total_gw'] for i in pending_issues)

    # Average loss percentage
    avg_loss_pct = float(total_loss_gw / total_recv_gw * 100) if total_recv_gw else 0

    # All refiners ever used by this retail (for the filter dropdown, not restricted by date)
    all_refiner_ids = set(
        list(RefinaryIssue.objects.filter(retail=retail).values_list('ldgr_id', flat=True)) +
        list(RefinaryReceive.objects.filter(retail=retail).values_list('ldgr_id', flat=True))
    )
    refiners = [
        {'id': l.id, 'name': l.ac_name}
        for l in Ledger.objects.filter(id__in=all_refiner_ids).order_by('ac_name')
    ]

    return Response({
        'issues':         issues,
        'receives':       receives,
        'pending_issues': pending_issues,
        'summary': {
            'total_issued_gw': float(total_issued_gw),
            'total_recv_gw':   float(total_recv_gw),
            'total_loss_gw':   float(total_loss_gw),
            'avg_loss_pct':    round(avg_loss_pct, 3),
            'pending_count':   len(pending_issues),
            'pending_gw':      float(pending_gw),
        },
        'refiners': refiners,
    })


# ── Repair Job Card ────────────────────────────────────────────────────────────

from manufacturing.models import RepairJobCard
from manufacturing.serializer import RepairJobCardSerializer, RepairJobCardListSerializer


class RepairJobCardViewSet(views.RetailBaseViewset):
    queryset = RepairJobCard.objects.select_related(
        'customer', 'item', 'purity', 'fiscal_year', 'retail'
    ).prefetch_related('stones', 'losses', 'karigar_links__karigar_issue', 'karigar_links__karigar_receive')
    filter_backends  = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields    = ['rjc_no', 'customer__ac_name']
    ordering_fields  = ['date1', 'rjc_no', 'status']
    ordering         = ['-date1']

    def get_serializer_class(self):
        if self.action == 'list':
            return RepairJobCardListSerializer
        return RepairJobCardSerializer

    def perform_create(self, serializer):
        retail = self.request.retail
        fy     = retail.active_fy if retail else None
        serializer.save(retail=retail, fiscal_year=fy)

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        instance   = self.get_object()
        new_status = request.data.get('status')
        valid      = [s[0] for s in RepairJobCard.STATUS_CHOICES]
        if new_status not in valid:
            return Response(
                {'error': f'Invalid status. Choices: {valid}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.status = new_status
        instance.save(update_fields=['status'])
        return Response({'status': instance.status, 'status_display': instance.get_status_display()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def repair_job_card_billno_view(request):
    """Return the next RJC bill number preview for the current retail."""
    try:
        bill_no = peek_next_bill_number(request.retail, 'RJC')
        return Response({'rjc_no': bill_no})
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Karigar Subcontractor Ledger — split view ─────────────────────────────────

class KarigarSubcontractorLedgerView(APIView):
    """
    GET /manufacturing/api/karigar-subcontractor-ledger/
        ?karigar=<ledger_id>   (required)
        &start=YYYY-MM-DD      (optional)
        &end=YYYY-MM-DD        (optional)

    Returns three sections:
      - finished_account:  pieces out (Sample Issue) vs receives IN (weight-based)
      - raw_gold_account:  raw gold issues vs incremental gold returned on receive
      - labour_summary:    making charges by receive slip
    Also keeps legacy `raw_gold`/`semi_finished` keys for older FE callers.
    """

    def get(self, request):
        from manufacturing.models import SampleIssueItem
        karigar_id = request.query_params.get('karigar')
        if not karigar_id:
            return Response({'error': 'karigar query param is required'}, status=status.HTTP_400_BAD_REQUEST)

        start_str = request.query_params.get('start') or None
        end_str = request.query_params.get('end') or None

        def _in_range(date_val):
            if start_str and str(date_val) < start_str:
                return False
            if end_str and str(date_val) > end_str:
                return False
            return True

        def _before_range(date_val):
            return bool(start_str and str(date_val) < start_str)

        # ── Raw Gold Issues ────────────────────────────────────────────────────
        gold_all = KarigarGoldIssue.objects.filter(
            header__karigar_ldgr_id=karigar_id
        ).select_related('header', 'metal_purity', 'conv_purity', 'item').order_by(
            'header__date1', 'header__billno'
        )

        raw_gold_rows = []
        raw_gold_opening = Decimal('0')
        raw_gold_issued_pure = Decimal('0')

        for gi in gold_all:
            if _before_range(gi.header.date1):
                raw_gold_opening += gi.conv_wt or 0
                continue
            if not _in_range(gi.header.date1):
                continue
            purity_label = (
                gi.metal_purity.purity if gi.metal_purity
                else f"{gi.custom_purity_per}%" if gi.custom_purity_per
                else '—'
            )
            raw_gold_rows.append({
                'date':         gi.header.date1,
                'slip':         gi.header.billno,
                'kind':         'GOLD_ISSUE',
                'item':         gi.item.item_name if gi.item else '—',
                'issued_gw':    float(gi.item_gw or 0),
                'metal_purity': purity_label,
                'conv_purity':  gi.conv_purity.purity if gi.conv_purity else '—',
                'conv_wt':      float(gi.conv_wt or 0),
                'received_gw':  0.0,
            })
            raw_gold_issued_pure += gi.conv_wt or 0

        # ── Receives: incremental gold returned + labour ───────────────────────
        receive_all = KarigarReceiveItem.objects.filter(
            receive_slip_no__karigar_ldgr_id=karigar_id
        ).select_related('receive_slip_no', 'item', 'purity', 'ref_sample_issue_item__piece').order_by(
            'date1', 'id'
        )

        finished_rows = []
        finished_opening_pcs = 0
        finished_opening_gw = Decimal('0')
        finished_in_gw = Decimal('0')

        raw_gold_received_pure = Decimal('0')

        labour_rows = []
        labour_total = Decimal('0')

        for r in receive_all:
            is_semi = not r.finish_status
            kind = 'RECEIVE_SEMI' if is_semi else 'RECEIVE_FINISHED'
            # Finished account: every receive is a piece IN
            if _before_range(r.date1):
                finished_opening_pcs += r.pcs or 0
                finished_opening_gw += r.gw or 0
            elif _in_range(r.date1):
                finished_rows.append({
                    'date':    r.date1,
                    'slip':    r.receive_slip_no.receive_slip_no,
                    'kind':    kind,
                    'item':    r.item.item_name if r.item else '—',
                    'pcs':     r.pcs or 0,
                    'in_gw':   float(r.gw or 0),
                    'out_gw':  0.0,
                    'ref':    (r.ref_sample_issue.billno if r.ref_sample_issue_id
                               else (r.ref_job_no.issue_slip_no if r.ref_job_no_id else '—')),
                })
                finished_in_gw += r.gw or 0

            # Raw gold account: incremental pure returned
            try:
                inc = r.incremental_gw or 0
            except Exception:
                inc = 0
            if inc and _in_range(r.date1):
                raw_gold_rows.append({
                    'date':         r.date1,
                    'slip':         r.receive_slip_no.receive_slip_no,
                    'kind':         'GOLD_RECEIVE_INCREMENTAL',
                    'item':         r.item.item_name if r.item else '—',
                    'issued_gw':    0.0,
                    'metal_purity': r.purity.purity if r.purity else '—',
                    'conv_purity':  '—',
                    'conv_wt':      0.0,
                    'received_gw':  float(inc),
                })
                raw_gold_received_pure += Decimal(str(inc))

            # Labour summary
            if _in_range(r.date1):
                labour_rows.append({
                    'receive_slip':   r.receive_slip_no.receive_slip_no,
                    'date':           r.date1,
                    'incremental_gw': float(inc or 0),
                    'making_rate':    float(r.making_rate_applied or 0),
                    'making_amount':  int(r.making or 0),
                    'auto':           bool(r.making_auto),
                    'loss_gw':        float((r.less_gw or 0) + (r.loss or 0)),
                })
                labour_total += Decimal(r.making or 0)

        # ── Sample Issue: pieces OUT (finished account) ────────────────────────
        sample_all = SampleIssueItem.objects.filter(
            issue__karigar_ldgr_id=karigar_id
        ).select_related('issue', 'piece', 'piece__item').order_by('issue__date1', 'issue__billno')

        finished_out_gw = Decimal('0')
        for si in sample_all:
            gw = si.piece.gw or 0 if si.piece_id else 0
            if _before_range(si.issue.date1):
                finished_opening_pcs -= si.piece.pcs or 0 if si.piece_id else 0
                finished_opening_gw -= gw
                continue
            if not _in_range(si.issue.date1):
                continue
            finished_rows.append({
                'date':   si.issue.date1,
                'slip':   si.issue.billno,
                'kind':   'SAMPLE_OUT',
                'item':   si.piece.item.item_name if (si.piece_id and si.piece.item_id) else '—',
                'pcs':    -(si.piece.pcs or 0) if si.piece_id else 0,
                'in_gw':  0.0,
                'out_gw': float(gw),
                'ref':    si.issue.billno,
            })
            finished_out_gw += gw

        finished_rows.sort(key=lambda r: (str(r['date']), r['slip']))
        raw_gold_rows.sort(key=lambda r: (str(r['date']), r['slip']))

        return Response({
            'karigar_id': karigar_id,
            'period': {'start': start_str, 'end': end_str},
            'finished_account': {
                'opening':  {'pcs': finished_opening_pcs, 'gw': float(finished_opening_gw)},
                'rows':     finished_rows,
                'totals':   {
                    'in_gw':      float(finished_in_gw),
                    'out_gw':     float(finished_out_gw),
                    'closing_gw': float(finished_opening_gw + finished_in_gw - finished_out_gw),
                },
            },
            'raw_gold_account': {
                'opening': {'gw_pure': float(raw_gold_opening)},
                'rows':    raw_gold_rows,
                'totals':  {
                    'issued_pure':   float(raw_gold_issued_pure),
                    'received_pure': float(raw_gold_received_pure),
                    'closing_pure':  float(raw_gold_opening + raw_gold_issued_pure - raw_gold_received_pure),
                },
            },
            'labour_summary': {
                'rows':   labour_rows,
                'totals': {'making_amount': int(labour_total)},
            },
            # Legacy keys (back-compat for existing callers, if any):
            'raw_gold': [r for r in raw_gold_rows if r['kind'] == 'GOLD_ISSUE'],
            'raw_gold_total': float(raw_gold_issued_pure),
            'semi_finished': [
                {
                    'date': r['date'], 'billno': r['slip'], 'item': r['item'],
                    'purity': '—', 'pcs': abs(r['pcs']), 'approx_wt': r['out_gw'],
                    'source_receive_slip': r['ref'],
                }
                for r in finished_rows if r['kind'] == 'SAMPLE_OUT'
            ],
            'semi_finished_total': float(finished_out_gw),
        })




