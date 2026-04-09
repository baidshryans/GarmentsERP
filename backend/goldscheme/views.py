from datetime import date, datetime

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from contacts.models import Ledger
from mastersconfig.models import SalesPersonMaster
from userauth.views import RetailBaseViewset
from .models import SchemeMaster, SchemeBenefitTier, SchemeEnrollment, SchemePayment
from .serializers import (
    SchemeMasterListSerializer, SchemeMasterWriteSerializer,
    SchemeEnrollmentListSerializer, SchemeEnrollmentCreateSerializer,
    SchemePaymentListSerializer, SchemePaymentCreateSerializer,
    SchemeBenefitTierSerializer,
)
from .services.enrollment import create_enrollment, check_and_update_maturity
from .services.payment import record_payment
from .services.redemption import get_applicable_benefits, redeem_enrollment, cancel_enrollment
from .services import reports


# ══════════════════════════════════════════════════════════════════════════════
#  Scheme Master CRUD
# ══════════════════════════════════════════════════════════════════════════════

class SchemeMasterViewSet(RetailBaseViewset):
    queryset = SchemeMaster.objects.all()
    serializer_class = SchemeMasterListSerializer
    filterset_fields = ['scheme_type', 'is_active']
    search_fields = ['name', 'scheme_code']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return SchemeMasterWriteSerializer
        return SchemeMasterListSerializer


# ══════════════════════════════════════════════════════════════════════════════
#  Enrollment CRUD + Actions
# ══════════════════════════════════════════════════════════════════════════════

class SchemeEnrollmentViewSet(RetailBaseViewset):
    queryset = SchemeEnrollment.objects.select_related('customer', 'scheme', 'salesperson')
    serializer_class = SchemeEnrollmentListSerializer
    filterset_fields = ['status', 'scheme', 'customer']
    search_fields = ['enrollment_no', 'customer__ac_name']

    def create(self, request, *args, **kwargs):
        ser = SchemeEnrollmentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        retail = request.retail
        scheme = ser.validated_data['scheme']
        customer = get_object_or_404(Ledger, pk=ser.validated_data['customer'], retail_code=retail)
        amount = ser.validated_data['installment_amount']

        salesperson = None
        sp_id = ser.validated_data.get('salesperson')
        if sp_id:
            salesperson = get_object_or_404(SalesPersonMaster, pk=sp_id)

        try:
            enrollment = create_enrollment(
                scheme=scheme,
                customer=customer,
                amount=amount,
                retail=retail,
                fiscal_year=request.fiscal_year,
                salesperson=salesperson,
                remarks=ser.validated_data.get('remarks', ''),
                start_date=ser.validated_data.get('start_date'),
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            SchemeEnrollmentListSerializer(enrollment).data,
            status=status.HTTP_201_CREATED,
        )

    # ── Pay action ────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """POST /api/enrollments/{id}/pay/ — Record an installment payment."""
        enrollment = self.get_object()
        ser = SchemePaymentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        payment_ledger = get_object_or_404(
            Ledger, pk=ser.validated_data['payment_ledger'], retail_code=request.retail
        )

        try:
            payment = record_payment(
                enrollment=enrollment,
                amount=ser.validated_data['amount'],
                payment_mode=ser.validated_data['payment_mode'],
                payment_ledger=payment_ledger,
                payment_date=ser.validated_data.get('date'),
                remarks=ser.validated_data.get('remarks', ''),
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(SchemePaymentListSerializer(payment).data, status=status.HTTP_201_CREATED)

    # ── Statement ─────────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'])
    def statement(self, request, pk=None):
        """GET /api/enrollments/{id}/statement/ — Full payment history."""
        enrollment = self.get_object()
        check_and_update_maturity(enrollment)

        payments = SchemePayment.objects.filter(enrollment=enrollment).order_by('date')
        return Response({
            'enrollment': SchemeEnrollmentListSerializer(enrollment).data,
            'payments': SchemePaymentListSerializer(payments, many=True).data,
        })

    # ── Benefit check ─────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'])
    def benefit(self, request, pk=None):
        """GET /api/enrollments/{id}/benefit/ — Check current applicable benefit."""
        enrollment = self.get_object()
        return Response(get_applicable_benefits(enrollment))

    # ── Redeem ────────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def redeem(self, request, pk=None):
        """POST /api/enrollments/{id}/redeem/ — Mark as redeemed."""
        enrollment = self.get_object()
        lc_discount = request.data.get('lc_discount_applied', 0)
        value_discount = request.data.get('value_discount_applied', 0)
        sales_vou_id = request.data.get('sales_vou_id')

        from sales.models import SalesVou
        sales_vou = None
        if sales_vou_id:
            sales_vou = get_object_or_404(SalesVou, pk=sales_vou_id)

        try:
            enrollment = redeem_enrollment(
                enrollment,
                sales_vou=sales_vou,
                lc_discount_amount=lc_discount,
                value_discount_amount=value_discount,
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(SchemeEnrollmentListSerializer(enrollment).data)

    # ── Cancel ────────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """POST /api/enrollments/{id}/cancel/ — Cancel enrollment."""
        enrollment = self.get_object()
        reason = request.data.get('reason', '')

        try:
            enrollment = cancel_enrollment(enrollment, reason=reason)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(SchemeEnrollmentListSerializer(enrollment).data)


# ══════════════════════════════════════════════════════════════════════════════
#  Payment list (read-only, for viewing all payments across enrollments)
# ══════════════════════════════════════════════════════════════════════════════

class SchemePaymentViewSet(RetailBaseViewset):
    queryset = SchemePayment.objects.select_related('enrollment', 'payment_ledger', 'voucher')
    serializer_class = SchemePaymentListSerializer
    filterset_fields = ['enrollment', 'payment_mode', 'date']
    search_fields = ['payment_no', 'enrollment__enrollment_no']
    http_method_names = ['get', 'head', 'options']  # Read-only


# ══════════════════════════════════════════════════════════════════════════════
#  Reports
# ══════════════════════════════════════════════════════════════════════════════

class SchemeSummaryView(APIView):
    """GET /api/reports/scheme-summary/ — Dashboard KPIs."""
    def get(self, request):
        retail = request.retail
        if not retail:
            return Response({'error': 'Retail not found.'}, status=400)
        return Response(reports.scheme_summary(retail))


class MaturityCalendarView(APIView):
    """GET /api/reports/maturity-calendar/?from_date=...&to_date=..."""
    def get(self, request):
        retail = request.retail
        if not retail:
            return Response({'error': 'Retail not found.'}, status=400)

        from_date = request.GET.get('from_date', str(date.today()))
        to_date = request.GET.get('to_date')
        if not to_date:
            to_date = str(date.today().replace(day=1).replace(month=date.today().month % 12 + 1))

        return Response(reports.maturity_calendar(retail, from_date, to_date))


class OverduePaymentsView(APIView):
    """GET /api/reports/overdue-payments/"""
    def get(self, request):
        retail = request.retail
        if not retail:
            return Response({'error': 'Retail not found.'}, status=400)
        return Response(reports.overdue_payments(retail))


class SchemeCollectionView(APIView):
    """GET /api/reports/scheme-collection/?from_date=...&to_date=..."""
    def get(self, request):
        retail = request.retail
        if not retail:
            return Response({'error': 'Retail not found.'}, status=400)

        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        data = reports.scheme_wise_collection(retail, from_date, to_date)
        # Convert Decimals for JSON
        for item in data:
            for k, v in item.items():
                if hasattr(v, 'quantize'):
                    item[k] = float(v)
        return Response(data)


# ══════════════════════════════════════════════════════════════════════════════
#  Customer Portal  (public endpoints — no retail session needed)
#  Authentication: enrollment_no + mobile number
# ══════════════════════════════════════════════════════════════════════════════

class CustomerPortalMySchemes(APIView):
    """
    GET /api/customer-portal/my-schemes/?mobile=9999999999&retail_code=R001
    Returns all enrollments for the customer identified by their mobile number.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        mobile = request.GET.get('mobile', '').strip()
        retail_code = request.GET.get('retail_code', '').strip()

        if not mobile or not retail_code:
            return Response({'error': 'mobile and retail_code are required.'}, status=400)

        from mastersconfig.models import RetailMaster
        try:
            retail = RetailMaster.objects.get(retail_code=retail_code)
        except RetailMaster.DoesNotExist:
            return Response({'error': 'Invalid retail_code.'}, status=404)

        # Find customer ledger(s) matching this mobile
        customers = Ledger.objects.filter(
            retail_code=retail,
            mobile1=mobile,
        )
        if not customers.exists():
            # Try other mobile fields
            from django.db.models import Q
            customers = Ledger.objects.filter(
                retail_code=retail,
            ).filter(Q(mobile1=mobile) | Q(mobile2=mobile) | Q(phone1=mobile))

        if not customers.exists():
            return Response({'error': 'No customer found with this mobile number.'}, status=404)

        enrollments = SchemeEnrollment.objects.filter(
            customer__in=customers,
            retail=retail,
        ).select_related('scheme', 'customer').order_by('-created_at')

        data = []
        for e in enrollments:
            data.append({
                'enrollment_no': e.enrollment_no,
                'scheme_name': e.scheme.name,
                'scheme_type': e.scheme_type,
                'status': e.status,
                'start_date': str(e.start_date),
                'maturity_date': str(e.maturity_date),
                'installment_amount': float(e.installment_amount),
                'total_paid': float(e.total_paid),
                'payments_made': e.payments_made,
                'gold_accumulated_wt': float(e.gold_accumulated_wt),
            })
        return Response(data)


class CustomerPortalSchemeDetail(APIView):
    """
    GET /api/customer-portal/scheme/{enrollment_no}/?mobile=9999999999
    Returns enrollment details + payment history, verified by customer mobile.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, enrollment_no):
        mobile = request.GET.get('mobile', '').strip()
        if not mobile:
            return Response({'error': 'mobile is required.'}, status=400)

        from django.db.models import Q
        try:
            enrollment = SchemeEnrollment.objects.select_related(
                'scheme', 'customer'
            ).get(enrollment_no=enrollment_no)
        except SchemeEnrollment.DoesNotExist:
            return Response({'error': 'Enrollment not found.'}, status=404)

        # Verify mobile matches the customer
        customer = enrollment.customer
        if mobile not in [customer.mobile1, customer.mobile2, customer.phone1]:
            return Response({'error': 'Mobile number does not match this enrollment.'}, status=403)

        check_and_update_maturity(enrollment)
        payments = SchemePayment.objects.filter(enrollment=enrollment).order_by('date')
        benefits = get_applicable_benefits(enrollment)

        return Response({
            'enrollment': SchemeEnrollmentListSerializer(enrollment).data,
            'payments': SchemePaymentListSerializer(payments, many=True).data,
            'benefits': benefits,
        })
