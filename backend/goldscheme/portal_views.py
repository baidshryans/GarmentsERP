import random

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from contacts.models import Ledger, LedgerRole
from contacts.tasks import send_email
from .models import (
    CustomerPortalAccount,
    CustomerPortalCredential, CustomerPortalOTP, CustomerPortalToken,
    SchemeEnrollment, SchemePayment,
)
from .portal_otp import issue_otp, is_throttled
from .portal_auth import PortalTokenAuthentication, IsPortalAuthenticated
from .portal_serializers import (
    PortalRequestOTPSerializer, PortalVerifyOTPSerializer,
    PortalSetPasswordSerializer, PortalPaymentSerializer,
    PortalPasswordLoginSerializer,
)
from .services.enrollment import check_and_update_maturity
from .services.payment import record_payment
from .services.redemption import get_applicable_benefits


def _resolve_account(userid):
    userid = (userid or "").strip()
    if "@" in userid:
        return CustomerPortalAccount.objects.filter(primary_email__iexact=userid, is_active=True).first()
    return CustomerPortalAccount.objects.filter(phone=userid, is_active=True).first()


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
        account = _resolve_account(ser.validated_data['userid'])
        generic = Response({'success': True,
                            'message': 'If an account exists, an OTP has been emailed.'})
        if account is None:
            return generic
        if is_throttled(account):
            return Response({'error': 'Please wait before requesting another OTP.'},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        code = issue_otp(account)
        retail_id = account.linked_ledgers.values_list('retail_code', flat=True).first()
        send_email.enqueue(
            retail_id, account.primary_email, "Your login OTP",
            f"Your one-time password is {code}. It expires in 5 minutes.", "otp",
        )
        return generic


class PortalVerifyOTPView(APIView):
    """POST /goldscheme/api/portal/verify-otp/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        ser = PortalVerifyOTPSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        account = _resolve_account(ser.validated_data['userid'])
        if account is None:
            return Response({'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        otp = CustomerPortalOTP.objects.filter(
            account=account, is_verified=False
        ).order_by('-created_at').first()
        if otp is None or otp.is_expired:
            return Response({'error': 'OTP expired. Please request a new one.'},
                            status=status.HTTP_400_BAD_REQUEST)

        max_attempts = getattr(settings, 'OTP_MAX_ATTEMPTS', 5)
        if not otp.check_code(ser.validated_data['otp'].strip()):
            otp.attempts += 1
            if otp.attempts >= max_attempts:
                otp.delete()
                return Response({'error': 'Too many failed attempts. Request a new OTP.'},
                                status=status.HTTP_429_TOO_MANY_REQUESTS)
            otp.save()
            return Response({'error': f'Invalid OTP. {max_attempts - otp.attempts} attempt(s) left.'},
                            status=status.HTTP_400_BAD_REQUEST)

        otp.delete()
        retail = None
        led = account.linked_ledgers.select_related('retail_code').first()
        if led is not None:
            retail = led.retail_code
        token = CustomerPortalToken.objects.create(account=account, retail=retail)
        return Response({'success': True, 'token': str(token.token),
                         'customer_name': account.primary_email})


class PortalPasswordLoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        ser = PortalPasswordLoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        account = _resolve_account(ser.validated_data['userid'])
        if account is None or not account.check_password(ser.validated_data['password']):
            return Response({'error': 'Invalid credentials.'},
                            status=status.HTTP_401_UNAUTHORIZED)
        led = account.linked_ledgers.select_related('retail_code').first()
        retail = led.retail_code if led is not None else None
        token = CustomerPortalToken.objects.create(account=account, retail=retail)
        return Response({'success': True, 'token': str(token.token),
                         'customer_name': account.primary_email})


class PortalSetPasswordView(APIView):
    """POST /goldscheme/api/portal/set-password/ — First-time setup or password reset."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        ser = PortalSetPasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        account = _resolve_account(ser.validated_data['userid'])
        if account is None:
            return Response({'error': 'Invalid request.'}, status=status.HTTP_400_BAD_REQUEST)
        otp = CustomerPortalOTP.objects.filter(account=account, is_verified=False)\
            .order_by('-created_at').first()
        if otp is None or otp.is_expired or not otp.check_code(ser.validated_data['otp'].strip()):
            return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
        otp.delete()  # single use
        account.set_password(ser.validated_data['new_password'])
        account.is_active = True
        account.email_verified = True
        account.save()
        return Response({'success': True, 'message': 'Password set. You can now log in.'})


class PortalChangePasswordView(APIView):
    """POST /goldscheme/api/portal/change-password/ — Logged-in customer changes password."""
    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalAuthenticated]

    def post(self, request):
        account = request.portal_account
        old = request.data.get('old_password', '')
        new = request.data.get('new_password', '')
        if len(new) < 6:
            return Response({'error': 'New password too short.'}, status=status.HTTP_400_BAD_REQUEST)
        if not account.check_password(old):
            return Response({'error': 'Current password is incorrect.'},
                            status=status.HTTP_400_BAD_REQUEST)
        account.set_password(new); account.save()
        return Response({'success': True, 'message': 'Password changed.'})


# ══════════════════════════════════════════════════════════════════════════════
#  Protected Portal Endpoints
# ══════════════════════════════════════════════════════════════════════════════

class PortalDashboardView(APIView):
    """GET /goldscheme/api/portal/dashboard/ — All enrollments across all retails."""
    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalAuthenticated]

    def get(self, request):
        from .portal_auth import portal_ledgers
        customer_ledgers = portal_ledgers(request)

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

        first_ledger = customer_ledgers.first()
        customer_name = first_ledger.ac_name if first_ledger else ''

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
        from .portal_auth import portal_ledgers
        customer_ledgers = portal_ledgers(request)

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

        from .portal_auth import portal_ledgers
        customer_ledgers = portal_ledgers(request)

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
