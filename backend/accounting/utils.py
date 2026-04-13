import re
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, F

from inventory.models import RawMaterialInventory, UnBarcodedDetails, BarcodeDetails
from mastersconfig.models import BillNumberSequence
from .models import *
from purchase.models import *


def get_company_cash_limits(retail):
    """
    Returns (receipt_limit, payment_limit) from the company linked via
    retail → branch → company. Falls back to statutory defaults if the
    chain is broken.

    Returns (None, None) when enforce_cash_limits is False — callers must
    skip the validation check entirely in that case.
    """
    company = getattr(getattr(retail, 'branch', None), 'company', None)
    if company:
        if not company.enforce_cash_limits:
            return None, None
        return (
            Decimal(str(company.max_cash_receipt_limit)),
            Decimal(str(company.max_cash_payment_limit)),
        )
    return Decimal('199999'), Decimal('10000')


def _get_company_retails(retail):
    """
    Return all RetailMaster instances belonging to the same company as `retail`.
    Section 269ST (cash receipt limit) and 40A(3) (cash payment limit) apply at
    the company/PAN level — not per retail branch.
    Falls back to [retail] if the company chain cannot be resolved.
    """
    from mastersconfig.models import RetailMaster
    company = getattr(getattr(retail, 'branch', None), 'company', None)
    if company:
        return list(RetailMaster.objects.filter(branch__company=company))
    return [retail]


def increment_series_no(bill_no):
    match = re.search(r'(\d+)$', bill_no)

    if match:
        number_part = match.group(1)  # Extract numeric part
        new_number = int(number_part) + 1  # Increment
        new_voucher_no = bill_no.replace(number_part, str(new_number).zfill(len(number_part)))
        return new_voucher_no

    return bill_no


def peek_next_bill_number(retail, prefix, fiscal_year=None):
    """Read-only preview of the next bill number (no DB write)."""
    fy = fiscal_year or getattr(retail, 'active_fy', None)
    fy_code = fy.fy_code if fy else ''
    try:
        seq = BillNumberSequence.objects.get(retail=retail, prefix=prefix, fiscal_year=fy)
        return f"{retail.get_bill_prefix(prefix, fy_code)}{seq.last_number + 1:05d}"
    except BillNumberSequence.DoesNotExist:
        max_num = _bootstrap_sequence_number(retail, prefix, fy)
        return f"{retail.get_bill_prefix(prefix, fy_code)}{max_num + 1:05d}"


def get_next_bill_number(retail, prefix, fiscal_year=None):
    """
    O(1) voucher number generation using a sequence table.
    Relies on transaction.atomic() for concurrency safety.
    Sequences reset per fiscal year so each FY starts from 00001.
    """
    fy = fiscal_year or getattr(retail, 'active_fy', None)
    if not fy:
        raise ValueError("No active fiscal year set for this retail location. Please create and activate a fiscal year first.")

    fy_code = fy.fy_code

    with transaction.atomic():
        seq, created = BillNumberSequence.objects.get_or_create(
            retail=retail, prefix=prefix, fiscal_year=fy,
            defaults={'last_number': 0}
        )
        if created:
            # Bootstrap: find the max existing number from the relevant model for this FY
            max_num = _bootstrap_sequence_number(retail, prefix, fy)
            seq.last_number = max_num

        seq.last_number += 1
        seq.save(update_fields=['last_number'])
        return f"{retail.get_bill_prefix(prefix, fy_code)}{seq.last_number:05d}"


def _bootstrap_sequence_number(retail, prefix, fiscal_year=None):
    """Extract the max existing number for a given prefix from the relevant model, filtered by FY date range."""
    # Import here to avoid circular imports
    from sales.models import SalesVou, SaleReturn, SalesApproval
    from inventory.models import StockJournal
    from global_vars import VoucherType

    from accounting.models import CreditDebitNote

    model_map_resolved = {
        'SV': (SalesVou, 'billno'),
        'SR': (SaleReturn, 'billno'),
        'SA': (SalesApproval, 'billno'),
        'PV': (PurchaseVoucher, 'billno'),
        'PR': (PurchaseReturn, 'billno'),
        'PO': (PurchaseOrder, 'po_no'),
        'GC': (CashGoldConversion, 'billno'),
        'CG': (CashGoldConversion, 'billno'),
        'SJ': (StockJournal, 'billno'),
        'CN': (CreditDebitNote, 'note_no'),
        'DN': (CreditDebitNote, 'note_no'),
    }

    # Build FY date filter if fiscal year is provided
    fy_filter = {}
    if fiscal_year:
        fy_filter = {'fiscal_year': fiscal_year}

    if prefix in model_map_resolved:
        Model, field = model_map_resolved[prefix]
        qs = Model.objects.filter(retail=retail, **fy_filter)
        if prefix in ('GC', 'CG'):
            qs = qs.filter(conv_type=prefix)
        if prefix in ('CN', 'DN'):
            qs = qs.filter(note_type=prefix)
        last = qs.order_by(f'-{field}').values_list(field, flat=True).first()
        if last:
            match = re.search(r'(\d+)$', last)
            if match:
                return int(match.group(1))

    # For voucher types like JRNL, PMNT, etc. that use VoucherMain
    voucher_type_map = {
        'JRNL': VoucherType.journal if hasattr(VoucherType, 'journal') else 'JRNL',
        'PMNT': VoucherType.pmnt if hasattr(VoucherType, 'pmnt') else 'PMNT',
        'CONTRA': VoucherType.cntr if hasattr(VoucherType, 'cntr') else 'CONTRA',
        'RCPT': VoucherType.rcpt if hasattr(VoucherType, 'rcpt') else 'RCPT',
        'RCPT-SALE': VoucherType.rcpt_sale if hasattr(VoucherType, 'rcpt_sale') else 'RCPT-SALE',
        'SALE': VoucherType.sale if hasattr(VoucherType, 'sale') else 'SALE',
        'PURC-RET': VoucherType.purc_ret if hasattr(VoucherType, 'purc_ret') else 'PURC-RET',
        'PURC-SC': VoucherType.purc_sc if hasattr(VoucherType, 'purc_sc') else 'PURC-SC',
        'SALE-RET': VoucherType.sale_ret if hasattr(VoucherType, 'sale_ret') else 'SALE-RET',
    }
    if prefix in voucher_type_map:
        vtype = voucher_type_map[prefix]
        qs = VoucherMain.objects.filter(retail=retail, voucher_type=vtype)
        if fiscal_year:
            qs = qs.filter(fiscal_year=fiscal_year)
        last = qs.order_by('-voucher_no').values_list('voucher_no', flat=True).first()
        if last:
            match = re.search(r'(\d+)$', last)
            if match:
                return int(match.group(1))

    # Stock Transfer between retails (RST prefix)
    if prefix == 'RST':
        from inventory.models import StockTransfer as StockTransferMdl
        qs = StockTransferMdl.objects.filter(retail=retail)
        if fiscal_year:
            qs = qs.filter(fiscal_year=fiscal_year)
        last = qs.order_by('-billno').values_list('billno', flat=True).first()
        if last:
            match = re.search(r'(\d+)$', last)
            if match:
                return int(match.group(1))

    return 0


def generate_voucher_no(type, retail, fiscal_year=None):
    """Generate next voucher number for accounting VoucherMain entries."""
    return get_next_bill_number(retail, type, fiscal_year)


def generate_next_gc_no(retail, fiscal_year=None):
    return get_next_bill_number(retail, "GC", fiscal_year)


def generate_next_cg_no(retail, fiscal_year=None):
    return get_next_bill_number(retail, "CG", fiscal_year)


def calculate_opening_stock(retail=None):
    """
    Calculate opening stock value from physical inventory.

    Sources:
      - BarcodeMain (op_stk=True), filtered by op_retail if retail given
      - UnBarcodedMain (op_stk=True), filtered by retail if retail given
      - RawMaterialInventory, filtered by retail if retail given

    Each item is valued at its weighted average rate (op_wtd_avg_rate / op_stock_wtd_avg_rate).
    """
    total_opening_stock_value = Decimal(0)

    # Barcoded Stock Value (op_stk=True)
    bar_filter = {'barcode__op_stk': True}
    if retail:
        bar_filter['barcode__op_retail'] = retail
    barcoded_stock = BarcodeDetails.objects.filter(**bar_filter).annotate(
        item_rate=F('item__op_wtd_avg_rate'),
        packet_rate=F('packet__op_stock_wtd_avg_rate')
    ).aggregate(
        total_gold_value=Sum(F('gw') * F('item_rate'), output_field=models.DecimalField()),
        total_stone_value=Sum(F('ct') * F('packet_rate'), output_field=models.DecimalField())
    )

    # Unbarcoded Stock Value (op_stk=True)
    unbar_filter = {'main_item__op_stk': True}
    if retail:
        unbar_filter['main_item__retail'] = retail
    unbarcoded_stock = UnBarcodedDetails.objects.filter(**unbar_filter).annotate(
        item_rate=F('item__op_wtd_avg_rate'),
        packet_rate=F('packet__op_stock_wtd_avg_rate')
    ).aggregate(
        total_gold_value=Sum(F('gw') * F('item_rate'), output_field=models.DecimalField()),
        total_stone_value=Sum(F('ct') * F('packet_rate'), output_field=models.DecimalField())
    )

    # Raw Material Inventory Stock Value
    rm_filter = {}
    if retail:
        rm_filter['retail'] = retail
    raw_material_stock = RawMaterialInventory.objects.filter(**rm_filter).annotate(
        item_rate=F('item__op_wtd_avg_rate'),
        packet_rate=F('packet__op_stock_wtd_avg_rate')
    ).aggregate(
        total_gold_value=Sum(F('gw') * F('item_rate'), output_field=models.DecimalField()),
        total_stone_value=Sum(F('ct') * F('packet_rate'), output_field=models.DecimalField())
    )

    total_opening_stock_value += barcoded_stock['total_gold_value'] or Decimal(0)
    total_opening_stock_value += barcoded_stock['total_stone_value'] or Decimal(0)
    total_opening_stock_value += unbarcoded_stock['total_gold_value'] or Decimal(0)
    total_opening_stock_value += unbarcoded_stock['total_stone_value'] or Decimal(0)
    total_opening_stock_value += raw_material_stock['total_gold_value'] or Decimal(0)
    total_opening_stock_value += raw_material_stock['total_stone_value'] or Decimal(0)

    return total_opening_stock_value


def get_customer_cash_received(retail, fiscal_year, customer_ledger):
    """
    Returns total cash received from a single customer in a fiscal year across
    ALL retail locations belonging to the same company (gross — no deductions for returns).

    Section 269ST applies at the company/PAN level, not per retail branch. Cash
    received by any branch of the same company counts toward the same limit.

    Counts:
      1. SalesVou.cash  — cash collected at the point of sale (all company retails)
      2. Standalone RCPT vouchers — cash debited where this customer is credited (all company retails)

    RCPT-SALE vouchers are auto-generated from Sales Vouchers and their cash amount is
    already captured in (1), so they are deliberately excluded here.

    Per Income Tax Section 269ST the gross received amount is used; returns / refunds
    do NOT reduce the limit.
    """
    from django.db.models import Sum as DSum
    from sales.models import SalesVou

    # All retails in the same company — 269ST is a company-level obligation.
    company_retails = _get_company_retails(retail)

    # Use date range instead of the fiscal_year FK since each retail has its own
    # separate FiscalYearMaster record for the same calendar period.
    fy_date_filter_sv = {}
    fy_date_filter_vm = {}
    if fiscal_year:
        fy_date_filter_sv = {
            'date1__gte': fiscal_year.fy_start,
            'date1__lte': fiscal_year.fy_end,
        }
        fy_date_filter_vm = {
            'date__gte': fiscal_year.fy_start,
            'date__lte': fiscal_year.fy_end,
        }

    # 1 ── Cash from Sale Vouchers across all company retails
    sales_cash = (
        SalesVou.objects.filter(
            retail__in=company_retails,
            ldgr=customer_ledger,
            **fy_date_filter_sv,
        ).aggregate(t=DSum('cash'))['t']
        or Decimal('0')
    )

    # 2 ── Cash from standalone RCPT vouchers across all company retails (not RCPT-SALE)
    # Use account role 'CA' to identify cash ledgers since each retail has its own cash_ldgr.
    rcpt_ids = list(
        VoucherMain.objects.filter(
            retail__in=company_retails,
            voucher_type='RCPT',
            transactions__account=customer_ledger,
            transactions__credit__gt=0,
            **fy_date_filter_vm,
        ).values_list('id', flat=True).distinct()
    )
    rcpt_cash = Decimal('0')
    if rcpt_ids:
        rcpt_cash = (
            VoucherDetail.objects.filter(
                voucher_main_id__in=rcpt_ids,
                account__roles__role='CA',
                debit__gt=0,
            ).aggregate(t=DSum('debit'))['t']
            or Decimal('0')
        )

    return Decimal(str(sales_cash)) + Decimal(str(rcpt_cash))


def get_vendor_cash_paid_on_date(retail, date, vendor_ledger):
    """
    Returns total cash paid to a single vendor on a specific date across ALL retail
    locations belonging to the same company (gross — returns don't reduce this).

    Section 40A(3) applies at the company/PAN level — the ₹10,000 daily ceiling
    covers payments made by any branch of the same company to the same party on the
    same day.

    Counts PMNT vouchers on `date` where:
      - vendor_ledger is on the DEBIT side  (liability to vendor reduces)
      - cash ledger   is on the CREDIT side (cash leaves the business)
    """
    from django.db.models import Sum as DSum

    company_retails = _get_company_retails(retail)

    # Find PMNT vouchers on this date across all company retails that debit this vendor
    pmnt_ids = list(
        VoucherMain.objects.filter(
            retail__in=company_retails,
            voucher_type='PMNT',
            date=date,
            transactions__account=vendor_ledger,
            transactions__debit__gt=0,
        ).values_list('id', flat=True).distinct()
    )

    if not pmnt_ids:
        return Decimal('0')

    # Use account role 'CA' to identify cash across retails (each has its own cash_ldgr)
    cash_paid = (
        VoucherDetail.objects.filter(
            voucher_main_id__in=pmnt_ids,
            account__roles__role='CA',
            credit__gt=0,
        ).aggregate(t=DSum('credit'))['t']
        or Decimal('0')
    )

    return Decimal(str(cash_paid))
