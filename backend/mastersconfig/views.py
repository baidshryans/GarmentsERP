from django.shortcuts import render, redirect,get_object_or_404
from django.http import HttpResponse
from django.core.cache import cache
from rest_framework.generics import ListCreateAPIView,RetrieveUpdateDestroyAPIView,ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework.decorators import api_view
from rest_framework import status
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
    serializer_class = HSNSerializer
    queryset         = Hsn.objects.all()

class RetrieveUpdateDeleteHsn(RetrieveUpdateDestroyAPIView):
    serializer_class = HSNSerializer
    queryset         = Hsn.objects.all()



#------------------Item-API-------------------------------------------
class ListCreateItem(ListCreateAPIView):
    queryset         = Item.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['hsn_no','item_type']
    pagination_class = None

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ItemWriteSerializer
        return ItemSerializer


class RetrieveUpdateDestroyItem(RetrieveUpdateDestroyAPIView):
    queryset         = Item.objects.all()

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
    queryset         = Packet.objects.all()
    filter_backends = [DjangoFilterBackend,SearchFilter]
    filterset_fields = ['stone_item']
    pagination_class = None

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
        if retail:
            return SalesPersonMaster.objects.filter(retail=retail)
        return SalesPersonMaster.objects.all()

    def perform_create(self, serializer):
        from django.db import transaction
        from contacts.models import Ledger, LedgerRole
        from accounting.models import Account

        retail = getattr(self.request, "retail", None)

        with transaction.atomic():
            # If no ledger was explicitly provided, auto-create a
            # "Sales Commission Payable" ledger under Sundry Creditors
            ledger = serializer.validated_data.get('ledger')
            if not ledger:
                sp_name = serializer.validated_data['salesperson_name']
                ledger_name = f"Commission Payable - {sp_name}"

                sc_group = Account.objects.filter(code='CL-SC').first()

                ledger = Ledger.objects.create(
                    ac_name=ledger_name,
                    display_name=ledger_name,
                    ac_group=sc_group,
                    retail_code=retail,
                    is_system=True,
                )
                LedgerRole.objects.create(
                    ledger=ledger, role='SC', is_primary=True,
                )

            serializer.save(retail=retail, ledger=ledger)

class RetrieveUpdateDestroySalesPersonMaster(RetrieveUpdateDestroyAPIView):
    serializer_class = SalesPersonMasterSerializer
    queryset         = SalesPersonMaster.objects.all()
    

#--------------------------Item Group------------------------------

#--------------------------Item Group-Api------------------------------

class ListCreateItemGroupMaster(ListCreateAPIView):
    serializer_class = ItemGroupMasterSerializer
    queryset         = ItemGroupMaster.objects.all().order_by('id')

class RetrieveUpdateDestroyItemGroupMaster(RetrieveUpdateDestroyAPIView):
    serializer_class = ItemGroupMasterSerializer
    queryset         = ItemGroupMaster.objects.all()

class StateListView(ListAPIView):
    from mastersconfig.serializers import StateSerializer
    serializer_class = StateSerializer
    queryset = State.objects.all().order_by('name')


class RetailMasterView(ListCreateAPIView):
    serializer_class = RetailSerializer
    queryset = RetailMaster.objects.select_related('state', 'active_fy', 'cash_ldgr', 'branch').all()

    def perform_create(self, serializer):
        retail = serializer.save()
        # Auto-assign the new retail to the creating user's UserLocation so
        # it appears immediately in their retail selector dropdown.
        user = self.request.user
        if user and user.is_authenticated:
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

    # Handle non-path fields
    bill_total = request.data.get('bill_total_auto_calc', None)
    if bill_total is not None:
        settings_obj.bill_total_auto_calc = bill_total

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
        from django.db.models import Sum, Q
        import datetime

        today = datetime.date.today()
        month_start = today.replace(day=1)

        # Import transaction models lazily to avoid circular imports
        from sales.models import SalesVou, SaleReturn
        from purchase.models import PurchaseVoucher, PurchaseOrder
        from contacts.models import Ledger

        retail_stats = []
        totals = {
            'today_sales': Decimal('0'),
            'month_sales': Decimal('0'),
            'today_purchases': Decimal('0'),
            'month_purchases': Decimal('0'),
            'outstanding': Decimal('0'),
            'purchase_orders': Decimal('0'),
        }

        for retail in retails:
            # Sales
            today_sales = SalesVou.objects.filter(
                retail=retail, voucher_date=today
            ).aggregate(s=Sum('grand_total'))['s'] or Decimal('0')

            month_sales = SalesVou.objects.filter(
                retail=retail, voucher_date__gte=month_start
            ).aggregate(s=Sum('grand_total'))['s'] or Decimal('0')

            # Sales returns adjustment
            today_sr = SaleReturn.objects.filter(
                retail=retail, voucher_date=today
            ).aggregate(s=Sum('grand_total'))['s'] or Decimal('0')

            month_sr = SaleReturn.objects.filter(
                retail=retail, voucher_date__gte=month_start
            ).aggregate(s=Sum('grand_total'))['s'] or Decimal('0')

            today_sales_net  = today_sales - today_sr
            month_sales_net  = month_sales - month_sr

            # Purchases
            today_purchases = PurchaseVoucher.objects.filter(
                retail=retail, voucher_date=today
            ).aggregate(s=Sum('grand_total'))['s'] or Decimal('0')

            month_purchases = PurchaseVoucher.objects.filter(
                retail=retail, voucher_date__gte=month_start
            ).aggregate(s=Sum('grand_total'))['s'] or Decimal('0')

            # Purchase Orders (open)
            po_value = PurchaseOrder.objects.filter(
                retail=retail, status='open'
            ).aggregate(s=Sum('grand_total'))['s'] or Decimal('0')

            # Outstanding (receivables) — sum of closing balances for debtor ledgers
            try:
                outstanding = Ledger.objects.filter(
                    retail=retail, ac_type='D'
                ).aggregate(s=Sum('closing_balance'))['s'] or Decimal('0')
            except Exception:
                outstanding = Decimal('0')

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
                'purchase_orders':  float(po_value),
            }
            retail_stats.append(stat)

            totals['today_sales']      += today_sales_net
            totals['month_sales']      += month_sales_net
            totals['today_purchases']  += today_purchases
            totals['month_purchases']  += month_purchases
            totals['outstanding']      += outstanding
            totals['purchase_orders']  += po_value

        return Response({
            'branch': {
                'id':          branch.id,
                'branch_name': branch.branch_name,
                'branch_code': branch.branch_code,
                'description': branch.description,
                'retail_count': retails.count(),
            },
            'retails':  retail_stats,
            'totals':   {k: float(v) for k, v in totals.items()},
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

                        # For new items, purchase_ledger and sale_ledger are required
                        is_existing = Item.objects.filter(short_code=short_code).exists()
                        if not is_existing:
                            if not purchase_ldgr_obj:
                                errors.append(f"Row {i}: purchase_ledger is required for new item '{short_code}'.")
                                continue
                            if not sale_ldgr_obj:
                                errors.append(f"Row {i}: sale_ledger is required for new item '{short_code}'.")
                                continue

                        defaults = {
                            'item_name': item_name,
                            'item_type': item_type,
                            'uom': uom,
                            'hsn_no': hsn_obj,
                            'show_in_pcs_report': show_pcs,
                            'sub_grp': '',
                        }
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

                        defaults = {
                            'stone_item_id': stone_item,
                            'rate_for_retail': int(float(row.get('rate_for_retail') or 0)),
                            'rate_for_wholesale': int(float(row.get('rate_for_wholesale') or 0)) or None,
                            'is_solitaire': is_solitaire,
                            'is_customer_stone': is_customer,
                            'packet_group': packet_group_obj,
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
    Expected columns: name (or item_group_name), short_code
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
                        obj, flag = ItemGroupMaster.objects.update_or_create(
                            short_code=short_code,
                            defaults={
                                'item_group_name': name[:20],
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


# ─────────────────────────────────────────────────────────────────────────────
# MySQL Sync View
# ─────────────────────────────────────────────────────────────────────────────

class MySQLSyncView(APIView):
    """
    POST /mastersconfig/api/mysql-sync/
    Body: { "tables": ["hsn", "item", "packet_group", "packet"] }  (optional — all synced if omitted)
    Requires MYSQL_SYNC_CONFIG in settings.py with host/port/user/password/database.
    """

    def post(self, request):
        try:
            import pymysql
        except ImportError:
            return Response(
                {'error': 'pymysql is not installed. Run: pip install pymysql'},
                status=500
            )

        cfg = getattr(settings, 'MYSQL_SYNC_CONFIG', {})
        if not cfg.get('database'):
            return Response(
                {'error': 'MYSQL_SYNC_DB is not configured in settings / environment variables'},
                status=500
            )

        tables_requested = request.data.get('tables', ['hsn', 'item', 'packet_group', 'packet'])
        results = {}

        try:
            conn = pymysql.connect(
                host=cfg['host'],
                port=cfg['port'],
                user=cfg['user'],
                password=cfg['password'],
                database=cfg['database'],
                charset=cfg.get('charset', 'utf8mb4'),
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

        except Exception as e:
            return Response({'error': f'Sync failed: {str(e)}'}, status=500)

        return Response({'status': 'ok', 'results': results})

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
        if retail:
            return FiscalYearMaster.objects.filter(retail=retail).order_by('-fy_start')
        return FiscalYearMaster.objects.none()

    def perform_create(self, serializer):
        retail = self.request.retail
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
