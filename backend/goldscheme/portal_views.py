import random

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from contacts.models import Ledger, LedgerRole
from .models import (
    CustomerPortalCredential, CustomerPortalOTP, CustomerPortalToken,
    SchemeEnrollment, SchemePayment,
)
from .portal_auth import PortalTokenAuthentication, IsPortalAuthenticated
from .portal_serializers import (
    PortalRequestOTPSerializer, PortalVerifyOTPSerializer,
    PortalSetPasswordSerializer, PortalPaymentSerializer,
)
from .services.enrollment import check_and_update_maturity
from .services.payment import record_payment
from .services.redemption import get_applicable_benefits


def _find_customer_by_mobile(mobile):
    """Find a customer Ledger by mobile number across all retails.
    Returns the customer Ledger that has a CO role.
    Raises ValueError if multiple customers share the same mobile within a retail.
    """
    candidates = Ledger.objects.filter(
        Q(mobile1=mobile) | Q(mobile2=mobile) | Q(phone1=mobile)
    )
    customer_ids = LedgerRole.objects.filter(
        ledger__in=candidates, role='CO'
    ).values_list('ledger_id', flat=True)
    customers = Ledger.objects.filter(id__in=customer_ids)

    if not customers.exists():
        return None

    # Check for ambiguity: multiple customers with portal credentials sharing the mobile
    portal_customers = customers.filter(portal_credential__is_active=True)
    if portal_customers.count() > 1:
        # Group by retail to give a clearer error
        retail_codes = list(
            portal_customers.values_list('retail_code__retail_code', flat=True).distinct()
        )
        raise ValueError(
            f"Multiple customer accounts are linked to mobile {mobile} "
            f"(retails: {', '.join(str(r) for r in retail_codes)}). "
            f"Please contact the shop to resolve the ambiguity."
        )

    if portal_customers.count() == 1:
        return portal_customers.first()

    # Fallback: return first customer (no portal credentials yet, or single match)
    return customers.first()


def _find_all_customer_ledgers(mobile):
    """Find ALL customer Ledger records matching this mobile across all retails."""
    candidates = Ledger.objects.filter(
        Q(mobile1=mobile) | Q(mobile2=mobile) | Q(phone1=mobile)
    )
    customer_ids = LedgerRole.objects.filter(
        ledger__in=candidates, role='CO'
    ).values_list('ledger_id', flat=True)
    return Ledger.objects.filter(id__in=customer_ids)


# ══════════════════════════════════════════════════════════════════════════════
#  Public Auth Endpoints
# ══════════════════════════════════════════════════════════════════════════════

class PortalRequestOTPView(APIView):
    """POST /goldscheme/api/portal/request-otp/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        ser = PortalRequestOTPSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        mobile = ser.validated_data['mobile'].strip()

        try:
            customer = _find_customer_by_mobile(mobile)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)
        if not customer:
            return Response(
                {'error': 'No customer found with this mobile number.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check portal credential exists
        if not hasattr(customer, 'portal_credential') or not customer.portal_credential.is_active:
            return Response(
                {'error': 'Portal access not set up. Contact the shop to enable portal access.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Delete old unverified OTPs for this mobile
        CustomerPortalOTP.objects.filter(mobile=mobile, is_verified=False).delete()

        # Generate and store OTP
        otp_code = f"{random.randint(100000, 999999)}"
        CustomerPortalOTP.objects.create(
            mobile=mobile, retail=customer.retail_code, otp_code=otp_code,
        )

        # Mock SMS — print to console
        print(f"\n{'='*50}")
        print(f"[PORTAL OTP] Mobile: {mobile} | OTP: {otp_code}")
        print(f"{'='*50}\n")

        return Response({
            'success': True,
            'message': 'OTP sent to your mobile number.',
            'customer_name': customer.ac_name,
        })


class PortalVerifyOTPView(APIView):
    """POST /goldscheme/api/portal/verify-otp/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        ser = PortalVerifyOTPSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        mobile = ser.validated_data['mobile'].strip()

        try:
            customer = _find_customer_by_mobile(mobile)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)
        if not customer:
            return Response({'error': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Find latest unverified OTP
        otp_record = CustomerPortalOTP.objects.filter(
            mobile=mobile, is_verified=False,
        ).order_by('-created_at').first()

        if not otp_record:
            return Response({'error': 'No OTP found. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)

        if otp_record.is_expired:
            otp_record.delete()
            return Response({'error': 'OTP has expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)

        # Brute-force protection
        max_attempts = getattr(settings, 'OTP_MAX_ATTEMPTS', 5)
        otp_record.attempts += 1
        if otp_record.attempts >= max_attempts:
            otp_record.delete()
            return Response(
                {'error': 'Too many failed attempts. Please request a new OTP.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if otp_record.otp_code != ser.validated_data['otp'].strip():
            otp_record.save()
            remaining = max_attempts - otp_record.attempts
            return Response(
                {'error': f'Invalid OTP. {remaining} attempt(s) remaining.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # OTP verified
        otp_record.is_verified = True
        otp_record.save()

        # Verify password
        try:
            credential = customer.portal_credential
        except CustomerPortalCredential.DoesNotExist:
            return Response({'error': 'Portal access not set up.'}, status=status.HTTP_403_FORBIDDEN)

        if not credential.check_password(ser.validated_data['password']):
            return Response({'error': 'Invalid password.'}, status=status.HTTP_401_UNAUTHORIZED)

        # Issue portal token (delete old ones for this mobile)
        CustomerPortalToken.objects.filter(mobile=mobile).delete()
        token = CustomerPortalToken.objects.create(
            ledger=customer, retail=customer.retail_code, mobile=mobile,
        )

        return Response({
            'token': str(token.token),
            'expires_at': token.expires_at.isoformat(),
            'customer_name': customer.ac_name,
            'mobile': mobile,
        })


class PortalSetPasswordView(APIView):
    """POST /goldscheme/api/portal/set-password/ — First-time setup or password reset."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        ser = PortalSetPasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        mobile = ser.validated_data['mobile'].strip()

        try:
            customer = _find_customer_by_mobile(mobile)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)
        if not customer:
            return Response({'error': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Verify OTP
        otp_record = CustomerPortalOTP.objects.filter(
            mobile=mobile, is_verified=False,
        ).order_by('-created_at').first()

        if not otp_record or otp_record.is_expired:
            return Response({'error': 'No valid OTP found.'}, status=status.HTTP_400_BAD_REQUEST)

        if otp_record.otp_code != ser.validated_data['otp'].strip():
            return Response({'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        otp_record.is_verified = True
        otp_record.save()

        # Create or update credential
        credential, _ = CustomerPortalCredential.objects.get_or_create(ledger=customer)
        credential.set_password(ser.validated_data['new_password'])
        credential.is_active = True
        credential.save()

        return Response({'success': True, 'message': 'Password set successfully. You can now log in.'})


# ══════════════════════════════════════════════════════════════════════════════
#  Protected Portal Endpoints
# ══════════════════════════════════════════════════════════════════════════════

class PortalDashboardView(APIView):
    """GET /goldscheme/api/portal/dashboard/ — All enrollments across all retails."""
    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalAuthenticated]

    def get(self, request):
        mobile = request.portal_token.mobile
        # Find all customer ledgers matching this mobile (across retails)
        customer_ledgers = _find_all_customer_ledgers(mobile)

        enrollments = SchemeEnrollment.objects.filter(
            customer__in=customer_ledgers,
        ).select_related('scheme', 'customer', 'retail').order_by('-created_at')

        # Update maturity status
        for e in enrollments:
            if e.status == 'ACTIVE':
                check_and_update_maturity(e)

        data = []
        total_invested = 0
        active_count = 0

        for e in enrollments:
            total_invested += float(e.total_paid)
            if e.status == 'ACTIVE':
                active_count += 1

            benefit = get_applicable_benefits(e)

            data.append({
                'enrollment_no': e.enrollment_no,
                'scheme_name': e.scheme.name,
                'scheme_code': e.scheme.scheme_code,
                'scheme_type': e.scheme.scheme_type,
                'status': e.status,
                'start_date': str(e.start_date),
                'maturity_date': str(e.maturity_date),
                'installment_amount': float(e.installment_amount),
                'total_paid': float(e.total_paid),
                'payments_made': e.payments_made,
                'remaining_installments': e.remaining_installments,
                'gold_accumulated_wt': float(e.gold_accumulated_wt),
                'months_completed': e.months_completed,
                'benefit': benefit,
                'shop': e.retail.retail_code if e.retail else '',
            })

        customer_name = request.portal_customer.ac_name

        return Response({
            'customer_name': customer_name,
            'summary': {
                'total_schemes': len(data),
                'active_schemes': active_count,
                'total_invested': total_invested,
            },
            'enrollments': data,
        })


class PortalEnrollmentDetailView(APIView):
    """GET /goldscheme/api/portal/enrollment/<enrollment_no>/ — Full detail + payments."""
    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalAuthenticated]

    def get(self, request, enrollment_no):
        mobile = request.portal_token.mobile
        customer_ledgers = _find_all_customer_ledgers(mobile)

        try:
            enrollment = SchemeEnrollment.objects.select_related(
                'scheme', 'customer', 'retail'
            ).get(enrollment_no=enrollment_no, customer__in=customer_ledgers)
        except SchemeEnrollment.DoesNotExist:
            return Response({'error': 'Enrollment not found.'}, status=status.HTTP_404_NOT_FOUND)

        check_and_update_maturity(enrollment)

        payments = SchemePayment.objects.filter(enrollment=enrollment).order_by('date')
        benefit = get_applicable_benefits(enrollment)

        payment_data = []
        for p in payments:
            payment_data.append({
                'payment_no': p.payment_no,
                'date': str(p.date),
                'amount': float(p.amount),
                'payment_mode': p.payment_mode,
                'installment_number': p.installment_number,
                'gold_weight_added': float(p.gold_weight_added) if p.gold_weight_added else 0,
                'gold_rate_at_payment': float(p.gold_rate_at_payment) if p.gold_rate_at_payment else 0,
            })

        return Response({
            'enrollment': {
                'enrollment_no': enrollment.enrollment_no,
                'scheme_name': enrollment.scheme.name,
                'scheme_code': enrollment.scheme.scheme_code,
                'scheme_type': enrollment.scheme.scheme_type,
                'status': enrollment.status,
                'start_date': str(enrollment.start_date),
                'maturity_date': str(enrollment.maturity_date),
                'installment_amount': float(enrollment.installment_amount),
                'total_paid': float(enrollment.total_paid),
                'payments_made': enrollment.payments_made,
                'remaining_installments': enrollment.remaining_installments,
                'gold_accumulated_wt': float(enrollment.gold_accumulated_wt),
                'months_completed': enrollment.months_completed,
                'locked_gold_rate': float(enrollment.locked_gold_rate) if enrollment.locked_gold_rate else None,
                'shop': enrollment.retail.retail_code if enrollment.retail else '',
            },
            'payments': payment_data,
            'benefit': benefit,
        })


class PortalPayInstallmentView(APIView):
    """POST /goldscheme/api/portal/pay/ — Mock UPI payment."""
    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalAuthenticated]

    def post(self, request):
        ser = PortalPaymentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        mobile = request.portal_token.mobile
        customer_ledgers = _find_all_customer_ledgers(mobile)

        try:
            enrollment = SchemeEnrollment.objects.select_related('scheme', 'retail').get(
                enrollment_no=ser.validated_data['enrollment_no'],
                customer__in=customer_ledgers,
            )
        except SchemeEnrollment.DoesNotExist:
            return Response({'error': 'Enrollment not found.'}, status=status.HTTP_404_NOT_FOUND)

        if enrollment.status != 'ACTIVE':
            return Response(
                {'error': f'Cannot pay — enrollment status is {enrollment.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use the enrollment's retail for payment context
        retail = enrollment.retail
        request.retail = retail
        request.fiscal_year = getattr(retail, 'active_fy', None)

        # Find a Bank ledger for UPI payments in this enrollment's retail
        bank_ledger_ids = LedgerRole.objects.filter(
            ledger__retail_code=retail, role='BA'
        ).values_list('ledger_id', flat=True)

        # Prefer one with "UPI" in name
        upi_ledger = Ledger.objects.filter(
            id__in=bank_ledger_ids, ac_name__icontains='UPI'
        ).first()

        if not upi_ledger:
            upi_ledger = Ledger.objects.filter(id__in=bank_ledger_ids).first()

        if not upi_ledger:
            return Response(
                {'error': 'UPI payments not configured for this shop. Contact the shop.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = ser.validated_data['amount']
        upi_ref = ser.validated_data.get('upi_reference', '')

        try:
            payment = record_payment(
                enrollment=enrollment,
                amount=amount,
                payment_mode='UPI',
                payment_ledger=upi_ledger,
                remarks=f"Portal UPI payment{f': {upi_ref}' if upi_ref else ''}",
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Refresh enrollment
        enrollment.refresh_from_db()

        return Response({
            'success': True,
            'payment': {
                'payment_no': payment.payment_no,
                'amount': float(payment.amount),
                'date': str(payment.date),
                'installment_number': payment.installment_number,
            },
            'enrollment': {
                'total_paid': float(enrollment.total_paid),
                'payments_made': enrollment.payments_made,
                'remaining_installments': enrollment.remaining_installments,
                'status': enrollment.status,
            },
        })


class PortalLogoutView(APIView):
    """POST /goldscheme/api/portal/logout/ — Delete the portal token."""
    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalAuthenticated]

    def post(self, request):
        request.portal_token.delete()
        return Response({'success': True, 'message': 'Logged out.'})
