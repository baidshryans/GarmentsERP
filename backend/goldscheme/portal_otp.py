import secrets
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from .models import CustomerPortalOTP

OTP_COOLDOWN_SECONDS = getattr(settings, 'OTP_COOLDOWN_SECONDS', 60)
OTP_HOURLY_CAP       = getattr(settings, 'OTP_HOURLY_CAP', 5)


def generate_otp_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def is_throttled(account):
    now = timezone.now()
    recent = CustomerPortalOTP.objects.filter(
        account=account, created_at__gte=now - timedelta(seconds=OTP_COOLDOWN_SECONDS)
    ).exists()
    hourly = CustomerPortalOTP.objects.filter(
        account=account, created_at__gte=now - timedelta(hours=1)
    ).count()
    return recent or hourly >= OTP_HOURLY_CAP


def issue_otp(account):
    """Create a fresh hashed OTP for the account and return the raw code."""
    CustomerPortalOTP.objects.filter(account=account, is_verified=False).delete()
    code = generate_otp_code()
    otp = CustomerPortalOTP(account=account)
    otp.set_code(code)
    otp.save()
    return code
