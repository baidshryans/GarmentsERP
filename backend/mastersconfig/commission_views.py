"""Salesperson commission report and journal voucher creation views."""
from decimal import Decimal
from rest_framework.decorators import api_view
from rest_framework.response import Response
from mastersconfig.models import SalesPersonMaster, SalesPersonCommission, SalesPersonCommissionReversal


@api_view(['GET'])
def commission_report(request):
    """
    Compute commission per salesperson per bill for the given date range.

    Query params:
      from_date  (YYYY-MM-DD)
      to_date    (YYYY-MM-DD)
      salesperson (optional PK filter)
      include_jv_created ('true' to also include bills already journalised)
    """
    from sales.models import SalesVou, SalesVouItem, SalesVouItemDetails
    from mastersconfig.serializers import SalesPersonMasterSerializer

    retail = request.retail
    if not retail:
        return Response({'error': 'Retail context missing'}, status=400)

    from_date = request.query_params.get('from_date')
    to_date   = request.query_params.get('to_date')
    sp_filter = request.query_params.get('salesperson')
    incl_jv   = request.query_params.get('include_jv_created', 'false').lower() == 'true'

    qs = SalesVou.objects.select_related(
        'ldgr', 'sales_person', 'sales_person2',
    ).filter(retail=retail, ret_status=False)

    if from_date:
        qs = qs.filter(date1__gte=from_date)
    if to_date:
        qs = qs.filter(date1__lte=to_date)

    def compute(voucher, sp):
        if sp is None:
            return None
        rate = float(sp.commission_rate or 0)
        if rate == 0:
            return None

        is_b2b = bool(getattr(voucher.ldgr, 'b2b', False))
        if is_b2b and not sp.apply_on_b2b:
            return None

        mrp      = float(voucher.mrp or 0)
        discount = float(voucher.discount or 0)

        if sp.commission_on == 'making':
            making_total = sum(
                float(si.making_value or 0)
                for si in SalesVouItem.objects.filter(billno=voucher)
            )
            base = making_total - (discount if sp.deduct_discount else 0)
        elif sp.commission_on == 'stone':
            base = sum(
                float(d.amount or 0)
                for d in SalesVouItemDetails.objects.filter(
                    billno=voucher, item__item_type='S'
                )
            )
        else:  # overall
            base = (mrp - discount) if sp.deduct_discount else mrp

        base = max(0.0, base)
        commission_amt = round(base * rate / 100, 2)
        if commission_amt == 0:
            return None

        existing = SalesPersonCommission.objects.filter(
            sales_vou=voucher, salesperson=sp
        ).prefetch_related('reversals').first()
        jv_id = existing.journal_voucher_id if existing else None

        # Aggregate all reversal amounts for this commission
        reversal_amt = 0.0
        has_reversal_jv = False
        if existing:
            for rev in existing.reversals.all():
                reversal_amt += float(rev.reversal_amt or 0)
                if rev.reversal_jv_id:
                    has_reversal_jv = True

        net_commission = round(commission_amt - reversal_amt, 2)

        return {
            'voucher_id':       voucher.id,
            'billno':           voucher.billno,
            'date':             str(voucher.date1),
            'party_name':       voucher.ldgr.ac_name if voucher.ldgr else '',
            'is_b2b':           is_b2b,
            'salesperson_id':   sp.id,
            'salesperson_name': sp.salesperson_name,
            'commission_on':    sp.get_commission_on_display(),
            'rate':             rate,
            'base_amount':      round(base, 2),
            'commission_amt':   commission_amt,
            'reversal_amt':     round(reversal_amt, 2),
            'net_commission':   net_commission,
            'has_reversal':     reversal_amt > 0,
            'has_reversal_jv':  has_reversal_jv,
            'deduct_discount':  sp.deduct_discount,
            'has_sp_ledger':    sp.ledger_id is not None,
            'jv_created':       jv_id is not None,
            'jv_id':            jv_id,
            'mrp':              mrp,
            'discount':         discount,
        }

    rows = []
    for voucher in qs:
        for attr in ('sales_person', 'sales_person2'):
            sp = getattr(voucher, attr, None)
            if sp_filter and sp and str(sp.id) != str(sp_filter):
                continue
            row = compute(voucher, sp)
            if row is None:
                continue
            if not incl_jv and row['jv_created']:
                continue
            rows.append(row)

    salespersons = SalesPersonMaster.objects.filter(retail=retail)

    return Response({
        'rows': rows,
        'salespersons': SalesPersonMasterSerializer(salespersons, many=True).data,
        'commission_ledger_configured': retail.commission_ldgr_id is not None,
        'total_commission':     round(sum(r['commission_amt'] for r in rows), 2),
        'total_reversal':       round(sum(r['reversal_amt'] for r in rows), 2),
        'total_net_commission': round(sum(r['net_commission'] for r in rows), 2),
    })


@api_view(['POST'])
def commission_create_jv(request):
    """
    Create journal vouchers for selected commission entries.

    Body:
    {
      "entries": [
        {"voucher_id": 1, "salesperson_id": 2, "commission_amt": 150.00,
         "base_amount": 5000.00, "rate": 3.0},
        ...
      ]
    }

    DR  retail.commission_ldgr   commission_amt
    CR  salesperson.ledger       commission_amt
    """
    from sales.models import SalesVou
    from accounting.models import VoucherMain, VoucherDetail
    from accounting.utils import get_next_bill_number
    from django.db import transaction

    retail = request.retail
    if not retail:
        return Response({'error': 'Retail context missing'}, status=400)

    if not retail.commission_ldgr_id:
        return Response(
            {'error': 'Commission ledger not configured. Go to Settings and assign a Commission Ledger first.'},
            status=400,
        )

    entries = request.data.get('entries', [])
    if not entries:
        return Response({'error': 'No entries provided'}, status=400)

    commission_ldgr = retail.commission_ldgr
    fy = retail.active_fy
    created_jvs = []
    skipped = []

    with transaction.atomic():
        for entry in entries:
            voucher_id     = entry.get('voucher_id')
            sp_id          = entry.get('salesperson_id')
            commission_amt = float(entry.get('commission_amt', 0))

            if commission_amt <= 0:
                continue

            try:
                sales_vou   = SalesVou.objects.get(pk=voucher_id, retail=retail)
                salesperson = SalesPersonMaster.objects.get(pk=sp_id)
            except (SalesVou.DoesNotExist, SalesPersonMaster.DoesNotExist):
                skipped.append({'voucher_id': voucher_id, 'reason': 'Not found'})
                continue

            if salesperson.ledger is None:
                skipped.append({
                    'voucher_id': voucher_id,
                    'reason': f'No payable ledger assigned to {salesperson.salesperson_name}',
                })
                continue

            # Prevent duplicate JV
            if SalesPersonCommission.objects.filter(
                sales_vou=sales_vou, salesperson=salesperson
            ).exclude(journal_voucher=None).exists():
                skipped.append({'voucher_id': voucher_id, 'reason': 'JV already created'})
                continue

            voucher_no = get_next_bill_number(retail, 'JRNL', fy)
            narration  = (
                f"Commission to {salesperson.salesperson_name} "
                f"for bill {sales_vou.billno}"
            )

            jv = VoucherMain.objects.create(
                date=sales_vou.date1,
                voucher_no=voucher_no,
                narration=narration,
                amount=commission_amt,
                voucher_type='JRNL',
                retail=retail,
                fiscal_year=fy,
            )
            VoucherDetail.objects.create(
                voucher_main=jv, account=commission_ldgr,
                debit=commission_amt, credit=0,
            )
            VoucherDetail.objects.create(
                voucher_main=jv, account=salesperson.ledger,
                debit=0, credit=commission_amt,
            )

            SalesPersonCommission.objects.update_or_create(
                sales_vou=sales_vou,
                salesperson=salesperson,
                defaults={
                    'base_amount':    entry.get('base_amount', 0),
                    'rate':           entry.get('rate', 0),
                    'commission_amt': commission_amt,
                    'journal_voucher': jv,
                    'retail':         retail,
                },
            )

            created_jvs.append({
                'jv_id': jv.id,
                'voucher_no': voucher_no,
                'billno': sales_vou.billno,
                'salesperson': salesperson.salesperson_name,
                'commission_amt': commission_amt,
            })

    return Response({
        'created': len(created_jvs),
        'skipped': len(skipped),
        'jvs': created_jvs,
        'skip_details': skipped,
    })


@api_view(['GET'])
def commission_ledger_config(request):
    """Return current commission ledger configured for the retail."""
    retail = request.retail
    if not retail:
        return Response({'error': 'Retail context missing'}, status=400)
    ldgr = retail.commission_ldgr
    return Response({
        'commission_ldgr_id':   ldgr.id if ldgr else None,
        'commission_ldgr_name': ldgr.ac_name if ldgr else None,
    })


@api_view(['PATCH'])
def commission_ledger_set(request):

    """Set or clear the commission ledger for the retail."""
    from contacts.models import Ledger
    retail = request.retail
    if not retail:
        return Response({'error': 'Retail context missing'}, status=400)

    ldgr_id = request.data.get('commission_ldgr_id')
    if ldgr_id:
        try:
            ldgr = Ledger.objects.get(pk=ldgr_id)
        except Ledger.DoesNotExist:
            return Response({'error': 'Ledger not found'}, status=404)
        retail.commission_ldgr = ldgr
    else:
        retail.commission_ldgr = None

    retail.save(update_fields=['commission_ldgr'])
    ldgr = retail.commission_ldgr
    return Response({
        'commission_ldgr_id':   ldgr.id if ldgr else None,
        'commission_ldgr_name': ldgr.ac_name if ldgr else None,
    })


# ── Commission Reversal Utility ───────────────────────────────────────────────

def reverse_commissions_for_return(sale_return, item_instances):
    """
    Called inside SaleReturnSerializer.create() after all return items are saved.

    For every original SalesVou referenced in the returned items, this looks up
    existing SalesPersonCommission records and creates a proportional reversal:

    • commission_on == 'making'  → sum of making_value on returned items
    • commission_on == 'stone'   → sum of stone amounts on returned item details
    • commission_on == 'overall' → prorated using returned making_value /
                                   original making_value × original base_amount

    If the original commission JV has already been posted AND the retail has a
    commission_ldgr configured AND the salesperson has a payable ledger, a
    reversing JRNL voucher is automatically created:
        DR  salesperson.ledger       (reverses the original CR)
        CR  retail.commission_ldgr   (reverses the original DR)

    Idempotent: update_or_create on (commission, sale_return) so re-saves are safe.
    """
    from sales.models import SalesVou, SalesVouItem, SaleReturnDetails
    from accounting.models import VoucherMain, VoucherDetail
    from accounting.utils import get_next_bill_number

    retail = sale_return.retail
    if not retail:
        return

    # Group returned items by their originating SalesVou pk
    vou_to_items: dict = {}
    for item in item_instances:
        key = item.sale_billno_id
        vou_to_items.setdefault(key, []).append(item)

    for vou_pk, returned_items in vou_to_items.items():
        try:
            sales_vou = SalesVou.objects.get(pk=vou_pk)
        except SalesVou.DoesNotExist:
            continue

        commissions = SalesPersonCommission.objects.filter(
            sales_vou=sales_vou
        ).select_related('salesperson', 'salesperson__ledger')

        for commission in commissions:
            sp   = commission.salesperson
            rate = float(commission.rate or 0)
            if rate == 0:
                continue

            # ── Calculate the base amount that is being reversed ───────────
            if sp.commission_on == 'making':
                returned_base = sum(float(it.making_value or 0) for it in returned_items)

            elif sp.commission_on == 'stone':
                returned_base = sum(
                    float(d.amount or 0)
                    for it in returned_items
                    for d in SaleReturnDetails.objects.filter(main_item=it)
                )

            else:  # 'overall'
                # Prorate using proportion of returned making value vs original
                returned_making = sum(float(it.making_value or 0) for it in returned_items)
                original_making = sum(
                    float(oi.making_value or 0)
                    for oi in SalesVouItem.objects.filter(billno=sales_vou)
                ) or 1.0  # avoid ZeroDivisionError
                proportion    = Decimal(str(returned_making)) / Decimal(str(original_making))
                returned_base = float(proportion * commission.base_amount)

            reversal_amt = round(max(0.0, returned_base * rate / 100), 2)
            if reversal_amt == 0:
                continue

            # Clamp to what was actually earned (guards against floating-point drift)
            reversal_amt = min(reversal_amt, float(commission.commission_amt))

            # ── Reversal JV (only if original JV posted + ledgers configured) ─
            reversal_jv = None
            if (
                commission.journal_voucher_id
                and retail.commission_ldgr_id
                and sp.ledger_id
            ):
                fy         = retail.active_fy
                voucher_no = get_next_bill_number(retail, 'JRNL', fy)
                reversal_jv = VoucherMain.objects.create(
                    date         = sale_return.date1,
                    voucher_no   = voucher_no,
                    narration    = (
                        f"Commission reversal – {sp.salesperson_name}"
                        f" | return {sale_return.billno}"
                        f" | original bill {sales_vou.billno}"
                    ),
                    amount       = Decimal(str(reversal_amt)),
                    voucher_type = 'JRNL',
                    retail       = retail,
                    fiscal_year  = fy,
                )
                # DR salesperson payable — reverses the original CR
                VoucherDetail.objects.create(
                    voucher_main = reversal_jv,
                    account      = sp.ledger,
                    debit        = Decimal(str(reversal_amt)),
                    credit       = Decimal('0'),
                )
                # CR commission expense — reverses the original DR
                VoucherDetail.objects.create(
                    voucher_main = reversal_jv,
                    account      = retail.commission_ldgr,
                    debit        = Decimal('0'),
                    credit       = Decimal(str(reversal_amt)),
                )

            SalesPersonCommissionReversal.objects.update_or_create(
                commission  = commission,
                sale_return = sale_return,
                defaults    = {
                    'reversal_amt': Decimal(str(reversal_amt)),
                    'reversal_jv':  reversal_jv,
                },
            )
