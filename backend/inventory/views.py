from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from inventory.filters import StockValuationReportFilter, BarCodeMainFilter
from inventory.serializer import BarCodeDetailSerializer, BarCodeMainListSerializer, BarCodeMainSerializer, BarcodeCreationReportSerializer, BarcodeMainToSaleVouSerializer, BarcodeSplitMergeSerializer, BarcodeTransactionSerializer, DesignMainSerializer, InterRetailTransferVoucherSerializer, ItemStockReportSerializer, OpeningInventorySerializer, RfidCountResultSerializer, RfidCountSessionSerializer, RfidTagAssignSerializer, StockJournalSerializer, StockTransferSerializer, UnBarcodedMainSerializer
from manufacturing.models import *
from manufacturing.serializer import HallmarkReceiveItemForPostSerializer
from userauth.views import RetailBaseViewset
from .models import *
from .utils import *
from barcode import EAN13
from django.db.models import Q
from barcode.writer import ImageWriter
from io import BytesIO
from django.db.models import F
import json
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from accounting.utils import peek_next_bill_number
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db.models import OuterRef, Subquery, Sum, IntegerField, Q, F, ExpressionWrapper, Prefetch, Count


@api_view()
@permission_classes([IsAuthenticated])
def gen_barcode(request):
    res = {"barcode":generate_ean13()}
    return Response(res)

@api_view()
@permission_classes([IsAuthenticated])
def get_barcode(request, barcode, hsn):
    try:
        obj = BarcodeMain.objects.select_related('customer_order', 'customer_order__ldgr').get(
            barcode=barcode,
            item__hsn_no__hsn_no=hsn,
            retail=request.retail,
            stk_status=True,
        )
    except BarcodeMain.DoesNotExist:
        return Response(
            {"detail": f"Barcode '{barcode}' is not available in the current retail's active stock."},
            status=404,
        )
    # Reservation guard: if barcode is reserved against a customer order, reject when
    # the sales-voucher's selected customer (ldgr) does not match the reserved party.
    ldgr_param = request.query_params.get('ldgr') if hasattr(request, 'query_params') else request.GET.get('ldgr')
    if obj.customer_order_id and ldgr_param not in (None, '', 'null', 'undefined'):
        try:
            bill_ldgr_id = int(ldgr_param)
        except (TypeError, ValueError):
            bill_ldgr_id = None
        reserved_ldgr_id = getattr(obj.customer_order, 'ldgr_id', None)
        if bill_ldgr_id is not None and reserved_ldgr_id is not None and bill_ldgr_id != reserved_ldgr_id:
            reserved_party = getattr(getattr(obj.customer_order, 'ldgr', None), 'ldgr_name', 'reserved customer')
            return Response(
                {"detail": (
                    f"Barcode '{barcode}' is reserved for customer order "
                    f"{obj.customer_order.order_no} ({reserved_party}). "
                    "Release it from the order before selling to a different party."
                )},
                status=400,
            )
    data = BarcodeMainToSaleVouSerializer(obj).data
    return Response(data)

@api_view()
@permission_classes([IsAuthenticated])
def get_barcode_only(request, barcode):
    try:
        obj = BarcodeMain.objects.select_related('customer_order', 'customer_order__ldgr').get(
            barcode=barcode,
            retail=request.retail,
            stk_status=True,
        )
    except BarcodeMain.DoesNotExist:
        return Response(
            {"detail": f"Barcode '{barcode}' is not available in the current retail's active stock."},
            status=404,
        )
    data = BarcodeMainToSaleVouSerializer(obj).data
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_barcode_for_return(request, barcode):
    """
    Look up a barcode for use in a SalesApprovalReturn form.
    Unlike get_barcode_only, this does NOT filter by stk_status — the
    barcode being returned is currently OUT (stk_status=False).
    """
    try:
        obj = BarcodeMain.objects.select_related(
            'item', 'purity',
        ).prefetch_related('barcodedetails_set__item').get(
            barcode=barcode,
            retail=request.retail,
        )
    except BarcodeMain.DoesNotExist:
        return Response(
            {"detail": f"Barcode '{barcode}' not found in the current retail."},
            status=404,
        )
    data = BarcodeMainToSaleVouSerializer(obj).data
    return Response(data)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def create_barcode_from_receive_api(request):
    sl_no = request.GET.get('sl_no')
    rec_slip_no = request.GET.get('rec_slip_no')
    
    try:
        # Fetch relevant records
        rec = KarigarReceive.objects.get(receive_slip_no=rec_slip_no)
        rec_item = KarigarReceiveItem.objects.get(receive_slip_no=rec, sl_no=sl_no)

        # Fetch details with related data
        rec_details = KarigarReceiveItemDetails.objects.filter(
            receive_slip_no=rec,
            sl_no=sl_no
        ).select_related('packet__stone_item_id',)

        # Resolve the originating issue item — either a Karigar job-work item or
        # a Sample-issue item, depending on what the receive references. Either
        # may carry a design_code, size, or order_no we want to prefill into the barcode form.
        order_no = None
        design_code = None
        size = None
        if rec_item.ref_job_sl_no_id:
            iss_item = KarigarIssueItem.objects.filter(id=rec_item.ref_job_sl_no_id).first()
            if iss_item:
                design_code = iss_item.design_code or None
                size = iss_item.size or None
                if iss_item.customer_order_item and iss_item.customer_order_item.order_no:
                    order_no = iss_item.customer_order_item.order_no.order_no
        elif rec_item.ref_sample_issue_item_id:
            from manufacturing.models import SampleIssueItem
            sample_item = SampleIssueItem.objects.filter(id=rec_item.ref_sample_issue_item_id).first()
            if sample_item:
                design_code = sample_item.design_code or None
                size = sample_item.size or None if hasattr(sample_item, 'size') else None

        # Resolve the HUID by walking back through any sample re-issue chain to the
        # original karigar receive that was hallmarked. See manufacturing/utils.py.
        from manufacturing.utils import resolve_huid_for_receive_item
        huid = resolve_huid_for_receive_item(rec_item)
        # Calculate net weight: gw minus all stone/sub-item weights
        stone_gw = sum(float(detail.balance_gw or 0) for detail in rec_details)
        nw = float(rec_item.gw or 0) - stone_gw

        # Prepare the response data
        response_data = {


            'order_no': order_no,
            'design_code': design_code,
            'size': size,
            'huid':huid,
            'voucher_no':rec.receive_slip_no,
            'purity':rec_item.purity.purity,
            'kr_code':rec.karigar_ldgr.id,
            'item':rec_item.item.short_code,
            'item_name':rec_item.item.item_name,
            'pcs':rec_item.pcs,
            'rec_item':rec_item.id,
            'gw':rec_item.gw,
            'nw':nw,
            'making':rec_item.making,
            'barcodedetails_set': [{
                'packet': detail.packet.pckt_no if detail.packet else None,
                'item': detail.item.short_code,
                'pcs': detail.balance_pcs,
                'ct': detail.balance_ct,
                'gw': detail.balance_gw,
                'rate': detail.rate,
                'uom': detail.packet.stone_item_id.uom if detail.packet else None
            } for detail in rec_details if detail.packet]
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except (KarigarReceive.DoesNotExist, KarigarReceiveItem.DoesNotExist) as e:
        return Response(
            {'error': 'Record not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def create_barcode_from_purchase(request):
    bill_no = request.GET.get('bill_no')
    sl_no = request.GET.get('sl_no')

    try:
        # Fetch purchase voucher
        purchase_voucher = PurchaseVoucher.objects.get(billno=bill_no)

        # Fetch purchase voucher item
        purchase_item = PurchaseVoucherItems.objects.get(billno=purchase_voucher, sl_no=sl_no)
        
        # Fetch purchase details with related data
        purchase_details = PurchaseVoucherDetails.objects.filter(main_item=purchase_item
        ).select_related('sub_item', 'packet')
        
        # Prepare response data
        response_data = {
            'order_no': purchase_item.order_no.order_no if purchase_item.order_no else None,
            'size': purchase_item.size or '',
            'huid': None,  # Assuming huid is not available in this model structure
            'voucher_no': purchase_voucher.billno,
            'purity': purchase_item.purity.purity if purchase_item.purity else None,
            'kr_code': purchase_voucher.ldgr.id if purchase_voucher.ldgr else None,
            'item': purchase_item.item.short_code if purchase_item.item else None,
            'item_name': purchase_item.item.item_name if purchase_item.item else None,
            'pur_voucher': purchase_item.id,
            'pcs': purchase_item.pending_pcs,
            'gw': str(purchase_item.pending_gw),
            'nw': None,  # Assuming net weight is not stored explicitly
            'making_val': purchase_item.making_value,
            'making_type': purchase_item.making_type,
            'barcodedetails_set': [
                {
                    'packet': detail.packet.pckt_no if detail.packet else None,
                    'item': detail.sub_item.short_code if detail.sub_item else None,
                    'item_name': detail.sub_item.item_name if detail.sub_item else None,
                    'pcs': detail.sub_pcs,
                    'ct': str(detail.sub_ct),
                    'gw': str(detail.sub_gw),
                    'rate': str(detail.rate),
                    'uom': detail.sub_item.uom if detail.sub_item else None,
                } for detail in purchase_details
            ]
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except (PurchaseVoucher.DoesNotExist, PurchaseVoucherItems.DoesNotExist) as e:
        return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def barcode_merge_view(request):
    with transaction.atomic():
        data = request.data.copy()
        data['retail'] = request.retail
        serializer = BarCodeMainSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')) if request else None

        
        barcodes = [barcode["barcode_text"] for barcode in data["barcodedetails_set"]]
        barcodes= set(barcodes)
        for barcode in barcodes:
            inst = BarcodeMain.objects.get(barcode=barcode)
            inst.stk_status = False
            inst.save()
        
        inst = serializer.save()
        BarcodeTransaction.objects.create(
            barcode=inst,
            billno="",
            trans_type="BAR-MER-CRT",
            user=request.user,
            ip_address=ip,
            retail=request.retail
        ) 

        for br in barcodes:
            old_br = BarcodeMain.objects.get(barcode=br)
            bsm = BarcodeSplitMerge.objects.create(
                transaction_type = "Merge",
                old_barcode = old_br,
                new_barcode = serializer.instance,
                retail = request.retail
            )
            BarcodeTransaction.objects.create(
            barcode=old_br,
            billno=f"${bsm.id}",
            trans_type="BAR-MER",
            user=request.user,
            ip_address=ip,
            retail=request.retail
            ) 
        
        return Response(data=serializer.data)
from rest_framework.views import APIView  
class ConvertBarcodeToUnbarcodedView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        barcode_value = request.data.get("barcode")
        if not barcode_value:
            return Response({"error": "Barcode is required"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            barcode_main = get_object_or_404(
                BarcodeMain.objects.select_for_update(), barcode=barcode_value
            )

            if not barcode_main.stk_status:
                return Response(
                    {"error": "Barcode has already been converted or is out of stock."},
                    status=status.HTTP_409_CONFLICT,
                )

            if barcode_main.rec_item_id:
                origin = 'KAR_REC'
            elif barcode_main.pur_voucher_id:
                origin = 'PUR_VOU'
            else:
                origin = 'BAR_CONV'

            unbarcoded_main = UnBarcodedMain.objects.create(
                item=barcode_main.item,
                item_desc=barcode_main.item.item_name if barcode_main.item else None,
                label=barcode_main.barcode,
                pcs=barcode_main.pcs,
                gw=barcode_main.gw,
                nw=barcode_main.nw,
                huid=barcode_main.huid,
                purity=barcode_main.purity,
                value=barcode_main.value,
                making_val=barcode_main.making_val,
                making_type=barcode_main.making_type,
                other_chg=barcode_main.other_chg,
                design_code=barcode_main.design_code,
                kr_code=barcode_main.kr_code,
                total_amount=barcode_main.total_amount,
                size=barcode_main.size,
                metal_color=barcode_main.metal_color,
                created_from=origin,
                source_barcode=barcode_main,
                customer_order=barcode_main.customer_order,
                created_by=barcode_main.created_by,
                created_date=barcode_main.created_date,
                stk_status=True,
                op_stk=False,
                voucher_no=barcode_main.voucher_no,
                retail=barcode_main.retail,
            )

            barcode_details = BarcodeDetails.objects.filter(barcode=barcode_main)
            UnBarcodedDetails.objects.bulk_create([
                UnBarcodedDetails(
                    main_item=unbarcoded_main,
                    packet=detail.packet,
                    pcs=detail.pcs,
                    ct=detail.ct,
                    gw=detail.gw,
                    item=detail.item,
                    rate=detail.rate,
                    amt=detail.amt,
                ) for detail in barcode_details
            ])

            barcode_main.stk_status = False
            barcode_main.save(update_fields=['stk_status'])

            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')) if request else None
            BarcodeTransaction.objects.create(
                barcode=barcode_main,
                billno="",
                trans_type="BAR-TRF-UNB",
                user=request.user,
                ip_address=ip,
                retail=request.retail,
            )

        return Response({"message": "Barcode converted to Unbarcoded successfully"}, status=status.HTTP_201_CREATED)

    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def barcode_split_view(request,old_barcode):
    from decimal import Decimal
    with transaction.atomic():
        old_br = BarcodeMain.objects.get(barcode=old_barcode)
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')) if request else None

        BarcodeTransaction.objects.create(
            barcode=old_br,
            billno=f"",
            trans_type="BAR-SPLIT",
            user=request.user,
            ip_address=ip,
            retail=request.retail
        ) 
        # Inherit traceability fields from the source barcode onto each new split row.
        # The user explicitly wants voucher_no + the source provenance FKs (pur_voucher,
        # rec_item, kr_code) + created_by carried forward so reports can still trace
        # post-split barcodes back to their purchase / karigar receive.
        inherited = {
            'voucher_no':  old_br.voucher_no,
            'pur_voucher': old_br.pur_voucher_id,
            'rec_item':    old_br.rec_item_id,
            'kr_code':     old_br.kr_code_id,
            'created_by':  old_br.created_by,
        }
        source_gw    = Decimal(str(old_br.gw or 0))
        source_value = Decimal(str(old_br.value or 0))

        for item in request.data:
            # Inject inherited fields (only when the client didn't already send a value).
            for k, v in inherited.items():
                if v is not None and not item.get(k):
                    item[k] = v

            # Compute nw = gw - sum(non-Raw sub-items' gw). Stones don't count as metal.
            # If the client already sent nw explicitly, respect that.
            new_gw = Decimal(str(item.get('gw') or 0))
            if not item.get('nw'):
                stone_gw = Decimal('0')
                for sub in item.get('barcodedetails_set', []):
                    # Sub-items committed as canonical (pcs/ct/gw/amt/purity); Raw subs
                    # are metal (gold) and should count toward NW, Stone subs should not.
                    # We treat anything with a `purity` field as metal (gold/raw) — stones
                    # don't carry a metal purity.
                    if not (sub.get('purity') or sub.get('metal_purity')):
                        stone_gw += Decimal(str(sub.get('gw') or 0))
                item['nw'] = float(max(Decimal('0'), new_gw - stone_gw))

            # Compute value proportionally from the source barcode by GW share, so the
            # new barcodes' metal values sum to the source's value (round to 2dp).
            if not item.get('value') and source_gw > 0 and source_value > 0:
                item['value'] = float((source_value * new_gw / source_gw).quantize(Decimal('0.01')))

            # The serializer's field list does not include `retail`, so pass it via
            # serializer.save(retail=...) instead of trying to set it through the payload.
            serializer = BarCodeMainSerializer(data=item, context={"request": request})
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            inst = BarcodeMain.objects.get(barcode=old_barcode)
            inst.stk_status = False
            inst.save()

            new_barcode = serializer.save(retail=request.retail)
            inst = BarcodeSplitMerge.objects.create(
                transaction_type = "Split",
                old_barcode = old_br,
                # new_barcode = serializer.instance[0],
                new_barcode = new_barcode,
                retail = request.retail
            )
            BarcodeTransaction.objects.create(
                barcode=new_barcode,
                billno=f"${inst.id}",
                trans_type="BAR-SPLIT-CRT",
                user=request.user,
                ip_address=ip,
                retail=request.retail
            )
        
        return Response(data=serializer.data)



class BarCodeView(RetailBaseViewset):
    serializer_class = BarCodeMainSerializer
    queryset = BarcodeMain.objects.select_related(
        'item', 'purity', 'kr_code', 'rec_item'
    ).prefetch_related(
        'barcodedetails_set__item',
        'barcodedetails_set__purity',
        'barcodedetails_set__packet',
    ).all()
    filter_backends = [DjangoFilterBackend,OrderingFilter,SearchFilter]
    filterset_class = BarCodeMainFilter
    search_fields = ['barcode', 'item__short_code', 'item__item_name',]

    def get_serializer_class(self):
        # Use lightweight serializer (no nested sub-items) for list queries
        if self.action == 'list':
            return BarCodeMainListSerializer
        return BarCodeMainSerializer

    def get_queryset(self):
        # For list action use a lean queryset — no heavy barcodedetails_set prefetch
        if getattr(self, 'action', None) == 'list':
            retail = getattr(self.request, 'retail', None)
            qs = (
                BarcodeMain.objects
                .select_related('item', 'purity', 'customer_order', 'customer_order__ldgr')
                .annotate(dia_ct=Sum('barcodedetails__ct'))
            )
            # Opt-in global search (used by the barcode-history lookup): a barcode
            # may currently belong to another retail (after a transfer), so the
            # history page must be able to find it regardless of the active retail.
            if self.request.query_params.get('all_retails', '').lower() not in ('1', 'true'):
                qs = qs.filter(retail=retail)
            ids_param = self.request.query_params.get('ids', '').strip()
            if ids_param:
                try:
                    id_list = [int(i) for i in ids_param.split(',') if i.strip().isdigit()]
                    if id_list:
                        qs = qs.filter(id__in=id_list)
                except (ValueError, TypeError):
                    pass
            return qs
        qs = super().get_queryset()
        ids_param = self.request.query_params.get('ids', '').strip()
        if ids_param:
            try:
                id_list = [int(i) for i in ids_param.split(',') if i.strip().isdigit()]
                if id_list:
                    qs = qs.filter(id__in=id_list)
            except (ValueError, TypeError):
                pass
        return qs

    def perform_destroy(self, instance):
        if not instance.stk_status:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                f"Barcode '{instance.barcode}' cannot be deleted because it is not in stock "
                "(it has been sold, transferred, or is otherwise unavailable)."
            )
        super().perform_destroy(instance)

    def perform_update(self, serializer):
        instance = serializer.instance
        if not instance.stk_status:
            from rest_framework.exceptions import ValidationError
            ALWAYS_EDITABLE = {'rfid_tag', 'huid', 'design_code'}
            restricted = set(serializer.validated_data.keys()) - ALWAYS_EDITABLE
            if restricted:
                raise ValidationError(
                    f"Barcode '{instance.barcode}' cannot be edited while it is not in stock. "
                    "Only RFID tag, HUID, and design code may be updated."
                )
        super().perform_update(serializer)

    @action(detail=True, methods=['post'], url_path='transfer-to-order')
    def transfer_to_order(self, request, pk=None):
        """Assign a barcode to a customer order. Rejects if barcode is already
        attached to another order or if the target order is closed/cancelled."""
        from rest_framework.exceptions import ValidationError
        from sales.models import CustomerOrder
        barcode = self.get_object()
        order_id = request.data.get('order_id')
        if not order_id:
            raise ValidationError({"order_id": "order_id is required."})
        if barcode.customer_order_id:
            raise ValidationError(
                f"Barcode '{barcode.barcode}' is already assigned to order "
                f"'{barcode.customer_order.order_no}'. Release it first."
            )
        try:
            order = CustomerOrder.objects.get(pk=order_id)
        except CustomerOrder.DoesNotExist:
            raise ValidationError({"order_id": "Customer order not found."})
        closed_status = (getattr(order, 'delivery_status', '') or '').lower()
        if closed_status in ('delivered', 'cancelled'):
            raise ValidationError(
                f"Order '{order.order_no}' is {closed_status} and cannot accept new barcodes."
            )
        with transaction.atomic():
            barcode.customer_order = order
            barcode.save(update_fields=['customer_order'])
        barcode.refresh_from_db()
        serializer = BarCodeMainListSerializer(barcode, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='release-from-order')
    def release_from_order(self, request, pk=None):
        from rest_framework.exceptions import ValidationError
        barcode = self.get_object()
        mode = (request.data.get('mode') or '').strip()
        remarks = (request.data.get('remarks') or '').strip()

        if mode not in (BarcodeOrderReleaseLog.MODE_CANCEL, BarcodeOrderReleaseLog.MODE_REASSIGN):
            raise ValidationError({"mode": "mode must be 'cancel_order' or 'reassign'."})
        if not barcode.customer_order_id:
            raise ValidationError(
                f"Barcode '{barcode.barcode}' is not linked to any customer order."
            )

        with transaction.atomic():
            order = barcode.customer_order
            original_order_no = order.order_no if order else ''

            if mode == BarcodeOrderReleaseLog.MODE_CANCEL:
                if hasattr(order, 'delivery_status'):
                    order.delivery_status = 'cancelled'
                    order.save(update_fields=['delivery_status'])
            else:  # reassign
                # Best-effort: reset lifecycle flags on matching order items so the order
                # still looks "pending fulfillment" and can be re-reserved later.
                matching_items = order.items.filter(
                    item_id=barcode.item_id, purity_id=barcode.purity_id,
                )
                for coi in matching_items:
                    updates = {}
                    if getattr(coi, 'iss_status', False):
                        updates['iss_status'] = False
                    if getattr(coi, 'sale_status', False):
                        updates['sale_status'] = False
                    if getattr(coi, 'del_status', False):
                        updates['del_status'] = False
                    if updates:
                        for k, v in updates.items():
                            setattr(coi, k, v)
                        coi.save(update_fields=list(updates.keys()))

            BarcodeOrderReleaseLog.objects.create(
                barcode=barcode,
                original_order=order,
                original_order_no=original_order_no,
                mode=mode,
                remarks=remarks,
                released_by=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
            )
            barcode.customer_order = None
            barcode.save(update_fields=['customer_order'])

        barcode.refresh_from_db()
        serializer = BarCodeMainListSerializer(barcode, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

class BarcodeBulkListView(APIView):
    """
    GET /inventory/api/barcode-bulk/?item=GL&packet=PKT001&stk_status=true&search=...
    Returns ALL matching barcodes (no pagination) for bulk print / CSV export.

    Supports filtering by:
      - item (short_code)
      - packet (pckt_no on BarcodeDetails)
      - purity
      - stk_status
      - search (barcode number, item name, item short_code)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        retail = getattr(request, 'retail', None)
        qs = BarcodeMain.objects.select_related('item', 'purity').prefetch_related('barcodedetails_set__packet', 'barcodedetails_set__item')
        if retail:
            qs = qs.filter(retail=retail)

        # Filters
        item = request.query_params.get('item')
        if item:
            qs = qs.filter(item__short_code=item)

        packet = request.query_params.get('packet')
        if packet:
            qs = qs.filter(barcodedetails_set__packet__pckt_no=packet).distinct()

        purity = request.query_params.get('purity')
        if purity:
            qs = qs.filter(purity__purity=purity)

        stk = request.query_params.get('stk_status')
        if stk is not None and stk != '':
            qs = qs.filter(stk_status=stk.lower() in ('true', '1'))

        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(barcode__icontains=search) |
                Q(item__short_code__icontains=search) |
                Q(item__item_name__icontains=search)
            )

        qs = qs.order_by('-created_date')[:2000]  # safety cap
        data = BarCodeMainSerializer(qs, many=True).data

        # Enrich with qr_code URL, item_name and purity display name for label printing
        bc_map = {bc.id: bc for bc in qs}
        for item in data:
            bc = bc_map.get(item['id'])
            if bc:
                item['qr_code'] = bc.qr_code.url if bc.qr_code else None
                item['purity_name'] = bc.purity.purity if bc.purity else ''
                item['item_name'] = bc.item.item_name if bc.item else ''

        return Response({'count': len(data), 'results': data})


class UnBarCodeView(RetailBaseViewset):
    serializer_class = UnBarcodedMainSerializer
    queryset = UnBarcodedMain.objects.all()

    def perform_destroy(self, instance):
        if not instance.stk_status:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                "This unbarcoded item cannot be deleted because it is not in stock."
            )
        super().perform_destroy(instance)

    def perform_update(self, serializer):
        if not serializer.instance.stk_status:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                "This unbarcoded item cannot be edited because it is not in stock."
            )
        super().perform_update(serializer)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, F, FloatField
from django.db.models.functions import Coalesce
from datetime import datetime, timedelta
from django.utils import timezone
from decimal import Decimal
from mastersconfig.models import Item, Packet
from purchase.models import PurchaseVoucherDetails, PurchaseReturnDetails
from sales.models import SaleReturnItem, SalesVouItem, SalesVouItemDetails, SaleReturnDetails
from mastersconfig.serializers import ItemSerializer

from decimal import Decimal
from django.db.models import F, Sum, Case, When, DecimalField, Value, ExpressionWrapper
from django.db.models.functions import Coalesce
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import (
    Item, Packet, 
    RawMaterialInventory, BarcodeDetails, UnBarcodedDetails
)

from purchase.models import (
                            PurchaseReturn,
                            PurchaseReturnItems,
                            PurchaseVoucher,
                            PurchaseVoucherItems,
                            PurchaseVoucherDetails,
                            PurchaseReturnDetails
                            )

class ClosingStockCalculator(APIView):
    """
    API endpoint to calculate closing stock value using weighted average method.
    Closing Stock = Opening Stock + Purchases - Purchase Returns - Sales + Sale Returns
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """
        Calculate and return the closing stock value for all items.
        Optional query parameters:
        - item_id: Filter by specific item
        - retail_id: Filter by specific retail store
        - from_date: Start date for calculation (defaults to beginning of time)
        - to_date: End date for calculation (defaults to current date)
        """
        # Get query parameters
        item_id = request.query_params.get('item_id')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        hide_zero = request.query_params.get('hide_zero', 'true').lower() != 'false'

        # Multi-retail: accept `retail_ids` as a repeated param or comma-separated list,
        # fall back to legacy single `retail_id`. Empty / missing = all retails combined.
        # Scope/combined access is gated to admin/superadmin; other users are pinned to
        # their own request.retail regardless of what they pass.
        # Closing stock is always reported company-wide (all retails combined),
        # never per-branch.
        retail_ids = None

        # Calculate closing stock
        try:
            closing_stock = ClosingStockCal().calculate_closing_stock(
                item_id=item_id, retail_ids=retail_ids, from_date=from_date, to_date=to_date
            )
            details = closing_stock['details']
            if hide_zero:
                details = [
                    d for d in details
                    if not (float(d.get('closing_gw') or 0) == 0
                            and float(d.get('closing_ct') or 0) == 0
                            and float(d.get('closing_amt') or 0) == 0)
                ]
            return Response({
                'closing_stock_value': closing_stock['total_value'],
                'opening_value': closing_stock['opening_value'],
                'total_purc': closing_stock['total_purc'],
                'total_purc_ret': closing_stock['total_purc_ret'],
                'total_sale_ret': closing_stock['total_sale_ret'],
                'total_sale': closing_stock['total_sale'],
                'retail_ids': retail_ids,
                'details': details,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class StockValuationReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        purity_filter = request.query_params.get("purity")
        item_filter = request.query_params.get("item")

        # Build detail prefetch with optional item filter
        from django.db.models import Prefetch
        detail_qs = BarcodeDetails.objects.select_related('item', 'packet')
        if item_filter:
            detail_qs = detail_qs.filter(item__id=item_filter)

        barcodes = (
            BarcodeMain.objects
            .filter(stk_status=True)
            .select_related('purity', 'customer_order')
            .prefetch_related(Prefetch('barcodedetails_set', queryset=detail_qs))
        )
        if purity_filter:
            barcodes = barcodes.filter(purity=purity_filter)

        stock_data = []
        for barcode in barcodes:
            stones = []
            others = []
            for detail in barcode.barcodedetails_set.all():
                detail_data = {
                    "code": detail.item_id,
                    "sub": detail.packet_id,
                    "pcs": detail.pcs or 0,
                    "weight": detail.ct or 0,
                    "rate": detail.rate,
                    "value": detail.amt
                }
                if detail.item.item_type == "stone":
                    stones.append(detail_data)
                else:
                    others.append(detail_data)
            stock_data.append({
                "barcode": barcode.barcode,
                "order": barcode.customer_order_id,
                "pcs": barcode.pcs,
                "gw": barcode.gw,
                "nw": barcode.nw,
                "purity": barcode.purity.purity if barcode.purity else None,
                "stones": stones,
                "others": others,
                "making": barcode.making_val,
                "total_value": barcode.total_amount
            })
        return Response({"stock_valuation": stock_data}, status=status.HTTP_200_OK)

class StockReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        as_on_date = request.query_params.get('as_on_date')

        if not as_on_date:
            return Response({"error": "as_on_date is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            as_on_date = datetime.strptime(as_on_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

        retail = request.retail

        # Single-day report semantics:
        #   Opening(D) = closing balance as of end of day (D-1)
        #              = op_stk seeds (created_date <= D-1)
        #              + inflow transactions (date <= D-1)
        #              - outflow transactions (date <= D-1)
        #   Inflow/Outflow columns = movements on day D only
        #   Stock(D) = Opening + Inflow - Outflow
        prev_date = as_on_date - timedelta(days=1)

        # Actual trans_type values from barcode_transaction table
        inflow_types = [
            'CREATE-PUR', 'CREATE-REC', 'SALE-RET', 'SALE-APP-RET',
            'TRF-RR-IN', 'BAR-MER-CRT', 'BAR-SPLIT-CRT',
        ]
        outflow_types = [
            'SALE', 'SALE-APP', 'TRF-RR-OUT',
            'BAR-MER', 'BAR-SPLIT', 'BAR-TRF-UNB', 'PURCHASE-RET',
        ]

        # Barcodes consumed by a split/merge must not count as stock. Two sources:
        #  1. old_barcode of a BarcodeSplitMerge row (skip NULLs — a NULL in a
        #     `NOT IN (...)` subquery makes the predicate NULL/false for every row
        #     under SQL three-valued logic, which would zero out the whole report).
        #  2. barcodes whose name carries the #SPL / #MER marker — the consumed
        #     parent is renamed this way and often isn't linked as old_barcode
        #     (the legacy split table stores the pre-rename id).
        # Materialised as a plain list of ints so the subqueries stay NULL-safe.
        split_merged_barcode_ids = list(
            set(BarcodeSplitMerge.objects.filter(old_barcode__isnull=False)
                .values_list('old_barcode_id', flat=True))
            | set(BarcodeMain.objects.filter(
                Q(barcode__icontains='#SPL') | Q(barcode__icontains='#MER')
            ).values_list('id', flat=True))
        )

        # op_stk seed barcodes still in inventory as of end of prev_date.
        # stk_status is intentionally NOT filtered — an op_stk barcode held with a
        # karigar or in approval still belongs to the retail's inventory.
        # EXCLUDE barcodes that have been split/merged.
        op_stk_pcs_sq = BarcodeMain.objects.filter(
            op_retail=retail,
            item=OuterRef('pk'),
            op_stk=True,
            created_date__lte=as_on_date,
        ).exclude(
            pk__in=split_merged_barcode_ids
        ).values('item').annotate(total=Coalesce(Sum('pcs'), 0)).values('total')

        # Prior-period transactions (date <= prev_date). Retail-less rows (legacy /
        # import) are included defensively so they don't vanish from every retail.
        # Inflow: EXCLUDE transactions from barcodes that have been split/merged.
        prior_inflow_tx = BarcodeTransaction.objects.filter(
            barcode__item=OuterRef('pk'),
            date__date__lte=prev_date,
            trans_type__in=inflow_types,
        ).exclude(
            barcode_id__in=split_merged_barcode_ids
        ).filter(Q(retail=retail) | Q(retail__isnull=True))

        prior_inflow_pcs_sq = prior_inflow_tx.values(
            'barcode__item'
        ).annotate(total=Coalesce(Sum('barcode__pcs'), 0)).values('total')

        # Outflow: Include BAR-SPLIT on old barcodes, but exclude other outflow on split barcodes.
        # BAR-SPLIT represents the outflow when a barcode is split, so it should always be included.
        prior_outflow_tx = BarcodeTransaction.objects.filter(
            barcode__item=OuterRef('pk'),
            date__date__lte=prev_date,
            trans_type__in=outflow_types,
        ).filter(Q(retail=retail) | Q(retail__isnull=True))

        # Exclude other outflow types from split barcodes, but keep BAR-SPLIT
        prior_outflow_tx = prior_outflow_tx.exclude(
            barcode_id__in=split_merged_barcode_ids,
            trans_type__in=[t for t in outflow_types if t != 'BAR-SPLIT']
        )

        prior_outflow_pcs_sq = prior_outflow_tx.values(
            'barcode__item'
        ).annotate(total=Coalesce(Sum('barcode__pcs'), 0)).values('total')

        # Day-of transactions (date == as_on_date) — drives all per-type inflow/outflow columns.
        # Exclude split barcodes from inflow, but include BAR-SPLIT outflow on old barcodes.
        transactions = BarcodeTransaction.objects.filter(
            barcode__item=OuterRef('pk'),
            date__date=as_on_date,
        ).filter(Q(retail=retail) | Q(retail__isnull=True))

        # Exclude inflow and non-BAR-SPLIT outflow on split barcodes, but keep BAR-SPLIT
        transactions = transactions.exclude(
            barcode_id__in=split_merged_barcode_ids,
            trans_type__in=inflow_types + [t for t in outflow_types if t != 'BAR-SPLIT']
        )

        # Map trans_type values to safe annotation field names
        type_field_map = {
            'CREATE-PUR': 'create_pur', 'CREATE-REC': 'create_rec',
            'SALE-RET': 'sale_ret', 'SALE-APP-RET': 'sale_app_ret',
            'TRF-RR-IN': 'trf_rr_in', 'BAR-MER-CRT': 'bar_mer_crt',
            'BAR-SPLIT-CRT': 'bar_split_crt',
            'SALE': 'sale', 'SALE-APP': 'sale_app',
            'TRF-RR-OUT': 'trf_rr_out', 'BAR-MER': 'bar_mer',
            'BAR-SPLIT': 'bar_split', 'BAR-TRF-UNB': 'bar_trf_unb',
            'PURCHASE-RET': 'pur_ret',
        }

        annotations = {
            '_op_stk_pcs': Coalesce(Subquery(op_stk_pcs_sq, output_field=IntegerField()), 0),
            '_prior_inflow_pcs': Coalesce(Subquery(prior_inflow_pcs_sq, output_field=IntegerField()), 0),
            '_prior_outflow_pcs': Coalesce(Subquery(prior_outflow_pcs_sq, output_field=IntegerField()), 0),
        }

        for trans_type, field_name in type_field_map.items():
            annotations[field_name] = Coalesce(Subquery(
                transactions.filter(trans_type=trans_type)
                .values('barcode__item')
                .annotate(total=Coalesce(Sum('barcode__pcs'), 0))
                .values('total'),
                output_field=IntegerField()
            ), 0)

        inflow_fields = [type_field_map[t] for t in inflow_types]
        outflow_fields = [type_field_map[t] for t in outflow_types]

        inflow_expr = F(inflow_fields[0])
        for fld in inflow_fields[1:]:
            inflow_expr = inflow_expr + F(fld)

        outflow_expr = F(outflow_fields[0])
        for fld in outflow_fields[1:]:
            outflow_expr = outflow_expr + F(fld)

        qs = Item.objects.all().annotate(
            **annotations,
            inflow=inflow_expr,
            outflow=outflow_expr,
        ).annotate(
            opening=F('_op_stk_pcs') + F('_prior_inflow_pcs') - F('_prior_outflow_pcs'),
        ).annotate(
            stock=F('opening') + F('inflow') - F('outflow'),
        ).filter(
            Q(opening__gt=0) | Q(inflow__gt=0) | Q(outflow__gt=0)
        ).order_by('short_code')

        data = [dict(r) for r in ItemStockReportSerializer(qs, many=True).data]

        # All *_count fields are computed in Python via bulk aggregation. Subquery +
        # Count(distinct=True) + OuterRef was returning 0 in this ORM version, so we
        # sidestep the ORM entirely and patch the response.
        retail_filter = Q(retail=retail) | Q(retail__isnull=True)

        op_stk_counts = {}
        for iid in BarcodeMain.objects.filter(
            op_retail=retail, op_stk=True, created_date__lte=as_on_date,
        ).exclude(
            pk__in=split_merged_barcode_ids
        ).values_list('item', flat=True):
            op_stk_counts[iid] = op_stk_counts.get(iid, 0) + 1

        prior_in_sets = {}
        for iid, bid in BarcodeTransaction.objects.filter(
            date__date__lte=prev_date, trans_type__in=inflow_types,
        ).exclude(
            barcode_id__in=split_merged_barcode_ids
        ).filter(retail_filter).values_list('barcode__item', 'barcode_id'):
            prior_in_sets.setdefault(iid, set()).add(bid)
        prior_in_counts = {iid: len(s) for iid, s in prior_in_sets.items()}

        prior_out_sets = {}
        for iid, bid in BarcodeTransaction.objects.filter(
            date__date__lte=prev_date, trans_type__in=outflow_types,
        ).filter(retail_filter).exclude(
            barcode_id__in=split_merged_barcode_ids,
            trans_type__in=[t for t in outflow_types if t != 'BAR-SPLIT']
        ).values_list('barcode__item', 'barcode_id'):
            prior_out_sets.setdefault(iid, set()).add(bid)
        prior_out_counts = {iid: len(s) for iid, s in prior_out_sets.items()}

        # Per-trans-type day-of distinct barcode counts: { item_id: { trans_type: count } }
        day_sets = {}
        for iid, tt, bid in BarcodeTransaction.objects.filter(
            date__date=as_on_date,
        ).filter(retail_filter).exclude(
            barcode_id__in=split_merged_barcode_ids,
            trans_type__in=inflow_types + [t for t in outflow_types if t != 'BAR-SPLIT']
        ).values_list('barcode__item', 'trans_type', 'barcode_id'):
            day_sets.setdefault(iid, {}).setdefault(tt, set()).add(bid)
        day_counts = {
            iid: {tt: len(s) for tt, s in by_tt.items()}
            for iid, by_tt in day_sets.items()
        }

        for row in data:
            iid = row['id']
            opening_count = (
                op_stk_counts.get(iid, 0)
                + prior_in_counts.get(iid, 0)
                - prior_out_counts.get(iid, 0)
            )
            row['opening_count'] = opening_count
            per_type = day_counts.get(iid, {})
            inflow_count = 0
            outflow_count = 0
            for tt in inflow_types:
                c = per_type.get(tt, 0)
                row[f'{type_field_map[tt]}_count'] = c
                inflow_count += c
            for tt in outflow_types:
                c = per_type.get(tt, 0)
                row[f'{type_field_map[tt]}_count'] = c
                outflow_count += c
            row['inflow_count'] = inflow_count
            row['outflow_count'] = outflow_count
            row['stock_count'] = opening_count + inflow_count - outflow_count

        return Response(data)


class StockReportBarcodesView(APIView):
    permission_classes = [IsAuthenticated]

    INFLOW_COLUMNS = {
        'create_pur': 'CREATE-PUR', 'create_rec': 'CREATE-REC',
        'sale_ret': 'SALE-RET', 'sale_app_ret': 'SALE-APP-RET',
        'trf_rr_in': 'TRF-RR-IN', 'bar_mer_crt': 'BAR-MER-CRT',
        'bar_split_crt': 'BAR-SPLIT-CRT',
    }
    OUTFLOW_COLUMNS = {
        'sale': 'SALE', 'sale_app': 'SALE-APP', 'trf_rr_out': 'TRF-RR-OUT',
        'bar_mer': 'BAR-MER', 'bar_split': 'BAR-SPLIT', 'bar_trf_unb': 'BAR-TRF-UNB',
        'pur_ret': 'PURCHASE-RET',
    }

    def get(self, request):
        item_id = request.query_params.get('item_id')
        column = request.query_params.get('column')
        as_on_date_raw = request.query_params.get('as_on_date')

        if not (item_id and column and as_on_date_raw):
            return Response(
                {"error": "item_id, column, and as_on_date are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            as_on_date = datetime.strptime(as_on_date_raw, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        retail = request.retail

        if column in ('opening', 'stock'):
            # Single-day report: opening = in-stock at end of (as_on_date - 1),
            # stock = in-stock at end of as_on_date.
            cutoff = as_on_date - timedelta(days=1) if column == 'opening' else as_on_date
            opening_ids = set(
                BarcodeMain.objects.filter(
                    op_retail=retail, item_id=item_id, op_stk=True,
                    created_date__lte=cutoff,
                ).values_list('pk', flat=True)
            )
            txn_qs = BarcodeTransaction.objects.filter(
                barcode__item_id=item_id,
                date__date__lte=cutoff,
            ).filter(Q(retail=retail) | Q(retail__isnull=True))

            inflow_trans = set(self.INFLOW_COLUMNS.values())
            outflow_trans = set(self.OUTFLOW_COLUMNS.values())
            per_barcode = {}
            for barcode_id, trans_type in txn_qs.order_by('date').values_list('barcode_id', 'trans_type'):
                net = per_barcode.get(barcode_id, 0)
                if trans_type in inflow_trans:
                    net += 1
                elif trans_type in outflow_trans:
                    net -= 1
                per_barcode[barcode_id] = net

            in_stock_ids = set(opening_ids)
            for bid, net in per_barcode.items():
                if net > 0:
                    in_stock_ids.add(bid)
                elif net < 0 and bid in in_stock_ids:
                    in_stock_ids.discard(bid)

            label = 'OPENING' if column == 'opening' else 'IN-STOCK'
            barcodes = BarcodeMain.objects.filter(pk__in=in_stock_ids).order_by('barcode')
            rows = [{
                'barcode': b.barcode,
                'pcs': b.pcs,
                'date': b.created_date.isoformat() if b.created_date else None,
                'billno': '',
                'trans_type': label,
            } for b in barcodes]
            return Response(rows)

        trans_type = self.INFLOW_COLUMNS.get(column) or self.OUTFLOW_COLUMNS.get(column)
        if not trans_type:
            return Response({"error": f"Unknown column '{column}'"}, status=status.HTTP_400_BAD_REQUEST)

        # Per-type columns are scoped to the selected day to match the main report.
        txns = BarcodeTransaction.objects.filter(
            barcode__item_id=item_id,
            trans_type=trans_type,
            date__date=as_on_date,
        ).filter(
            Q(retail=retail) | Q(retail__isnull=True)
        ).select_related('barcode').order_by('date')

        rows = [{
            'barcode': t.barcode.barcode,
            'pcs': t.barcode.pcs,
            'date': t.date.date().isoformat() if t.date else None,
            'billno': t.billno or '',
            'trans_type': t.trans_type,
        } for t in txns]
        return Response(rows)


# ── In-stock helper (shared semantics with the Barcode Stock Report) ─────────
def in_stock_barcode_ids(retail, as_on_date):
    """Return the set of BarcodeMain ids in stock as of end of `as_on_date` for
    `retail`. Mirrors the 'stock' branch of StockReportBarcodesView so the Value
    Report's barcode set matches the Barcode Stock Report's stock column:
      stock = op_stk seeds (created <= date) + net inflow/outflow movements,
              minus split/merge-consumed barcodes (#SPL/#MER + old_barcode).
    Retail-less transactions (legacy/import) are included defensively.
    """
    inflow_types = {
        'CREATE-PUR', 'CREATE-REC', 'SALE-RET', 'SALE-APP-RET',
        'TRF-RR-IN', 'BAR-MER-CRT', 'BAR-SPLIT-CRT',
    }
    outflow_types = {
        'SALE', 'SALE-APP', 'TRF-RR-OUT',
        'BAR-MER', 'BAR-SPLIT', 'BAR-TRF-UNB', 'PURCHASE-RET',
    }

    split_merged = set(
        BarcodeSplitMerge.objects.filter(old_barcode__isnull=False)
        .values_list('old_barcode_id', flat=True)
    ) | set(
        BarcodeMain.objects.filter(
            Q(barcode__icontains='#SPL') | Q(barcode__icontains='#MER')
        ).values_list('id', flat=True)
    )

    opening_ids = set(
        BarcodeMain.objects.filter(
            op_retail=retail, op_stk=True, created_date__lte=as_on_date,
        ).values_list('pk', flat=True)
    )

    txn_qs = BarcodeTransaction.objects.filter(
        date__date__lte=as_on_date,
    ).filter(Q(retail=retail) | Q(retail__isnull=True))

    per_barcode = {}
    for barcode_id, trans_type in txn_qs.order_by('date').values_list('barcode_id', 'trans_type'):
        net = per_barcode.get(barcode_id, 0)
        if trans_type in inflow_types:
            net += 1
        elif trans_type in outflow_types:
            net -= 1
        per_barcode[barcode_id] = net

    in_stock = set(opening_ids)
    for bid, net in per_barcode.items():
        if net > 0:
            in_stock.add(bid)
        elif net < 0:
            in_stock.discard(bid)

    return in_stock - split_merged


# `serializers` is bound to mastersconfig.serializers in this module; use the
# real DRF serializers (with field classes) under an explicit alias here.
from rest_framework import serializers as rf_serializers


class ValueReportLineSerializer(rf_serializers.ModelSerializer):
    """One stone or 'other' (HMC/RHC/making-component) line under a barcode."""
    code = rf_serializers.CharField(source='item.short_code', read_only=True, default=None)
    name = rf_serializers.CharField(source='item.item_name', read_only=True, default=None)
    sub = rf_serializers.CharField(source='packet.pckt_no', read_only=True, default=None)
    value = rf_serializers.DecimalField(source='amt', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = BarcodeDetails
        fields = ['code', 'name', 'sub', 'pcs', 'ct', 'gw', 'rate', 'value']


class ValueReportBarcodeSerializer(rf_serializers.ModelSerializer):
    """A single barcode row with its weights, purity, stone/other breakdown,
    making and total value. `stone`/`other` come from the to_attr prefetch."""
    purity = rf_serializers.CharField(source='purity.purity', read_only=True, default=None)
    item_name = rf_serializers.CharField(source='item.item_name', read_only=True, default=None)
    order_no = rf_serializers.CharField(source='customer_order.order_no', read_only=True, default=None)
    stone = ValueReportLineSerializer(many=True, read_only=True)
    other = ValueReportLineSerializer(many=True, read_only=True)

    class Meta:
        model = BarcodeMain
        fields = [
            'barcode', 'design_code', 'order_no', 'pcs', 'gw', 'nw', 'purity', 'item_name',
            'making_val', 'other_chg', 'value', 'total_amount', 'stone', 'other',
        ]


class ItemBarcodeSerializer(rf_serializers.ModelSerializer):
    barcodemain_set = ValueReportBarcodeSerializer(many=True, read_only=True)

    class Meta:
        model = Item
        fields = ['short_code', 'item_name', 'barcodemain_set']


class ItemwiseBarcodeReport(APIView):
    """Barcode Value Report — lists in-stock barcodes (as of a date, current
    branch) grouped by item, with per-barcode stone/other/making/value detail."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        as_on_raw = request.query_params.get('as_on_date')
        if as_on_raw:
            try:
                as_on_date = datetime.strptime(as_on_raw, '%Y-%m-%d').date()
            except ValueError:
                return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            as_on_date = timezone.localdate()

        retail = request.retail
        ids = in_stock_barcode_ids(retail, as_on_date)

        # Optional filters: item (short_code of the parent Item) and purity (label).
        item_code = (request.query_params.get('item') or '').strip()
        purity_label = (request.query_params.get('purity') or '').strip()
        base = BarcodeMain.objects.filter(id__in=ids)
        if item_code:
            base = base.filter(item__short_code=item_code)
        if purity_label:
            base = base.filter(purity__purity=purity_label)
        keep_ids = set(base.values_list('id', flat=True))

        barcode_qs = BarcodeMain.objects.filter(id__in=keep_ids).select_related(
            'purity', 'item', 'customer_order',
        ).prefetch_related(
            Prefetch('barcodedetails_set',
                     queryset=BarcodeDetails.objects.select_related('item', 'packet').filter(item__item_type='S'),
                     to_attr='stone'),
            # Other = non-stone lines, EXCLUDING the base metal line (Gold): its
            # weight is already shown in the barcode's Gw/Nw columns.
            Prefetch('barcodedetails_set',
                     queryset=BarcodeDetails.objects.select_related('item', 'packet')
                     .exclude(item__item_type='S')
                     .exclude(item__short_code__iexact='Gold'),
                     to_attr='other'),
        ).order_by('item__short_code', 'barcode')

        # Only items that actually have matching in-stock barcodes (no empty rows).
        qs = Item.objects.filter(barcodemain__id__in=keep_ids).distinct().order_by(
            'short_code',
        ).prefetch_related(Prefetch('barcodemain_set', queryset=barcode_qs))

        return Response(ItemBarcodeSerializer(qs, many=True).data)
    

class ClosingStockCal:
    """
    Closing stock calculation with separate gw (gross weight), ct (carat),
    and amt (amount) for each transaction type, plus refinery issue/receive.
    """

    @staticmethod
    def _zero():
        return {'gw': Decimal('0.00'), 'ct': Decimal('0.00'), 'amt': Decimal('0.00')}

    @staticmethod
    def _normalize_retail_ids(retail_id=None, retail_ids=None):
        """Accept either retail_id (int) or retail_ids (list) and return a normalized list or None."""
        if retail_ids is not None:
            if not retail_ids:
                return None
            return list(retail_ids)
        if retail_id is None:
            return None
        if isinstance(retail_id, (list, tuple, set)):
            return list(retail_id) if retail_id else None
        return [retail_id]

    def calculate_closing_stock(self, item_id=None, retail_id=None, retail_ids=None, from_date=None, to_date=None):
        """Batched implementation: one GROUP BY item_id query per movement type
        instead of ~9 queries per item. Per-item Python glue preserves the
        item_type branches from the original logic."""
        retail_ids = self._normalize_retail_ids(retail_id, retail_ids)
        zero = Decimal('0.00')

        items_query = Item.objects.exclude(item_type__in=['M', 'O'])
        if item_id:
            items_query = items_query.filter(id=item_id)
        items = list(items_query)
        item_ids = [i.id for i in items]

        # Early exit: nothing to report.
        if not item_ids:
            return {
                'total_value': zero, 'opening_value': zero, 'total_purc': zero,
                'total_purc_ret': zero, 'total_sale_ret': zero, 'total_sale': zero,
                'details': [],
            }

        def _retail_q(field='retail_id'):
            if retail_ids:
                return Q(**{f'{field}__in': retail_ids}) | Q(**{f'{field}__isnull': True})
            return Q()

        def _date_filter(qs, field='billno__date1'):
            if from_date:
                qs = qs.filter(**{f'{field}__gte': from_date})
            if to_date:
                qs = qs.filter(**{f'{field}__lte': to_date})
            return qs

        def _batch(qs, key, annotations):
            out = {}
            for row in qs.values(key).annotate(**annotations):
                iid = row[key]
                if iid is None:
                    continue
                out[iid] = {k: row[k] for k in annotations}
            return out

        def _get(d, iid, key):
            return d.get(iid, {}).get(key, zero)

        # ── Opening stock (single source: OpeningInventory) ──────────────────
        # Opening stock is pulled exclusively from the Opening Stock entry
        # screen (`/inventory/opening-stock` → OpeningInventory). Opening value
        # is computed per-row as wtd_avg_rate × primary_qty (gw for M/R,
        # ct for S) and summed; we aggregate both candidate amounts here and
        # pick the right one per item.item_type in the per-item loop below.
        op_r_qs = OpeningInventory.objects.filter(item_id__in=item_ids)
        if retail_ids:
            op_r_qs = op_r_qs.filter(_retail_q())

        op_r = _batch(op_r_qs, 'item_id', {
            'total_gw': Coalesce(Sum('gw'), zero),
            'total_ct': Coalesce(Sum('ct'), zero),
            'total_amt_gw': Coalesce(
                Sum(F('wtd_avg_rate') * F('gw'), output_field=DecimalField(max_digits=20, decimal_places=4)),
                zero,
            ),
            'total_amt_ct': Coalesce(
                Sum(F('wtd_avg_rate') * F('ct'), output_field=DecimalField(max_digits=20, decimal_places=4)),
                zero,
            ),
        })

        # ── Purchases (main + sub-item details) ──────────────────────────────
        pu_main_qs = PurchaseVoucherItems.objects.filter(
            item_id__in=item_ids, is_return=False, is_finished=False,
        ).filter(_retail_q())
        pu_main_qs = _date_filter(pu_main_qs)
        pu_main = _batch(pu_main_qs, 'item_id', {
            'total_gw': Coalesce(Sum('gw'), zero),
            'total_amt': Coalesce(Sum('item_value'), zero),
        })
        pu_det_qs = PurchaseVoucherDetails.objects.filter(
            sub_item_id__in=item_ids,
        ).filter(
            Q(main_item__isnull=True) |
            Q(main_item__is_finished=False, main_item__is_return=False)
        ).exclude(
            # Skip rows where the parent main_item is the same item as the
            # sub_item — pu_main already accounts for these via _real_value.
            # Otherwise R-type items (e.g., raw Gold bought via customer
            # purchase) get their gw and amount counted twice.
            main_item__item_id=F('sub_item_id'),
        ).filter(_retail_q())
        pu_det_qs = _date_filter(pu_det_qs)
        pu_det = _batch(pu_det_qs, 'sub_item_id', {
            'total_gw': Coalesce(Sum('sub_gw'), zero),
            'total_ct': Coalesce(Sum('sub_ct'), zero),
            'total_amt': Coalesce(Sum('value'), zero),
        })

        # ── Purchase returns ─────────────────────────────────────────────────
        pr_main_qs = PurchaseReturnItems.objects.filter(item_id__in=item_ids).filter(_retail_q())
        pr_main_qs = _date_filter(pr_main_qs)
        pr_main = _batch(pr_main_qs, 'item_id', {
            'total_gw': Coalesce(Sum('gw'), zero),
            'total_amt': Coalesce(Sum(F('gw') * F('making_value'), output_field=DecimalField()), zero),
        })
        pr_det_qs = PurchaseReturnDetails.objects.filter(sub_item_id__in=item_ids).filter(_retail_q())
        pr_det_qs = _date_filter(pr_det_qs)
        pr_det = _batch(pr_det_qs, 'sub_item_id', {
            'total_gw': Coalesce(Sum('sub_gw'), zero),
            'total_ct': Coalesce(Sum('sub_ct'), zero),
            'total_amt': Coalesce(Sum('value'), zero),
        })

        # ── Sales ────────────────────────────────────────────────────────────
        sa_main_qs = SalesVouItem.objects.filter(item_id__in=item_ids).filter(_retail_q())
        sa_main_qs = _date_filter(sa_main_qs)
        _amt_field = DecimalField(max_digits=20, decimal_places=2)
        sa_main = _batch(sa_main_qs, 'item_id', {
            'total_gw': Coalesce(Sum('gw'), zero),
            'total_amt': Coalesce(Sum('amount', output_field=_amt_field), zero),
        })
        sa_det_qs = SalesVouItemDetails.objects.filter(item_id__in=item_ids).filter(_retail_q())
        # Filter on the detail's own billno date, not main_item's — direct sale
        # details (main_id=0 -> main_item NULL) would otherwise be dropped.
        sa_det_qs = _date_filter(sa_det_qs, 'billno__date1')
        sa_det = _batch(sa_det_qs, 'item_id', {
            'total_gw': Coalesce(Sum('gw'), zero),
            'total_ct': Coalesce(Sum('ct'), zero),
            'total_amt': Coalesce(Sum('amount', output_field=_amt_field), zero),
        })

        # ── Sale returns ─────────────────────────────────────────────────────
        sr_main_qs = SaleReturnItem.objects.filter(item_id__in=item_ids).filter(_retail_q())
        sr_main_qs = _date_filter(sr_main_qs)
        sr_main = _batch(sr_main_qs, 'item_id', {'total_gw': Coalesce(Sum('gw'), zero)})
        sr_det_qs = SaleReturnDetails.objects.filter(item_id__in=item_ids).filter(_retail_q())
        sr_det_qs = _date_filter(sr_det_qs, 'main_item__billno__date1')
        sr_det = _batch(sr_det_qs, 'item_id', {
            'total_gw': Coalesce(Sum('gw'), zero),
            'total_ct': Coalesce(Sum('ct'), zero),
            'total_amt': Coalesce(Sum('amount'), zero),
        })

        # ── Refinery issues / receives ───────────────────────────────────────
        # ISSUES stay attributed to the issued raw-metal item (e.g. Old Gold)
        # and deduct its gross weight. RECEIVES come back as fine gold: the
        # refiner returns pure metal at the converted purity, so the received
        # quantity is the converted net weight (conv_nw) — NOT the gross weight
        # that was issued — and it is booked entirely against the "Fine Gold"
        # item, never the old-gold item that was issued. (Any gold received
        # from refinery is fine gold.)
        ri_qs = _date_filter(RefinaryIssueDetail.objects.filter(item_id__in=item_ids).filter(_retail_q()))
        rr_qs = _date_filter(RefinaryReceiveDetail.objects.filter(_retail_q()))
        gwct_ann = {
            'total_gw': Coalesce(Sum('gw'), zero),
            'total_ct': Coalesce(Sum('ct'), zero),
        }
        ri = _batch(ri_qs, 'item_id', gwct_ann)

        # Sum the converted net (fine) weight across all receives and book it
        # against the Fine Gold item, irrespective of the issued item.
        fine_gold = next((i for i in items if i.item_name == 'Fine Gold'), None)
        rr = {}
        if fine_gold is not None:
            rr_agg = rr_qs.aggregate(
                total_gw=Coalesce(Sum('conv_nw'), zero),
                total_ct=Coalesce(Sum('ct'), zero),
            )
            rr = {fine_gold.id: {'total_gw': rr_agg['total_gw'], 'total_ct': rr_agg['total_ct']}}

        # ── Inter-retail transfers (received status only) ────────────────────
        trn_base = InterRetailTransferItem.objects.filter(
            item_id__in=item_ids,
            voucher__status=InterRetailTransferVoucher.STATUS_RECEIVED,
        )
        if from_date:
            trn_base = trn_base.filter(voucher__transfer_date__gte=from_date)
        if to_date:
            trn_base = trn_base.filter(voucher__transfer_date__lte=to_date)
        trn_anns = {
            'total_gw': Coalesce(Sum('qty_gw'), zero),
            'total_ct': Coalesce(Sum('qty_ct'), zero),
            'total_amt': Coalesce(Sum('transfer_value'), zero),
        }
        trn_iss_qs = trn_base.filter(voucher__from_retail_id__in=retail_ids) if retail_ids else trn_base
        trn_rec_qs = trn_base.filter(voucher__to_retail_id__in=retail_ids) if retail_ids else trn_base
        trn_iss_d = _batch(trn_iss_qs, 'item_id', trn_anns)
        trn_rec_d = _batch(trn_rec_qs, 'item_id', trn_anns)

        # Mfg adjustment is a single global aggregate — hoist out of the loop.
        mfg_adj_total = self.get_mfg_adj() or zero

        results = {
            'total_value': zero, 'opening_value': zero, 'total_purc': zero,
            'total_purc_ret': zero, 'total_sale_ret': zero, 'total_sale': zero,
            'details': [],
        }

        for item in items:
            iid = item.id

            # Opening — pulled only from OpeningInventory.
            # Amount uses the per-row stored wtd_avg_rate × primary_qty
            # (gw for M/R, ct for S), summed at the DB level.
            op_gw = _get(op_r, iid, 'total_gw')
            op_ct = _get(op_r, iid, 'total_ct')
            op_amt = _get(op_r, iid, 'total_amt_ct') if item.item_type == 'S' else _get(op_r, iid, 'total_amt_gw')
            opening = {'gw': op_gw, 'ct': op_ct, 'amt': op_amt}

            # Purchases
            pu_gw = _get(pu_main, iid, 'total_gw')
            pu_amt = _get(pu_main, iid, 'total_amt')
            pu_ct = _get(pu_det, iid, 'total_ct')
            if item.item_type == 'S':
                pu_gw = _get(pu_det, iid, 'total_gw')
                pu_amt = _get(pu_det, iid, 'total_amt')
            elif item.item_type == 'R':
                pu_gw += _get(pu_det, iid, 'total_gw')
                pu_amt += _get(pu_det, iid, 'total_amt')
            purchase = {'gw': pu_gw, 'ct': pu_ct, 'amt': pu_amt}

            # Purchase returns (mirror the Purchases aggregation: stone GW/CT/amount
            # live on the detail rows, so pull them from pr_det for S/R items).
            pr_gw = _get(pr_main, iid, 'total_gw')
            pr_amt = _get(pr_main, iid, 'total_amt')
            pr_ct = _get(pr_det, iid, 'total_ct')
            if item.item_type == 'S':
                pr_gw = _get(pr_det, iid, 'total_gw')
                pr_amt = _get(pr_det, iid, 'total_amt')
            elif item.item_type == 'R':
                pr_gw += _get(pr_det, iid, 'total_gw')
                pr_amt += _get(pr_det, iid, 'total_amt')
            purc_ret = {'gw': pr_gw, 'ct': pr_ct, 'amt': pr_amt}

            # Sales — amount shown at ACTUAL sale value (matches the drill-down),
            # mirroring the gw aggregation to avoid double-counting. Closing value
            # is unaffected: it is derived from quantities (sa_qty), not this amount.
            sa_gw = _get(sa_main, iid, 'total_gw')
            sa_amt = _get(sa_main, iid, 'total_amt')
            sa_ct = zero
            if item.item_type == 'S':
                sa_gw = _get(sa_det, iid, 'total_gw')
                sa_ct = _get(sa_det, iid, 'total_ct')
                sa_amt = _get(sa_det, iid, 'total_amt')
            elif item.item_type == 'R':
                sa_gw += _get(sa_det, iid, 'total_gw')
                sa_amt += _get(sa_det, iid, 'total_amt')
            sales = {'gw': sa_gw, 'ct': sa_ct, 'amt': sa_amt}

            # Sale returns — amount at ACTUAL return value (matches the drill-down),
            # from the detail rows (SaleReturnItem has no amount). Closing value is
            # unaffected: it is derived from quantities (sr_qty), not this amount.
            sr_gw = _get(sr_main, iid, 'total_gw')
            sr_ct = zero
            sr_amt = zero
            if item.item_type == 'S':
                sr_gw = _get(sr_det, iid, 'total_gw')
                sr_ct = _get(sr_det, iid, 'total_ct')
                sr_amt = _get(sr_det, iid, 'total_amt')
            elif item.item_type == 'R':
                sr_gw += _get(sr_det, iid, 'total_gw')
                sr_amt = _get(sr_det, iid, 'total_amt')
            sale_ret = {'gw': sr_gw, 'ct': sr_ct, 'amt': sr_amt}

            # Refinery + transfers
            ref_iss = {'gw': _get(ri, iid, 'total_gw'), 'ct': _get(ri, iid, 'total_ct'), 'amt': zero}
            ref_rec = {'gw': _get(rr, iid, 'total_gw'), 'ct': _get(rr, iid, 'total_ct'), 'amt': zero}
            trn_iss = {'gw': _get(trn_iss_d, iid, 'total_gw'), 'ct': _get(trn_iss_d, iid, 'total_ct'), 'amt': _get(trn_iss_d, iid, 'total_amt')}
            trn_rec = {'gw': _get(trn_rec_d, iid, 'total_gw'), 'ct': _get(trn_rec_d, iid, 'total_ct'), 'amt': _get(trn_rec_d, iid, 'total_amt')}

            # Determine primary quantity for weighted average based on item type
            if item.item_type in ['M', 'R']:
                pq = 'gw'
            elif item.item_type == 'S':
                pq = 'ct'
            else:
                pq = 'gw'  # fallback

            op_qty = opening[pq]
            pu_qty = purchase[pq]
            pr_qty = purc_ret[pq]
            tr_in_qty = trn_rec[pq]
            tr_out_qty = trn_iss[pq]
            sr_qty = sale_ret[pq]

            # Weighted-average cost pool: opening + inward movements. Customer
            # returns (sale returns) re-enter the pool at their return value,
            # matching the legacy ERP's valuation.
            total_in_qty = op_qty + pu_qty - pr_qty + tr_in_qty + sr_qty
            total_in_value = (opening['amt'] + purchase['amt'] - purc_ret['amt']
                              + trn_rec['amt'] + sale_ret['amt'])

            weighted_avg_rate = Decimal('0.00')
            if total_in_qty > 0:
                weighted_avg_rate = total_in_value / total_in_qty

            sa_qty = sales[pq]  # quantity drives the closing balance (cost), below

            ri_qty = ref_iss[pq]
            rr_qty = ref_rec[pq]

            adjustment = mfg_adj_total if item.item_name == "GOLD" else zero

            closing_qty = total_in_qty - sa_qty - ri_qty + rr_qty - tr_out_qty - adjustment
            closing_value = closing_qty * weighted_avg_rate

            # Closing gw and ct
            closing_gw = (opening['gw'] + purchase['gw'] - purc_ret['gw']
                          - sales['gw'] + sale_ret['gw']
                          - ref_iss['gw'] + ref_rec['gw']
                          - trn_iss['gw'] + trn_rec['gw'])
            closing_ct = (opening['ct'] + purchase['ct'] - purc_ret['ct']
                          - sales['ct'] + sale_ret['ct']
                          - ref_iss['ct'] + ref_rec['ct']
                          - trn_iss['ct'] + trn_rec['ct'])

            results['total_value'] += closing_value
            results['opening_value'] += opening['amt']
            results['total_purc'] += purchase['amt']
            results['total_purc_ret'] += purc_ret['amt']
            results['total_sale_ret'] += sale_ret['amt']
            results['total_sale'] += sales['amt']

            results['details'].append({
                'item_id': item.id,
                'item_name': item.item_name,
                'item_type': item.item_type,
                # Opening
                'opening_gw': float(opening['gw']),
                'opening_ct': float(opening['ct']),
                'opening_amt': float(opening['amt']),
                # Purchases
                'purchase_gw': float(purchase['gw']),
                'purchase_ct': float(purchase['ct']),
                'purchase_amt': float(purchase['amt']),
                # Purchase Returns
                'purc_ret_gw': float(purc_ret['gw']),
                'purc_ret_ct': float(purc_ret['ct']),
                'purc_ret_amt': float(purc_ret['amt']),
                # Sales
                'sales_gw': float(sales['gw']),
                'sales_ct': float(sales['ct']),
                'sales_amt': float(sales['amt']),
                # Sale Returns
                'sale_ret_gw': float(sale_ret['gw']),
                'sale_ret_ct': float(sale_ret['ct']),
                'sale_ret_amt': float(sale_ret['amt']),
                # Refinery
                'ref_iss_gw': float(ref_iss['gw']),
                'ref_iss_ct': float(ref_iss['ct']),
                'ref_rec_gw': float(ref_rec['gw']),
                'ref_rec_ct': float(ref_rec['ct']),
                # Inter-retail transfers
                'trn_iss_gw': float(trn_iss['gw']),
                'trn_iss_ct': float(trn_iss['ct']),
                'trn_iss_amt': float(trn_iss['amt']),
                'trn_rec_gw': float(trn_rec['gw']),
                'trn_rec_ct': float(trn_rec['ct']),
                'trn_rec_amt': float(trn_rec['amt']),
                # Closing
                'weighted_avg_rate': float(weighted_avg_rate),
                'closing_gw': float(closing_gw),
                'closing_ct': float(closing_ct),
                'closing_amt': float(closing_value),
            })

        return results

    def get_mfg_adj(self):
        total_mfg_adj = KarigarReceiveItem.objects.all().aggregate(
            total_mfg_adj=Sum(F('wastage') * F('nw') + F('add_gw') - F('less_gw') - F('loss'))
        )["total_mfg_adj"]
        return total_mfg_adj

    def _aggregate_gw_ct(self, queryset, gw_field='gw', ct_field='ct'):
        """Aggregate both gw and ct from a queryset."""
        data = queryset.aggregate(
            total_gw=Coalesce(Sum(gw_field), Decimal('0.00')),
            total_ct=Coalesce(Sum(ct_field), Decimal('0.00')),
        )
        return data['total_gw'], data['total_ct']

    def get_opening_stock(self, item: Item, retail_ids=None):
        result = self._zero()
        retail_ids = self._normalize_retail_ids(retail_ids=retail_ids) if not isinstance(retail_ids, list) else retail_ids
        # BarcodeDetails/UnBarcodedDetails don't carry retail directly — filter via parent.
        barcoded_q = BarcodeDetails.objects.filter(item=item, barcode__op_stk=True)
        unbarcoded_q = UnBarcodedDetails.objects.filter(item=item, main_item__op_stk=True)
        raw_q = OpeningInventory.objects.filter(item=item)
        if retail_ids:
            # Include rows whose retail FK is NULL (legacy/unattributed data) so a
            # retail-filtered report doesn't silently lose stock that was created
            # before the row-level retail field was populated. Matches the pattern
            # in StockReportView (see the "Retail-less rows" comment).
            barcoded_q = barcoded_q.filter(Q(barcode__retail_id__in=retail_ids) | Q(barcode__retail_id__isnull=True))
            unbarcoded_q = unbarcoded_q.filter(Q(main_item__retail_id__in=retail_ids) | Q(main_item__retail_id__isnull=True))
            raw_q = raw_q.filter(Q(retail_id__in=retail_ids) | Q(retail_id__isnull=True))

        for q in [barcoded_q, unbarcoded_q, raw_q]:
            gw, ct = self._aggregate_gw_ct(q)
            result['gw'] += gw
            result['ct'] += ct

        # Value based on primary quantity
        if item.item_type in ['M', 'R']:
            result['amt'] = result['gw'] * item.op_wtd_avg_rate
        elif item.item_type == 'S':
            result['amt'] = result['ct'] * item.op_wtd_avg_rate
        else:
            result['amt'] = result['gw'] * item.op_wtd_avg_rate

        return result

    def get_purchases(self, item, retail_ids=None, from_date=None, to_date=None):
        result = self._zero()

        # Main item purchases (non-finished, non-return). Date lives on the voucher header.
        query = PurchaseVoucherItems.objects.filter(item=item, is_return=False, is_finished=False)
        if retail_ids:
            query = query.filter(Q(retail_id__in=retail_ids) | Q(retail_id__isnull=True))
        if from_date:
            query = query.filter(billno__date1__gte=from_date)
        if to_date:
            query = query.filter(billno__date1__lte=to_date)

        agg = query.aggregate(
            total_gw=Coalesce(Sum('gw'), Decimal('0.00')),
            total_amt=Coalesce(Sum('item_value'), Decimal('0.00')),
        )
        result['gw'] = agg['total_gw']
        result['amt'] = agg['total_amt']

        # Detail sub-item purchases: query directly by sub_item so that S/R items
        # that are only sub-components (never main items) are still captured.
        detail_query = PurchaseVoucherDetails.objects.filter(
            sub_item=item,
        ).filter(
            Q(main_item__isnull=True) |
            Q(main_item__is_finished=False, main_item__is_return=False)
        )
        if retail_ids:
            detail_query = detail_query.filter(Q(retail_id__in=retail_ids) | Q(retail_id__isnull=True))
        if from_date:
            detail_query = detail_query.filter(billno__date1__gte=from_date)
        if to_date:
            detail_query = detail_query.filter(billno__date1__lte=to_date)

        detail_agg = detail_query.aggregate(
            total_ct=Coalesce(Sum('sub_ct'), Decimal('0.00')),
            total_gw=Coalesce(Sum('sub_gw'), Decimal('0.00')),
            total_val=Coalesce(Sum('value'), Decimal('0.00')),
        )
        result['ct'] = detail_agg['total_ct']

        # Stone items exist only as sub-items — gw and amt come entirely from details.
        if item.item_type == 'S':
            result['gw'] = detail_agg['total_gw']
            result['amt'] = detail_agg['total_val']
        # R items may also appear as sub-items; add detail quantities on top of main-item totals.
        elif item.item_type == 'R':
            result['gw'] += detail_agg['total_gw']
            result['amt'] += detail_agg['total_val']

        return result

    def get_purchase_returns(self, item, retail_ids=None, from_date=None, to_date=None):
        result = self._zero()
        query = PurchaseReturnItems.objects.filter(item=item)
        if retail_ids:
            query = query.filter(Q(retail_id__in=retail_ids) | Q(retail_id__isnull=True))
        if from_date:
            query = query.filter(billno__date1__gte=from_date)
        if to_date:
            query = query.filter(billno__date1__lte=to_date)

        agg = query.aggregate(
            total_gw=Coalesce(Sum('gw'), Decimal('0.00')),
            total_amt=Coalesce(Sum(F('gw') * F('making_value'), output_field=DecimalField()), Decimal('0.00')),
        )
        result['gw'] = agg['total_gw']
        result['amt'] = agg['total_amt']

        # ct from details — query directly so stone items (only sub-items) are found.
        if item.item_type == 'S':
            detail_q = PurchaseReturnDetails.objects.filter(sub_item=item)
            if retail_ids:
                detail_q = detail_q.filter(Q(retail_id__in=retail_ids) | Q(retail_id__isnull=True))
            if from_date:
                detail_q = detail_q.filter(billno__date1__gte=from_date)
            if to_date:
                detail_q = detail_q.filter(billno__date1__lte=to_date)
            detail_agg = detail_q.aggregate(
                total_ct=Coalesce(Sum('sub_ct'), Decimal('0.00')),
                total_val=Coalesce(Sum('value'), Decimal('0.00')),
            )
            result['ct'] = detail_agg['total_ct']
            result['amt'] = detail_agg['total_val']

        return result

    def get_sales(self, item, retail_ids=None, from_date=None, to_date=None):
        result = self._zero()

        # Direct sales: raw material item sold as the main line (loose gold, loose diamonds)
        main_q = SalesVouItem.objects.filter(item=item)
        if retail_ids:
            main_q = main_q.filter(Q(retail_id__in=retail_ids) | Q(retail_id__isnull=True))
        if from_date:
            main_q = main_q.filter(billno__date1__gte=from_date)
        if to_date:
            main_q = main_q.filter(billno__date1__lte=to_date)

        main_agg = main_q.aggregate(
            total_gw=Coalesce(Sum('gw'), Decimal('0.00')),
        )
        result['gw'] = main_agg['total_gw']

        # Sub-item sales: raw material sold as a component of a finished good
        detail_q = SalesVouItemDetails.objects.filter(item=item)
        if retail_ids:
            detail_q = detail_q.filter(Q(retail_id__in=retail_ids) | Q(retail_id__isnull=True))
        if from_date:
            detail_q = detail_q.filter(billno__date1__gte=from_date)
        if to_date:
            detail_q = detail_q.filter(billno__date1__lte=to_date)

        detail_agg = detail_q.aggregate(
            total_gw=Coalesce(Sum('gw'), Decimal('0.00')),
            total_ct=Coalesce(Sum('ct'), Decimal('0.00')),
        )

        if item.item_type == 'S':
            result['gw'] = detail_agg['total_gw']
            result['ct'] = detail_agg['total_ct']
        elif item.item_type == 'R':
            result['gw'] += detail_agg['total_gw']

        return result

    def get_sale_returns(self, item, retail_ids=None, from_date=None, to_date=None):
        result = self._zero()

        # Direct returns: raw material item returned as the main line
        main_q = SaleReturnItem.objects.filter(item=item)
        if retail_ids:
            main_q = main_q.filter(Q(retail_id__in=retail_ids) | Q(retail_id__isnull=True))
        if from_date:
            main_q = main_q.filter(billno__date1__gte=from_date)
        if to_date:
            main_q = main_q.filter(billno__date1__lte=to_date)

        main_agg = main_q.aggregate(
            total_gw=Coalesce(Sum('gw'), Decimal('0.00')),
        )
        result['gw'] = main_agg['total_gw']

        # Sub-item returns: raw material returned as a component of a finished good
        detail_q = SaleReturnDetails.objects.filter(item=item)
        if retail_ids:
            detail_q = detail_q.filter(Q(retail_id__in=retail_ids) | Q(retail_id__isnull=True))
        if from_date:
            detail_q = detail_q.filter(main_item__billno__date1__gte=from_date)
        if to_date:
            detail_q = detail_q.filter(main_item__billno__date1__lte=to_date)

        detail_agg = detail_q.aggregate(
            total_gw=Coalesce(Sum('gw'), Decimal('0.00')),
            total_ct=Coalesce(Sum('ct'), Decimal('0.00')),
        )

        if item.item_type == 'S':
            result['gw'] = detail_agg['total_gw']
            result['ct'] = detail_agg['total_ct']
        elif item.item_type == 'R':
            result['gw'] += detail_agg['total_gw']

        return result

    def get_refinery_issues(self, item, retail_ids=None, from_date=None, to_date=None):
        result = self._zero()
        query = RefinaryIssueDetail.objects.filter(item=item)
        if retail_ids:
            query = query.filter(Q(retail_id__in=retail_ids) | Q(retail_id__isnull=True))
        if from_date:
            query = query.filter(billno__date1__gte=from_date)
        if to_date:
            query = query.filter(billno__date1__lte=to_date)

        agg = query.aggregate(
            total_gw=Coalesce(Sum('gw'), Decimal('0.00')),
            total_ct=Coalesce(Sum('ct'), Decimal('0.00')),
        )
        result['gw'] = agg['total_gw']
        result['ct'] = agg['total_ct']
        return result

    def get_refinery_receives(self, item, retail_ids=None, from_date=None, to_date=None):
        result = self._zero()
        query = RefinaryReceiveDetail.objects.filter(item=item)
        if retail_ids:
            query = query.filter(Q(retail_id__in=retail_ids) | Q(retail_id__isnull=True))
        if from_date:
            query = query.filter(billno__date1__gte=from_date)
        if to_date:
            query = query.filter(billno__date1__lte=to_date)

        agg = query.aggregate(
            total_gw=Coalesce(Sum('gw'), Decimal('0.00')),
            total_ct=Coalesce(Sum('ct'), Decimal('0.00')),
        )
        result['gw'] = agg['total_gw']
        result['ct'] = agg['total_ct']
        return result

    # ── Inter-retail transfer movement methods ───────────────────────────────
    # Mirror the refinery issue/receive shape. Only status='received' lines affect
    # valuation — in-transit stock remains attributed to the source (transferring)
    # retail per product requirement.

    def get_transfer_issues(self, item, retail_ids=None, from_date=None, to_date=None):
        """Sum transfer-out lines where the source retail is in scope."""
        result = self._zero()
        query = InterRetailTransferItem.objects.filter(
            item=item,
            voucher__status=InterRetailTransferVoucher.STATUS_RECEIVED,
        )
        if retail_ids:
            query = query.filter(voucher__from_retail_id__in=retail_ids)
        if from_date:
            query = query.filter(voucher__transfer_date__gte=from_date)
        if to_date:
            query = query.filter(voucher__transfer_date__lte=to_date)

        agg = query.aggregate(
            total_gw=Coalesce(Sum('qty_gw'), Decimal('0.00')),
            total_ct=Coalesce(Sum('qty_ct'), Decimal('0.00')),
            total_amt=Coalesce(Sum('transfer_value'), Decimal('0.00')),
        )
        result['gw'] = agg['total_gw']
        result['ct'] = agg['total_ct']
        result['amt'] = agg['total_amt']
        return result

    def get_transfer_receives(self, item, retail_ids=None, from_date=None, to_date=None):
        """Sum transfer-in lines where the destination retail is in scope.

        Value uses the snapshotted source_avg_rate on each line — never recomputed.
        When combined/multi-retail queries include both sides of a transfer, the
        transfer-in and transfer-out cancel (same qty, same value) so consolidated
        totals remain invariant.
        """
        result = self._zero()
        query = InterRetailTransferItem.objects.filter(
            item=item,
            voucher__status=InterRetailTransferVoucher.STATUS_RECEIVED,
        )
        if retail_ids:
            query = query.filter(voucher__to_retail_id__in=retail_ids)
        if from_date:
            query = query.filter(voucher__transfer_date__gte=from_date)
        if to_date:
            query = query.filter(voucher__transfer_date__lte=to_date)

        agg = query.aggregate(
            total_gw=Coalesce(Sum('qty_gw'), Decimal('0.00')),
            total_ct=Coalesce(Sum('qty_ct'), Decimal('0.00')),
            total_amt=Coalesce(Sum('transfer_value'), Decimal('0.00')),
        )
        result['gw'] = agg['total_gw']
        result['ct'] = agg['total_ct']
        result['amt'] = agg['total_amt']
        return result

    def get_weighted_avg_rate(self, item, retail_id, as_of_date):
        """Compute the weighted-average rate for an item in a single retail, as of a given date.

        Used at StockTransferVoucher save time to snapshot source_avg_rate. Mirrors the
        in-flow portion of calculate_closing_stock: opening + purchases − purchase returns
        + transfer receives (all up to and including as_of_date), divided by the matching
        quantity pool. Raises ValueError if the retail has no inbound quantity for the item
        (can't snapshot a rate from nothing).
        """
        if retail_id is None:
            raise ValueError("retail_id is required for get_weighted_avg_rate")

        retail_ids = [retail_id]
        opening = self.get_opening_stock(item, retail_ids)
        purchase = self.get_purchases(item, retail_ids, None, as_of_date)
        purc_ret = self.get_purchase_returns(item, retail_ids, None, as_of_date)
        trn_rec = self.get_transfer_receives(item, retail_ids, None, as_of_date)

        if item.item_type in ['M', 'R']:
            pq = 'gw'
        elif item.item_type == 'S':
            pq = 'ct'
        else:
            pq = 'gw'

        total_in_qty = opening[pq] + purchase[pq] - purc_ret[pq] + trn_rec[pq]
        total_in_value = opening['amt'] + purchase['amt'] - purc_ret['amt'] + trn_rec['amt']

        if total_in_qty <= 0:
            raise ValueError(
                f"Cannot compute weighted average for item {item.item_name} at retail "
                f"{retail_id} as of {as_of_date}: no inbound stock found."
            )
        return total_in_value / total_in_qty


class DesignMainViewSet(RetailBaseViewset):
    queryset = DesignMain.objects.all()
    serializer_class = DesignMainSerializer
    filter_backends = [SearchFilter]
    search_fields = ['design_no', 'variation_suffix', 'item__item_name', 'item_desc']

    def get_queryset(self):
        from django.db.models import Count, Q, Prefetch
        # Designs are company-global — NOT scoped to the current branch.
        return (
            DesignMain.objects
            .select_related('item')
            .prefetch_related(
                Prefetch('images', queryset=DesignImage.objects.order_by('sort_order', 'id')),
                Prefetch(
                    'designdetails_set',
                    queryset=DesignDetails.objects.select_related('sub_item', 'metal_purity', 'packet'),
                ),
            )
            .annotate(
                in_stock_count_ann=Count('barcodes', filter=Q(barcodes__stk_status=True), distinct=True),
                total_barcodes_ann=Count('barcodes', distinct=True),
            )
            .order_by("design_no", "id")
        )

    def get_serializer_class(self):
        if self.action == 'list':
            from inventory.serializer import DesignMainListSerializer
            return DesignMainListSerializer
        return DesignMainSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

class StockValuationReport(ListAPIView):
    queryset = BarcodeDetails.objects.all()
    serializer_class = BarCodeDetailSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = StockValuationReportFilter

from rest_framework import serializers, viewsets
from django.contrib.contenttypes.models import ContentType
from .models import CVDTest
from django_filters import rest_framework as filters
from datetime import datetime, timedelta

class CVDTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CVDTest
        fields = '__all__'

class CVDTestViewSet(ListCreateAPIView):
    queryset = CVDTest.objects.all()
    serializer_class = CVDTestSerializer
    permission_classes = [IsAuthenticated]

class IDGenerationReportFilter(filters.FilterSet):
    start_date = filters.DateFilter(field_name='barcode__created_date', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='barcode__created_date', lookup_expr='lte')
    item_type = filters.CharFilter(field_name='item__item_type')
    purity = filters.CharFilter(field_name='barcode__purity')
    min_weight = filters.NumberFilter(field_name='gw', lookup_expr='gte')
    max_weight = filters.NumberFilter(field_name='gw', lookup_expr='lte')
    
    class Meta:
        model = BarcodeDetails
        fields = ['barcode', 'item', 'packet', 'pcs', 'ct', 'gw', 'rate', 'amt']

    def filter_queryset(self, queryset):
        # Default date range if not specified (last 30 days)
        if not self.form.cleaned_data.get('start_date'):
            self.form.cleaned_data['start_date'] = datetime.now() - timedelta(days=30)
        if not self.form.cleaned_data.get('end_date'):
            self.form.cleaned_data['end_date'] = datetime.now()
            
        return super().filter_queryset(queryset)

class BarcodeSplitMergeView(ListAPIView):
    serializer_class = BarcodeSplitMergeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'transaction_type': ['exact'],
        'date1': ['range', 'gte', 'lte']
    }

    def get_queryset(self):
        return BarcodeSplitMerge.objects.filter(retail=self.request.retail)    

class IDGenerationReport(ListAPIView):
    serializer_class = BarCodeMainSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = IDGenerationReportFilter
    
    def get_queryset(self):
        return BarcodeMain.objects.filter(retail=self.request.retail)
    
class StockJournalViewSet(RetailBaseViewset):
    serializer_class = StockJournalSerializer
    queryset = StockJournal.objects.all()
    filter_backends=[DjangoFilterBackend,OrderingFilter,SearchFilter]
    search_fields=['billno']

    @transaction.atomic
    def perform_create(self, serializer):
        super().perform_create(serializer)

    @transaction.atomic
    def perform_update(self, serializer):
        super().perform_update(serializer)

    @transaction.atomic
    def perform_destroy(self, instance):
        from accounting.utils import release_last_bill_number
        retail = instance.retail
        fiscal_year = instance.fiscal_year
        billno = instance.billno
        super().perform_destroy(instance)
        release_last_bill_number(retail, 'SJ', billno, fiscal_year)

class BarcodeTransactionView(RetailBaseViewset):
    serializer_class = BarcodeTransactionSerializer
    queryset = BarcodeTransaction.objects.select_related('barcode__item').order_by('-date')
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['trans_type']
    search_fields = ['barcode__barcode', 'billno', 'barcode__item__item_name']
    ordering_fields = ['date', 'trans_type']

    def get_queryset(self):
        # Barcode history is a global audit trail: a barcode can move between
        # retails (transfers), so its full life must NOT be retail-scoped.
        return BarcodeTransaction.objects.select_related('barcode__item').order_by('-date')


class BarcodeCreationReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')

        if not from_date or not to_date:
            return Response({"error": "from_date and to_date are required"}, status=status.HTTP_400_BAD_REQUEST)

        def _ids(key):
            raw = request.query_params.get(key)
            if not raw:
                return None
            return [v for v in raw.split(',') if v.strip()]

        artisan_ids = _ids('artisan_ids')
        item_ids    = _ids('item_ids')
        purity_ids  = _ids('purity_ids')
        user_ids    = _ids('user_ids')

        stone_prefetch= Prefetch('barcodedetails_set',queryset=BarcodeDetails.objects.filter(
            barcode__created_date__range=[from_date, to_date],
            item__item_type='S'
        ),to_attr='stone_details')
        other_prefetch=Prefetch('barcodedetails_set',queryset=BarcodeDetails.objects.filter(
            barcode__created_date__range=[from_date, to_date],).exclude(
            item__item_type='S',
        ), to_attr='other_details'
        )

        qs = BarcodeMain.objects.filter(
            created_date__range=[from_date, to_date]
        )
        if artisan_ids:
            qs = qs.filter(kr_code_id__in=artisan_ids)
        if item_ids:
            qs = qs.filter(item_id__in=item_ids)
        if purity_ids:
            qs = qs.filter(purity_id__in=purity_ids)
        if user_ids:
            qs = qs.filter(created_by__in=user_ids)

        qs = qs.prefetch_related(stone_prefetch, other_prefetch).order_by('-created_date', '-id')
        serializer=BarcodeCreationReportSerializer(qs,many=True)


        return Response(serializer.data, status=status.HTTP_200_OK)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stock_journal_billno_view(request):
    try:
        bill_no = peek_next_bill_number(request.retail, 'SJ')
        return Response({"bill_no": bill_no}, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Stock Transfer ─────────────────────────────────────────────────────────────

class StockTransferViewset(RetailBaseViewset):
    from inventory.models import StockTransfer as _StockTransfer
    queryset = _StockTransfer.objects.all()
    serializer_class = StockTransferSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['billno']
    ordering = ['-date1', '-id']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    def get_queryset(self):
        from inventory.models import StockTransfer
        retail = getattr(self.request, 'retail', None)
        qs = StockTransfer.objects.filter(
            Q(retail=retail) | Q(to_rt_code=retail)
        ).select_related('retail', 'to_rt_code').order_by('-date1', '-billno')
        # FY-scope the list (custom Q above precludes routing through super(),
        # which would drop inbound `to_rt_code` transfers). Detail/edit unaffected.
        if (
            getattr(self, 'action', None) == 'list'
            and getattr(retail, 'active_fy_id', None)
            and self.request.query_params.get('all_fy', '').lower() not in ('1', 'true')
        ):
            qs = qs.filter(fiscal_year_id=retail.active_fy_id)
        return qs

    def perform_update(self, serializer):
        if serializer.instance.sent_status:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                f"Stock transfer '{serializer.instance.billno}' cannot be edited because it has already been dispatched."
            )
        super().perform_update(serializer)

    def destroy(self, request, *args, **kwargs):
        transfer = self.get_object()
        if transfer.rec_status:
            return Response(
                {'detail': 'Cannot delete a received transfer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from accounting.utils import release_last_bill_number
        retail = transfer.retail
        fiscal_year = transfer.fiscal_year
        billno = transfer.billno
        with transaction.atomic():
            barcode_ids = list(transfer.stocktransfermain_set.values_list('barcode_id', flat=True))
            if transfer.sent_status:
                # Restore barcodes to sender's inventory
                BarcodeMain.objects.filter(id__in=barcode_ids).update(stk_status=True)
            # Clean up barcode transaction audit records
            BarcodeTransaction.objects.filter(billno=transfer.billno).delete()
        response = super().destroy(request, *args, **kwargs)
        release_last_bill_number(retail, 'RST', billno, fiscal_year)
        return response

    @action(detail=True, methods=['post'], url_path='mark-sent')
    def mark_sent(self, request, pk=None):
        transfer = self.get_object()
        if transfer.retail != request.retail:
            return Response({'detail': 'Only the sending retail can mark a transfer as sent.'}, status=status.HTTP_403_FORBIDDEN)
        if transfer.sent_status:
            return Response({'detail': 'Transfer already marked as sent.'}, status=status.HTTP_400_BAD_REQUEST)
        if transfer.rec_status:
            return Response({'detail': 'Transfer is already received.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            transfer.sent_status = True
            transfer.save(update_fields=['sent_status'])
            barcode_ids = list(transfer.stocktransfermain_set.values_list('barcode_id', flat=True))
            BarcodeMain.objects.filter(id__in=barcode_ids).update(stk_status=False)
        return Response({'detail': 'Transfer marked as sent. Barcodes are now in transit.'})

    @action(detail=True, methods=['post'], url_path='mark-received')
    def mark_received(self, request, pk=None):
        transfer = self.get_object()
        if transfer.to_rt_code != request.retail:
            return Response({'detail': 'Only the receiving retail can mark a transfer as received.'}, status=status.HTTP_403_FORBIDDEN)
        if not transfer.sent_status:
            return Response({'detail': 'Transfer has not been marked as sent yet.'}, status=status.HTTP_400_BAD_REQUEST)
        if transfer.rec_status:
            return Response({'detail': 'Transfer already received.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            barcode_ids = list(transfer.stocktransfermain_set.values_list('barcode_id', flat=True))
            BarcodeMain.objects.filter(id__in=barcode_ids).update(retail=transfer.to_rt_code, stk_status=True)
            transfer.rec_status = True
            transfer.save(update_fields=['rec_status'])
            transfer.stocktransfermain_set.update(rec_status=True)
        return Response({'detail': 'Transfer received. Barcodes added to your inventory.'})

    @action(detail=False, methods=['get'], url_path='in-transit-barcodes')
    def in_transit_barcodes(self, request):
        from inventory.models import StockTransfer, StockTransferMain
        retail = request.retail
        in_transit_transfers = StockTransfer.objects.filter(
            sent_status=True, rec_status=False
        ).filter(Q(retail=retail) | Q(to_rt_code=retail))
        items = StockTransferMain.objects.filter(billno__in=in_transit_transfers).select_related(
            'barcode', 'barcode__item', 'barcode__purity',
            'billno', 'billno__retail', 'billno__to_rt_code',
        )
        data = []
        for item in items:
            bc, trf = item.barcode, item.billno
            data.append({
                'barcode':          bc.barcode,
                'item_code':        bc.item.short_code  if bc.item   else None,
                'item_name':        bc.item.item_name   if bc.item   else None,
                'purity':           bc.purity.purity    if bc.purity else None,
                'gw':               float(bc.gw)  if bc.gw  else None,
                'nw':               float(bc.nw)  if bc.nw  else None,
                'pcs':              bc.pcs,
                'from_retail_name': trf.retail.retail_name     if trf.retail     else None,
                'from_retail_code': trf.retail.retail_code     if trf.retail     else None,
                'to_retail_name':   trf.to_rt_code.retail_name if trf.to_rt_code else None,
                'to_retail_code':   trf.to_rt_code.retail_code if trf.to_rt_code else None,
                'transfer_billno':  trf.billno,
                'transfer_date':    trf.date1,
                'transfer_id':      trf.id,
            })
        return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stock_transfer_billno_view(request):
    try:
        from accounting.utils import peek_next_bill_number
        bill_no = peek_next_bill_number(request.retail, 'RST')
        return Response({"bill_no": bill_no}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Barcode Images ─────────────────────────────────────────────────────────────

class BarcodeImageListCreate(ListCreateAPIView):
    from rest_framework.parsers import MultiPartParser
    parser_classes = [MultiPartParser]

    def get_serializer_class(self):
        from inventory.serializer import BarcodeImageSerializer
        return BarcodeImageSerializer

    def get_queryset(self):
        barcode_id = self.request.query_params.get('barcode')
        if barcode_id:
            return BarcodeImage.objects.select_related('barcode').filter(barcode_id=barcode_id).order_by('sort_order', 'id')
        return BarcodeImage.objects.none()

    def create(self, request, *args, **kwargs):
        from inventory.serializer import BarcodeImageSerializer
        files = request.FILES.getlist('image')
        barcode_id = request.data.get('barcode')
        if not barcode_id:
            return Response({"error": "barcode is required"}, status=status.HTTP_400_BAD_REQUEST)
        # New images append to the end of the existing order. The cover is the
        # image at position 0 (lowest sort_order); the first image ever added to
        # a barcode becomes the cover.
        from django.db.models import Max
        existing = BarcodeImage.objects.filter(barcode_id=barcode_id)
        has_primary = existing.filter(is_primary=True).exists()
        next_order = (existing.aggregate(m=Max('sort_order'))['m'] or -1) + 1
        results = []
        for f in files:
            serializer = BarcodeImageSerializer(data={'barcode': barcode_id, 'image': f})
            serializer.is_valid(raise_exception=True)
            make_primary = not has_primary
            serializer.save(is_primary=make_primary, sort_order=next_order)
            if make_primary:
                has_primary = True
            next_order += 1
            results.append(serializer.data)
        return Response(results, status=status.HTTP_201_CREATED)


class BarcodeImageDelete(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            img = BarcodeImage.objects.get(pk=pk)
            was_primary = img.is_primary
            barcode_id = img.barcode_id
            img.image.delete(save=False)
            img.delete()
            # If the cover image was deleted, promote the first remaining image
            # (lowest sort_order) so the barcode always keeps a cover.
            if was_primary:
                nxt = BarcodeImage.objects.filter(barcode_id=barcode_id).order_by('sort_order', 'id').first()
                if nxt:
                    nxt.is_primary = True
                    nxt.save(update_fields=['is_primary'])
            return Response(status=status.HTTP_204_NO_CONTENT)
        except BarcodeImage.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, pk):
        """Make this image the cover by moving it to the front of the order."""
        try:
            img = BarcodeImage.objects.get(pk=pk)
        except BarcodeImage.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        if request.data.get('is_primary'):
            from django.db.models import Min
            siblings = BarcodeImage.objects.filter(barcode_id=img.barcode_id)
            min_order = siblings.aggregate(m=Min('sort_order'))['m'] or 0
            siblings.exclude(pk=pk).update(is_primary=False)
            img.is_primary = True
            img.sort_order = min_order - 1   # in front of the current first
            img.save(update_fields=['is_primary', 'sort_order'])
        from inventory.serializer import BarcodeImageSerializer
        return Response(BarcodeImageSerializer(img).data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def barcode_image_reorder(request):
    """Persist a new photo order. Body: {"barcode": <id>, "order": [id, id, ...]}.
    sort_order follows the list; the first image becomes the cover (is_primary)."""
    barcode_id = request.data.get('barcode')
    order = request.data.get('order') or []
    if not barcode_id or not isinstance(order, list):
        return Response({"error": "barcode and order[] are required"}, status=status.HTTP_400_BAD_REQUEST)
    imgs = {img.id: img for img in BarcodeImage.objects.filter(barcode_id=barcode_id)}
    for index, img_id in enumerate(order):
        img = imgs.get(int(img_id))
        if not img:
            continue
        img.sort_order = index
        img.is_primary = (index == 0)
        img.save(update_fields=['sort_order', 'is_primary'])
    from inventory.serializer import BarcodeImageSerializer
    refreshed = BarcodeImage.objects.filter(barcode_id=barcode_id).order_by('sort_order', 'id')
    return Response(BarcodeImageSerializer(refreshed, many=True).data, status=status.HTTP_200_OK)


# ── Design Images (catalog photos) ─────────────────────────────────────────────
# Mirror of the Barcode-image endpoints; same dynamic storage root, served by the
# shared serve_barcode_image_file view (design files live under design_images/).

class DesignImageListCreate(ListCreateAPIView):
    from rest_framework.parsers import MultiPartParser
    parser_classes = [MultiPartParser]

    def get_serializer_class(self):
        from inventory.serializer import DesignImageSerializer
        return DesignImageSerializer

    def get_queryset(self):
        design_id = self.request.query_params.get('design')
        if design_id:
            return DesignImage.objects.select_related('design').filter(design_id=design_id).order_by('sort_order', 'id')
        return DesignImage.objects.none()

    def create(self, request, *args, **kwargs):
        from inventory.serializer import DesignImageSerializer
        from django.db.models import Max
        files = request.FILES.getlist('image')
        design_id = request.data.get('design')
        if not design_id:
            return Response({"error": "design is required"}, status=status.HTTP_400_BAD_REQUEST)
        existing = DesignImage.objects.filter(design_id=design_id)
        has_primary = existing.filter(is_primary=True).exists()
        next_order = (existing.aggregate(m=Max('sort_order'))['m'] or -1) + 1
        results = []
        for f in files:
            serializer = DesignImageSerializer(data={'design': design_id, 'image': f})
            serializer.is_valid(raise_exception=True)
            make_primary = not has_primary
            serializer.save(is_primary=make_primary, sort_order=next_order)
            if make_primary:
                has_primary = True
            next_order += 1
            results.append(serializer.data)
        return Response(results, status=status.HTTP_201_CREATED)


class DesignImageDelete(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            img = DesignImage.objects.get(pk=pk)
            was_primary = img.is_primary
            design_id = img.design_id
            img.image.delete(save=False)
            img.delete()
            if was_primary:
                nxt = DesignImage.objects.filter(design_id=design_id).order_by('sort_order', 'id').first()
                if nxt:
                    nxt.is_primary = True
                    nxt.save(update_fields=['is_primary'])
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DesignImage.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, pk):
        """Make this image the cover by moving it to the front of the order."""
        try:
            img = DesignImage.objects.get(pk=pk)
        except DesignImage.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        if request.data.get('is_primary'):
            from django.db.models import Min
            siblings = DesignImage.objects.filter(design_id=img.design_id)
            min_order = siblings.aggregate(m=Min('sort_order'))['m'] or 0
            siblings.exclude(pk=pk).update(is_primary=False)
            img.is_primary = True
            img.sort_order = min_order - 1
            img.save(update_fields=['is_primary', 'sort_order'])
        from inventory.serializer import DesignImageSerializer
        return Response(DesignImageSerializer(img).data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def design_image_reorder(request):
    """Persist a new photo order. Body: {"design": <id>, "order": [id, id, ...]}.
    sort_order follows the list; the first image becomes the cover (is_primary)."""
    design_id = request.data.get('design')
    order = request.data.get('order') or []
    if not design_id or not isinstance(order, list):
        return Response({"error": "design and order[] are required"}, status=status.HTTP_400_BAD_REQUEST)
    imgs = {img.id: img for img in DesignImage.objects.filter(design_id=design_id)}
    for index, img_id in enumerate(order):
        img = imgs.get(int(img_id))
        if not img:
            continue
        img.sort_order = index
        img.is_primary = (index == 0)
        img.save(update_fields=['sort_order', 'is_primary'])
    from inventory.serializer import DesignImageSerializer
    refreshed = DesignImage.objects.filter(design_id=design_id).order_by('sort_order', 'id')
    return Response(DesignImageSerializer(refreshed, many=True).data, status=status.HTTP_200_OK)


# ── Catalog (design-driven, priced) ─────────────────────────────────────────────

def _base_design_qs(retail=None):
    # Designs are company-global; `retail` is ignored (kept for call-site
    # compatibility). The catalog shows every design regardless of branch.
    return (
        DesignMain.objects.all()
        .select_related("item")
        .prefetch_related(
            "designdetails_set__sub_item", "designdetails_set__metal_purity",
            "images", "barcodes",
        )
    )


def _apply_catalog_filters(qs, g):
    """Apply catalog filters. `g` is a value getter: request.GET.get or dict.get."""
    from django.db.models import Q
    search = g("search")
    if search:
        qs = qs.filter(Q(design_no__icontains=search) | Q(item_desc__icontains=search))
    item = g("item")
    if item:
        qs = qs.filter(item__short_code=item)
    purity = g("purity")
    if purity:
        qs = qs.filter(designdetails__metal_purity_id=purity).distinct()
    minw = g("min_weight")
    if minw:
        qs = qs.filter(nw__gte=minw)
    maxw = g("max_weight")
    if maxw:
        qs = qs.filter(nw__lte=maxw)
    if str(g("in_stock") or "") in ("1", "true", "True"):
        qs = qs.filter(barcodes__stk_status=True).distinct()
    return qs


def _resolve_pricelists(tier, pricelist_id):
    b2b_pl = retail_pl = None
    if pricelist_id:
        if tier == "b2b":
            from mastersconfig.models import B2BPricelist
            b2b_pl = B2BPricelist.objects.filter(pk=pricelist_id).first()
        else:
            from mastersconfig.models import RetailDiscountPricelist
            retail_pl = RetailDiscountPricelist.objects.filter(pk=pricelist_id).first()
    return b2b_pl, retail_pl


def _resolve_catalog(request):
    """Build the (retail-scoped, filtered) design queryset and resolve the pricing
    tier / pricelist from query params. Shared by catalog_list and catalog_pdf.
    Returns (queryset, b2b_pricelist, retail_pricelist, tier)."""
    retail = getattr(request, "retail", None)
    qs = _apply_catalog_filters(_base_design_qs(retail), request.GET.get)

    tier = request.GET.get("tier", "retail")
    b2b_pl = retail_pl = None
    ledger_id = request.GET.get("ledger")
    if ledger_id:
        from contacts.models import Ledger
        ldg = Ledger.objects.filter(pk=ledger_id).first()
        if ldg:
            if tier == "b2b":
                b2b_pl = ldg.b2b_pricelist
            else:
                retail_pl = ldg.retail_discount_pricelist
    b2b_pl2, retail_pl2 = _resolve_pricelists(tier, request.GET.get("pricelist"))
    return qs, (b2b_pl2 or b2b_pl), (retail_pl2 or retail_pl), tier


def _tier_label(b2b_pl, retail_pl):
    if b2b_pl:
        return f"B2B: {b2b_pl.name}"
    if retail_pl:
        return f"Retail: {retail_pl.name}"
    return "Retail (list)"


def _price_bounds(get):
    def f(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    return f(get("min_price")), f(get("max_price"))


def _in_price(total, lo, hi):
    return (lo is None or total >= lo) and (hi is None or total <= hi)


def _catalog_row(d, b2b_pl, retail_pl):
    from inventory.catalog_pricing import compute_design_price
    price = compute_design_price(d, b2b_pricelist=b2b_pl, retail_pricelist=retail_pl)
    cover = next((im for im in d.images.all() if im.is_primary), None) or next(iter(d.images.all()), None)
    barcodes = list(d.barcodes.all())
    return {
        "id": d.id,
        "design_no": d.design_no,
        "variation_suffix": d.variation_suffix,
        "item": d.item.short_code if d.item else None,
        "item_name": d.item.item_name if d.item else None,
        "item_desc": d.item_desc,
        "pcs": d.pcs,
        "gw": float(d.gw or 0),
        "nw": float(d.nw or 0),
        "making_type": d.making_type,
        "cover_image": cover.image.url if cover else None,
        "in_stock_count": sum(1 for b in barcodes if b.stk_status),
        "total_barcodes": len(barcodes),
        "price": price,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def catalog_list(request):
    """Priced catalog of designs. Filters: search, item, purity, min_weight,
    max_weight, in_stock=1, min_price, max_price. Pricing: tier=retail|b2b +
    ledger=<id> or pricelist=<id>."""
    from jewel_test.pagination_custom import CustomPagination

    qs, b2b_pl, retail_pl, tier = _resolve_catalog(request)
    qs = qs.order_by("design_no", "id")
    paginator = CustomPagination()

    # Price is computed live (not a DB column). When a price filter is supplied we
    # must price the whole filtered set, filter, then paginate the resulting list.
    def _f(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    min_price = _f(request.GET.get("min_price"))
    max_price = _f(request.GET.get("max_price"))

    if min_price is not None or max_price is not None:
        rows = [_catalog_row(d, b2b_pl, retail_pl) for d in qs]
        rows = [
            r for r in rows
            if (min_price is None or r["price"]["total_price"] >= min_price)
            and (max_price is None or r["price"]["total_price"] <= max_price)
        ]
        page = paginator.paginate_queryset(rows, request)
        return paginator.get_paginated_response(page)

    page = paginator.paginate_queryset(qs, request)
    data = [_catalog_row(d, b2b_pl, retail_pl) for d in page]
    return paginator.get_paginated_response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def catalog_detail(request, pk):
    """One design, priced — specs, images, component details and available barcodes.
    Accepts the same tier / pricelist query params as catalog_list."""
    from inventory.catalog_pricing import compute_design_price
    try:
        d = (
            DesignMain.objects.select_related("item")
            .prefetch_related(
                "designdetails_set__sub_item", "designdetails_set__metal_purity",
                "images", "barcodes",
            )
            .get(pk=pk)
        )
    except DesignMain.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    tier = request.GET.get("tier", "retail")
    b2b_pl = retail_pl = None
    pricelist_id = request.GET.get("pricelist")
    if pricelist_id:
        if tier == "b2b":
            from mastersconfig.models import B2BPricelist
            b2b_pl = B2BPricelist.objects.filter(pk=pricelist_id).first()
        else:
            from mastersconfig.models import RetailDiscountPricelist
            retail_pl = RetailDiscountPricelist.objects.filter(pk=pricelist_id).first()

    price = compute_design_price(d, b2b_pricelist=b2b_pl, retail_pricelist=retail_pl)
    barcodes = list(d.barcodes.all())
    return Response({
        "id": d.id,
        "design_no": d.design_no,
        "variation_suffix": d.variation_suffix,
        "item": d.item.short_code if d.item else None,
        "item_name": d.item.item_name if d.item else None,
        "item_desc": d.item_desc,
        "pcs": d.pcs,
        "gw": float(d.gw or 0),
        "nw": float(d.nw or 0),
        "making_type": d.making_type,
        "images": [
            {"id": im.id, "image": im.image.url, "is_primary": im.is_primary}
            for im in d.images.all()
        ],
        "details": [
            {
                "sub_item": x.sub_item.item_name,
                "purity": x.metal_purity.purity if x.metal_purity else None,
                "pcs": x.pcs, "ct": float(x.ct or 0), "rate": x.rate, "amt": x.amt,
            }
            for x in d.designdetails_set.all()
        ],
        "barcodes": [
            {"barcode": b.barcode, "in_stock": b.stk_status, "gw": float(b.gw or 0), "nw": float(b.nw or 0)}
            for b in barcodes
        ],
        "in_stock_count": sum(1 for b in barcodes if b.stk_status),
        "total_barcodes": len(barcodes),
        "price": price,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def catalog_pdf(request):
    """Generate a catalog PDF. ?format=summary|detailed|quotation, plus the same
    filters / tier params as catalog_list. Capped at 300 designs."""
    from django.http import HttpResponse
    from django.utils import timezone
    from inventory.catalog_pricing import compute_design_price
    from inventory.catalog_pdf import build_catalog_pdf

    # NB: the layout param is `fmt`, NOT `format` — DRF reserves `format` for
    # renderer selection and 404s on an unknown value.
    fmt = request.GET.get("fmt", "summary")
    if fmt not in ("summary", "detailed", "quotation"):
        fmt = "summary"

    qs, b2b_pl, retail_pl, tier = _resolve_catalog(request)
    designs = list(qs.order_by("design_no", "id")[:300])

    rows = []
    for d in designs:
        price = compute_design_price(d, b2b_pricelist=b2b_pl, retail_pricelist=retail_pl)
        cover = next((im for im in d.images.all() if im.is_primary), None) or next(iter(d.images.all()), None)
        img_path = None
        if cover:
            try:
                img_path = cover.image.path
            except Exception:
                img_path = None
        rows.append({
            "design_no": d.design_no + (f"-{d.variation_suffix}" if d.variation_suffix else ""),
            "item_name": d.item.item_name if d.item else "",
            "gw": float(d.gw or 0), "nw": float(d.nw or 0),
            "in_stock_count": sum(1 for b in d.barcodes.all() if b.stk_status),
            "image_path": img_path,
            "price": price,
        })

    meta = {
        "title": "Quotation" if fmt == "quotation" else "Catalog",
        "tier_label": _tier_label(b2b_pl, retail_pl),
        "date": timezone.localtime().strftime("%d %b %Y"),
        "count": len(rows),
    }
    pdf = build_catalog_pdf(fmt, rows, meta)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="catalog_{fmt}.pdf"'
    return resp


# ── Catalog share links ─────────────────────────────────────────────────────────

class CatalogShareListCreate(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from inventory.serializer import CatalogShareSerializer
        retail = getattr(request, "retail", None)
        qs = CatalogShare.objects.filter(retail=retail)
        return Response(CatalogShareSerializer(qs, many=True).data)

    def post(self, request):
        from inventory.serializer import CatalogShareSerializer
        retail = getattr(request, "retail", None)
        s = CatalogShareSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save(retail=retail, created_by=request.user if request.user.is_authenticated else None)
        return Response(s.data, status=status.HTTP_201_CREATED)


class CatalogShareDelete(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        retail = getattr(request, "retail", None)
        CatalogShare.objects.filter(pk=pk, retail=retail).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request, pk):
        from inventory.serializer import CatalogShareSerializer
        retail = getattr(request, "retail", None)
        sh = CatalogShare.objects.filter(pk=pk, retail=retail).first()
        if not sh:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if "is_active" in request.data:
            sh.is_active = bool(request.data["is_active"])
            sh.save(update_fields=["is_active"])
        return Response(CatalogShareSerializer(sh).data)


def _get_active_share(token):
    from django.utils import timezone
    sh = CatalogShare.objects.filter(token=token, is_active=True).first()
    if not sh:
        return None
    if sh.expires_at and sh.expires_at < timezone.now():
        return None
    return sh


@api_view(['GET'])
@permission_classes([AllowAny])
def public_catalog(request, token):
    """Public, tokenised catalog grid. Shows sale price only (no cost breakdown)."""
    from inventory.catalog_pricing import compute_design_price
    from jewel_test.pagination_custom import CustomPagination

    sh = _get_active_share(token)
    if not sh:
        return Response({"error": "This catalog link is no longer available."},
                        status=status.HTTP_404_NOT_FOUND)

    sh_filters = sh.filters or {}
    qs = _apply_catalog_filters(_base_design_qs(sh.retail), sh_filters.get)
    b2b_pl, retail_pl = _resolve_pricelists(sh.tier, sh.pricelist_id)
    lo, hi = _price_bounds(sh_filters.get)

    # Price the whole set, honour the share's price band, then paginate the list.
    rows = []
    for d in qs.order_by("design_no", "id"):
        price = compute_design_price(d, b2b_pricelist=b2b_pl, retail_pricelist=retail_pl)
        if not _in_price(price.get("total_price"), lo, hi):
            continue
        cover = next((im for im in d.images.all() if im.is_primary), None) or next(iter(d.images.all()), None)
        rows.append({
            "id": d.id,
            "design_no": d.design_no,
            "item_name": d.item.item_name if d.item else None,
            "nw": float(d.nw or 0),
            "gold_purity": price.get("gold_purity"),
            "cover_image": cover.image.url if cover else None,
            "in_stock_count": sum(1 for b in d.barcodes.all() if b.stk_status),
            "price": price.get("total_price"),   # sale price only
        })
    paginator = CustomPagination()
    page = paginator.paginate_queryset(rows, request)
    resp = paginator.get_paginated_response(page)
    resp.data["catalog_label"] = sh.label or "Catalog"
    return resp


@api_view(['GET'])
@permission_classes([AllowAny])
def public_catalog_pdf(request, token):
    """Public PDF for a shared catalog link."""
    from django.http import HttpResponse
    from django.utils import timezone
    from inventory.catalog_pricing import compute_design_price
    from inventory.catalog_pdf import build_catalog_pdf

    sh = _get_active_share(token)
    if not sh:
        return Response({"error": "This catalog link is no longer available."},
                        status=status.HTTP_404_NOT_FOUND)

    fmt = request.GET.get("fmt", "summary")
    if fmt not in ("summary", "detailed", "quotation"):
        fmt = "summary"
    sh_filters = sh.filters or {}
    qs = _apply_catalog_filters(_base_design_qs(sh.retail), sh_filters.get)
    b2b_pl, retail_pl = _resolve_pricelists(sh.tier, sh.pricelist_id)
    lo, hi = _price_bounds(sh_filters.get)

    rows = []
    for d in qs.order_by("design_no", "id"):
        price = compute_design_price(d, b2b_pricelist=b2b_pl, retail_pricelist=retail_pl)
        if not _in_price(price.get("total_price"), lo, hi):
            continue
        cover = next((im for im in d.images.all() if im.is_primary), None) or next(iter(d.images.all()), None)
        ip = None
        if cover:
            try:
                ip = cover.image.path
            except Exception:
                ip = None
        rows.append({
            "design_no": d.design_no, "item_name": d.item.item_name if d.item else "",
            "gw": float(d.gw or 0), "nw": float(d.nw or 0),
            "in_stock_count": 0, "image_path": ip, "price": price,
        })
        if len(rows) >= 300:
            break
    meta = {"title": sh.label or "Catalog", "tier_label": "",
            "date": timezone.localtime().strftime("%d %b %Y"), "count": len(rows)}
    pdf = build_catalog_pdf(fmt, rows, meta)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = 'inline; filename="catalog.pdf"'
    return resp


@api_view(['GET'])
@permission_classes([AllowAny])
def serve_barcode_image_file(request, name):
    """Stream a barcode/design image from the configured storage root."""
    import os, mimetypes
    from urllib.parse import unquote
    from django.http import FileResponse
    from mastersconfig.storage import _barcode_image_root

    decoded = unquote(name)
    abs_root = os.path.abspath(_barcode_image_root())
    full_path = os.path.normpath(os.path.join(abs_root, decoded))

    # Path-traversal guard: resolved path must stay within the storage root
    if not full_path.startswith(abs_root + os.sep) and full_path != abs_root:
        return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    if not os.path.isfile(full_path):
        return Response({"error": "File not found"}, status=status.HTTP_404_NOT_FOUND)

    content_type, _ = mimetypes.guess_type(full_path)
    return FileResponse(open(full_path, 'rb'), content_type=content_type or 'application/octet-stream')


# ── Raw Material Inventory ─────────────────────────────────────────────────────

class RawMaterialInventoryViewSet(RetailBaseViewset):
    from inventory.serializer import RawMaterialInventorySerializer
    serializer_class = RawMaterialInventorySerializer
    queryset = RawMaterialInventory.objects.select_related('item', 'packet', 'purity').all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['item', 'packet', 'purity']
    search_fields = ['item__item_name', 'item__short_code']
    ordering_fields = ['item__item_name', 'gw', 'ct', 'pcs']


class RawMaterialTransactionListView(RetailBaseViewset):
    from inventory.serializer import RawMaterialTransactionSerializer
    serializer_class = RawMaterialTransactionSerializer
    queryset = RawMaterialTransaction.objects.select_related('item', 'packet', 'purity').order_by('-date')
    http_method_names = ['get']
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['item', 'packet', 'trans_type']
    search_fields = ['item__item_name', 'item__short_code', 'billno']
    ordering_fields = ['date', 'item__item_name']

    def get_queryset(self):
        qs = super().get_queryset()
        from_date = self.request.query_params.get('from_date')
        to_date = self.request.query_params.get('to_date')
        if from_date:
            qs = qs.filter(date__date__gte=from_date)
        if to_date:
            qs = qs.filter(date__date__lte=to_date)
        return qs


class RawMaterialBalanceReportView(APIView):
    """Current raw material stock balance grouped by item."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Sum, CharField, Value
        from django.db.models.functions import Coalesce

        qs = RawMaterialInventory.objects.select_related('item', 'packet', 'purity').filter(
            retail=request.retail,
        ).exclude(item__item_type='M')

        item_id = request.query_params.get('item')
        item_type = request.query_params.get('item_type')
        if item_id:
            qs = qs.filter(item_id=item_id)
        if item_type:
            qs = qs.filter(item__item_type=item_type)

        # Exclude zero-balance rows
        qs = qs.exclude(pcs=0, ct=0, gw=0)

        data = []
        total_gw = total_ct = total_pcs = 0
        for rm in qs.order_by('item__item_name', 'packet__pckt_no'):
            row = {
                'id': rm.id,
                'item': rm.item.short_code,
                'item_name': rm.item.item_name,
                'item_type': rm.item.item_type,
                'packet': rm.packet.pckt_no if rm.packet else None,
                'purity': rm.purity.purity if rm.purity else None,
                'pcs': rm.pcs,
                'ct': float(rm.ct),
                'gw': float(rm.gw),
            }
            data.append(row)
            total_gw += float(rm.gw)
            total_ct += float(rm.ct)
            total_pcs += rm.pcs

        return Response({
            'results': data,
            'summary': {
                'total_pcs': total_pcs,
                'total_ct': round(total_ct, 3),
                'total_gw': round(total_gw, 3),
                'count': len(data),
            }
        })


class RawMaterialMovementLedgerView(APIView):
    """Chronological transaction ledger for a specific item with running balance."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        item_id = request.query_params.get('item')
        if not item_id:
            return Response({'error': 'item parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

        qs = RawMaterialTransaction.objects.filter(
            item_id=item_id, retail=request.retail,
        ).select_related('item', 'packet', 'purity').order_by('date', 'id')

        packet_id = request.query_params.get('packet')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        if packet_id:
            qs = qs.filter(packet_id=packet_id)
        if from_date:
            qs = qs.filter(date__date__gte=from_date)
        if to_date:
            qs = qs.filter(date__date__lte=to_date)

        running_gw = running_ct = running_pcs = 0
        data = []
        for txn in qs:
            running_pcs += txn.pcs
            running_ct += float(txn.ct)
            running_gw += float(txn.gw)
            data.append({
                'id': txn.id,
                'date': txn.date,
                'trans_type': txn.trans_type,
                'billno': txn.billno,
                'packet': txn.packet.pckt_no if txn.packet else None,
                'purity': txn.purity.purity if txn.purity else None,
                'pcs': txn.pcs,
                'ct': float(txn.ct),
                'gw': float(txn.gw),
                'rate': float(txn.rate),
                'amt': float(txn.amt),
                'running_pcs': running_pcs,
                'running_ct': round(running_ct, 3),
                'running_gw': round(running_gw, 3),
            })

        return Response({'results': data, 'count': len(data)})


class SemiFinishedStockReportView(APIView):
    """Semi-finished stock in two categories: With Karigar (WIP) and Pending Barcode."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from manufacturing.models import KarigarIssueItem
        from django.db.models import Sum, F

        retail = request.retail

        # ── With Karigar (WIP): issued but not received back ──
        wip_qs = KarigarIssueItem.objects.filter(
            rec_status=False, retail=retail,
        ).select_related('item', 'purity', 'issue_slip__karigar_ldgr')

        wip_data = []
        for row in wip_qs.order_by('issue_slip__karigar_ldgr__ac_name', '-issue_slip__date1'):
            from datetime import date
            days_pending = (date.today() - row.issue_slip.date1).days if row.issue_slip.date1 else None
            wip_data.append({
                'id': row.id,
                'karigar': row.issue_slip.karigar_ldgr.ac_name if row.issue_slip.karigar_ldgr else None,
                'karigar_id': row.issue_slip.karigar_ldgr_id if row.issue_slip else None,
                'issue_slip_no': row.issue_slip.issue_slip_no,
                'issue_date': row.issue_slip.date1,
                'item': row.item.short_code if row.item else None,
                'item_name': row.item.item_name if row.item else None,
                'purity': str(row.purity) if row.purity else None,
                'pcs': row.pcs,
                'approx_wt': float(row.approx_wt) if row.approx_wt else None,
                'design_code': row.design_code,
                'days_pending': days_pending,
            })

        # ── Pending Barcode: received but not yet barcoded ──
        pending_qs = UnBarcodedMain.objects.filter(
            stk_status=True, retail=retail,
        ).select_related('item', 'purity')

        pending_data = []
        for row in pending_qs.order_by('-created_date'):
            pending_data.append({
                'id': row.id,
                'item': row.item.short_code if row.item else None,
                'item_name': row.item.item_name if row.item else None,
                'purity': str(row.purity) if row.purity else None,
                'pcs': row.pcs,
                'gw': float(row.gw) if row.gw else 0,
                'nw': float(row.nw) if row.nw else 0,
                'created_date': row.created_date,
                'created_from': row.created_from,
                'design_code': row.design_code,
                'voucher_no': row.voucher_no,
            })

        # ── Summaries ──
        wip_summary = {
            'total_pcs': sum(r['pcs'] for r in wip_data),
            'total_approx_wt': round(sum(r['approx_wt'] or 0 for r in wip_data), 3),
            'count': len(wip_data),
        }
        pending_summary = {
            'total_pcs': sum(r['pcs'] or 0 for r in pending_data),
            'total_gw': round(sum(r['gw'] for r in pending_data), 3),
            'count': len(pending_data),
        }

        return Response({
            'with_karigar': wip_data,
            'with_karigar_summary': wip_summary,
            'pending_barcode': pending_data,
            'pending_barcode_summary': pending_summary,
        })


# ── RFID Views ────────────────────────────────────────────────────────────────

from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination


class RfidTagAssignView(APIView):
    """
    POST  /inventory/api/rfid/assign/
    Assign (or clear) an RFID tag EPC to a BarcodeMain record.

    Body: { "barcode": "<13-digit>", "rfid_tag": "<EPC>" }
    To clear: send rfid_tag as empty string.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = RfidTagAssignSerializer(data=request.data, context={'retail': request.retail, 'request': request})
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response({
            'barcode': obj.barcode,
            'rfid_tag': obj.rfid_tag,
            'item': obj.item.item_name if obj.item else None,
        }, status=status.HTTP_200_OK)


class RfidInventoryCountView(APIView):
    """
    POST  /inventory/api/rfid/count/
    Submit a list of RFID tag IDs read by a scanner.
    Returns:
      - matched: tags found in stock with full barcode detail
      - unexpected: tags not registered or already sold
      - missing: barcodes that have an rfid_tag but were NOT scanned (possible loss/theft)

    Body: { "tags": ["EPC1", "EPC2", ...] }
    Optional: { "save_session": true, "note": "..." } to persist results.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tags = request.data.get('tags', [])
        if not isinstance(tags, list):
            return Response({'detail': 'tags must be a list.'}, status=status.HTTP_400_BAD_REQUEST)

        retail = request.retail
        tags_set = set(str(t).strip() for t in tags if t)

        # All barcodes in this retail that have an rfid_tag assigned
        rfid_qs = BarcodeMain.objects.filter(
            retail=retail,
            rfid_tag__isnull=False,
        ).exclude(rfid_tag='').select_related('item', 'purity')

        rfid_map = {b.rfid_tag: b for b in rfid_qs}

        matched = []
        unexpected = []
        for tag in tags_set:
            bc = rfid_map.get(tag)
            if bc:
                matched.append({
                    'rfid_tag': tag,
                    'barcode': bc.barcode,
                    'item': bc.item.item_name if bc.item else None,
                    'item_short': bc.item.short_code if bc.item else None,
                    'purity': str(bc.purity) if bc.purity else None,
                    'stk_status': bc.stk_status,
                    'gw': float(bc.gw) if bc.gw else 0,
                })
            else:
                unexpected.append({'rfid_tag': tag})

        # Missing = rfid-tagged barcodes in stock not seen in this scan
        scanned_rfids = tags_set
        missing = []
        for rfid_tag, bc in rfid_map.items():
            if rfid_tag not in scanned_rfids and bc.stk_status:
                missing.append({
                    'rfid_tag': rfid_tag,
                    'barcode': bc.barcode,
                    'item': bc.item.item_name if bc.item else None,
                    'item_short': bc.item.short_code if bc.item else None,
                    'purity': str(bc.purity) if bc.purity else None,
                    'gw': float(bc.gw) if bc.gw else 0,
                })

        # Optionally persist as a count session
        if request.data.get('save_session'):
            from .utils import generate_stock_journal_billno
            session_no = generate_stock_journal_billno(retail).replace('SJ', 'RFID')
            session = RfidCountSession.objects.create(
                session_no=session_no,
                note=request.data.get('note', ''),
                retail=retail,
                created_by=request.user,
            )
            bulk_results = []
            for row in matched:
                bc = rfid_map[row['rfid_tag']]
                bulk_results.append(RfidCountResult(
                    session=session, rfid_tag=row['rfid_tag'],
                    barcode=bc, match_status='matched',
                ))
            for row in unexpected:
                bulk_results.append(RfidCountResult(
                    session=session, rfid_tag=row['rfid_tag'],
                    barcode=None, match_status='unexpected',
                ))
            RfidCountResult.objects.bulk_create(bulk_results)
            session_id = session.id
            session_no_out = session.session_no
        else:
            session_id = None
            session_no_out = None

        return Response({
            'session_id': session_id,
            'session_no': session_no_out,
            'total_scanned': len(tags_set),
            'matched_count': len(matched),
            'unexpected_count': len(unexpected),
            'missing_count': len(missing),
            'matched': matched,
            'unexpected': unexpected,
            'missing': missing,
        })


class RfidCountSessionViewSet(RetailBaseViewset):
    """CRUD for saved RFID count sessions."""
    serializer_class = RfidCountSessionSerializer

    def get_queryset(self):
        if not self.request.retail:
            return RfidCountSession.objects.none()
        return RfidCountSession.objects.filter(retail=self.request.retail).order_by('-date')

    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        session = self.get_object()
        qs = RfidCountResult.objects.filter(session=session).select_related('barcode__item')
        ser = RfidCountResultSerializer(qs, many=True)
        return Response(ser.data)


class RfidTagListView(APIView):
    """
    GET /inventory/api/rfid/tags/
    Returns all barcodes with their rfid_tag assignments for the current retail.
    Supports ?search=<barcode or item> and ?assigned=true|false filter.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        retail = request.retail
        qs = BarcodeMain.objects.filter(retail=retail, stk_status=True).select_related('item', 'purity')
        search = request.query_params.get('search', '').strip()
        assigned = request.query_params.get('assigned', '')
        if search:
            qs = qs.filter(
                Q(barcode__icontains=search) |
                Q(item__item_name__icontains=search) |
                Q(item__short_code__icontains=search)
            )
        if assigned == 'true':
            qs = qs.filter(rfid_tag__isnull=False).exclude(rfid_tag='')
        elif assigned == 'false':
            qs = qs.filter(Q(rfid_tag__isnull=True) | Q(rfid_tag=''))

        qs = qs[:200]
        data = [{
            'id': b.id,
            'barcode': b.barcode,
            'rfid_tag': b.rfid_tag or '',
            'item': b.item.item_name if b.item else None,
            'item_short': b.item.short_code if b.item else None,
            'purity': str(b.purity) if b.purity else None,
            'gw': float(b.gw) if b.gw else 0,
            'stk_status': b.stk_status,
        } for b in qs]
        return Response({'results': data, 'count': len(data)})

class ClosingStockTxnView(APIView):
    """Return individual voucher rows for a given item+transaction-type drill-down."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        item_id   = request.query_params.get('item_id')
        txn_type  = request.query_params.get('txn_type')
        to_date   = request.query_params.get('to_date', str(datetime.today().date()))

        if not item_id or not txn_type:
            return Response({'error': 'item_id and txn_type are required'}, status=400)

        # Closing stock is always company-wide; the drill-down matches (all retails).
        retail_q = Q()

        try:
            item = Item.objects.get(id=item_id)
        except Item.DoesNotExist:
            return Response({'error': 'Item not found'}, status=404)

        vouchers = []

        if txn_type == 'purchases':
            qs = PurchaseVoucherItems.objects.filter(
                item=item, is_return=False, is_finished=False,
                billno__date1__lte=to_date,
            ).select_related('billno', 'billno__ldgr')
            qs = qs.filter(retail_q)
            for r in qs:
                vouchers.append({
                    'date': str(r.billno.date1),
                    'voucher_no': r.billno.billno,
                    'party': r.billno.ldgr.ac_name if r.billno.ldgr else '',
                    'gw': float(r.gw or 0),
                    'ct': 0.0,
                    'amount': float(r.item_value or 0),
                })
            if item.item_type in ['S', 'R']:
                dq = PurchaseVoucherDetails.objects.filter(
                    sub_item=item,
                    billno__date1__lte=to_date,
                ).filter(
                    Q(main_item__isnull=True) |
                    Q(main_item__is_finished=False, main_item__is_return=False)
                ).exclude(
                    # Don't double-count: if the parent main_item is the same
                    # item we're drilling on (e.g., customer purchase of pure
                    # Gold where main_item.item == sub_item == Gold), the main
                    # row already includes this detail's value via the
                    # _real_value fallback above.
                    main_item__item_id=item.id,
                ).select_related('billno', 'billno__ldgr')
                dq = dq.filter(retail_q)
                for r in dq:
                    vouchers.append({
                        'date': str(r.billno.date1),
                        'voucher_no': r.billno.billno,
                        'party': r.billno.ldgr.ac_name if r.billno.ldgr else '',
                        'gw': float(r.sub_gw or 0),
                        'ct': float(r.sub_ct or 0),
                        'amount': float(r.value or 0),
                    })

        elif txn_type == 'purchase_returns':
            qs = PurchaseReturnItems.objects.filter(
                item=item, billno__date1__lte=to_date,
            ).select_related('billno', 'billno__ldgr')
            qs = qs.filter(retail_q)
            for r in qs:
                vouchers.append({
                    'date': str(r.billno.date1),
                    'voucher_no': r.billno.billno,
                    'party': r.billno.ldgr.ac_name if r.billno.ldgr else '',
                    'gw': float(r.gw or 0),
                    'ct': 0.0,
                    'amount': float((r.gw or 0) * (r.making_value or 0)),
                })
            if item.item_type == 'S':
                dq = PurchaseReturnDetails.objects.filter(
                    sub_item=item, billno__date1__lte=to_date,
                ).select_related('billno', 'billno__ldgr')
                dq = dq.filter(retail_q)
                for r in dq:
                    vouchers.append({
                        'date': str(r.billno.date1),
                        'voucher_no': r.billno.billno,
                        'party': r.billno.ldgr.ac_name if r.billno.ldgr else '',
                        'gw': float(r.sub_gw or 0),
                        'ct': float(r.sub_ct or 0),
                        'amount': float(r.value or 0),
                    })

        elif txn_type == 'sales':
            qs = SalesVouItem.objects.filter(
                item=item, billno__date1__lte=to_date,
            ).select_related('billno', 'billno__ldgr')
            qs = qs.filter(retail_q)
            for r in qs:
                vouchers.append({
                    'date': str(r.billno.date1),
                    'voucher_no': r.billno.billno,
                    'party': r.billno.ldgr.ac_name if r.billno.ldgr else '',
                    'gw': float(r.gw or 0),
                    'ct': 0.0,
                    'amount': float(r.amount or 0),
                })
            if item.item_type in ['S', 'R']:
                dq = SalesVouItemDetails.objects.filter(
                    item=item, billno__date1__lte=to_date,
                ).select_related('billno', 'billno__ldgr', 'main_item__billno', 'main_item__billno__ldgr')
                dq = dq.filter(retail_q)
                for r in dq:
                    vou = r.main_item.billno if r.main_item else r.billno
                    vouchers.append({
                        'date': str(vou.date1),
                        'voucher_no': vou.billno,
                        'party': vou.ldgr.ac_name if vou.ldgr else '',
                        'gw': float(r.gw or 0),
                        'ct': float(r.ct or 0),
                        'amount': float(r.amount or 0),
                    })

        elif txn_type == 'sale_returns':
            qs = SaleReturnItem.objects.filter(
                item=item, billno__date1__lte=to_date,
            ).select_related('billno', 'billno__ldgr')
            qs = qs.filter(retail_q)
            for r in qs:
                vouchers.append({
                    'date': str(r.billno.date1),
                    'voucher_no': r.billno.billno,
                    'party': r.billno.ldgr.ac_name if r.billno.ldgr else '',
                    'gw': float(r.gw or 0),
                    'ct': 0.0,
                    'amount': 0.0,
                })
            if item.item_type in ['S', 'R']:
                dq = SaleReturnDetails.objects.filter(
                    item=item, main_item__billno__date1__lte=to_date,
                ).select_related('main_item__billno', 'main_item__billno__ldgr')
                dq = dq.filter(retail_q)
                for r in dq:
                    vou = r.main_item.billno
                    vouchers.append({
                        'date': str(vou.date1),
                        'voucher_no': vou.billno,
                        'party': vou.ldgr.ac_name if vou.ldgr else '',
                        'gw': float(r.gw or 0),
                        'ct': float(r.ct or 0),
                        'amount': float(r.amount or 0),
                    })

        elif txn_type == 'refinery_issues':
            from manufacturing.models import RefinaryIssueDetail as RID
            qs = RID.objects.filter(
                item=item, billno__date1__lte=to_date,
            ).select_related('billno', 'billno__ldgr')
            qs = qs.filter(retail_q)
            for r in qs:
                vouchers.append({
                    'date': str(r.billno.date1),
                    'voucher_no': r.billno.billno,
                    'party': r.billno.ldgr.ac_name if r.billno.ldgr else '',
                    'gw': float(r.gw or 0),
                    'ct': float(r.ct or 0),
                    'amount': 0.0,
                })

        elif txn_type == 'refinery_receives':
            # Receives are booked against Fine Gold as the converted net (fine)
            # weight, not against the issued item at gross weight. Only the Fine
            # Gold row drills into refinery receives; show conv_nw as the weight.
            from manufacturing.models import RefinaryReceiveDetail as RRD
            if item.item_name == 'Fine Gold':
                qs = RRD.objects.filter(
                    billno__date1__lte=to_date,
                ).select_related('billno', 'billno__ldgr')
                qs = qs.filter(retail_q)
                for r in qs:
                    vouchers.append({
                        'date': str(r.billno.date1),
                        'voucher_no': r.billno.billno,
                        'party': r.billno.ldgr.ac_name if r.billno.ldgr else '',
                        'gw': float(r.conv_nw or 0),
                        'ct': float(r.ct or 0),
                        'amount': 0.0,
                    })

        vouchers.sort(key=lambda x: x['date'])
        return Response({
            'item_name': item.item_name,
            'item_type': item.item_type,
            'txn_type': txn_type,
            'to_date': to_date,
            'vouchers': vouchers,
        })




# ---------------------------------------------------------------------------
# Inter-Retail Transfer Voucher
# ---------------------------------------------------------------------------

class InterRetailTransferVoucherViewSet(ModelViewSet):
    """Inter-retail (inter-branch) stock transfer vouchers.

    Visibility: a voucher is visible to users whose active retail is either
    the source or the destination. Listing is scoped accordingly.

    Status machine: draft -> in_transit -> received (or cancelled from draft/in_transit).
    Edits are only allowed while in draft.
    """
    serializer_class = InterRetailTransferVoucherSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ['status', 'from_retail', 'to_retail']
    search_fields = ['voucher_no', 'narration']
    ordering_fields = ['transfer_date', 'voucher_no', 'status']
    ordering = ['-transfer_date', '-id']

    def get_queryset(self):
        qs = InterRetailTransferVoucher.objects.all().select_related(
            'from_retail', 'to_retail', 'fiscal_year', 'created_by',
        ).prefetch_related('items', 'items__item')
        retail = getattr(self.request, 'retail', None)
        if retail is not None:
            qs = qs.filter(Q(from_retail=retail) | Q(to_retail=retail))
        # Optional transfer_date range
        q = self.request.query_params
        d_from, d_to = q.get('date_from'), q.get('date_to')
        if d_from:
            qs = qs.filter(transfer_date__gte=d_from)
        if d_to:
            qs = qs.filter(transfer_date__lte=d_to)
        return qs

    def destroy(self, request, *args, **kwargs):
        voucher = self.get_object()
        if voucher.status != InterRetailTransferVoucher.STATUS_DRAFT:
            return Response(
                {'detail': f"Cannot delete voucher in status '{voucher.status}'. Cancel it instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Capture before delete so the latest number can be reclaimed for reuse.
        from_retail, voucher_no, fiscal_year = voucher.from_retail, voucher.voucher_no, voucher.fiscal_year
        response = super().destroy(request, *args, **kwargs)
        from accounting.utils import release_last_bill_number
        release_last_bill_number(from_retail, 'IRT', voucher_no, fiscal_year)
        return response

    def _require_status(self, voucher, expected):
        if isinstance(expected, str):
            expected = [expected]
        if voucher.status not in expected:
            return Response(
                {'detail': f"Invalid transition: voucher is '{voucher.status}', expected one of {expected}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    @action(detail=True, methods=['post'], url_path='send')
    def send(self, request, pk=None):
        """draft -> in_transit. Inventory remains attributed to source until 'receive'."""
        voucher = self.get_object()
        err = self._require_status(voucher, InterRetailTransferVoucher.STATUS_DRAFT)
        if err:
            return err
        if not voucher.items.exists():
            return Response({'detail': 'Cannot send an empty voucher.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            voucher.status = InterRetailTransferVoucher.STATUS_IN_TRANSIT
            voucher.save(update_fields=['status', 'updated_at'])
        return Response({'detail': 'Voucher marked in_transit.', 'status': voucher.status})

    @action(detail=True, methods=['post'], url_path='receive')
    def receive(self, request, pk=None):
        """in_transit -> received. Flips barcode/unbarcoded retail FK and stamps received_at."""
        from django.utils import timezone
        voucher = self.get_object()
        err = self._require_status(voucher, InterRetailTransferVoucher.STATUS_IN_TRANSIT)
        if err:
            return err
        with transaction.atomic():
            voucher.status = InterRetailTransferVoucher.STATUS_RECEIVED
            voucher.received_at = timezone.now()
            voucher.save(update_fields=['status', 'received_at', 'updated_at'])
            barcode_ids = list(voucher.items.exclude(barcode__isnull=True).values_list('barcode_id', flat=True))
            if barcode_ids:
                BarcodeMain.objects.filter(id__in=barcode_ids).update(retail=voucher.to_retail)
            unbar_ids = list(voucher.items.exclude(unbarcoded_ref__isnull=True).values_list('unbarcoded_ref_id', flat=True))
            if unbar_ids:
                UnBarcodedMain.objects.filter(id__in=unbar_ids).update(retail=voucher.to_retail)
        return Response({'detail': 'Voucher received.', 'status': voucher.status})

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """{draft, in_transit} -> cancelled. No inventory impact."""
        voucher = self.get_object()
        err = self._require_status(
            voucher,
            [InterRetailTransferVoucher.STATUS_DRAFT, InterRetailTransferVoucher.STATUS_IN_TRANSIT],
        )
        if err:
            return err
        with transaction.atomic():
            voucher.status = InterRetailTransferVoucher.STATUS_CANCELLED
            voucher.save(update_fields=['status', 'updated_at'])
        return Response({'detail': 'Voucher cancelled.', 'status': voucher.status})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def inter_retail_transfer_next_no(request):
    """Read-only preview of the next IRT voucher number for the current retail."""
    retail = getattr(request, 'retail', None)
    if retail is None:
        return Response({'detail': 'No active retail in context.'}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'next_no': peek_next_bill_number(retail, 'IRT')})


def _sync_opening_to_raw_material(item, purity, packet, retail, pcs, ct, gw):
    from decimal import Decimal
    # get_or_merge tolerates duplicate rows (NULL packet/purity bypass the
    # unique_together) and creates with zeroes, so we add the delta unconditionally.
    rm = RawMaterialInventory.get_or_merge(item, packet, purity, retail)
    rm.pcs += pcs
    rm.ct += Decimal(str(ct))
    rm.gw += Decimal(str(gw))
    rm.save(update_fields=['pcs', 'ct', 'gw'])


class OpeningInventoryViewSet(RetailBaseViewset):
    serializer_class = OpeningInventorySerializer
    queryset = OpeningInventory.objects.select_related(
        'item', 'ldgr', 'purity', 'packet'
    ).all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['type']

    def get_queryset(self):
        retail = getattr(self.request, 'retail', None)
        return (
            OpeningInventory.objects
            .select_related('item', 'ldgr', 'purity', 'packet')
            .filter(retail=retail)
        )

    def perform_create(self, serializer):
        instance = serializer.save(retail=self.request.retail)
        _sync_opening_to_raw_material(
            instance.item, instance.purity, instance.packet, instance.retail,
            instance.pcs, instance.ct, instance.gw,
        )

    def perform_update(self, serializer):
        old = serializer.instance
        _sync_opening_to_raw_material(
            old.item, old.purity, old.packet, old.retail,
            -old.pcs, -old.ct, -old.gw,
        )
        instance = serializer.save()
        _sync_opening_to_raw_material(
            instance.item, instance.purity, instance.packet, instance.retail,
            instance.pcs, instance.ct, instance.gw,
        )

    def perform_destroy(self, instance):
        _sync_opening_to_raw_material(
            instance.item, instance.purity, instance.packet, instance.retail,
            -instance.pcs, -instance.ct, -instance.gw,
        )
        instance.delete()


class UnbarcodedStockReportView(APIView):
    """Unbarcoded stock report with rich filtering. Lists rows from UnBarcodedMain
    scoped to the request user's retail."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = UnBarcodedMain.objects.select_related(
            'item', 'purity', 'retail', 'kr_code', 'customer_order'
        ).filter(retail=request.retail)

        p = request.query_params

        # Stock status filter: 'active' (default), 'sold', 'all'
        status_param = (p.get('stk_status') or 'active').lower()
        if status_param == 'active':
            qs = qs.filter(stk_status=True)
        elif status_param == 'sold':
            qs = qs.filter(stk_status=False)
        # 'all' -> no filter

        # Source / created_from (comma-separated codes)
        sources = p.get('source')
        if sources:
            codes = [c.strip() for c in sources.split(',') if c.strip()]
            if codes:
                qs = qs.filter(created_from__in=codes)

        # Item / Purity / Karigar / Customer order / Design code / Metal color
        if p.get('item'):
            qs = qs.filter(item_id=p.get('item'))
        if p.get('purity'):
            qs = qs.filter(purity_id=p.get('purity'))
        if p.get('kr_code'):
            qs = qs.filter(kr_code_id=p.get('kr_code'))
        if p.get('customer_order'):
            qs = qs.filter(customer_order_id=p.get('customer_order'))
        if p.get('design_code'):
            qs = qs.filter(design_code__icontains=p.get('design_code'))
        if p.get('metal_color'):
            qs = qs.filter(metal_color__iexact=p.get('metal_color'))
        if p.get('label'):
            qs = qs.filter(label__icontains=p.get('label'))

        # Date range on created_date
        date_from = p.get('date_from')
        date_to = p.get('date_to')
        if date_from:
            qs = qs.filter(created_date__gte=date_from)
        if date_to:
            qs = qs.filter(created_date__lte=date_to)

        # Weight ranges
        for fld, key in (('gw', 'gw_min'), ('gw', 'gw_max'),
                         ('nw', 'nw_min'), ('nw', 'nw_max')):
            pass  # handled below explicitly for clarity

        if p.get('gw_min'):
            qs = qs.filter(gw__gte=p.get('gw_min'))
        if p.get('gw_max'):
            qs = qs.filter(gw__lte=p.get('gw_max'))
        if p.get('nw_min'):
            qs = qs.filter(nw__gte=p.get('nw_min'))
        if p.get('nw_max'):
            qs = qs.filter(nw__lte=p.get('nw_max'))

        qs = qs.order_by('-created_date', '-id')

        rows = []
        total_pcs = 0
        total_gw = 0.0
        total_nw = 0.0
        total_value = 0.0
        for ub in qs:
            pcs = ub.pcs or 0
            gw = float(ub.gw or 0)
            nw = float(ub.nw or 0)
            val = float(ub.total_amount or 0)
            total_pcs += pcs
            total_gw += gw
            total_nw += nw
            total_value += val
            rows.append({
                'id': ub.id,
                'label': ub.label,
                'item': ub.item.short_code if ub.item else None,
                'item_name': ub.item.item_name if ub.item else (ub.item_desc or ''),
                'purity': ub.purity.purity if ub.purity else None,
                'pcs': pcs,
                'gw': gw,
                'nw': nw,
                'huid': ub.huid,
                'design_code': ub.design_code,
                'kr_code_id': ub.kr_code_id,
                'kr_code_name': getattr(ub.kr_code, 'ac_name', None) if ub.kr_code else None,
                'customer_order_id': ub.customer_order_id,
                'customer_order_no': getattr(ub.customer_order, 'order_no', None) if ub.customer_order else None,
                'metal_color': ub.metal_color,
                'size': ub.size,
                'making_val': float(ub.making_val or 0),
                'making_type': ub.making_type,
                'other_chg': float(ub.other_chg or 0),
                'value': float(ub.value or 0),
                'total_amount': val,
                'source': ub.created_from,
                'source_label': dict(UnBarcodedMain.CREATED_FROM_CHOICES).get(ub.created_from, ub.created_from),
                'stk_status': ub.stk_status,
                'op_stk': ub.op_stk,
                'voucher_no': ub.voucher_no,
                'created_by': ub.created_by,
                'created_date': ub.created_date,
            })

        return Response({
            'rows': rows,
            'totals': {
                'pcs': total_pcs,
                'gw': round(total_gw, 3),
                'nw': round(total_nw, 3),
                'value': round(total_value, 2),
                'count': len(rows),
            },
        })
