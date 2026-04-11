from django.contrib.auth.models import User
from rest_framework import serializers

from mastersconfig.models import State, SalesPersonMaster

from .models import (
    Employee, SalaryStructure, PayrollDeductionConfig,
    SalarySlip, LeaveBalance, HRSettings,
)


class EmployeeSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    state_name    = serializers.CharField(source='state.state_name', read_only=True, default='')

    class Meta:
        model  = Employee
        fields = '__all__'
        read_only_fields = ('created_at',)


class CreateEmployeeWithUserSerializer(serializers.Serializer):
    # User fields
    username   = serializers.CharField(max_length=150)
    password   = serializers.CharField(write_only=True)
    email      = serializers.EmailField(required=False, default='')
    first_name = serializers.CharField(max_length=150, required=False, default='')
    last_name  = serializers.CharField(max_length=150, required=False, default='')

    # Employee fields
    employee_code   = serializers.CharField(max_length=20)
    full_name       = serializers.CharField(max_length=150)
    designation     = serializers.CharField(max_length=100, required=False, default='')
    department      = serializers.CharField(max_length=100, required=False, default='')
    date_of_joining = serializers.DateField()
    date_of_birth   = serializers.DateField(required=False, allow_null=True, default=None)
    gender          = serializers.ChoiceField(choices=['M', 'F', 'O'], required=False, default='')
    address_line1   = serializers.CharField(max_length=150, required=False, default='')
    address_line2   = serializers.CharField(max_length=150, required=False, default='')
    city            = serializers.CharField(max_length=100, required=False, default='')
    state           = serializers.PrimaryKeyRelatedField(
        queryset=State.objects.all(),
        required=False, allow_null=True, default=None,
    )
    pincode         = serializers.CharField(max_length=10, required=False, default='')
    bank_name       = serializers.CharField(max_length=100, required=False, default='')
    account_no      = serializers.CharField(max_length=30, required=False, default='')
    ifsc_code       = serializers.CharField(max_length=15, required=False, default='')
    pan_number      = serializers.CharField(max_length=10, required=False, default='')
    pf_number       = serializers.CharField(max_length=25, required=False, default='')
    esi_number      = serializers.CharField(max_length=20, required=False, default='')
    salesperson     = serializers.PrimaryKeyRelatedField(
        queryset=SalesPersonMaster.objects.all(),
        required=False, allow_null=True, default=None,
    )

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(f"Username '{value}' already exists.")
        return value

    def validate_employee_code(self, value):
        if Employee.objects.filter(employee_code=value).exists():
            raise serializers.ValidationError(f"Employee code '{value}' already exists.")
        return value


class SalaryStructureSerializer(serializers.ModelSerializer):
    gross_ctc = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model  = SalaryStructure
        fields = '__all__'


class PayrollDeductionConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PayrollDeductionConfig
        fields = '__all__'


class SalarySlipSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)

    class Meta:
        model  = SalarySlip
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class LeaveBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LeaveBalance
        fields = '__all__'


class HRSettingsSerializer(serializers.ModelSerializer):
    # True when at least one salary slip has been approved for this retail.
    # Locked fields cannot be changed once a payroll voucher has been created.
    locked = serializers.SerializerMethodField(read_only=True)

    def get_locked(self, obj):
        from .models import SalarySlip
        return SalarySlip.objects.filter(
            employee__retail=obj.retail,
            status='APPROVED',
            voucher__isnull=False,
        ).exists()

    class Meta:
        model  = HRSettings
        fields = '__all__'
