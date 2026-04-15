from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from inventory.filters import StockValuationReportFilter
from inventory.serializer import BarCodeDetailSerializer, BarCodeMainSerializer, BarcodeCreationReportSerializer, BarcodeMainToSaleVouSerializer, BarcodeSplitMergeSerializer, BarcodeTransactionSerializer, DesignMainSerializer, ItemStockReportSerializer, RfidCountResultSerializer, RfidCountSessionSerializer, RfidTagAssignSerializer, StockJournalSerializer, StockTransferSerializer, UnBarcodedMainSerializer
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
from rest_framework.decorators import api_view, action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db.models import OuterRef, Subquery, Sum, IntegerField, Q, F, ExpressionWrapper, Prefetch


@api_view()
def gen_barcode(request):   
    res = {"barcode":generate_ean13()}
    return Response(res)

@api_view()
def get_barcode(request, barcode, hsn):
    try:
        obj = BarcodeMain.objects.get(
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
    data = BarcodeMainToSaleVouSerializer(obj).data
    return Response(data)

@api_view()
def get_barcode_only(request, barcode):
    try:
        obj = BarcodeMain.objects.get(
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
        
        iss_item = KarigarIssueItem.objects.get(id=rec_item.ref_job_sl_no_id)
        huid = HallmarkReceiveItemForPostSerializer(rec_item.hallmarkreceiveitem_set,many=True).data[0]["huid"] if len(HallmarkReceiveItemForPostSerializer(rec_item.hallmarkreceiveitem_set,many=True).data) > 0 else None
        # Prepare the response data
        response_data = {
            
           
            'order_no': iss_item.customer_order_item.order_no.order_no if iss_item.customer_order_item else None,
            'design_code': iss_item.design_code,
            'huid':huid,
            'voucher_no':rec.receive_slip_no,
            'purity':rec_item.purity.purity,
            'kr_code':rec.karigar_ldgr.id,
            'item':rec_item.item.short_code,
            'pcs':rec_item.pending_pcs,
            'rec_item':rec_item.id,
            'gw':rec_item.pending_gw,
            'nw':rec_item.nw,
            'making':rec_item.making,
            'barcodedetails_set': [{
                'packet': detail.packet.pckt_no if detail.packet else None,
                'item': detail.item.short_code,
                'pcs': detail.balance_pcs,
                'ct': detail.balance_ct,
                'gw': detail.balance_gw,
                'rate': detail.rate,
                'uom': detail.packet.stone_item_id.uom if detail.packet else None
            } for detail in rec_details]
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
    def post(self, request):
        barcode_value = request.data.get("barcode")
        if not barcode_value:
            return Response({"error": "Barcode is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        barcode_main = get_object_or_404(BarcodeMain, barcode=barcode_value)
        
        # Create UnBarcodedMain entry with optimized field assignments
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
            created_from='KAR_REC' if barcode_main.rec_item_id else ('PUR_VOU' if barcode_main.pur_voucher_id else 'MANUAL'),
            customer_order=barcode_main.customer_order,
            created_by=barcode_main.created_by,
            created_date=barcode_main.created_date,
            stk_status=True,
            op_stk=False,
            voucher_no=barcode_main.voucher_no,
            retail=barcode_main.retail
        )
        
        # Bulk create UnBarcodedDetails
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
                amt=detail.amt
            ) for detail in barcode_details
        ])
        
        # Mark BarcodeMain as inactive instead of deleting
        barcode_main.stk_status = False
        barcode_main.save()
       
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')) if request else None

        BarcodeTransaction.objects.create(
                    barcode=barcode_main,
                    billno="",
                    trans_type="BAR-TRF-UNB",
                    user=request.user,
                    ip_address=ip,
                    retail=request.retail
                ) 
        
        return Response({"message": "Barcode converted to Unbarcoded successfully"}, status=status.HTTP_201_CREATED)

    
@api_view(['POST'])
def barcode_split_view(request,old_barcode):
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
        for item in request.data:
            item['retail'] = request.retail
            # serializer = BarCodeMainSerializer(data=request.data,many=True)
            serializer = BarCodeMainSerializer(data=item, context={"request": request})
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
        
            inst = BarcodeMain.objects.get(barcode=old_barcode)
            inst.stk_status = False
            inst.save()
            
            serializer.save()
            inst = BarcodeSplitMerge.objects.create(
                transaction_type = "Split",
                old_barcode = old_br,
                # new_barcode = serializer.instance[0],
                new_barcode = serializer.instance,
                retail = request.retail
            )
            BarcodeTransaction.objects.create(
            barcode=old_br,
            billno=f"${inst.id}",
            trans_type="BAR-SPLIT-CRT",
            user=request.user,
            ip_address=ip,
            retail=request.retail
            )
        
        return Response(data=serializer.data)



class BarCodeView(RetailBaseViewset):
    serializer_class = BarCodeMainSerializer
    queryset = BarcodeMain.objects.all()
    filter_backends = [DjangoFilterBackend,OrderingFilter,SearchFilter]
    filterset_fields = ['barcode', 'item', 'purity', 'stk_status']
    search_fields = ['barcode', 'item__short_code', 'item__item_name',]

    def get_queryset(self):
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
from datetime import datetime
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
        retail_id = request.query_params.get('retail_id')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')

        # Calculate closing stock
        try:
            closing_stock = ClosingStockCal().calculate_closing_stock(item_id, retail_id, from_date, to_date)
            return Response({
                'closing_stock_value': closing_stock['total_value'],
                'opening_value': closing_stock['opening_value'],
                'total_purc': closing_stock['total_purc'],
                'total_purc_ret': closing_stock['total_purc_ret'],
                'total_sale_ret': closing_stock['total_sale_ret'],
                'total_sale': closing_stock['total_sale'],
                'details': closing_stock['details']
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class StockValuationReportView(APIView):
    def get(self, request, *args, **kwargs):
        # Fetch query parameters
        purity_filter = request.query_params.get("purity")
        item_filter = request.query_params.get("item")
        # Filter only in-stock barcodes
        barcodes = BarcodeMain.objects.filter(stk_status=True)
        if purity_filter:
            barcodes = barcodes.filter(purity=purity_filter)
        stock_data = []
        for barcode in barcodes:
            barcode_details = BarcodeDetails.objects.filter(barcode=barcode)
            # Apply item filter if provided
            if item_filter:
                barcode_details = barcode_details.filter(item__id=item_filter)
            stones = []
            others = []
            for detail in barcode_details:
                item_type = detail.item.item_type  # Assuming `item_type` determines if it's a stone
                detail_data = {
                    "code": detail.item.id,  # Assuming `id` acts as code
                    "sub": detail.packet.id if detail.packet else None,  # Packet details
                    "pcs": detail.pcs or 0,
                    "weight": detail.ct or 0,
                    "rate": detail.rate,
                    "value": detail.amt
                }
                if item_type == "stone":
                    stones.append(detail_data)
                else:
                    others.append(detail_data)
            stock_data.append({
                "barcode": barcode.barcode,
                "order": barcode.customer_order.id if barcode.customer_order else None,
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
    def get(self, request):
        as_on_date = request.query_params.get('as_on_date')

        if not as_on_date:
            return Response({"error": "as_on_date is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            as_on_date = datetime.strptime(as_on_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

        retail = request.retail

        # Opening stock: barcodes marked as op_stk created on or before as_on_date
        base_barcodes = BarcodeMain.objects.filter(
            op_retail=retail,
            item=OuterRef('pk'),
            op_stk=True,
            stk_status=True,
            created_date__lte=as_on_date
        ).values('item').annotate(total_pcs=Coalesce(Sum('pcs'), 0)).values('total_pcs')

        # All transactions up to as_on_date from barcode_transaction
        transactions = BarcodeTransaction.objects.filter(
            barcode__item=OuterRef('pk'),
            retail=retail,
            date__lte=as_on_date
        )

        # Actual trans_type values from barcode_transaction table
        inflow_types = [
            'CREATE-PUR', 'CREATE-REC', 'SALE-RET', 'SALE-APP-RET',
            'TRF-RR-IN', 'BAR-MER-CRT', 'BAR-SPLIT-CRT',
        ]
        outflow_types = [
            'SALE', 'SALE-APP', 'TRF-RR-OUT',
            'BAR-MER', 'BAR-SPLIT', 'BAR-TRF-UNB',
        ]

        # Map trans_type values to safe annotation field names
        type_field_map = {
            'CREATE-PUR': 'create_pur', 'CREATE-REC': 'create_rec',
            'SALE-RET': 'sale_ret', 'SALE-APP-RET': 'sale_app_ret',
            'TRF-RR-IN': 'trf_rr_in', 'BAR-MER-CRT': 'bar_mer_crt',
            'BAR-SPLIT-CRT': 'bar_split_crt',
            'SALE': 'sale', 'SALE-APP': 'sale_app',
            'TRF-RR-OUT': 'trf_rr_out', 'BAR-MER': 'bar_mer',
            'BAR-SPLIT': 'bar_split', 'BAR-TRF-UNB': 'bar_trf_unb',
        }

        annotations = {
            'opening': Coalesce(Subquery(base_barcodes, output_field=IntegerField()), 0),
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
            stock=F('opening') + F('inflow') - F('outflow')
        ).exclude(
            opening=0, inflow=0, outflow=0
        )

        serializer = ItemStockReportSerializer(qs, many=True)
        return Response(serializer.data)

class BarcodeDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BarcodeDetails
        fields = "__all__"

class BarcodeMainSerializer(serializers.ModelSerializer):
    stone = BarcodeDetailsSerializer(many=True)
    other = BarcodeDetailsSerializer(many=True)
    class Meta:
        model = BarcodeMain
        fields = ['barcode','stone','other']

class ItemBarcodeSerializer(serializers.ModelSerializer):

    barcodemain_set = BarcodeMainSerializer(many=True)
    class Meta:
        model = Item
        fields = ['barcodemain_set','short_code']


class ItemwiseBarcodeReport(APIView):
    def get(self, request):
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')

        if not from_date or not to_date:
            return Response({"error": "from_date and to_date are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        qs = Item.objects.all().prefetch_related(Prefetch('barcodemain_set',queryset=BarcodeMain.objects.filter(created_date__range=[from_date,to_date]).prefetch_related(
            Prefetch('barcodedetails_set',queryset=BarcodeDetails.objects.filter(item__item_type="S"),to_attr='stone'),
            Prefetch('barcodedetails_set',queryset=BarcodeDetails.objects.exclude(item__item_type="S"),to_attr='other'),

            
            )))
        return Response(ItemBarcodeSerializer(qs,many=True).data)
    

class ClosingStockCal:
    """
    Closing stock calculation with separate gw (gross weight), ct (carat),
    and amt (amount) for each transaction type, plus refinery issue/receive.
    """

    @staticmethod
    def _zero():
        return {'gw': Decimal('0.00'), 'ct': Decimal('0.00'), 'amt': Decimal('0.00')}

    def calculate_closing_stock(self, item_id=None, retail_id=None, from_date=None, to_date=None):
        items_query = Item.objects.exclude(item_type__in=['M', 'O'])
        if item_id:
            items_query = items_query.filter(id=item_id)
        if retail_id:
            items_query = items_query.filter(retail_id=retail_id)

        results = {
            'total_value': Decimal('0.00'),
            'opening_value': Decimal('0.00'),
            'total_purc': Decimal('0.00'),
            'total_purc_ret': Decimal('0.00'),
            'total_sale_ret': Decimal('0.00'),
            'total_sale': Decimal('0.00'),
            'details': []
        }

        for item in items_query:
            opening = self.get_opening_stock(item, retail_id)
            purchase = self.get_purchases(item, retail_id, from_date, to_date)
            purc_ret = self.get_purchase_returns(item, retail_id, from_date, to_date)
            sales = self.get_sales(item, retail_id, from_date, to_date)
            sale_ret = self.get_sale_returns(item, retail_id, from_date, to_date)
            ref_iss = self.get_refinery_issues(item, retail_id, from_date, to_date)
            ref_rec = self.get_refinery_receives(item, retail_id, from_date, to_date)

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

            total_in_qty = op_qty + pu_qty - pr_qty
            total_in_value = opening['amt'] + purchase['amt'] - purc_ret['amt']

            weighted_avg_rate = Decimal('0.00')
            if total_in_qty > 0:
                weighted_avg_rate = total_in_value / total_in_qty

            sa_qty = sales[pq]
            sales_value = sa_qty * weighted_avg_rate

            sr_qty = sale_ret[pq]
            sale_return_value = sr_qty * weighted_avg_rate

            ri_qty = ref_iss[pq]
            rr_qty = ref_rec[pq]

            adjustment = Decimal('0.00')
            if item.item_name == "GOLD":
                adj = self.get_mfg_adj()
                adjustment = adj if adj else Decimal('0.00')

            closing_qty = total_in_qty - sa_qty + sr_qty - ri_qty + rr_qty - adjustment
            closing_value = closing_qty * weighted_avg_rate

            # Closing gw and ct
            closing_gw = opening['gw'] + purchase['gw'] - purc_ret['gw'] - sales['gw'] + sale_ret['gw'] - ref_iss['gw'] + ref_rec['gw']
            closing_ct = opening['ct'] + purchase['ct'] - purc_ret['ct'] - sales['ct'] + sale_ret['ct'] - ref_iss['ct'] + ref_rec['ct']

            results['total_value'] += closing_value
            results['opening_value'] += opening['amt']
            results['total_purc'] += purchase['amt']
            results['total_purc_ret'] += purc_ret['amt']
            results['total_sale_ret'] += sale_return_value
            results['total_sale'] += sales_value

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
                'sales_amt': float(sales_value),
                # Sale Returns
                'sale_ret_gw': float(sale_ret['gw']),
                'sale_ret_ct': float(sale_ret['ct']),
                'sale_ret_amt': float(sale_return_value),
                # Refinery
                'ref_iss_gw': float(ref_iss['gw']),
                'ref_iss_ct': float(ref_iss['ct']),
                'ref_rec_gw': float(ref_rec['gw']),
                'ref_rec_ct': float(ref_rec['ct']),
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

    def get_opening_stock(self, item: Item, retail_id=None):
        result = self._zero()
        filters = {'item': item}
        if retail_id:
            filters['retail_id'] = retail_id

        barcoded_q = BarcodeDetails.objects.filter(**filters, barcode__op_stk=True)
        unbarcoded_q = UnBarcodedDetails.objects.filter(**filters, main_item__op_stk=True)
        raw_q = OpeningInventory.objects.filter(**filters)

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

    def get_purchases(self, item, retail_id=None, from_date=None, to_date=None):
        result = self._zero()

        # Main item purchases (non-finished, non-return). Date lives on the voucher header.
        query = PurchaseVoucherItems.objects.filter(item=item, is_return=False, is_finished=False)
        if retail_id:
            query = query.filter(retail_id=retail_id)
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
            main_item__is_finished=False,
            main_item__is_return=False,
        )
        if retail_id:
            detail_query = detail_query.filter(retail_id=retail_id)
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

    def get_purchase_returns(self, item, retail_id=None, from_date=None, to_date=None):
        result = self._zero()
        query = PurchaseReturnItems.objects.filter(item=item)
        if retail_id:
            query = query.filter(retail_id=retail_id)
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
            if retail_id:
                detail_q = detail_q.filter(retail_id=retail_id)
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

    def get_sales(self, item, retail_id=None, from_date=None, to_date=None):
        result = self._zero()
        query = SalesVouItem.objects.filter(item=item)
        if retail_id:
            query = query.filter(retail_id=retail_id)
        if from_date:
            query = query.filter(billno__date1__gte=from_date)
        if to_date:
            query = query.filter(billno__date1__lte=to_date)

        agg = query.aggregate(
            total_gw=Coalesce(Sum('gw'), Decimal('0.00')),
        )
        result['gw'] = agg['total_gw']

        if item.item_type == 'S':
            detail_q = SalesVouItemDetails.objects.filter(main_item__in=query, item=item)
            detail_agg = detail_q.aggregate(
                total_ct=Coalesce(Sum('ct'), Decimal('0.00')),
                total_val=Coalesce(Sum('amount'), Decimal('0.00')),
            )
            result['ct'] = detail_agg['total_ct']
            # amt for sales is computed via weighted avg in calculate_closing_stock

        return result

    def get_sale_returns(self, item, retail_id=None, from_date=None, to_date=None):
        result = self._zero()
        query = SaleReturnItem.objects.filter(item=item)
        if retail_id:
            query = query.filter(retail_id=retail_id)
        if from_date:
            query = query.filter(billno__date1__gte=from_date)
        if to_date:
            query = query.filter(billno__date1__lte=to_date)

        agg = query.aggregate(
            total_gw=Coalesce(Sum('gw'), Decimal('0.00')),
        )
        result['gw'] = agg['total_gw']

        if item.item_type == 'S':
            detail_q = SaleReturnDetails.objects.filter(main_item__in=query, item=item)
            detail_agg = detail_q.aggregate(
                total_ct=Coalesce(Sum('ct'), Decimal('0.00')),
                total_val=Coalesce(Sum('amount'), Decimal('0.00')),
            )
            result['ct'] = detail_agg['total_ct']
            # amt for sale returns is computed via weighted avg in calculate_closing_stock

        return result

    def get_refinery_issues(self, item, retail_id=None, from_date=None, to_date=None):
        result = self._zero()
        query = RefinaryIssueDetail.objects.filter(item=item)
        if retail_id:
            query = query.filter(retail_id=retail_id)
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

    def get_refinery_receives(self, item, retail_id=None, from_date=None, to_date=None):
        result = self._zero()
        query = RefinaryReceiveDetail.objects.filter(item=item)
        if retail_id:
            query = query.filter(retail_id=retail_id)
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


class DesignMainViewSet(RetailBaseViewset):
    queryset = DesignMain.objects.all()
    serializer_class = DesignMainSerializer

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
        'date1': ['range']
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

    def perform_destroy(self, instance):
        from accounting.utils import release_last_bill_number
        retail = instance.retail
        fiscal_year = instance.fiscal_year
        billno = instance.billno
        super().perform_destroy(instance)
        release_last_bill_number(retail, 'SJ', billno, fiscal_year)

class BarcodeTransactionView(RetailBaseViewset):
    serializer_class = BarcodeTransactionSerializer
    queryset = BarcodeTransaction.objects.all()
    filter_backends = [DjangoFilterBackend,SearchFilter,OrderingFilter]
    search_fields = ['barcode__barcode']


class BarcodeCreationReportView(APIView):
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
    ordering = ['billno']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    def get_queryset(self):
        from inventory.models import StockTransfer
        retail = getattr(self.request, 'retail', None)
        return StockTransfer.objects.filter(
            Q(retail=retail) | Q(to_rt_code=retail)
        ).select_related('retail', 'to_rt_code').order_by('-date1', '-billno')

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
            return BarcodeImage.objects.filter(barcode_id=barcode_id).order_by('-uploaded_at')
        return BarcodeImage.objects.none()

    def create(self, request, *args, **kwargs):
        from inventory.serializer import BarcodeImageSerializer
        files = request.FILES.getlist('image')
        barcode_id = request.data.get('barcode')
        if not barcode_id:
            return Response({"error": "barcode is required"}, status=status.HTTP_400_BAD_REQUEST)
        results = []
        for f in files:
            serializer = BarcodeImageSerializer(data={'barcode': barcode_id, 'image': f})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            results.append(serializer.data)
        return Response(results, status=status.HTTP_201_CREATED)


class BarcodeImageDelete(APIView):
    def delete(self, request, pk):
        try:
            img = BarcodeImage.objects.get(pk=pk)
            img.image.delete(save=False)
            img.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except BarcodeImage.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def serve_barcode_image_file(request, name):
    """Stream a barcode image from the configured storage root."""
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


class RawMaterialBalanceReportView(APIView):
    """Current raw material stock balance grouped by item."""

    def get(self, request):
        from django.db.models import Sum, CharField, Value
        from django.db.models.functions import Coalesce

        qs = RawMaterialInventory.objects.select_related('item', 'packet', 'purity').filter(
            retail=request.retail
        )

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
                'purity': str(rm.purity) if rm.purity else None,
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
                'purity': str(txn.purity) if txn.purity else None,
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


class RfidCountSessionViewSet(ModelViewSet):
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