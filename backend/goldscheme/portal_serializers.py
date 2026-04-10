from decimal import Decimal
from rest_framework import serializers


class PortalRequestOTPSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=20, min_length=10)


class PortalVerifyOTPSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=20, min_length=10)
    password = serializers.CharField(max_length=128)
    otp = serializers.CharField(max_length=6, min_length=4)


class PortalSetPasswordSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=20, min_length=10)
    otp = serializers.CharField(max_length=6, min_length=4)
    new_password = serializers.CharField(max_length=128, min_length=6)


class PortalPaymentSerializer(serializers.Serializer):
    enrollment_no = serializers.CharField(max_length=30)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('1'))
    upi_reference = serializers.CharField(max_length=100, required=False, default='')
