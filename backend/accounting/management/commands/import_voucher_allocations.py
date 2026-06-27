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
        self.text_tagged = 0  # bills tagged by number only (no migrated voucher FK)

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
        for name, (alloc, skipped, errored, unresolved, recorded) in totals.items():
            self.stdout.write(self.style.SUCCESS(
                f"[{mode}] {name}: vouchers-allocated={alloc} skipped(existing)={skipped} "
                f"bill-unresolved={unresolved} errored={errored}"
            ))
        if self.text_tagged:
            self.stdout.write(self.style.SUCCESS(
                f"  ({self.text_tagged} bill(s) tagged by vendor bill-no only — "
                f"journal-recorded, no migrated voucher to link)"))
        if not self.apply:
            self.stdout.write(self.style.WARNING("Dry run — re-run with --apply to persist."))

    # ------------------------------------------------------------------ #
    # Prior-year amount rows reference vouchers that aren't in the migrated
    # voucher_main (only 2026-2027 exists), so skip them.
    SKIP_ACC_YEARS = {'2025-2026', '25-26'}

    def _run(self, path, kind):
        if not os.path.exists(path):
            raise CommandError(f"File not found: {path}")
        df = pd.read_csv(path, dtype=str)
        df.columns = [c.strip() for c in df.columns]

        year_skipped = 0
        if 'acc_year' in df.columns:
            mask = df['acc_year'].astype(str).str.strip().isin(self.SKIP_ACC_YEARS)
            year_skipped = int(mask.sum())
            df = df[~mask]

        # Drop exact-duplicate allocation rows (legacy double-inserts). The legacy
        # `id` repeats per branch so it isn't part of the identity; an allocation
        # is identified by voucher + ledger + bill + amount.
        idcols = [c for c in ('v_typ', 'v_id', 'acc_year', 'rt_code',
                              'ledger_id', 'billno', 'amount') if c in df.columns]
        before = len(df)
        df = df.drop_duplicates(subset=idcols)
        dup_dropped = before - len(df)
        if dup_dropped:
            self.stdout.write(self.style.WARNING(
                f"{kind}: dropped {dup_dropped} exact-duplicate row(s)"))

        allocated = skipped = errored = unresolved = recorded = 0
        grouped = df.groupby([df[c] for c in GROUP_COLS], sort=False)
        for _, group in grouped:
            head = group.iloc[0]
            try:
                with transaction.atomic():
                    res = self._allocate_group(head, group, kind)
                if res == 'skipped':
                    skipped += 1
                elif res == 'unresolved':
                    unresolved += 1
                elif res == 'recorded':
                    recorded += 1
                elif res == 'done':
                    allocated += 1
            except Exception as exc:
                errored += 1
                key = f"{clean(head['v_typ'])}:{clean(head['v_id'])} ldgr={clean(head['ledger_id'])}"
                self.unresolved.append({'kind': kind, 'voucher': key, 'error': str(exc)})
                self.stderr.write(self.style.ERROR(f"{kind} {key}: {exc}"))
                if not self.cont:
                    raise CommandError(str(exc))
        if year_skipped:
            self.stdout.write(self.style.WARNING(
                f"{kind}: skipped {year_skipped} prior-year (2025-2026) row(s)"))
        return allocated, skipped, errored, unresolved, recorded

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

        # idempotency: a line already carrying a bill reference for this ledger —
        # either the FK or a non-empty ref_bill_no (text, for journal-recorded
        # bills) — means this voucher was already allocated -> skip.
        if voucher.transactions.filter(account_id=ledger_id).filter(
            Q(**{f'{ref_field}__isnull': False})
            | (Q(ref_bill_no__isnull=False) & ~Q(ref_bill_no=''))
        ).exists():
            return 'skipped'

        # the unallocated party leg(s) for this ledger: no FK and no bill text yet.
        party = list(voucher.transactions.filter(
            account_id=ledger_id, **{f'{side}__gt': 0},
        ).filter(**{f'{ref_field}__isnull': True}).filter(
            Q(ref_bill_no__isnull=True) | Q(ref_bill_no='')
        ))
        if not party:
            raise ValueError(f"no unallocated {side} party leg for ledger {ledger_id}")
        original_total = sum((getattr(l, side) for l in party), Decimal('0'))

        allocated_total = Decimal('0')
        new_lines = []  # (bill_or_None, amt, billno)
        for _, r in group.iterrows():
            billno = clean(r['billno'])
            amt = dec(r['amount'])
            if not billno:
                continue
            # bill may be None: the bill wasn't migrated as a SalesVou/PurchaseVoucher
            # (e.g. a journal-recorded vendor invoice). We still tag the party leg
            # with the bill number so the voucher reads as allocated.
            bill = self._resolve_bill(billno, is_sales)
            allocated_total += amt
            new_lines.append((bill, amt, billno))
            if bill is not None:
                tracker = self.sales_alloc if is_sales else self.purch_alloc
                tracker[bill] = tracker.get(bill, Decimal('0')) + amt
            else:
                self.text_tagged += 1

        if not new_lines:
            return 'unresolved'  # no bill number in this group

        if allocated_total > original_total + Decimal('0.01'):
            # Corrupt/inconsistent source rows (e.g. a bill listed twice with
            # different amounts). Don't force it — report and leave the leg
            # on-account for manual review rather than over-allocating the GL.
            self.unresolved.append({
                'kind': kind, 'voucher': f"{v_typ}:{v_id}", 'billno': '',
                'error': f"allocations {allocated_total} exceed party leg "
                         f"{original_total} (corrupt/duplicate source rows)",
            })
            return 'unresolved'

        if self.apply:
            from accounting.models import ReferenceBills
            VoucherDetail.objects.filter(id__in=[l.id for l in party]).delete()
            for bill, amt, billno in new_lines:
                vd = VoucherDetail.objects.create(
                    voucher_main=voucher, voucher_no=voucher.voucher_no,
                    voucher_type=voucher.voucher_type, account_id=ledger_id,
                    debit=(Decimal('0') if is_sales else amt),
                    credit=(amt if is_sales else Decimal('0')),
                    ref_bill_no=billno[:30], **{ref_field: bill},
                )
                # Mirror the live allocate-bills: one ReferenceBills per bill. For
                # journal-recorded bills (bill is None) this carries the vendor
                # bill number as text on the voucher.
                ReferenceBills.objects.get_or_create(
                    voucher=voucher, ldgr_id=ledger_id, vendor_bill_no=billno[:50],
                    defaults={'amount': amt, 'ref_bill': vd, 'ref_bill_txt': billno[:50]},
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
            if not is_sales:
                self._set_vendor_bill(voucher, [bn for _, _, bn in new_lines])
        return 'done'

    def _set_vendor_bill(self, voucher, billnos):
        """Populate the header VoucherMain.vendor_bill — the 'Vendor Bill No' field
        shown on the voucher form — with the bill number(s) this voucher settles."""
        if not self.apply:
            return
        new = [b for b in dict.fromkeys(billnos) if b]
        if not new:
            return
        existing = [b.strip() for b in (voucher.vendor_bill or '').split(',') if b.strip()]
        val = ', '.join(dict.fromkeys(existing + new))[:50]
        if val != (voucher.vendor_bill or ''):
            voucher.vendor_bill = val
            voucher.save(update_fields=['vendor_bill'])

    def _tag_journal(self, voucher, ledger_id, group):
        """Journals are not split — tag the matching party line with the bill
        reference (FK if a unique bill resolves, plus ref_bill_no text)."""
        line = voucher.transactions.filter(account_id=ledger_id).first()
        if line is None:
            # The journal_amount references a ledger that has no line in the
            # imported GL voucher — report and skip rather than error.
            self.unresolved.append({
                'kind': 'journal', 'voucher': voucher.voucher_no,
                'billno': clean(group.iloc[0]['billno']),
                'error': f"no GL line for ledger {ledger_id} on this journal",
            })
            return 'unresolved'
        billnos = [b for b in (clean(x) for x in group['billno']) if b]
        billno = billnos[0] if billnos else ''
        sv = SalesVou.objects.filter(billno=billno).order_by('id').first()
        pv = None if sv else PurchaseVoucher.objects.filter(billno=billno).order_by('id').first()
        if self.apply:
            line.ref_bill_no = billno[:30]
            if sv:
                line.ref_sales_vou = sv
            elif pv:
                line.ref_purchase_vou = pv
            line.save(update_fields=['ref_bill_no', 'ref_sales_vou', 'ref_purchase_vou'])
            self._set_vendor_bill(voucher, billnos)
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
