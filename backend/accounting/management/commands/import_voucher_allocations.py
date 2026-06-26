"""
Phase 2 of the legacy migration: attach bill-wise allocations to imported GL
vouchers, using the legacy "amount" tables.

  receive_amount  -> allocates RCPT party (credit) legs to SalesVou bills
  payment_amount  -> allocates PMNT party (debit)  legs to PurchaseVoucher bills
  journal_amount  -> tags JRNL party legs with the referenced bill (no split)

Each amount row = (v_id, v_typ, ledger_id, billno, amount, acc_year, rt_code):
"voucher (v_id,v_typ)'s line for ledger_id settles `amount` of bill `billno`".

This mirrors the live `allocate-bills` endpoint exactly: the single unallocated
party leg created by `import_vouchers` is DELETED and re-created as one
VoucherDetail per bill (carrying ref_sales_vou / ref_purchase_vou + ref_bill_no),
plus a remainder line for any unallocated balance. Affected bills' `due_amt` is
then reconciled to (gross total − total allocated).

Idempotent: a (voucher, ledger) group already carrying ref_* lines is skipped.

Usage:
  python manage.py import_voucher_allocations \
      [--receive receive_amount.csv] [--payment payment_amount.csv] \
      [--journal journal_amount.csv] [--apply] [--continue-on-error] [--report-dir DIR]
"""
import os
from decimal import Decimal

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from accounting.models import VoucherMain, VoucherDetail
from sales.models import SalesVou
from purchase.models import PurchaseVoucher
from accounting.migration_utils import clean, dec, resolve_ac_voucher, resolve_ledger

GROUP_COLS = ['v_typ', 'v_id', 'acc_year', 'rt_code', 'ledger_id']


class Command(BaseCommand):
    help = "Phase 2: attach bill-wise allocations from legacy amount tables."

    def add_arguments(self, parser):
        parser.add_argument('--receive', help='receive_amount CSV (sales)')
        parser.add_argument('--payment', help='payment_amount CSV (purchase)')
        parser.add_argument('--journal', help='journal_amount CSV')
        parser.add_argument('--apply', action='store_true', help='Persist (default: dry-run).')
        parser.add_argument('--continue-on-error', action='store_true')
        parser.add_argument('--report-dir', default='.')

    def handle(self, *args, **opts):
        if not any(opts[k] for k in ('receive', 'payment', 'journal')):
            raise CommandError("Provide at least one of --receive / --payment / --journal.")
        self.apply = opts['apply']
        self.cont = opts['continue_on_error']
        self.unresolved = []
        # bill object -> Decimal allocated (for final due_amt reconciliation)
        self.sales_alloc = {}
        self.purch_alloc = {}

        totals = {}
        if opts['receive']:
            totals['receive'] = self._run(opts['receive'], kind='sales')
        if opts['payment']:
            totals['payment'] = self._run(opts['payment'], kind='purchase')
        if opts['journal']:
            totals['journal'] = self._run(opts['journal'], kind='journal')

        if self.apply:
            self._reconcile_due_amts()

        self._report(opts['report_dir'])
        mode = "APPLIED" if self.apply else "DRY-RUN (no writes)"
        for name, (alloc, skipped, errored) in totals.items():
            self.stdout.write(self.style.SUCCESS(
                f"[{mode}] {name}: vouchers-allocated={alloc} skipped(existing)={skipped} errored={errored}"
            ))
        if not self.apply:
            self.stdout.write(self.style.WARNING("Dry run — re-run with --apply to persist."))

    # ------------------------------------------------------------------ #
    def _run(self, path, kind):
        if not os.path.exists(path):
            raise CommandError(f"File not found: {path}")
        df = pd.read_csv(path, dtype=str)
        df.columns = [c.strip() for c in df.columns]

        allocated = skipped = errored = 0
        grouped = df.groupby([df[c] for c in GROUP_COLS], sort=False)
        for _, group in grouped:
            head = group.iloc[0]
            try:
                with transaction.atomic():
                    res = self._allocate_group(head, group, kind)
                if res == 'skipped':
                    skipped += 1
                elif res == 'done':
                    allocated += 1
            except Exception as exc:
                errored += 1
                key = f"{clean(head['v_typ'])}:{clean(head['v_id'])} ldgr={clean(head['ledger_id'])}"
                self.unresolved.append({'kind': kind, 'voucher': key, 'error': str(exc)})
                self.stderr.write(self.style.ERROR(f"{kind} {key}: {exc}"))
                if not self.cont:
                    raise CommandError(str(exc))
        return allocated, skipped, errored

    def _allocate_group(self, head, group, kind):
        v_typ, v_id = clean(head['v_typ']), clean(head['v_id'])
        ac_yr, rt = clean(head['acc_year']), clean(head['rt_code'])
        _led = resolve_ledger(head['ledger_id'])
        if _led is None:
            raise ValueError(f"ledger {clean(head['ledger_id'])!r} not found")
        ledger_id = _led.id

        voucher = resolve_ac_voucher(v_typ, v_id, ac_yr, rt)
        if voucher is None:
            raise ValueError(f"no imported VoucherMain for {v_typ}:{v_id}:{ac_yr}:{rt}")

        if kind == 'journal':
            return self._tag_journal(voucher, ledger_id, group)

        is_sales = (kind == 'sales')
        side = 'credit' if is_sales else 'debit'
        ref_field = 'ref_sales_vou' if is_sales else 'ref_purchase_vou'

        # idempotency: already has allocated lines for this ledger?
        if voucher.transactions.filter(account_id=ledger_id).filter(
            **{f'{ref_field}__isnull': False}
        ).exists():
            return 'skipped'

        # the unallocated party leg(s) for this ledger
        # A party leg is "unallocated" when it has no ref_sales_vou/ref_purchase_vou
        # FK yet. We deliberately do NOT filter on ref_bill_no: the GL import seeds
        # it from the legacy rmks (e.g. "Against Reference" / "On Account"), which
        # is descriptive text, not an allocation. The idempotency guard above
        # (a ref_* FK already set for this ledger -> skip) prevents re-splitting.
        party = list(voucher.transactions.filter(
            account_id=ledger_id, **{f'{side}__gt': 0},
        ).filter(**{f'{ref_field}__isnull': True}))
        if not party:
            raise ValueError(f"no unallocated {side} party leg for ledger {ledger_id}")
        original_total = sum((getattr(l, side) for l in party), Decimal('0'))

        allocated_total = Decimal('0')
        new_lines = []
        for _, r in group.iterrows():
            billno = clean(r['billno'])
            amt = dec(r['amount'])
            bill = self._resolve_bill(billno, is_sales)
            if bill is None:
                self.unresolved.append({
                    'kind': kind, 'voucher': f"{v_typ}:{v_id}", 'billno': billno,
                    'error': 'bill not found',
                })
                raise ValueError(f"bill {billno!r} not found")
            allocated_total += amt
            new_lines.append((bill, amt, billno))
            tracker = self.sales_alloc if is_sales else self.purch_alloc
            tracker[bill] = tracker.get(bill, Decimal('0')) + amt

        if allocated_total > original_total + Decimal('0.01'):
            raise ValueError(
                f"allocations {allocated_total} exceed party leg {original_total}"
            )

        if self.apply:
            VoucherDetail.objects.filter(id__in=[l.id for l in party]).delete()
            for bill, amt, billno in new_lines:
                VoucherDetail.objects.create(
                    voucher_main=voucher, voucher_no=voucher.voucher_no,
                    voucher_type=voucher.voucher_type, account_id=ledger_id,
                    debit=(Decimal('0') if is_sales else amt),
                    credit=(amt if is_sales else Decimal('0')),
                    ref_bill_no=billno, **{ref_field: bill},
                )
            remainder = original_total - allocated_total
            if remainder > Decimal('0.005'):
                VoucherDetail.objects.create(
                    voucher_main=voucher, voucher_no=voucher.voucher_no,
                    voucher_type=voucher.voucher_type, account_id=ledger_id,
                    debit=(Decimal('0') if is_sales else remainder),
                    credit=(remainder if is_sales else Decimal('0')),
                    ref_bill_no='',
                )
        return 'done'

    def _tag_journal(self, voucher, ledger_id, group):
        """Journals are not split — tag the matching party line with the bill
        reference (FK if a unique bill resolves, plus ref_bill_no text)."""
        line = voucher.transactions.filter(account_id=ledger_id).first()
        if line is None:
            raise ValueError(f"no line for ledger {ledger_id} on journal {voucher.voucher_no}")
        billno = clean(group.iloc[0]['billno'])
        sv = SalesVou.objects.filter(billno=billno).order_by('id').first()
        pv = None if sv else PurchaseVoucher.objects.filter(billno=billno).order_by('id').first()
        if self.apply:
            line.ref_bill_no = billno[:30]
            if sv:
                line.ref_sales_vou = sv
            elif pv:
                line.ref_purchase_vou = pv
            line.save(update_fields=['ref_bill_no', 'ref_sales_vou', 'ref_purchase_vou'])
        return 'done'

    # ------------------------------------------------------------------ #
    def _resolve_bill(self, billno, is_sales):
        model = SalesVou if is_sales else PurchaseVoucher
        return model.objects.filter(billno=clean(billno)).order_by('id').first()

    def _reconcile_due_amts(self):
        """due_amt = max(0, gross total − total allocated) for each touched bill."""
        for sv, alloc in self.sales_alloc.items():
            gross = Decimal(str(sv.total_bill_value or 0))
            sv.due_amt = max(Decimal('0'), gross - alloc)
            sv.save(update_fields=['due_amt'])
        for pv, alloc in self.purch_alloc.items():
            gross = pv.total_incl_gst or pv.bill_value or Decimal('0')
            pv.due_amt = max(Decimal('0'), gross - alloc)
            pv.save(update_fields=['due_amt'])

    def _report(self, report_dir):
        if not self.unresolved:
            return
        os.makedirs(report_dir, exist_ok=True)
        path = os.path.join(report_dir, 'unresolved_allocations.csv')
        pd.DataFrame(self.unresolved).to_csv(path, index=False)
        self.stdout.write(self.style.WARNING(f"{len(self.unresolved)} unresolved row(s) -> {path}"))
