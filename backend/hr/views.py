from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction

from rest_framework import viewsets, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounting.models import VoucherMain, VoucherDetail
from accounting.utils import get_next_bill_number
from contacts.models import UserLocation
from global_vars import VoucherType
from userauth.views import RetailBaseViewset
from userauth.permissions import RBACPermission

from .models import (
    Employee, SalaryStructure, PayrollDeductionConfig,
    SalarySlip, LeaveBalance, HRSettings,
)
from .serializers import (
    EmployeeSerializer, CreateEmployeeWithUserSerializer,
    SalaryStructureSerializer, PayrollDeductionConfigSerializer,
    SalarySlipSerializer, LeaveBalanceSerializer, HRSettingsSerializer,
)
from .services import generate_salary_slip


# ── ERP Admin Views ────────────────────────────────────────────────────────────

class EmployeeViewSet(RetailBaseViewset):
    queryset         = Employee.objects.select_related('user', 'retail', 'state', 'salesperson')
    serializer_class = EmployeeSerializer

    @action(detail=False, methods=['post'], url_path='create-with-user')
    def create_with_user(self, request):
        ser = CreateEmployeeWithUserSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        retail = getattr(request, 'retail', None)

        with transaction.atomic():
            user = User.objects.create_user(
                username=d['username'],
                password=d['password'],
                email=d.get('email', ''),
                first_name=d.get('first_name', ''),
                last_name=d.get('last_name', ''),
            )
            UserLocation.objects.create(user=user)

            employee = Employee.objects.create(
                user=user,
                retail=retail,
                employee_code=d['employee_code'],
                full_name=d['full_name'],
                designation=d.get('designation', ''),
                department=d.get('department', ''),
                date_of_joining=d['date_of_joining'],
                date_of_birth=d.get('date_of_birth'),
                gender=d.get('gender', ''),
                address_line1=d.get('address_line1', ''),
                address_line2=d.get('address_line2', ''),
                city=d.get('city', ''),
                state=d.get('state'),
                pincode=d.get('pincode', ''),
                bank_name=d.get('bank_name', ''),
                account_no=d.get('account_no', ''),
                ifsc_code=d.get('ifsc_code', ''),
                pan_number=d.get('pan_number', ''),
                pf_number=d.get('pf_number', ''),
                esi_number=d.get('esi_number', ''),
                salesperson=d.get('salesperson'),
            )

        return Response(
            EmployeeSerializer(employee).data,
            status=status.HTTP_201_CREATED,
        )


class SalaryStructureViewSet(RetailBaseViewset):
    queryset         = SalaryStructure.objects.select_related('employee')
    serializer_class = SalaryStructureSerializer

    def get_queryset(self):
        qs = SalaryStructure.objects.select_related('employee')
        retail = getattr(self.request, 'retail', None)
        qs = qs.filter(employee__retail=retail)
        emp_id = self.request.query_params.get('employee')
        if emp_id:
            qs = qs.filter(employee_id=emp_id)
        return qs

    def perform_create(self, serializer):
        employee = serializer.validated_data['employee']
        SalaryStructure.objects.filter(employee=employee, is_active=True).update(is_active=False)
        serializer.save()


class PayrollDeductionConfigViewSet(RetailBaseViewset):
    queryset         = PayrollDeductionConfig.objects.select_related('employee')
    serializer_class = PayrollDeductionConfigSerializer

    def get_queryset(self):
        retail = getattr(self.request, 'retail', None)
        return PayrollDeductionConfig.objects.filter(employee__retail=retail)


class SalarySlipViewSet(RetailBaseViewset):
    queryset         = SalarySlip.objects.select_related('employee', 'retail')
    serializer_class = SalarySlipSerializer

    def get_queryset(self):
        retail = getattr(self.request, 'retail', None)
        qs = SalarySlip.objects.filter(retail=retail).select_related('employee')
        month = self.request.query_params.get('month')
        year  = self.request.query_params.get('year')
        emp   = self.request.query_params.get('employee')
        if month:
            qs = qs.filter(month=month)
        if year:
            qs = qs.filter(year=year)
        if emp:
            qs = qs.filter(employee_id=emp)
        return qs


class GeneratePayslipView(APIView):
    permission_classes = [RBACPermission]

    def post(self, request):
        retail = getattr(request, 'retail', None)
        fiscal_year = getattr(request, 'fiscal_year', None)
        employee_id = request.data.get('employee_id')
        month       = request.data.get('month')
        year        = request.data.get('year')
        days_worked = request.data.get('days_worked')

        if not all([employee_id, month, year]):
            return Response({'detail': 'employee_id, month, and year are required.'}, status=400)

        try:
            employee = Employee.objects.get(pk=employee_id, retail=retail)
        except Employee.DoesNotExist:
            return Response({'detail': 'Employee not found.'}, status=404)

        try:
            data = generate_salary_slip(employee, int(month), int(year), days_worked)
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)

        slip, created = SalarySlip.objects.update_or_create(
            employee=employee, month=int(month), year=int(year),
            defaults={
                'retail': retail,
                'fiscal_year': fiscal_year,
                'status': 'DRAFT',
                **data,
            }
        )
        return Response(SalarySlipSerializer(slip).data, status=201 if created else 200)


class BulkGeneratePayslipView(APIView):
    permission_classes = [RBACPermission]

    def post(self, request):
        retail = getattr(request, 'retail', None)
        fiscal_year = getattr(request, 'fiscal_year', None)
        month   = request.data.get('month')
        year    = request.data.get('year')
        entries = request.data.get('entries', [])  # [{employee_id, days_worked}, ...]

        if not all([month, year]):
            return Response({'detail': 'month and year are required.'}, status=400)

        results = []
        errors  = []
        for entry in entries:
            emp_id = entry.get('employee_id')
            dw     = entry.get('days_worked')
            try:
                employee = Employee.objects.get(pk=emp_id, retail=retail)
                data = generate_salary_slip(employee, int(month), int(year), dw)
                slip, _ = SalarySlip.objects.update_or_create(
                    employee=employee, month=int(month), year=int(year),
                    defaults={'retail': retail, 'fiscal_year': fiscal_year, 'status': 'DRAFT', **data},
                )
                results.append(SalarySlipSerializer(slip).data)
            except Employee.DoesNotExist:
                errors.append({'employee_id': emp_id, 'error': 'Not found'})
            except ValueError as e:
                errors.append({'employee_id': emp_id, 'error': str(e)})

        return Response({'results': results, 'errors': errors})


class ApprovePayslipView(APIView):
    permission_classes = [RBACPermission]

    def post(self, request, pk):
        retail = getattr(request, 'retail', None)
        fiscal_year = getattr(request, 'fiscal_year', None)

        try:
            slip = SalarySlip.objects.select_related('employee', 'retail').get(pk=pk, retail=retail)
        except SalarySlip.DoesNotExist:
            return Response({'detail': 'Salary slip not found.'}, status=404)

        if slip.status == 'PAID':
            return Response({'detail': 'Slip is already paid.'}, status=400)

        try:
            settings_obj = retail.hr_settings
        except HRSettings.DoesNotExist:
            return Response({'detail': 'HR Settings not configured for this retail. Please set up ledger mappings.'}, status=400)

        if not settings_obj.salary_expense_ldgr or not settings_obj.employee_payable_ldgr:
            return Response({'detail': 'salary_expense_ldgr and employee_payable_ldgr must be set in HR Settings.'}, status=400)

        with transaction.atomic():
            import datetime
            bill_no = get_next_bill_number(retail, VoucherType.salary, fiscal_year)
            narration = f"Salary — {slip.employee.full_name} — {slip.month}/{slip.year}"

            # Total CTC = gross_salary + employer PF + employer ESI
            # This ensures the voucher balances: Dr CTC = Cr (net + all payables)
            employer_pf = slip.pf_employer or Decimal('0')
            employer_esi = slip.esi_employer or Decimal('0')
            total_ctc = slip.gross_salary + employer_pf + employer_esi

            voucher = VoucherMain.objects.create(
                retail=retail,
                fiscal_year=fiscal_year,
                voucher_type=VoucherType.salary,
                voucher_no=bill_no,
                date=datetime.date.today(),
                narration=narration[:150],
                amount=total_ctc,
            )

            details = []
            def _detail(ledger, debit=0, credit=0):
                return VoucherDetail(
                    voucher_main=voucher,
                    voucher_no=bill_no,
                    voucher_type=VoucherType.salary,
                    account=ledger,
                    debit=debit,
                    credit=credit,
                )

            # Dr Salary Expense (gross + employer contributions = total CTC)
            details.append(_detail(settings_obj.salary_expense_ldgr, debit=total_ctc))
            # Cr Employee Payable (net take-home)
            details.append(_detail(settings_obj.employee_payable_ldgr, credit=slip.net_salary))

            pf_total = (slip.pf_employee or Decimal('0')) + employer_pf
            if pf_total > 0 and settings_obj.pf_payable_ldgr:
                details.append(_detail(settings_obj.pf_payable_ldgr, credit=pf_total))

            esi_total = (slip.esi_employee or Decimal('0')) + employer_esi
            if esi_total > 0 and settings_obj.esi_payable_ldgr:
                details.append(_detail(settings_obj.esi_payable_ldgr, credit=esi_total))

            if slip.professional_tax > 0 and settings_obj.pt_payable_ldgr:
                details.append(_detail(settings_obj.pt_payable_ldgr, credit=slip.professional_tax))

            if slip.tds_deducted > 0 and settings_obj.tds_payable_ldgr:
                details.append(_detail(settings_obj.tds_payable_ldgr, credit=slip.tds_deducted))

            # bulk_create_with_history so payroll voucher details land in the audit log too
            VoucherDetail.objects.bulk_create_with_history(details, VoucherDetail)

            slip.voucher = voucher
            slip.status  = 'APPROVED'
            slip.save(update_fields=['voucher', 'status'])

        return Response(SalarySlipSerializer(slip).data)


class HRSettingsView(APIView):
    permission_classes = [RBACPermission]

    def get(self, request):
        retail = getattr(request, 'retail', None)
        obj, _ = HRSettings.objects.get_or_create(retail=retail)
        return Response(HRSettingsSerializer(obj).data)

    def put(self, request):
        retail = getattr(request, 'retail', None)
        obj, _ = HRSettings.objects.get_or_create(retail=retail)

        # Ledger fields that are locked once any payslip has been approved
        LEDGER_FIELDS = [
            'salary_expense_ldgr', 'employee_payable_ldgr',
            'pf_payable_ldgr', 'esi_payable_ldgr',
            'pt_payable_ldgr', 'tds_payable_ldgr',
        ]
        slips_approved = SalarySlip.objects.filter(
            employee__retail=retail, status='APPROVED', voucher__isnull=False
        ).exists()
        if slips_approved:
            changed = [
                f for f in LEDGER_FIELDS
                if f in request.data or f"{f}_id" in request.data
            ]
            if changed:
                return Response(
                    {f: "Cannot change — salary slips have been approved using this ledger." for f in changed},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        ser = HRSettingsSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class LeaveBalanceViewSet(RetailBaseViewset):
    serializer_class = LeaveBalanceSerializer

    def get_queryset(self):
        retail = getattr(self.request, 'retail', None)
        return LeaveBalance.objects.filter(employee__retail=retail)


# ── Employee Portal Views ──────────────────────────────────────────────────────

class IsEmployeeUser(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and hasattr(request.user, 'employee_profile')


class PortalMyProfileView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes     = [IsEmployeeUser]

    def get(self, request):
        employee = request.user.employee_profile
        return Response(EmployeeSerializer(employee).data)


class PortalMySlipsView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes     = [IsEmployeeUser]

    def get(self, request):
        employee = request.user.employee_profile
        year = request.query_params.get('year')
        qs = SalarySlip.objects.filter(employee=employee).exclude(status='DRAFT')
        if year:
            qs = qs.filter(year=year)
        return Response(SalarySlipSerializer(qs, many=True).data)


class PortalMySlipDetailView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes     = [IsEmployeeUser]

    def get(self, request, month, year):
        employee = request.user.employee_profile
        try:
            slip = SalarySlip.objects.get(employee=employee, month=month, year=year)
        except SalarySlip.DoesNotExist:
            return Response({'detail': 'Salary slip not found.'}, status=404)
        if slip.status == 'DRAFT':
            return Response({'detail': 'Slip not yet approved.'}, status=403)
        return Response(SalarySlipSerializer(slip).data)
