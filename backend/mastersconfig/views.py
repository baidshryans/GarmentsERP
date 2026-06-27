from django.shortcuts import render, redirect,get_object_or_404
from django.http import HttpResponse
from django.core.cache import cache
from rest_framework.generics import ListCreateAPIView,RetrieveUpdateDestroyAPIView,ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework.decorators import api_view
from rest_framework import status
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from mastersconfig.serializers import *
from .models import *
from contacts.models import *
from django.contrib.auth.decorators import login_required
from userauth import views
from rest_framework.filters import OrderingFilter, SearchFilter
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
import csv
import io





#__________HSN-API____________________
class ListCreateHsn(ListCreateAPIView):
    queryset = Hsn.objects.all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return HSNSerializer
        return HSNListSerializer

class RetrieveUpdateDeleteHsn(RetrieveUpdateDestroyAPIView):
    serializer_class = HSNSerializer
    queryset         = Hsn.objects.prefetch_related('item_set')



#------------------Item-API-------------------------------------------
class ListCreateItem(ListCreateAPIView):
    queryset         = Item.objects.select_related('grp', 'hsn_no', 'purchase_ledger', 'sale_ledger')
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['hsn_no','item_type']
    search_fields    = ['item_name', 'short_name']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ItemWriteSerializer
        return ItemSerializer


class RetrieveUpdateDestroyItem(RetrieveUpdateDestroyAPIView):
    queryset         = Item.objects.select_related('grp', 'hsn_no', 'purchase_ledger', 'sale_ledger')

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return ItemWriteSerializer
        return ItemSerializer




#---------------------------------------Shapes-API---------------------------------------------
class ListCreateShape(ListCreateAPIView):
    serializer_class = ShapeSerializer
    queryset         = Shapes.objects.all()

class RetrieveUpdateDestroyShape(RetrieveUpdateDestroyAPIView):
    serializer_class = ShapeSerializer
    queryset         = Shapes.objects.all()



#---------------------------------------Color---------------------------------------------



#---------------------------------------Color-API---------------------------------------------

class ListCreateColor(ListCreateAPIView):
    serializer_class = ColorSerializer
    queryset         = Colors.objects.all()

class RetrieveUpdateDestroyColor(RetrieveUpdateDestroyAPIView):
    serializer_class = ColorSerializer
    queryset         = Colors.objects.all()


#-------------------packet group -api---------------------

class ListCreatePacketGroup(ListCreateAPIView):
    serializer_class = PacketGroupSerializer
    queryset         = PacketGroup.objects.all()

class RetrieveUpdateDestroyPacketGroup(RetrieveUpdateDestroyAPIView):
    serializer_class = PacketGroupSerializer
    queryset         = PacketGroup.objects.all()





#----------------packet_view-api-----------------------------------------------
class ListCreatePacket(ListCreateAPIView):
    serializer_class = PacketSerializer
    queryset         = Packet.objects.select_related('packet_group', 'stone_item_id', 'stone_item_id__hsn_no', 'color', 'shape').all()
    filter_backends = [DjangoFilterBackend,SearchFilter]
    filterset_fields = ['stone_item_id']

    def get_queryset(self):
        qs = super().get_queryset()
        items = self.request.query_params.get('item_ids')
        if items:
            ids = [v for v in items.split(',') if v.strip()]
            if ids:
                qs = qs.filter(stone_item_id__in=ids)
        return qs


class RetrieveUpdateDestroyPacket(RetrieveUpdateDestroyAPIView):
    serializer_class = PacketSerializer
    queryset         = Packet.objects.all()
    


#-------------------Salespersons---------------------

#-------------------Salespersons-API---------------------

class ListCreateSalesPersonMaster(ListCreateAPIView):
    serializer_class = SalesPersonMasterSerializer
    pagination_class = None

    def get_queryset(self):
        retail = getattr(self.request, "retail", None)
        if retail is None:
            return SalesPersonMaster.objects.none()
        return SalesPersonMaster.objects.filter(retail=retail)

    def perform_create(self, serializer):
        retail = getattr(self.request, "retail", None)
        serializer.save(retail=retail)

class RetrieveUpdateDestroySalesPersonMaster(RetrieveUpdateDestroyAPIView):
    serializer_class = SalesPersonMasterSerializer
    queryset         = SalesPersonMaster.objects.all()

    def get_queryset(self):
        retail = getattr(self.request, 'retail', None)
        if retail is None:
            return SalesPersonMaster.objects.none()
        return SalesPersonMaster.objects.filter(retail=retail)

    def perform_update(self, serializer):
        retail = getattr(self.request, 'retail', None) or serializer.instance.retail
        serializer.save(retail=retail)


#--------------------------Item Group------------------------------

#--------------------------Item Group-Api------------------------------

class ListCreateItemGroupMaster(ListCreateAPIView):
    serializer_class = ItemGroupMasterSerializer
    queryset         = ItemGroupMaster.objects.all().order_by('id')

class RetrieveUpdateDestroyItemGroupMaster(RetrieveUpdateDestroyAPIView):
    serializer_class = ItemGroupMasterSerializer
    queryset         = ItemGroupMaster.objects.all()

class StateListView(ListAPIView):
    serializer_class = StateSerializer
    queryset = State.objects.all().order_by('name')
    authentication_classes = []
    permission_classes = [AllowAny]
    pagination_class = None


class RetailMasterView(ListCreateAPIView):
    serializer_class = RetailSerializer
    queryset = RetailMaster.objects.select_related('state', 'active_fy', 'cash_ldgr', 'branch').all()

    def perform_create(self, serializer):
        retail = serializer.save()
        # Auto-assign the new retail to the creating user's UserLocation so
        # it appears immediately in their retail selector dropdown.
        user = self.request.user
        if user and user.is_authenticated and not user.is_superuser:
            from contacts.models import UserLocation
            ul, _ = UserLocation.objects.get_or_create(user=user)
            ul.location.add(retail)
            if ul.default_location is None:
                ul.default_location = retail
                ul.save(update_fields=['default_location'])


class RetailMasterDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = RetailSerializer
    queryset = RetailMaster.objects.select_related('state', 'active_fy', 'cash_ldgr', 'branch').all()

    def destroy(self, request, *args, **kwargs):
        """
        Block deletion if any system ledger owned by this retail has
        transactions in the active financial year.  If clean, auto-delete
        the system ledgers before removing the retail.
        """
        from accounting.models import VoucherDetail

        retail = self.get_object()
        active_fy = retail.active_fy

        # ── Collect system ledgers owned by this retail ──────────────
        ledgers_to_delete = []

        # 1) Cash ledger (always retail-specific)
        if retail.cash_ldgr_id:
            ledgers_to_delete.append(retail.cash_ldgr)

        # 2) GSTIN GST ledgers — only if this is the last retail on that GSTIN
        gstin = retail.gstin_master
        delete_gstin = False
        if gstin:
            other_retails = gstin.retails.exclude(pk=retail.pk).count()
            if other_retails == 0:
                delete_gstin = True
                for fld in ('input_cgst', 'input_sgst', 'input_igst',
                            'output_cgst', 'output_sgst', 'output_igst'):
                    ldgr = getattr(gstin, fld, None)
                    if ldgr:
                        ledgers_to_delete.append(ldgr)

        # ── Check for transactions across all fiscal years ─────────────
        if ledgers_to_delete:
            ledger_ids = [l.pk for l in ledgers_to_delete]
            txn_count = VoucherDetail.objects.filter(
                account_id__in=ledger_ids,
            ).count()
            if txn_count > 0:
                fy_label = f" (active FY: {active_fy.fy_code})" if active_fy else ""
                return Response(
                    {'error': (
                        f'Cannot delete retail — {txn_count} transaction(s) exist '
                        f'for its system ledgers{fy_label}. '
                        f'Close or delete those entries first.'
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── Safe to delete — clean up system ledgers ─────────────────
        # Detach FKs first so the retail delete doesn't fail on protected refs
        RetailMaster.objects.filter(pk=retail.pk).update(cash_ldgr=None)

        for ldgr in ledgers_to_delete:
            ldgr.delete()

        if delete_gstin and gstin:
            gstin.delete()

        return super().destroy(request, *args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Branch Master Views
# ─────────────────────────────────────────────────────────────────────────────

class CompanyMasterView(ListCreateAPIView):
    serializer_class = CompanyMasterSerializer
    queryset = CompanyMaster.objects.select_related('state').all()


class CompanyMasterDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = CompanyMasterSerializer
    queryset = CompanyMaster.objects.select_related('state').all()


@api_view(['GET', 'PATCH'])
def system_settings_view(request):
    """
    GET  → return current system settings (singleton, pk=1).
    PATCH → update one or more fields. Validates that attachment_storage_path
            is an absolute path when provided, and attempts to create the
            directory so permission errors surface immediately.
    """
    from mastersconfig.models import SystemSettings
    from mastersconfig.serializers import SystemSettingsSerializer

    settings_obj = SystemSettings.get()

    if request.method == 'GET':
        return Response(SystemSettingsSerializer(settings_obj).data)

    # PATCH — validate and save each path field
    for field in ('attachment_storage_path', 'barcode_image_storage_path'):
        path = request.data.get(field, None)
        if path is not None:
            path = path.strip()
            if path and not os.path.isabs(path):
                return Response(
                    {field: 'Must be an absolute path (e.g. C:\\Attachments\\ERP or /srv/erp/attachments).'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if path:
                try:
                    os.makedirs(path, exist_ok=True)
                except Exception as exc:
                    return Response(
                        {field: f'Cannot create directory: {exc}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            setattr(settings_obj, field, path)

    # Handle non-path boolean/value fields
    for field in ('bill_total_auto_calc', 'spell_check_enabled', 'enable_gst_bill'):
        val = request.data.get(field, None)
        if val is not None:
            setattr(settings_obj, field, val)

    settings_obj.save()

    return Response(SystemSettingsSerializer(settings_obj).data)


class BranchMasterView(ListCreateAPIView):
    serializer_class = BranchMasterSerializer
    queryset = BranchMaster.objects.select_related('company', 'state').all()


class BranchMasterDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = BranchMasterSerializer
    queryset = BranchMaster.objects.select_related('company', 'state').all()


class GSTINMasterView(ListCreateAPIView):
    serializer_class = GSTINMasterSerializer
    queryset = GSTINMaster.objects.select_related(
        'branch', 'state',
        'input_cgst', 'input_sgst', 'input_igst',
        'output_cgst', 'output_sgst', 'output_igst',
    ).all()


class GSTINMasterDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = GSTINMasterSerializer
    queryset = GSTINMaster.objects.select_related(
        'branch', 'state',
        'input_cgst', 'input_sgst', 'input_igst',
        'output_cgst', 'output_sgst', 'output_igst',
    ).all()


class BranchAnalyticsView(APIView):
    """
    GET /mastersconfig/api/branch/<pk>/analytics/
    Returns KPI aggregates for every retail belonging to this branch,
    plus a branch-wide grand total.  Aggregation mirrors the logic used
    in userauth.views.dashboard_summary.
    """

    def get(self, request, pk):
        branch = get_object_or_404(BranchMaster, pk=pk)
        retails = RetailMaster.objects.filter(branch=branch).select_related('active_fy')

        from decimal import Decimal
        from django.db.models import Sum, F, DecimalField
        from django.db.models.functions import Coalesce
        import datetime

        today = datetime.date.today()
        month_start = today.replace(day=1)

        # Import transaction models lazily to avoid circular imports
        from sales.models import SalesVou, SaleReturn
        from purchase.models import PurchaseVoucher, PurchaseOrder

        # Sales / sale-return totals are derived as (mrp - discount) — no
        # stored grand_total column on these models. We compute via annotated
        # aggregation so the work happens in the database.
        zero = Decimal('0')
        net_expr = Coalesce(F('mrp'), zero) - Coalesce(F('discount'), zero)

        def _sales_total(qs):
            return qs.aggregate(
                s=Sum(net_expr, output_field=DecimalField(max_digits=14, decimal_places=2))
            )['s'] or zero

        retail_stats = []
        totals = {
            'today_sales': zero,
            'month_sales': zero,
            'today_purchases': zero,
            'month_purchases': zero,
            'outstanding': zero,
            'purchase_orders': 0,
        }

        for retail in retails:
            # Sales (excluding fully-returned vouchers)
            today_sales = _sales_total(
                SalesVou.objects.filter(retail=retail, date1=today, ret_status=False)
            )
            month_sales = _sales_total(
                SalesVou.objects.filter(retail=retail, date1__gte=month_start, ret_status=False)
            )

            # Sales-return adjustment
            today_sr = _sales_total(
                SaleReturn.objects.filter(retail=retail, date1=today)
            )
            month_sr = _sales_total(
                SaleReturn.objects.filter(retail=retail, date1__gte=month_start)
            )

            today_sales_net = today_sales - today_sr
            month_sales_net = month_sales - month_sr

            # Purchases — use item_total (matches dashboard_summary)
            today_purchases = PurchaseVoucher.objects.filter(
                retail=retail, date1=today, is_return=False
            ).aggregate(s=Sum('item_total'))['s'] or zero

            month_purchases = PurchaseVoucher.objects.filter(
                retail=retail, date1__gte=month_start, is_return=False
            ).aggregate(s=Sum('item_total'))['s'] or zero

            # Open purchase orders — count (PO model has no monetary total)
            po_count = PurchaseOrder.objects.filter(retail=retail).count()

            # Outstanding receivable — sum of due_amt on open sales vouchers
            outstanding = SalesVou.objects.filter(
                retail=retail, ret_status=False
            ).aggregate(s=Sum('due_amt'))['s'] or zero

            stat = {
                'retail_id':        retail.id,
                'retail_code':      retail.retail_code,
                'retail_name':      retail.retail_name,
                'active_fy_code':   retail.active_fy.fy_code if retail.active_fy else '',
                'today_sales':      float(today_sales_net),
                'month_sales':      float(month_sales_net),
                'today_purchases':  float(today_purchases),
                'month_purchases':  float(month_purchases),
                'outstanding':      float(outstanding),
                'purchase_orders':  po_count,
            }
            retail_stats.append(stat)

            totals['today_sales']      += today_sales_net
            totals['month_sales']      += month_sales_net
            totals['today_purchases']  += today_purchases
            totals['month_purchases']  += month_purchases
            totals['outstanding']      += outstanding
            totals['purchase_orders']  += po_count

        return Response({
            'branch': {
                'id':          branch.id,
                'branch_name': branch.branch_name,
                'branch_code': branch.branch_code,
                'description': branch.description,
                'retail_count': retails.count(),
            },
            'retails':  retail_stats,
            'totals':   {
                'today_sales':     float(totals['today_sales']),
                'month_sales':     float(totals['month_sales']),
                'today_purchases': float(totals['today_purchases']),
                'month_purchases': float(totals['month_purchases']),
                'outstanding':     float(totals['outstanding']),
                'purchase_orders': int(totals['purchase_orders']),
            },
        })


class RetailAnalyticsView(APIView):
    """
    GET /mastersconfig/api/retail/<pk>/analytics/
    Returns KPI aggregates for a single retail, plus top-customer and
    top-vendor breakdowns for the current month. Mirrors the field
    semantics used in BranchAnalyticsView and userauth.dashboard_summary.
    """

    def get(self, request, pk):
        retail = get_object_or_404(
            RetailMaster.objects.select_related('active_fy', 'branch'), pk=pk
        )

        from decimal import Decimal
        from django.db.models import Sum, F, DecimalField
        from django.db.models.functions import Coalesce
        import datetime

        today = datetime.date.today()
        month_start = today.replace(day=1)

        from sales.models import SalesVou, SaleReturn
        from purchase.models import PurchaseVoucher, PurchaseOrder

        zero = Decimal('0')
        net_expr = Coalesce(F('mrp'), zero) - Coalesce(F('discount'), zero)

        def _sales_total(qs):
            return qs.aggregate(
                s=Sum(net_expr, output_field=DecimalField(max_digits=14, decimal_places=2))
            )['s'] or zero

        # Sales (excluding fully-returned vouchers)
        today_sales = _sales_total(
            SalesVou.objects.filter(retail=retail, date1=today, ret_status=False)
        )
        month_sales = _sales_total(
            SalesVou.objects.filter(retail=retail, date1__gte=month_start, ret_status=False)
        )

        # Sales-return adjustment
        today_sr = _sales_total(SaleReturn.objects.filter(retail=retail, date1=today))
        month_sr = _sales_total(SaleReturn.objects.filter(retail=retail, date1__gte=month_start))

        today_sales_net = today_sales - today_sr
        month_sales_net = month_sales - month_sr

        # Purchases — use item_total (matches dashboard_summary)
        today_purchases = PurchaseVoucher.objects.filter(
            retail=retail, date1=today, is_return=False
        ).aggregate(s=Sum('item_total'))['s'] or zero

        month_purchases = PurchaseVoucher.objects.filter(
            retail=retail, date1__gte=month_start, is_return=False
        ).aggregate(s=Sum('item_total'))['s'] or zero

        po_count = PurchaseOrder.objects.filter(retail=retail).count()

        outstanding = SalesVou.objects.filter(
            retail=retail, ret_status=False
        ).aggregate(s=Sum('due_amt'))['s'] or zero

        # Top customers — by month sales (mrp - discount)
        top_customers_qs = (
            SalesVou.objects
            .filter(retail=retail, date1__gte=month_start, ret_status=False)
            .values('ldgr_id', 'ldgr__ac_name')
            .annotate(
                total=Sum(net_expr, output_field=DecimalField(max_digits=14, decimal_places=2))
            )
            .order_by('-total')[:5]
        )
        top_customers = [
            {
                'ledger_id':   row['ldgr_id'],
                'ledger_name': row['ldgr__ac_name'] or '',
                'total':       float(row['total'] or 0),
            }
            for row in top_customers_qs
        ]

        # Top vendors — by month purchases (item_total)
        top_vendors_qs = (
            PurchaseVoucher.objects
            .filter(retail=retail, date1__gte=month_start, is_return=False)
            .values('ldgr_id', 'ldgr__ac_name')
            .annotate(total=Sum('item_total'))
            .order_by('-total')[:5]
        )
        top_vendors = [
            {
                'ledger_id':   row['ldgr_id'],
                'ledger_name': row['ldgr__ac_name'] or '',
                'total':       float(row['total'] or 0),
            }
            for row in top_vendors_qs
        ]

        return Response({
            'retail': {
                'id':            retail.id,
                'retail_code':   retail.retail_code,
                'retail_name':   retail.retail_name,
                'branch_name':   retail.branch.branch_name if retail.branch else '',
                'active_fy_code': retail.active_fy.fy_code if retail.active_fy else '',
                'is_exhibition': bool(getattr(retail, 'is_exhibition', False)),
            },
            'totals': {
                'today_sales':     float(today_sales_net),
                'month_sales':     float(month_sales_net),
                'today_purchases': float(today_purchases),
                'month_purchases': float(month_purchases),
                'outstanding':     float(outstanding),
                'purchase_orders': int(po_count),
            },
            'top_customers': top_customers,
            'top_vendors':   top_vendors,
        })


class ListCreateTDSSection(ListCreateAPIView):
    serializer_class = TDSSectionMasterSerializer
    queryset = TDSSectionMaster.objects.filter(is_active=True)


class RetrieveUpdateDestroyTDSSection(RetrieveUpdateDestroyAPIView):
    serializer_class = TDSSectionMasterSerializer
    queryset = TDSSectionMaster.objects.all()


class ListCreateTCSSection(ListCreateAPIView):
    serializer_class = TCSSectionMasterSerializer
    queryset = TCSSectionMaster.objects.filter(is_active=True)


class RetrieveUpdateDestroyTCSSection(RetrieveUpdateDestroyAPIView):
    serializer_class = TCSSectionMasterSerializer
    queryset = TCSSectionMaster.objects.all()


# ─────────────────────────────────────────────────────────────────────────────
# CSV Upload Views
# ─────────────────────────────────────────────────────────────────────────────

class HSNCSVUploadView(APIView):
    """POST multipart/form-data with field 'file' (CSV). Upserts HSN records."""
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)

        created = updated = 0
        errors = []
        try:
            decoded = file.read().decode('utf-8-sig')
            with transaction.atomic():
                reader = csv.DictReader(io.StringIO(decoded))
                for i, row in enumerate(reader, start=2):
                    try:
                        hsn_no = row.get('hsn_no', '').strip()
                        if not hsn_no:
                            continue
                        cgst_raw = row.get('hsn_per_cgst', row.get('cgst', '0')).strip() or '0'
                        igst_raw = row.get('hsn_per_igst', row.get('igst', '0')).strip() or '0'
                        hsn_type = row.get('hsn_type', 'GD').strip()
                        if hsn_type not in ('GD', 'SR'):
                            hsn_type = 'GD'
                        obj, flag = Hsn.objects.update_or_create(
                            hsn_no=hsn_no,
                            defaults={
                                'cgst': cgst_raw,
                                'sgst': cgst_raw,
                                'igst': igst_raw,
                                'description': (row.get('description', '') or '').strip()[:100],
                                'hsn_type': hsn_type,
                            }
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


class SalespersonCSVUploadView(APIView):
    """POST multipart 'file' (CSV). Upserts SalesPersonMaster, preserving the
    legacy id (sales/customer-order vouchers reference salesperson by id).
    Columns: id, s_name (or salesperson_name), rt_code."""
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)

        created = updated = 0
        errors = []
        retail_map = {r.retail_code: r for r in RetailMaster.objects.all()}
        try:
            decoded = file.read().decode('utf-8-sig')
            with transaction.atomic():
                reader = csv.DictReader(io.StringIO(decoded))
                for i, row in enumerate(reader, start=2):
                    try:
                        sid = (row.get('id') or '').strip()
                        name = (row.get('s_name') or row.get('salesperson_name') or '').strip()
                        if not sid or not name:
                            continue
                        retail = retail_map.get((row.get('rt_code') or '').strip())
                        _, flag = SalesPersonMaster.objects.update_or_create(
                            id=int(float(sid)),
                            defaults={'salesperson_name': name[:100], 'retail': retail},
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


class ItemCSVUploadView(APIView):
    """POST multipart/form-data with field 'file' (CSV). Upserts Item records."""
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)

        created = updated = 0
        errors = []
        try:
            decoded = file.read().decode('utf-8-sig')
            with transaction.atomic():
                reader = csv.DictReader(io.StringIO(decoded))
                for i, row in enumerate(reader, start=2):
                    try:
                        short_code = row.get('short_code', '').strip()
                        if not short_code:
                            continue
                        item_name = (row.get('item_name') or row.get('item') or '').strip()
                        item_type = row.get('item_type', 'O').strip()
                        if item_type not in ('M', 'R', 'S', 'O', 'C'):
                            item_type = 'O'
                        uom = row.get('uom', 'Gm').strip()
                        if uom not in ('Gm', 'Pcs', 'Ct'):
                            uom = 'Gm'
                        hsn_obj = None
                        hsn_val = (row.get('hsn_no') or '').strip()
                        if hsn_val:
                            hsn_obj = Hsn.objects.filter(hsn_no=hsn_val).first()
                            if not hsn_obj and hsn_val.isdigit():
                                hsn_obj = Hsn.objects.filter(pk=int(hsn_val)).first()
                        show_pcs_raw = (row.get('show_in_pcs_report') or '0').strip()
                        show_pcs = show_pcs_raw in ('1', 'true', 'True', 'yes', 'Yes', 'Y')

                        # Resolve purchase_ledger and sale_ledger (required)
                        from contacts.models import Ledger as _Ldgr
                        purchase_ldgr_val = (row.get('purchase_ledger') or '').strip()
                        sale_ldgr_val = (row.get('sale_ledger') or '').strip()
                        purchase_ldgr_obj = None
                        sale_ldgr_obj = None
                        if purchase_ldgr_val:
                            purchase_ldgr_obj = _Ldgr.objects.filter(ac_name=purchase_ldgr_val).first()
                            if not purchase_ldgr_obj and purchase_ldgr_val.isdigit():
                                purchase_ldgr_obj = _Ldgr.objects.filter(pk=int(purchase_ldgr_val)).first()
                        if sale_ldgr_val:
                            sale_ldgr_obj = _Ldgr.objects.filter(ac_name=sale_ldgr_val).first()
                            if not sale_ldgr_obj and sale_ldgr_val.isdigit():
                                sale_ldgr_obj = _Ldgr.objects.filter(pk=int(sale_ldgr_val)).first()

                        # Warn if a ledger name was supplied but not found in DB
                        if purchase_ldgr_val and not purchase_ldgr_obj:
                            errors.append(f"Row {i}: purchase_ledger '{purchase_ldgr_val}' not found — ledger not assigned for '{short_code}'.")
                        if sale_ldgr_val and not sale_ldgr_obj:
                            errors.append(f"Row {i}: sale_ledger '{sale_ldgr_val}' not found — ledger not assigned for '{short_code}'.")

                        # For new items, purchase_ledger and sale_ledger are required
                        is_existing = Item.objects.filter(short_code=short_code).exists()
                        if not is_existing:
                            if not purchase_ldgr_obj:
                                errors.append(f"Row {i}: purchase_ledger is required for new item '{short_code}'.")
                                continue
                            if not sale_ldgr_obj:
                                errors.append(f"Row {i}: sale_ledger is required for new item '{short_code}'.")
                                continue

                        # Resolve item group
                        grp_obj = None
                        grp_val = (row.get('grp') or '').strip()
                        if grp_val.isdigit():
                            grp_obj = ItemGroupMaster.objects.filter(pk=int(grp_val)).first()
                        if not grp_obj and grp_val:
                            # fallback: match by short_code or name
                            grp_obj = ItemGroupMaster.objects.filter(short_code=grp_val).first()
                            if not grp_obj:
                                grp_obj = ItemGroupMaster.objects.filter(item_group_name=grp_val).first()

                        defaults = {
                            'item_name': item_name,
                            'item_type': item_type,
                            'uom': uom,
                            'hsn_no': hsn_obj,
                            'show_in_pcs_report': show_pcs,
                            'sub_grp': '',
                        }
                        if grp_obj:
                            defaults['grp'] = grp_obj
                        elif grp_val:
                            errors.append(f"Row {i}: item group '{grp_val}' not found — group not assigned for '{short_code}'.")
                        if purchase_ldgr_obj:
                            defaults['purchase_ledger'] = purchase_ldgr_obj
                        if sale_ldgr_obj:
                            defaults['sale_ledger'] = sale_ldgr_obj
                        # Preserve MySQL id as Django pk so packet master stone_id lookup works
                        mysql_id_val = (row.get('id') or row.get('item_id') or '').strip()
                        if mysql_id_val.isdigit():
                            mysql_id = int(mysql_id_val)
                            # If item already exists with this short_code but wrong pk, delete it first
                            Item.objects.filter(short_code=short_code).exclude(pk=mysql_id).delete()
                            obj, flag = Item.objects.update_or_create(
                                pk=mysql_id,
                                defaults={**defaults, 'short_code': short_code}
                            )
                        else:
                            obj, flag = Item.objects.update_or_create(
                                short_code=short_code,
                                defaults=defaults
                            )
                        if flag:
                            created += 1
                        else:
                            updated += 1
                    except Exception as e:
                        errors.append(f"Row {i}: {str(e)}")
        except Exception as e:
            return Response({'error': str(e)}, status=400)

        # Reset SQLite auto-increment so next auto-generated pk starts after max existing pk
        try:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE sqlite_sequence SET seq = (SELECT MAX(id) FROM item_master) WHERE name = 'item_master'")
        except Exception:
            pass  # Non-critical; only matters for future auto-generated rows

        return Response({'created': created, 'updated': updated, 'errors': errors})


class PacketGroupCSVUploadView(APIView):
    """POST multipart/form-data with field 'file' (CSV). Upserts PacketGroup records."""
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)

        created = updated = 0
        errors = []
        try:
            decoded = file.read().decode('utf-8-sig')
            with transaction.atomic():
                reader = csv.DictReader(io.StringIO(decoded))
                for i, row in enumerate(reader, start=2):
                    try:
                        name = (row.get('packet_group') or row.get('packet_group_name') or '').strip()
                        if not name:
                            continue
                        obj, flag = PacketGroup.objects.update_or_create(
                            packet_group_name=name,
                            defaults={}
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


class PacketCSVUploadView(APIView):
    """POST multipart/form-data with field 'file' (CSV). Upserts Packet records.
    Stone_id can be: MySQL item_master.id (numeric) or Item.short_code (string)
    If numeric, queries MySQL to map id → short_code for reliable lookup.
    """
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)

        # Item CSV preserves MySQL id as Django pk, so stone_id = Item.pk directly.

        created = updated = 0
        errors = []
        try:
            decoded = file.read().decode('utf-8-sig')
            with transaction.atomic():
                reader = csv.DictReader(io.StringIO(decoded))
                for i, row in enumerate(reader, start=2):
                    try:
                        pckt_no = (row.get('pckt_no') or '').strip()
                        if not pckt_no:
                            continue
                        stone_item = None
                        stone_val = (row.get('stone_id') or row.get('stone_item_id') or '').strip()
                        if stone_val:
                            if stone_val.isdigit():
                                # stone_id = MySQL item_master.id = Django Item.pk (preserved on import)
                                stone_item = Item.objects.filter(pk=int(stone_val)).first()
                            if not stone_item:
                                stone_item = Item.objects.filter(short_code=stone_val).first()

                        is_solitaire = (row.get('solitare') or row.get('is_solitaire') or 'N').strip().upper() in ('Y', '1', 'TRUE', 'YES')
                        is_customer = (row.get('customer') or row.get('is_customer_stone') or '0').strip() in ('1', 'Y', 'true', 'True', 'YES')

                        packet_group_name = (row.get('packet_group') or '').strip()
                        packet_group_obj = None
                        if packet_group_name:
                            packet_group_obj = PacketGroup.objects.filter(packet_group_name=packet_group_name).first()

                        # Resolve color by name
                        color_val = (row.get('color') or '').strip()
                        color_obj = None
                        if color_val:
                            if color_val.isdigit():
                                color_obj = Colors.objects.filter(pk=int(color_val)).first()
                            if not color_obj:
                                color_obj = Colors.objects.filter(color_name__iexact=color_val).first()

                        # Resolve shape by name
                        shape_val = (row.get('shape') or '').strip()
                        shape_obj = None
                        if shape_val:
                            if shape_val.isdigit():
                                shape_obj = Shapes.objects.filter(pk=int(shape_val)).first()
                            if not shape_obj:
                                shape_obj = Shapes.objects.filter(shape_name__iexact=shape_val).first()

                        defaults = {
                            'stone_item_id': stone_item,
                            'rate_for_retail': int(float(row.get('rate_for_retail') or 0)),
                            'rate_for_wholesale': int(float(row.get('rate_for_wholesale') or 0)) or None,
                            'is_solitaire': is_solitaire,
                            'is_customer_stone': is_customer,
                            'packet_group': packet_group_obj,
                            'cut': (row.get('cut') or '').strip() or None,
                            'clarity': (row.get('clarity') or '').strip() or None,
                            'sieve_max': (row.get('sieve_max') or row.get('seives') or row.get('sieve') or '').strip() or None,
                            'sieve_min': (row.get('sieve_min') or '').strip() or None,
                            'ct_min': row.get('ct_min') or None,
                            'ct_max': row.get('ct_max') or None,
                            'color': color_obj,
                            'shape': shape_obj,
                            'op_stock_wtd_avg_rate': row.get('op_stock_wtd_avg_rate') or row.get('op_rate') or '0',
                        }
                        # Preserve MySQL id as Django pk
                        mysql_id_val = (row.get('id') or '').strip()
                        if mysql_id_val.isdigit():
                            mysql_id = int(mysql_id_val)
                            Packet.objects.filter(pckt_no=pckt_no).exclude(pk=mysql_id).delete()
                            obj, flag = Packet.objects.update_or_create(
                                pk=mysql_id,
                                defaults={**defaults, 'pckt_no': pckt_no}
                            )
                        else:
                            obj, flag = Packet.objects.update_or_create(
                                pckt_no=pckt_no,
                                defaults=defaults
                            )
                        if flag:
                            created += 1
                        else:
                            updated += 1
                    except Exception as e:
                        errors.append(f"Row {i}: {str(e)}")
        except Exception as e:
            return Response({'error': str(e)}, status=400)

        # Reset SQLite auto-increment so next auto-generated pk starts after max existing pk
        try:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE sqlite_sequence SET seq = (SELECT MAX(id) FROM packet_master) WHERE name = 'packet_master'")
        except Exception:
            pass

        return Response({'created': created, 'updated': updated, 'errors': errors})


class ItemGroupCSVUploadView(APIView):
    """POST multipart/form-data with field 'file' (CSV). Upserts ItemGroupMaster records.
    Expected columns: id, name (or item_group_name), short_code
    The 'id' column is preserved as the Django pk so that item master grp references match.
    """
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)

        created = updated = 0
        errors = []
        try:
            decoded = file.read().decode('utf-8-sig')
            with transaction.atomic():
                reader = csv.DictReader(io.StringIO(decoded))
                for i, row in enumerate(reader, start=2):
                    try:
                        short_code = (row.get('short_code') or '').strip()
                        name = (row.get('item_group_name') or row.get('name') or '').strip()
                        if not short_code and not name:
                            continue
                        defaults = {'item_group_name': name[:20], 'short_code': short_code}
                        mysql_id_val = (row.get('id') or '').strip()
                        if mysql_id_val.isdigit():
                            mysql_id = int(mysql_id_val)
                            # Remove any conflicting record with same short_code but different pk
                            ItemGroupMaster.objects.filter(short_code=short_code).exclude(pk=mysql_id).delete()
                            obj, flag = ItemGroupMaster.objects.update_or_create(
                                pk=mysql_id,
                                defaults=defaults,
                            )
                        else:
                            obj, flag = ItemGroupMaster.objects.update_or_create(
                                short_code=short_code,
                                defaults={'item_group_name': name[:20]},
                            )
                        if flag:
                            created += 1
                        else:
                            updated += 1
                    except Exception as e:
                        errors.append(f"Row {i}: {str(e)}")

            # Reset SQLite auto-increment so future auto-generated pks start after max existing
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE sqlite_sequence SET seq = (SELECT MAX(id) FROM item_group_master)"
                        " WHERE name = 'item_group_master'"
                    )
            except Exception:
                pass

        except Exception as e:
            return Response({'error': str(e)}, status=400)

        return Response({'created': created, 'updated': updated, 'errors': errors})


# ─────────────────────────────────────────────────────────────────────────────
# MySQL Sync View
# ─────────────────────────────────────────────────────────────────────────────

class MySQLSyncView(APIView):
    """
    GET  /mastersconfig/api/mysql-sync/  — return saved connection config (password omitted)
    POST /mastersconfig/api/mysql-sync/  — save connection details and run sync
    Body: {
        "host": "...", "port": 3306, "database": "...", "user": "...", "password": "...",
        "tables": ["hsn", "item", "packet_group", "packet"]   (optional)
    }
    Connection details are persisted to SystemSettings so they only need to be entered once.
    """

    def get(self, request):
        from .models import SystemSettings
        saved = SystemSettings.get().mysql_sync_config or {}
        fallback = getattr(settings, 'MYSQL_SYNC_CONFIG', {})
        return Response({
            'host':     saved.get('host')     or fallback.get('host', ''),
            'port':     saved.get('port')     or fallback.get('port', 3306),
            'database': saved.get('database') or fallback.get('database', ''),
            'user':     saved.get('user')     or fallback.get('user', ''),
            'password': saved.get('password') or fallback.get('password', ''),
        })

    def post(self, request):
        try:
            import pymysql
        except ImportError:
            return Response(
                {'error': 'pymysql is not installed. Run: pip install pymysql'},
                status=500
            )

        from .models import SystemSettings

        # Build config: request body takes precedence, then saved DB config, then settings.py
        body = request.data
        saved = SystemSettings.get().mysql_sync_config or {}
        fallback = getattr(settings, 'MYSQL_SYNC_CONFIG', {})

        # Honor an explicitly-provided password even when blank: a MySQL whose
        # root has no password must be able to override a previously-saved (or
        # settings) password. Only fall back when the field is absent entirely.
        if 'password' in body:
            _password = body.get('password') or ''
        else:
            _password = saved.get('password') or fallback.get('password', '')
        cfg = {
            'host':     body.get('host')     or saved.get('host')     or fallback.get('host', '127.0.0.1'),
            'port':     int(body.get('port') or saved.get('port')     or fallback.get('port', 3306)),
            'user':     body.get('user')     or saved.get('user')     or fallback.get('user', 'root'),
            'password': _password,
            'database': body.get('database') or saved.get('database') or fallback.get('database', ''),
            'charset':  'utf8mb4',
        }

        if not cfg['database']:
            return Response({'error': 'Database name is required'}, status=400)

        # Persist updated config to SystemSettings
        ss = SystemSettings.get()
        ss.mysql_sync_config = {k: v for k, v in cfg.items() if k != 'charset'}
        ss.save(update_fields=['mysql_sync_config'])

        tables_requested = body.get('tables', ['hsn', 'item', 'packet_group', 'packet'])
        results = {}

        try:
            conn = pymysql.connect(
                host=cfg['host'],
                port=cfg['port'],
                user=cfg['user'],
                password=cfg['password'],
                database=cfg['database'],
                charset=cfg['charset'],
                cursorclass=pymysql.cursors.DictCursor,
            )
        except Exception as e:
            return Response({'error': f'MySQL connection failed: {str(e)}'}, status=500)

        try:
            with conn:
                cursor = conn.cursor()

                if 'hsn' in tables_requested:
                    results['hsn'] = self._sync_hsn(cursor)

                if 'item' in tables_requested:
                    results['item'] = self._sync_item(cursor)

                if 'packet_group' in tables_requested:
                    results['packet_group'] = self._sync_packet_group(cursor)

                if 'packet' in tables_requested:
                    results['packet'] = self._sync_packet(cursor)

                if 'salesperson' in tables_requested:
                    results['salesperson'] = self._sync_salesperson(cursor)

                if 'ledger' in tables_requested:
                    results['ledger'] = self._sync_ledger(cursor)

                if 'retail' in tables_requested:
                    results['retail'] = self._sync_retail(cursor)

                # customer_orders first (barcode order_no -> customer_order link),
                # then barcodes (purchases below set barcode.pur_voucher).
                if 'customer_orders' in tables_requested:
                    results['customer_orders'] = self._sync_transaction(cursor, 'customer_orders')
                if 'barcode' in tables_requested:
                    results['barcode'] = self._sync_barcodes(cursor)

                for _tx_key in ('ledger_opening', 'gl_vouchers', 'sales', 'purchases', 'allocations'):
                    if _tx_key in tables_requested:
                        results[_tx_key] = self._sync_transaction(cursor, _tx_key)

        except Exception as e:
            return Response({'error': f'Sync failed: {str(e)}'}, status=500)

        return Response({'status': 'ok', 'results': results})

    def _sync_ledger(self, cursor):
        """Sync legacy account hierarchy (main_group/group_master/subgroup_master)
        into Account, and ledger_master into Ledger + LedgerRole. Legacy ledger id
        is preserved as the Django PK (so transactional imports resolve ldgr=id).
        Role is inferred intelligently: ledger_type if known, else the group name
        / ledger name. App-created system ledgers are never overwritten."""
        from contacts.models import Ledger, LedgerRole, LedgerAlias
        from accounting.models import Account
        import re as _re

        def _norm(name):
            """Normalize a ledger name for matching: lowercase, collapse spaces."""
            return _re.sub(r'\s+', ' ', _s(name)).strip().lower()

        def _rows(table):
            try:
                cursor.execute(f"SELECT * FROM {table}")
            except Exception:
                return []
            return cursor.fetchall()

        def _s(v):
            return '' if v is None else str(v).strip()

        def _pick(row, *keys):
            """First non-empty value among candidate column names (case-insensitive)."""
            lower = {str(k).lower(): v for k, v in row.items()}
            for k in keys:
                val = _s(lower.get(k.lower()))
                if val:
                    return val
            return ''

        def _int(v):
            """Parse an int from values that may arrive as float ('5.0'), str or int."""
            s = _s(v)
            if not s:
                return None
            try:
                return int(float(s))
            except (ValueError, TypeError):
                return None

        def _sid(v):
            """Clean integer-string id ('5.0' -> '5') for stable hierarchy codes/keys."""
            i = _int(v)
            return '' if i is None else str(i)

        # ── 1. Account hierarchy. Level-prefixed codes avoid cross-level
        #       collisions (Account.code is not unique). ──
        main_by_id, group_by_id = {}, {}
        main_by_name, group_by_name, sub_by_name = {}, {}, {}
        for r in _rows('main_group'):
            sid = _sid(r.get('id'))
            name = _s(r.get('name')) or f"MG-{sid}"
            acc, _ = Account.objects.update_or_create(
                code=f"MG-{sid}", defaults={'name': name, 'parent': None})
            main_by_id[sid] = acc
            main_by_name.setdefault(name.lower(), acc)
        for r in _rows('group_master'):
            sid = _sid(r.get('id'))
            name = _s(r.get('name')) or f"GM-{sid}"
            acc, _ = Account.objects.update_or_create(
                code=f"GM-{sid}",
                defaults={'name': name, 'parent': main_by_id.get(_sid(r.get('mn_grp')))})
            group_by_id[sid] = acc
            group_by_name.setdefault(name.lower(), acc)
        for r in _rows('subgroup_master'):
            sid = _sid(r.get('id'))
            name = _s(r.get('name')) or f"SG-{sid}"
            parent = group_by_id.get(_sid(r.get('grp'))) or main_by_id.get(_sid(r.get('mn_grp')))
            acc, _ = Account.objects.update_or_create(
                code=f"SG-{sid}", defaults={'name': name, 'parent': parent})
            sub_by_name.setdefault(name.lower(), acc)

        # ── 2. Ledgers ──
        rows = _rows('ledger_master')
        if not rows:
            return {'created': 0, 'updated': 0, 'errors': ['ledger_master table not found / empty']}

        # Existing system ledgers keyed by normalized name — legacy ledgers matching
        # these are aliased onto them rather than duplicated. Handles verbatim
        # matches (Round Off, Hallmark Charges, Ornament Sales, Gold Purchase, …).
        system_by_name = {_norm(l.ac_name): l for l in Ledger.objects.filter(is_system=True)}

        # GST registers are GSTIN-prefixed ("{gstin}_Input_CGST"), so they never
        # match legacy names like "INPUT CGST". Map those reliably via GSTINMaster
        # FK links instead. (Uses the first GSTIN; multi-GSTIN setups should review.)
        from mastersconfig.models import GSTINMaster
        _g = GSTINMaster.objects.first()
        if _g:
            for _legacy_name, _fk in (
                ('input cgst', _g.input_cgst_id), ('input sgst', _g.input_sgst_id), ('input igst', _g.input_igst_id),
                ('output cgst', _g.output_cgst_id), ('output sgst', _g.output_sgst_id), ('output igst', _g.output_igst_id),
                ('input cgst rcm', _g.input_cgst_rcm_id), ('input sgst rcm', _g.input_sgst_rcm_id), ('input igst rcm', _g.input_igst_rcm_id),
                ('output cgst rcm', _g.output_cgst_rcm_id), ('output sgst rcm', _g.output_sgst_rcm_id), ('output igst rcm', _g.output_igst_rcm_id),
            ):
                if _fk:
                    system_by_name.setdefault(_legacy_name, Ledger.objects.get(id=_fk))

        # Curated synonyms: legacy ledger name (normalized) -> canonical system
        # ledger name (normalized). Add entries here for seeded ledgers whose
        # legacy name differs from the Django name.
        _SYNONYMS = {
            'round off': 'round off',
            'discount': 'sales discount',
            'hallmark charges': 'hallmark charges',
            'freight charges': 'freight outward',
            'tcs': 'tcs payable u/s 206c1h',
            'tds': 'tds payable',
        }
        for _legacy, _canon in _SYNONYMS.items():
            tgt = system_by_name.get(_norm(_canon))
            if tgt is not None:
                system_by_name.setdefault(_legacy, tgt)

        # Retail cash ledgers: explicit legacy ledger code -> that retail's
        # cash_ldgr. Legacy cash names ("Cash") don't match the Django
        # "R00x_Cash" system ledger, so these must be mapped by code.
        cash_by_code = {}
        for _legacy_code, _rt in (('1422', 'R001'), ('60438', 'R002')):
            _r = RetailMaster.objects.filter(retail_code=_rt).first()
            if _r and _r.cash_ldgr_id:
                cash_by_code[_legacy_code] = _r.cash_ldgr

        created = updated = aliased = 0
        skipped_invalid = skipped_system = 0
        errors = []
        ungrouped = []  # ledgers whose ac_grp didn't resolve to any Account
        for row in rows:
            try:
                # Use the ledger CODE (ldgr_code / ac_code) as the Django PK —
                # this is the value transactional vouchers reference via `ldgr`,
                # NOT ledger_master.id.
                lid = _int(_pick(row, 'ldgr_code', 'ac_code', 'id'))
                ac_name = _pick(row, 'ac_name', 'ledger_name', 'account_name', 'name', 'ledger_display_name')
                if lid is None or not ac_name:
                    skipped_invalid += 1
                    continue

                # Retail cash ledger: alias the legacy cash code onto the
                # retail's cash_ldgr (e.g. 1422 -> R001_Cash, 60438 -> R002_Cash).
                cash_led = cash_by_code.get(str(lid))
                if cash_led is not None:
                    LedgerAlias.objects.update_or_create(
                        legacy_code=str(lid), defaults={'ledger': cash_led})
                    aliased += 1
                    continue

                # Fold legacy ledgers that match an existing system ledger
                # (GST in/out, TCS, TDS, etc.) onto that ledger via an alias —
                # don't create a duplicate. Legacy transactions referencing this
                # code will resolve to the system ledger via resolve_ledger().
                sys_ledger = system_by_name.get(_norm(ac_name))
                if sys_ledger is not None:
                    LedgerAlias.objects.update_or_create(
                        legacy_code=str(lid), defaults={'ledger': sys_ledger})
                    aliased += 1
                    continue

                existing = Ledger.objects.filter(id=lid).first()
                if existing and getattr(existing, 'is_system', False):
                    skipped_system += 1
                    continue  # never clobber app-managed system ledgers

                grp_name = _pick(row, 'ac_grp', 'group_name', 'gr_name')
                ac_group = (sub_by_name.get(grp_name.lower())
                            or group_by_name.get(grp_name.lower())
                            or main_by_name.get(grp_name.lower()))

                defaults = {
                    'ac_name': ac_name[:100],
                    'display_name': (_pick(row, 'ledger_display_name', 'display_name') or ac_name)[:100],
                    'mobile1': _pick(row, 'mobile1', 'mobile', 'telephone')[:20],
                    'add1':    (_pick(row, 'address', 'add1', 'adrs_off') or None),
                    'city':    (_pick(row, 'city') or None),
                    'pincode': (_pick(row, 'pincode') or None),
                    'email':   (_pick(row, 'email') or None),
                    'pan':     (_pick(row, 'pan_no', 'pan', 'panno') or None),
                    'aadhar':  (_pick(row, 'aadhar_no', 'aadhar') or None),
                    'phone1':  (_pick(row, 'phone1', 'phone') or None),
                }
                if ac_group is not None:
                    defaults['ac_group'] = ac_group

                ledger, flag = Ledger.objects.update_or_create(id=lid, defaults=defaults)

                role = self._infer_ledger_role(_pick(row, 'ledger_type', 'type', 'sl_type'), grp_name, ac_name)
                LedgerRole.objects.get_or_create(
                    ledger=ledger, role=role,
                    defaults={'is_primary': not ledger.roles.exists()},
                )

                if ledger.ac_group_id is None:
                    ungrouped.append({'id': lid, 'ac_name': ac_name, 'group': grp_name})

                if flag:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append(f"{row.get('id')}: {e}")
        if created == 0 and updated == 0:
            r0 = rows[0] if rows else {}
            sample = {k: r0.get(k) for k in ('id', 'ac_name', 'ledger_display_name', 'ac_code', 'ledger_type')}
            errors.append(
                f"diagnostic: fetched {len(rows)} ledger_master rows; skipped "
                f"{skipped_invalid} (missing id/name), {skipped_system} (system ledger). "
                f"row0 id={r0.get('id')!r} ac_name={r0.get('ac_name')!r} "
                f"picked_id={_pick(r0, 'id', 'ldgr_id', 'ledger_id')!r} "
                f"picked_name={_pick(r0, 'ac_name', 'ledger_name', 'account_name', 'name', 'ledger_display_name')!r} "
                f"sample={sample}"
            )
        return {
            'created': created, 'updated': updated, 'aliased': aliased, 'errors': errors,
            'ungrouped': ungrouped[:1000], 'ungrouped_count': len(ungrouped),
        }

    def _infer_ledger_role(self, ledger_type, group_name, ac_name):
        """Pick a LedgerRole: trust ledger_type when it's a known code/synonym,
        otherwise infer from the group name and ledger name keywords."""
        DIRECT = {'CO', 'DL', 'KR', 'VD', 'CA', 'BA', 'SC', 'SD', 'REF', 'MLT', 'EXP', 'INC', 'HM', 'OTH'}
        t = (ledger_type or '').strip().upper()
        if t in DIRECT:
            return t
        SYN = {
            'C': 'CO', 'CUST': 'CO', 'CUSTOMER': 'CO', 'D': 'DL', 'DEALER': 'DL',
            'V': 'VD', 'VEND': 'VD', 'VENDOR': 'VD', 'SUPPLIER': 'VD',
            'K': 'KR', 'KARIGAR': 'KR', 'B': 'BA', 'BANK': 'BA', 'CASH': 'CA',
            'E': 'EXP', 'EXPENSE': 'EXP', 'I': 'INC', 'INCOME': 'INC',
        }
        if t in SYN:
            return SYN[t]
        text = f"{group_name} {ac_name}".lower()
        RULES = [
            ('bank', 'BA'), ('cash', 'CA'),
            ('sundry debtor', 'SD'), ('debtor', 'SD'),
            ('sundry creditor', 'SC'), ('creditor', 'SC'),
            ('karigar', 'KR'), ('goldsmith', 'KR'),
            ('refin', 'REF'), ('melt', 'MLT'), ('hallmark', 'HM'),
            ('supplier', 'VD'), ('vendor', 'VD'),
            ('customer', 'CO'), ('dealer', 'DL'),
            ('purchase', 'EXP'), ('expense', 'EXP'), ('charges', 'EXP'),
            ('sales', 'INC'), ('income', 'INC'), ('revenue', 'INC'),
            ('discount received', 'INC'), ('interest received', 'INC'),
        ]
        for kw, role in RULES:
            if kw in text:
                return role
        return 'OTH'

    def _sync_retail(self, cursor):
        """Sync legacy retail_master -> RetailMaster, matched by retail_code.
        Only scalar fields are written; existing FK links (gstin_master, branch,
        active_fy) are preserved. cash_ldgr is set only when the ledger is free."""
        from contacts.models import Ledger
        from .models import State

        rows = None
        for tbl in ('retail_master', 'retail'):
            try:
                cursor.execute(f"SELECT * FROM {tbl}")
            except Exception:
                continue
            rows = cursor.fetchall()
            break
        if rows is None:
            return {'created': 0, 'updated': 0, 'errors': ['retail_master table not found']}

        created = updated = 0
        errors = []
        for row in rows:
            try:
                rt_code = (row.get('rt_code') or '').strip()
                if not rt_code:
                    continue

                # bill_series is unique — fall back to rt_code if taken elsewhere
                bill_series = ((row.get('bill_series') or '').strip() or rt_code)[:20]
                if RetailMaster.objects.filter(bill_series=bill_series).exclude(retail_code=rt_code).exists():
                    bill_series = rt_code[:20]
                defaults = {
                    'retail_name': (row.get('rt_nm') or '').strip() or rt_code,
                    'bill_series': bill_series,
                }
                addr = (row.get('rt_add') or '').strip()
                if addr:
                    defaults['address_line1'] = addr[:100]
                phone = (row.get('rt_ph') or '').strip()
                if phone:
                    defaults['phone'] = phone[:15]
                # email is unique — set only if not already used by another retail
                email = (row.get('rt_email') or '').strip()[:254]
                if email and not RetailMaster.objects.filter(email=email).exclude(retail_code=rt_code).exists():
                    defaults['email'] = email

                # state by name, then by code
                name = (row.get('state_name') or '').strip()
                code = str(row.get('state_code') or '').strip()
                st = State.objects.filter(name__iexact=name).first() if name else None
                if st is None and code and code != '0':
                    st = State.objects.filter(code=code).first()
                if st:
                    defaults['state'] = st

                obj, flag = RetailMaster.objects.update_or_create(
                    retail_code=rt_code, defaults=defaults,
                )

                # cash_ldgr is OneToOne — assign only if resolvable and unused
                ldgr_raw = (str(row.get('ldgr')) if row.get('ldgr') is not None else '').strip()
                try:
                    ledger_id = int(float(ldgr_raw)) if ldgr_raw else None
                except (ValueError, TypeError):
                    ledger_id = None
                if ledger_id is not None and obj.cash_ldgr_id is None:
                    led = Ledger.objects.filter(id=ledger_id).first()
                    if led and not RetailMaster.objects.filter(cash_ldgr=led).exclude(pk=obj.pk).exists():
                        obj.cash_ldgr = led
                        obj.save(update_fields=['cash_ldgr'])

                if flag:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append(f"{row.get('rt_code')}: {e}")
        return {'created': created, 'updated': updated, 'errors': errors}

    def _sync_barcodes(self, cursor):
        """Sync legacy barcode_main + barcode_details via the SAME logic the CSV
        importer uses (inventory.api_views.import_barcode_rows) — so total ->
        total_amount, order_no -> customer_order, voucher_no, etc. behave
        identically for sync and import. Unresolvable rows (bad item/purity/
        retail) are skipped and reported rather than failing the whole batch."""
        from inventory.api_views import import_barcode_rows
        from inventory.csv_parsers import (
            match_item_id, match_purity, match_retail_code, match_packet, BarcodeOpeningCSVError,
        )

        def _s(v):
            return '' if v is None else str(v).strip()

        def _rows(table):
            try:
                cursor.execute(f"SELECT * FROM {table}")
            except Exception:
                return []
            return cursor.fetchall()

        # ── map legacy barcode_main -> CSV import row keys ──
        main_rows, errors, valid_barcodes = [], [], set()
        for i, r in enumerate(_rows('barcode_main'), start=2):
            barcode = _s(r.get('barcode'))
            if not barcode:
                continue
            row = {
                'barcode': barcode,
                'item_id': _s(r.get('item_id')),
                'purity': _s(r.get('purity')),
                'quantity_pieces': _s(r.get('qty')) or '0',
                'gross_weight': _s(r.get('gw')) or '0',
                'net_weight': _s(r.get('nw')) or '0',
                'value': _s(r.get('amount')) or '0',
                'making_value': _s(r.get('making_value')) or '0',
                'total': _s(r.get('total')),
                'other_charges': _s(r.get('making_other')),
                'making_type': _s(r.get('making_type')),
                'huid': _s(r.get('huid')),
                'design_code': _s(r.get('design_code')),
                'retail_code': _s(r.get('rt_code')),
                'order_no': _s(r.get('order_no')),
                'voucher_no': _s(r.get('voucher_no')),
            }
            # Pre-filter so one bad row doesn't fail the whole (all-or-nothing) batch.
            try:
                match_item_id(row['item_id'])
                match_purity(row['purity'])
                match_retail_code(row['retail_code'])
            except BarcodeOpeningCSVError as e:
                errors.append(f"{barcode}: {e}")
                continue
            main_rows.append((i, row))
            valid_barcodes.add(barcode)

        # ── map legacy barcode_details -> CSV details keys (valid barcodes only) ──
        details_rows = []
        for i, r in enumerate(_rows('barcode_details'), start=2):
            barcode = _s(r.get('barcode'))
            if not barcode or barcode not in valid_barcodes:
                continue
            item_id = _s(r.get('item_id'))
            try:
                match_item_id(item_id)
            except BarcodeOpeningCSVError as e:
                errors.append(f"detail {barcode}: {e}")
                continue
            # legacy '0'/blank metal_purity = no metal purity on stone lines
            _mp = _s(r.get('metal_purity'))
            purity = '' if _mp in ('', '0', '0.0', '0.00') else _mp
            # drop an unresolvable packet rather than fail the row
            packet = _s(r.get('packet_id'))
            if packet and packet not in ('0', '0.0'):
                try:
                    match_packet(packet)
                except BarcodeOpeningCSVError:
                    packet = ''
            else:
                packet = ''
            details_rows.append((i, {
                'barcode': barcode,
                'item_id': item_id,
                'purity': purity,
                'quantity_pieces': _s(r.get('qty')) or '0',
                'carat_weight': _s(r.get('ct')) or '0',
                'gross_weight': _s(r.get('gw')) or '0',
                'rate': _s(r.get('rate_stock')) or '0',
                'amount': _s(r.get('amount')) or '0',
                'packet_number': packet,
            }))

        result = import_barcode_rows(main_rows, details_rows, conflict_action='update')
        if not result.get('success'):
            errors = (result.get('errors') or [result.get('error', 'failed')]) + errors
            return {'created': 0, 'updated': 0, 'errors': errors[:50]}
        return {
            'created': result['created'], 'updated': result['updated'],
            'details_created': result.get('details_created', 0),
            'errors': errors[:50],
        }

    # ── Transactional sync — reuses the legacy import_* management commands ────
    # NOTE: legacy table names. sales_vou / purchase_voucher / *_amount are
    # confirmed from the source DB; GL voucher table names (voucher_main /
    # voucher_details) are the assumed names — a wrong/absent name is reported
    # gracefully as "missing legacy table", not a crash.
    _TX_TABLES = {
        'gl_vouchers': ('import_vouchers',
                        {'main': ('voucher_main',),
                         'details': ('voucher_detail', 'voucher_details')},  # legacy uses singular
                        ['main', 'details']),
        'sales':       ('import_sales',
                        {'header': 'sales_vou', 'items': 'sales_vou_main', 'details': 'sales_vou_detail'},
                        ['header', 'items', 'details']),
        'purchases':   ('import_purchases',
                        {'header':  ('stock_inward', 'purchase_voucher'),
                         'items':   ('stock_inward_main', 'purchase_voucher_main'),
                         'details': ('stock_inward_detail', 'purchase_voucher_details')},
                        ['header', 'items', 'details']),
        'customer_orders': ('import_customer_orders',
                            {'header': 'customer_order', 'items': 'customer_order_main'},
                            ['header', 'items']),
        'ledger_opening':  ('import_ledger_opening',
                            {'file': ('ldgr_open_balance',)},
                            ['file']),
        'allocations': ('import_voucher_allocations',
                        {'receive': 'receive_amount', 'payment': 'payment_amount', 'journal': 'journal_amount'},
                        []),
    }

    def _sync_transaction(self, cursor, key):
        """Pull legacy transactional table(s) from MySQL into temp CSVs and run
        the matching import_* command (apply, continue-on-error)."""
        import io as _io, os as _os, shutil as _shutil, tempfile as _tempfile
        import pandas as _pd
        from django.core.management import call_command as _call
        from django.core.management.base import CommandError as _CmdErr

        command, file_map, required = self._TX_TABLES[key]
        tmp = _tempfile.mkdtemp(prefix='mysql_tx_')
        try:
            kwargs = {'apply': True, 'continue_on_error': True, 'report_dir': tmp}
            found = []
            for cmd_kwarg, table_spec in file_map.items():
                candidates = [table_spec] if isinstance(table_spec, str) else list(table_spec)
                rows, used = None, None
                for tbl in candidates:
                    try:
                        cursor.execute(f"SELECT * FROM {tbl}")
                    except Exception:
                        continue  # candidate table absent in this DB
                    rows, used = cursor.fetchall(), tbl
                    break
                if not rows:
                    continue
                path = _os.path.join(tmp, f"{used}.csv")
                _df = _pd.DataFrame(rows)
                # Legacy data can contain NUL bytes / stray CRs in text columns
                # (e.g. a corrupted billno), which the CSV writer cannot escape.
                for _col in _df.select_dtypes(include='object').columns:
                    _df[_col] = _df[_col].map(
                        lambda v: v.replace('\x00', '').replace('\r', '') if isinstance(v, str) else v)
                _df.to_csv(path, index=False)
                kwargs[cmd_kwarg] = path
                found.append(cmd_kwarg)

            missing = [f for f in required if f not in found]
            if missing:
                return {'status': 'error', 'error': f"missing legacy table(s): {', '.join(missing)}"}
            if not found:
                return {'status': 'error', 'error': 'no source tables found / all empty'}

            buf = _io.StringIO()
            try:
                _call(command, stdout=buf, stderr=buf, **kwargs)
            except _CmdErr as e:
                return {'status': 'error', 'error': str(e), 'output': buf.getvalue()}

            reports = {}
            for fn in _os.listdir(tmp):
                if fn.startswith('unresolved') or fn.startswith('imbalanced'):
                    with open(_os.path.join(tmp, fn), encoding='utf-8') as r:
                        reports[fn] = r.read()[:10000]
            return {'status': 'ok', 'output': buf.getvalue(), 'reports': reports}
        finally:
            _shutil.rmtree(tmp, ignore_errors=True)

    def _sync_salesperson(self, cursor):
        """Sync legacy salesperson_master -> SalesPersonMaster, preserving the
        legacy id (sales / customer-order vouchers reference salesperson by id)."""
        try:
            cursor.execute("SELECT id, s_name, rt_code FROM salesperson_master")
        except Exception:
            return {'created': 0, 'updated': 0, 'errors': ['salesperson_master table not found']}
        rows = cursor.fetchall()
        retail_map = {r.retail_code: r for r in RetailMaster.objects.all()}
        created = updated = 0
        errors = []
        for row in rows:
            try:
                sid = (str(row.get('id')) if row.get('id') is not None else '').strip()
                name = (row.get('s_name') or '').strip()
                if not sid or not name:
                    continue
                retail = retail_map.get((row.get('rt_code') or '').strip())
                _, flag = SalesPersonMaster.objects.update_or_create(
                    id=int(float(sid)),
                    defaults={'salesperson_name': name[:100], 'retail': retail},
                )
                if flag:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append(f"{row.get('id')}: {e}")
        return {'created': created, 'updated': updated, 'errors': errors}

    def _sync_hsn(self, cursor):
        cursor.execute("SELECT hsn_no, description, hsn_type, hsn_per_cgst, hsn_per_igst FROM hsn_master")
        rows = cursor.fetchall()
        created = updated = 0
        errors = []
        for row in rows:
            try:
                hsn_no = (row['hsn_no'] or '').strip()
                if not hsn_no:
                    continue
                hsn_type = (row.get('hsn_type') or 'GD').strip()
                if hsn_type not in ('GD', 'SR'):
                    hsn_type = 'GD'
                cgst = row.get('hsn_per_cgst') or 0
                igst = row.get('hsn_per_igst') or 0
                _, flag = Hsn.objects.update_or_create(
                    hsn_no=hsn_no,
                    defaults={
                        'description': (row.get('description') or '').strip()[:100],
                        'hsn_type': hsn_type,
                        'cgst': cgst,
                        'sgst': cgst,
                        'igst': igst,
                    }
                )
                if flag:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append(str(e))
        return {'created': created, 'updated': updated, 'errors': errors}

    def _sync_item(self, cursor):
        # Fetch hsn_master rows to build id→hsn_no mapping
        cursor.execute("SELECT id, hsn_no FROM hsn_master")
        hsn_id_map = {r['id']: r['hsn_no'] for r in cursor.fetchall()}

        cursor.execute("SELECT id, short_code, item, item_type, uom, hsn_no, show_in_pcs_report FROM item_master")
        rows = cursor.fetchall()
        created = updated = 0
        errors = []
        for row in rows:
            try:
                short_code = (row.get('short_code') or '').strip()
                if not short_code:
                    continue
                item_type = (row.get('item_type') or 'O').strip()
                if item_type not in ('M', 'R', 'S', 'O', 'C'):
                    item_type = 'O'
                uom = (row.get('uom') or 'Gm').strip()
                if uom not in ('Gm', 'Pcs', 'Ct'):
                    uom = 'Gm'
                hsn_obj = None
                mysql_hsn_id = row.get('hsn_no')
                if mysql_hsn_id:
                    hsn_no_str = hsn_id_map.get(mysql_hsn_id)
                    if hsn_no_str:
                        hsn_obj = Hsn.objects.filter(hsn_no=hsn_no_str).first()
                show_pcs = bool(row.get('show_in_pcs_report'))
                _, flag = Item.objects.update_or_create(
                    short_code=short_code,
                    defaults={
                        'item_name': (row.get('item') or '').strip(),
                        'item_type': item_type,
                        'uom': uom,
                        'hsn_no': hsn_obj,
                        'show_in_pcs_report': show_pcs,
                        'sub_grp': '',
                    }
                )
                if flag:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append(f"short_code={row.get('short_code')}: {str(e)}")
        return {'created': created, 'updated': updated, 'errors': errors}

    def _sync_packet_group(self, cursor):
        cursor.execute("SELECT packet_group FROM packet_group_master")
        rows = cursor.fetchall()
        created = updated = 0
        errors = []
        for row in rows:
            try:
                name = (row.get('packet_group') or '').strip()
                if not name:
                    continue
                _, flag = PacketGroup.objects.update_or_create(
                    packet_group_name=name,
                    defaults={}
                )
                if flag:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append(str(e))
        return {'created': created, 'updated': updated, 'errors': errors}

    def _sync_packet(self, cursor):
        # Build item id→short_code map from MySQL
        cursor.execute("SELECT id, short_code FROM item_master")
        item_id_map = {r['id']: r['short_code'] for r in cursor.fetchall()}

        cursor.execute("""
            SELECT pm.pckt_no, pm.stone_id, pm.rate_for_retail, pm.rate_for_wholesale,
                   pm.solitare, pm.customer,
                   pgm.packet_group
            FROM packet_master pm
            LEFT JOIN packet_group_master pgm ON pm.packet_group_id = pgm.id
        """)
        rows = cursor.fetchall()
        created = updated = 0
        errors = []
        for row in rows:
            try:
                pckt_no = (row.get('pckt_no') or '').strip()
                if not pckt_no:
                    continue
                stone_item = None
                mysql_stone_id = row.get('stone_id')
                if mysql_stone_id:
                    # Try pk lookup first (direct match if pk sequence is same)
                    stone_item = Item.objects.filter(pk=mysql_stone_id).first()
                    # Fall back to short_code lookup via MySQL id mapping
                    if not stone_item:
                        short_code = item_id_map.get(mysql_stone_id)
                        if short_code:
                            stone_item = Item.objects.filter(short_code=short_code).first()
                is_solitaire = (row.get('solitare') or 'N').upper() == 'Y'
                is_customer = str(row.get('customer') or '0') == '1'
                pg_name = (row.get('packet_group') or '').strip()
                pg_obj = PacketGroup.objects.filter(packet_group_name=pg_name).first() if pg_name else None
                _, flag = Packet.objects.update_or_create(
                    pckt_no=pckt_no,
                    defaults={
                        'stone_item_id': stone_item,
                        'rate_for_retail': int(float(row.get('rate_for_retail') or 0)),
                        'rate_for_wholesale': int(float(row.get('rate_for_wholesale') or 0)) or None,
                        'is_solitaire': is_solitaire,
                        'is_customer_stone': is_customer,
                        'packet_group': pg_obj,
                    }
                )
                if flag:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append(f"pckt_no={row.get('pckt_no')}: {str(e)}")
        return {'created': created, 'updated': updated, 'errors': errors}


# ─────────────────────────────────────────────────────────────────────────────
# Fiscal Year Management
# ─────────────────────────────────────────────────────────────────────────────

class FiscalYearListCreate(ListCreateAPIView):
    """GET: list all FYs for current retail. POST: create a new FY."""
    serializer_class = FiscalYearSerializer
    pagination_class = None

    def get_queryset(self):
        retail = getattr(self.request, 'retail', None)
        if retail is None:
            retail = RetailMaster.objects.first()
        if retail:
            return FiscalYearMaster.objects.filter(retail=retail).order_by('-fy_start')
        return FiscalYearMaster.objects.none()

    def perform_create(self, serializer):
        retail = self.request.retail
        # During setup wizard no X-RETAIL-ID is sent — fall back to the single retail
        if retail is None:
            retail = RetailMaster.objects.first()
        if retail is None:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"retail": "No retail found. Complete the retail setup step first."})
        fy = serializer.save(retail=retail)
        # If this is the first FY for this retail, auto-activate it
        if not retail.active_fy:
            retail.active_fy = fy
            retail.save(update_fields=['active_fy'])
            # Invalidate cached retail so middleware picks up the new active_fy
            cache.delete(f"retail_{retail.retail_code}")


@api_view(['PATCH'])
def set_active_fiscal_year(request, pk):
    """Set a fiscal year as the active one for the current retail."""
    retail = request.retail
    if not retail:
        return Response({"error": "Missing retail context"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        fy = FiscalYearMaster.objects.get(pk=pk, retail=retail)
    except FiscalYearMaster.DoesNotExist:
        return Response({"error": "Fiscal year not found"}, status=status.HTTP_404_NOT_FOUND)

    retail.active_fy = fy
    retail.save(update_fields=['active_fy'])
    # Invalidate cached retail so middleware picks up the new active_fy
    cache.delete(f"retail_{retail.retail_code}")
    return Response(FiscalYearSerializer(fy).data)


@api_view(['PATCH'])
def close_fiscal_year(request, pk):
    """Close a fiscal year. Closed FYs only allow journal entries."""
    retail = request.retail
    if not retail:
        return Response({"error": "Missing retail context"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        fy = FiscalYearMaster.objects.get(pk=pk, retail=retail)
    except FiscalYearMaster.DoesNotExist:
        return Response({"error": "Fiscal year not found"}, status=status.HTTP_404_NOT_FOUND)

    if fy.is_closed:
        return Response({"error": "This fiscal year is already closed"}, status=status.HTTP_400_BAD_REQUEST)

    fy.is_closed = True
    fy.closed_at = timezone.now()
    fy.save(update_fields=['is_closed', 'closed_at'])
    return Response(FiscalYearSerializer(fy).data)


@api_view(['PATCH'])
def reopen_fiscal_year(request, pk):
    """Reopen a closed fiscal year."""
    retail = request.retail
    if not retail:
        return Response({"error": "Missing retail context"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        fy = FiscalYearMaster.objects.get(pk=pk, retail=retail)
    except FiscalYearMaster.DoesNotExist:
        return Response({"error": "Fiscal year not found"}, status=status.HTTP_404_NOT_FOUND)

    if not fy.is_closed:
        return Response({"error": "This fiscal year is not closed"}, status=status.HTTP_400_BAD_REQUEST)

    fy.is_closed = False
    fy.closed_at = None
    fy.save(update_fields=['is_closed', 'closed_at'])
    return Response(FiscalYearSerializer(fy).data)


@api_view(['PATCH'])
def hard_close_fiscal_year(request, pk):
    """Hard-close a fiscal year — absolute lock, no entries of any kind.
    The FY must already be soft-closed first.
    Can be called multiple times (idempotent if already hard-closed)."""
    retail = request.retail
    if not retail:
        return Response({"error": "Missing retail context"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        fy = FiscalYearMaster.objects.get(pk=pk, retail=retail)
    except FiscalYearMaster.DoesNotExist:
        return Response({"error": "Fiscal year not found"}, status=status.HTTP_404_NOT_FOUND)

    if not fy.is_closed:
        return Response(
            {"error": "Soft-close the fiscal year first before hard-closing."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    fy.is_hard_closed = True
    fy.hard_closed_at = timezone.now()
    fy.save(update_fields=['is_hard_closed', 'hard_closed_at'])
    return Response(FiscalYearSerializer(fy).data)


@api_view(['PATCH'])
def reopen_hard_close_fiscal_year(request, pk):
    """Reopen a hard-closed fiscal year so further adjustment entries can be posted.
    After posting, sync opening balances again and hard-close again."""
    retail = request.retail
    if not retail:
        return Response({"error": "Missing retail context"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        fy = FiscalYearMaster.objects.get(pk=pk, retail=retail)
    except FiscalYearMaster.DoesNotExist:
        return Response({"error": "Fiscal year not found"}, status=status.HTTP_404_NOT_FOUND)

    if not fy.is_hard_closed:
        return Response({"error": "This fiscal year is not hard-closed."}, status=status.HTTP_400_BAD_REQUEST)

    fy.is_hard_closed = False
    fy.hard_closed_at = None
    fy.save(update_fields=['is_hard_closed', 'hard_closed_at'])
    return Response(FiscalYearSerializer(fy).data)


@api_view(['POST'])
def sync_opening_balances(request, pk):
    """Compute the closing balance of FY pk and write it as the opening balance
    for the immediately following fiscal year.

    Idempotent — can be called multiple times. Each call overwrites the previous
    sync result for the next FY so the numbers stay current after late adjustments.

    Typical workflow:
      1. Soft-close FY N           (is_closed = True, JRNL entries still allowed)
      2. Post depreciation / interest / audit adjustments as journal entries
      3. POST /sync-opening-balances/  →  copies FY N closing → FY N+1 opening
      4. Hard-close FY N           (is_hard_closed = True)

    If a further adjustment is needed after step 4:
      4b. Reopen hard-close
      4c. Post adjustment journal entry
      4d. Repeat step 3 (sync again)
      4e. Hard-close again
    """
    from decimal import Decimal
    from accounting.models import LedgerOpenBalance, VoucherDetail
    from contacts.models import Ledger

    retail = request.retail
    if not retail:
        return Response({"error": "Missing retail context"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        fy = FiscalYearMaster.objects.get(pk=pk, retail=retail)
    except FiscalYearMaster.DoesNotExist:
        return Response({"error": "Fiscal year not found"}, status=status.HTTP_404_NOT_FOUND)

    # Find the immediately following fiscal year for this retail
    next_fy = (
        FiscalYearMaster.objects
        .filter(retail=retail, fy_start__gt=fy.fy_end)
        .order_by('fy_start')
        .first()
    )
    if not next_fy:
        return Response(
            {"error": f"No fiscal year found after FY {fy.fy_code}. Create the next FY first."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ── Step 1: Opening balance of THIS FY (stored, per acc_year) ─────────────
    ob_qs = (
        LedgerOpenBalance.objects
        .filter(retail=retail, acc_year=fy.fy_code)
        .values('ldgr')
        .annotate(ob=Sum(F('debit') - F('credit')))
    )
    ob_dict = {row['ldgr']: Decimal(str(row['ob'] or 0)) for row in ob_qs}

    # ── Step 2: All transactions WITHIN this FY ────────────────────────────────
    txn_qs = (
        VoucherDetail.objects
        .filter(
            voucher_main__retail=retail,
            voucher_main__date__range=(fy.fy_start, fy.fy_end),
        )
        .values('account')
        .annotate(total=Sum(F('debit') - F('credit')))
    )
    txn_dict = {row['account']: Decimal(str(row['total'] or 0)) for row in txn_qs}

    # ── Step 3: Compute closing balance for every ledger ───────────────────────
    all_ledger_ids = set(ob_dict.keys()) | set(txn_dict.keys())
    new_ob_rows = []
    for ldgr_id in all_ledger_ids:
        closing = ob_dict.get(ldgr_id, Decimal(0)) + txn_dict.get(ldgr_id, Decimal(0))
        if closing == 0:
            continue  # zero-balance ledgers need no opening balance row
        if closing > 0:
            new_ob_rows.append(LedgerOpenBalance(
                ldgr_id=ldgr_id, retail=retail,
                acc_year=next_fy.fy_code,
                debit=float(closing), credit=Decimal('0.00'),
            ))
        else:
            new_ob_rows.append(LedgerOpenBalance(
                ldgr_id=ldgr_id, retail=retail,
                acc_year=next_fy.fy_code,
                debit=0.0, credit=abs(closing),
            ))

    # ── Step 4: Replace previous sync results atomically ──────────────────────
    with transaction.atomic():
        deleted, _ = LedgerOpenBalance.objects.filter(
            retail=retail, acc_year=next_fy.fy_code
        ).delete()
        LedgerOpenBalance.objects.bulk_create(new_ob_rows)
        fy.last_synced_at = timezone.now()
        fy.save(update_fields=['last_synced_at'])

    return Response({
        "message": (
            f"Opening balances for FY {next_fy.fy_code} synced from "
            f"FY {fy.fy_code} closing balance."
        ),
        "source_fy":      fy.fy_code,
        "target_fy":      next_fy.fy_code,
        "synced_ledgers": len(new_ob_rows),
        "replaced_rows":  deleted,
        "synced_at":      fy.last_synced_at,
    })


# ── Exhibition Profile ────────────────────────────────────────────────────────

class ExhibitionListCreate(ListCreateAPIView):
    serializer_class = ExhibitionProfileSerializer

    def get_queryset(self):
        return ExhibitionProfile.objects.filter(
            retail=self.request.retail
        ).select_related('state').order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(retail=self.request.retail)


class ExhibitionDetail(RetrieveUpdateDestroyAPIView):
    serializer_class = ExhibitionProfileSerializer

    def get_queryset(self):
        return ExhibitionProfile.objects.filter(retail=self.request.retail)


@api_view(['POST'])
def activate_exhibition(request, pk):
    """Set this exhibition as active; deactivate all others for this retail."""
    retail = request.retail
    if not retail:
        return Response({'error': 'Missing retail context'}, status=status.HTTP_400_BAD_REQUEST)
    ExhibitionProfile.objects.filter(retail=retail).update(is_active=False)
    updated = ExhibitionProfile.objects.filter(pk=pk, retail=retail).update(is_active=True)
    if not updated:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'status': 'activated'})


@api_view(['POST'])
def deactivate_exhibition(request, pk):
    """Deactivate this exhibition."""
    retail = request.retail
    if not retail:
        return Response({'error': 'Missing retail context'}, status=status.HTTP_400_BAD_REQUEST)
    updated = ExhibitionProfile.objects.filter(pk=pk, retail=retail).update(is_active=False)
    if not updated:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'status': 'deactivated'})


# ── CRM Settings ──────────────────────────────────────────────────────────────

@api_view(['GET', 'PUT', 'PATCH'])
def crm_settings_view(request):
    """Get or update CRM automation settings for the current retail."""
    from mastersconfig.models import CRMSettings
    from mastersconfig.serializers import CRMSettingsSerializer

    retail = request.retail
    settings, _ = CRMSettings.objects.get_or_create(retail=retail)

    if request.method == 'GET':
        return Response(CRMSettingsSerializer(settings).data)

    serializer = CRMSettingsSerializer(settings, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['GET'])
def crm_send_log(request):
    """Return the last 100 CRM send log entries for the current retail."""
    from mastersconfig.models import CRMSendLog
    from mastersconfig.serializers import CRMSendLogSerializer

    logs = CRMSendLog.objects.filter(retail=request.retail)[:100]
    return Response(CRMSendLogSerializer(logs, many=True).data)


@api_view(['POST'])
def crm_test_send(request):
    """
    Immediately trigger the CRM sender for the current retail (for testing).
    Does NOT check the send_time or last_send_date — always fires.
    """
    from mastersconfig.models import CRMSettings
    from contacts.crm_sender import send_occasions_for_retail

    retail = request.retail
    try:
        settings = CRMSettings.objects.get(retail=retail)
    except CRMSettings.DoesNotExist:
        return Response({'error': 'CRM settings not configured'}, status=400)

    if not settings.is_enabled:
        return Response({'error': 'CRM automation is disabled. Enable it first.'}, status=400)

    try:
        send_occasions_for_retail(settings)
        return Response({'status': 'ok', 'message': settings.last_run_status})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


# ── B2B Pricelist CRUD ──────────────────────────────────────────────────────

class ListCreateB2BPricelist(ListCreateAPIView):
    serializer_class = B2BPricelistSerializer
    queryset = B2BPricelist.objects.prefetch_related(
        'tunch_entries', 'making_entries', 'stone_overrides',
    ).all()
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields   = ['name']
    ordering        = ['name']


class RetrieveUpdateDestroyB2BPricelist(RetrieveUpdateDestroyAPIView):
    serializer_class = B2BPricelistSerializer
    queryset = B2BPricelist.objects.prefetch_related(
        'tunch_entries', 'making_entries', 'stone_overrides',
    ).all()


# ── Retail Discount Pricelist ─────────────────────────────────────────────────

class ListCreateRetailDiscountPricelist(ListCreateAPIView):
    serializer_class = RetailDiscountPricelistSerializer
    queryset         = RetailDiscountPricelist.objects.prefetch_related('rules').all()
    filter_backends  = [SearchFilter, OrderingFilter]
    search_fields    = ['name']
    ordering         = ['name']


class RetrieveUpdateDestroyRetailDiscountPricelist(RetrieveUpdateDestroyAPIView):
    serializer_class = RetailDiscountPricelistSerializer
    queryset         = RetailDiscountPricelist.objects.prefetch_related('rules').all()


# ── Sales Offer ───────────────────────────────────────────────────────────────

class ListCreateSalesOffer(ListCreateAPIView):
    serializer_class = SalesOfferSerializer
    queryset         = SalesOffer.objects.prefetch_related('rules').all()
    filter_backends  = [SearchFilter, OrderingFilter]
    search_fields    = ['name']
    ordering         = ['-created_at']


class RetrieveUpdateDestroySalesOffer(RetrieveUpdateDestroyAPIView):
    serializer_class = SalesOfferSerializer
    queryset         = SalesOffer.objects.prefetch_related('rules').all()


@api_view(['GET'])
def active_sales_offer(request):
    """Return the currently active SalesOffer (with rules), or {} if none."""
    offer = SalesOffer.objects.prefetch_related('rules').filter(is_active=True).first()
    if not offer:
        return Response({})
    return Response(SalesOfferSerializer(offer).data)
