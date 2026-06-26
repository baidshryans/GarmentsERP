"""
Import legacy ledger opening balances (ldgr_open_balance) into
accounting.LedgerOpenBalance.

Legacy table `ldgr_open_balance` columns: id, ldgrcd (ledger code), debit,
credit, acc_year (e.g. '2025-2026'), comcd, gr_code, mn_grp, br_code, rt_code.

  ldgrcd   -> ldgr      (via resolve_ledger: alias-aware, Ledger.id == code)
  debit    -> debit
  credit   -> credit
  acc_year -> acc_year  (stored as fy_code '25-26', matching how the app reads it)
  rt_code  -> retail

Idempotent: upserts on the (ldgr, retail, acc_year) unique key. Run after
ledgers + retail masters are imported.

Usage:
  python manage.py import_ledger_opening --file ldgr_open_balance.csv \
      [--apply] [--continue-on-error] [--report-dir DIR]
"""
import os

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from accounting.models import LedgerOpenBalance
from accounting.migration_utils import clean, dec, fy_short, OrgResolver, resolve_ledger


class Command(BaseCommand):
    help = "Import legacy ledger opening balances (ldgr_open_balance CSV)."

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='ldgr_open_balance CSV')
        parser.add_argument('--apply', action='store_true', help='Persist (default: dry-run).')
        parser.add_argument('--continue-on-error', action='store_true')
        parser.add_argument('--report-dir', default='.')

    def handle(self, *args, **opts):
        path = opts['file']
        if not os.path.exists(path):
            raise CommandError(f"File not found: {path}")
        apply = opts['apply']
        cont = opts['continue_on_error']

        df = pd.read_csv(path, dtype=str)
        df.columns = [c.strip() for c in df.columns]

        org = OrgResolver(self.stdout, self.style, apply=apply)
        errs = org.validate_retail(set(df.get('rt_code', pd.Series(dtype=str)).dropna()))
        if errs:
            for e in errs:
                self.stderr.write(self.style.ERROR(e))
            raise CommandError("Unresolved retail codes — import masters first.")

        created = updated = skipped = errored = 0
        unresolved = []
        for _, r in df.iterrows():
            try:
                code = clean(r.get('ldgrcd'))
                ldgr = resolve_ledger(code)
                retail = org.retail.get(clean(r.get('rt_code')))
                if ldgr is None or retail is None:
                    skipped += 1
                    unresolved.append({
                        'ldgrcd': code, 'rt_code': clean(r.get('rt_code')),
                        'error': 'ledger not found' if ldgr is None else 'retail not found',
                    })
                    continue
                acc_year = fy_short(r.get('acc_year'))
                defaults = {'debit': dec(r.get('debit')), 'credit': dec(r.get('credit'))}
                exists = LedgerOpenBalance.objects.filter(
                    ldgr=ldgr, retail=retail, acc_year=acc_year).exists()
                if apply:
                    LedgerOpenBalance.objects.update_or_create(
                        ldgr=ldgr, retail=retail, acc_year=acc_year, defaults=defaults)
                if exists:
                    updated += 1
                else:
                    created += 1
            except Exception as exc:
                errored += 1
                unresolved.append({'ldgrcd': clean(r.get('ldgrcd')), 'error': str(exc)})
                self.stderr.write(self.style.ERROR(f"ldgr {clean(r.get('ldgrcd'))}: {exc}"))
                if not cont:
                    raise CommandError(str(exc))

        if unresolved:
            os.makedirs(opts['report_dir'], exist_ok=True)
            rp = os.path.join(opts['report_dir'], 'unresolved_ledger_opening.csv')
            pd.DataFrame(unresolved).to_csv(rp, index=False)
            self.stdout.write(self.style.WARNING(f"{len(unresolved)} unresolved row(s) -> {rp}"))

        mode = "APPLIED" if apply else "DRY-RUN (no writes)"
        self.stdout.write(self.style.SUCCESS(
            f"[{mode}] ledger_opening: created={created} updated={updated} "
            f"skipped(unresolved)={skipped} errored={errored}"
        ))
        if not apply:
            self.stdout.write(self.style.WARNING("Dry run — re-run with --apply to persist."))
