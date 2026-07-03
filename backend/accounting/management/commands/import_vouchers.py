"""
Import legacy GL vouchers (Voucher Main + Voucher Details) into VoucherMain /
VoucherDetail.

The legacy system stores vouchers as two tables with NO foreign key between
them; they are joined on the composite key (v_id, v_typ) scoped by
(ac_yr, br_code, rt_code) because v_id restarts per voucher type / branch / year.

Ledger codes need no mapping table: the legacy ledger import (importaccs.py)
creates Ledger rows with id == legacy ledger code, so legacy `ldgr` resolves
directly to Ledger.objects.get(id=<code>).

Usage:
    python manage.py import_vouchers \
        --main  path/to/voucher_main.csv \
        --details path/to/voucher_details.csv \
        [--apply] [--continue-on-error] [--report-dir DIR]

Without --apply the command runs as a dry-run: it validates, balances and
reports, but writes nothing to the database.
"""
import os
from decimal import Decimal, InvalidOperation

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounting.models import VoucherMain, VoucherDetail
from contacts.models import Ledger
from mastersconfig.models import RetailMaster, BranchMaster, FiscalYearMaster
from accounting.migration_utils import resolve_ledger, norm_id


# Legacy v_typ -> target voucher_type. Most values already line up; this dict
# only needs entries for renames. Anything not listed passes through unchanged.
VOUCHER_TYPE_MAP = {
    # 'OLD': 'NEW',
}

# Key columns used to reconstruct the missing Main<->Details relationship.
GROUP_COLS = ['v_id', 'v_typ', 'ac_yr', 'br_code', 'rt_code']


def _clean(val):
    """Return a stripped string, or '' for NaN/None."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ''
    return str(val).strip()


def _dec(val):
    """Parse a decimal; blank/NaN -> Decimal('0')."""
    s = _clean(val)
    if s == '':
        return Decimal('0')
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal('0')


def _date(val):
    s = _clean(val)
    if s == '' or s.startswith('0000'):
        return None
    ts = pd.to_datetime(s, errors='coerce', dayfirst=False)
    return None if pd.isna(ts) else ts.date()


def _fy_short(ac_yr):
    """'2025-2026' -> '25-26'; '25-26' -> '25-26'."""
    s = _clean(ac_yr)
    if '-' not in s:
        return s
    a, b = s.split('-', 1)
    return f"{a[-2:]}-{b[-2:]}"


def _fy_dates(ac_yr):
    """Indian FY date range from a legacy ac_yr. '2025-2026' / '25-26' ->
    (2025-04-01, 2026-03-31). Returns (None, None) if unparseable."""
    from datetime import date
    s = _clean(ac_yr)
    parts = s.split('-') if '-' in s else [s]

    def _yr(p):
        p = p.strip()
        if p.isdigit() and len(p) == 4:
            return int(p)
        if p.isdigit() and len(p) == 2:
            return 2000 + int(p)
        return None

    start = _yr(parts[0]) if parts else None
    if start is None:
        return None, None
    end = _yr(parts[1]) if len(parts) > 1 and _yr(parts[1]) else start + 1
    return date(start, 4, 1), date(end, 3, 31)


class Command(BaseCommand):
    help = "Import legacy GL vouchers (voucher_main + voucher_details CSVs)."

    def add_arguments(self, parser):
        parser.add_argument('--main', required=True, help='voucher_main CSV path')
        parser.add_argument('--details', required=True, help='voucher_details CSV path')
        parser.add_argument('--apply', action='store_true',
                            help='Persist to the database (default: dry-run).')
        parser.add_argument('--continue-on-error', action='store_true',
                            help='Skip bad vouchers instead of aborting.')
        parser.add_argument('--report-dir', default='.',
                            help='Directory for unresolved_*.csv reports.')

    # ------------------------------------------------------------------ #
    # status mapping. In the legacy schema the `status` column is NOT a
    # posted/cancelled flag: it holds a bill-number reference (e.g.
    # "C2526/00457" on RCPT-SALE receipts — used by the Phase 2 allocation
    # pass) or the literal "Voucher Cancelled". `hide_status` is meaningless.
    # Only an explicit cancellation maps to 'cancelled'.
    # ------------------------------------------------------------------ #
    @staticmethod
    def _map_status(main_row):
        status = _clean(main_row.get('status')).lower()
        if 'cancel' in status:
            return 'cancelled'
        return 'posted'

    def handle(self, *args, **opts):
        main_path, det_path = opts['main'], opts['details']
        for p in (main_path, det_path):
            if not os.path.exists(p):
                raise CommandError(f"File not found: {p}")

        apply = opts['apply']
        cont = opts['continue_on_error']
        report_dir = opts['report_dir']

        main_df = pd.read_csv(main_path, dtype=str)
        det_df = pd.read_csv(det_path, dtype=str)
        main_df.columns = [c.strip() for c in main_df.columns]
        det_df.columns = [c.strip() for c in det_df.columns]

        # ---- 1. resolve org masters up front --------------------------- #
        org_maps, org_errors = self._build_org_maps(main_df, det_df)
        if org_errors:
            for e in org_errors:
                self.stderr.write(self.style.ERROR(e))
            raise CommandError(
                "Unresolved org codes (retail / branch / fiscal year). "
                "Import the masters first, then re-run."
            )
        retail_map, branch_map, fy_map = org_maps

        # ---- 2. index the main headers by group key -------------------- #
        main_index = {}
        for _, r in main_df.iterrows():
            main_index[self._key(r)] = r

        # ---- 3. group detail rows -------------------------------------- #
        grouped = det_df.groupby([det_df[c] for c in GROUP_COLS], sort=False)

        created = skipped = errored = imbalanced = 0
        unresolved_rows = []   # bad detail rows (ledger missing, etc.)
        imbalance_rows = []    # vouchers that don't balance

        for _, group in grouped:
            head = group.iloc[0]
            legacy_key = self._legacy_key(head)

            if VoucherMain.objects.filter(legacy_key=legacy_key).exists():
                skipped += 1
                continue

            main_row = main_index.get(self._key(head))

            try:
                with transaction.atomic():
                    result = self._import_one(
                        group, main_row, legacy_key,
                        retail_map, branch_map, fy_map, apply,
                    )
                if result.get('imbalanced'):
                    imbalanced += 1
                    imbalance_rows.append(result['imbalance_info'])
                    if not cont:
                        raise CommandError(
                            f"Voucher {legacy_key} does not balance "
                            f"(Dr {result['debit']} != Cr {result['credit']}). "
                            f"Use --continue-on-error to skip."
                        )
                    continue
                unresolved_rows.extend(result.get('unresolved', []))
                created += 1
            except CommandError:
                raise
            except Exception as exc:
                errored += 1
                msg = f"Voucher {legacy_key}: {exc}"
                self.stderr.write(self.style.ERROR(msg))
                unresolved_rows.append({'legacy_key': legacy_key, 'error': str(exc)})
                if not cont:
                    raise CommandError(msg)

        self._write_reports(report_dir, unresolved_rows, imbalance_rows)

        mode = "APPLIED" if apply else "DRY-RUN (no writes)"
        self.stdout.write(self.style.SUCCESS(
            f"\n[{mode}] created={created} skipped(existing)={skipped} "
            f"errored={errored} imbalanced={imbalanced}"
        ))
        if not apply:
            self.stdout.write(self.style.WARNING(
                "Dry run complete — re-run with --apply to persist."
            ))

    # ------------------------------------------------------------------ #
    def _resolve_fy(self, retail, ac, apply):
        """Get-or-create THE FiscalYearMaster for this legacy ac_yr. FY is
        company-global (identified by fy_code; no per-retail rows): reuse any
        existing row for the code; create one (Apr 1 – Mar 31) when none exists.
        Cached by fy_code. Dry-run returns existing only. After creating/finding
        an FY (when applying) advances the company-wide active FY to the newest
        FY seen so the sidebar populates right after a data sync."""
        short = _fy_short(ac)
        if not short:
            return None
        cache = getattr(self, '_fy_cache', None)
        if cache is None:
            cache = self._fy_cache = {}
        if short in cache:
            return cache[short]
        fy = FiscalYearMaster.objects.filter(fy_code=short).first()
        if fy is None and apply:
            start, end = _fy_dates(ac)
            if start is not None:
                fy = FiscalYearMaster.objects.create(
                    fy_code=short, fy_start=start, fy_end=end,
                )
                self.stdout.write(self.style.WARNING(
                    f"created FiscalYearMaster {short} ({start}–{end})"
                ))
        cache[short] = fy
        if fy is not None and apply:
            from mastersconfig.models import SystemSettings
            current = SystemSettings.get().active_fy
            if current is None or (
                fy.fy_start and (current.fy_start is None or fy.fy_start >= current.fy_start)
            ):
                SystemSettings.set_company_active_fy(fy)
        return fy

    def _import_one(self, group, main_row, legacy_key,
                    retail_map, branch_map, fy_map, apply):
        head = group.iloc[0]
        rt, br, ac = _clean(head['rt_code']), _clean(head['br_code']), _clean(head['ac_yr'])
        retail = retail_map[rt]
        branch = branch_map.get(br)
        fy = self._resolve_fy(retail, ac, apply)

        v_typ = _clean(head['v_typ'])
        voucher_type = VOUCHER_TYPE_MAP.get(v_typ, v_typ)
        v_id = _clean(head['v_id'])

        # header fields (fall back to detail row when no main header found)
        if main_row is not None:
            date = _date(main_row.get('date1')) or _date(head.get('date1'))
            narration = _clean(main_row.get('nar'))[:150]
            amount = _dec(main_row.get('tot_amt'))
            status = self._map_status(main_row)
            bank_nm = _clean(main_row.get('bank_nm'))[:200]
        else:
            date = _date(head.get('date1'))
            narration = ''
            amount = Decimal('0')
            status = 'posted'
            bank_nm = ''

        voucher_no = self._voucher_no(voucher_type, rt, ac, v_id)

        # build detail lines first so we can validate balance pre-write
        lines, unresolved = [], []
        total_dr = total_cr = Decimal('0')
        for _, r in group.iterrows():
            ldgr_code = _clean(r['ldgr'])
            account = resolve_ledger(ldgr_code)
            if account is None:
                unresolved.append({
                    'legacy_key': legacy_key, 'ldgr': ldgr_code,
                    'error': 'ledger not found',
                })
                raise ValueError(f"ledger code {ldgr_code!r} not found")
            dr, cr = _dec(r['dbt']), _dec(r['crdt'])
            total_dr += dr
            total_cr += cr
            lines.append(dict(
                account=account, debit=dr, credit=cr,
                # rmks is descriptive ("Against Reference" / "On Account"), not a
                # bill number — leave ref_bill_no empty so the allocation pass can
                # populate it with the real bill it settles.
                ref_bill_no='',
                chq_no=(_clean(r.get('chq_no'))[:200] or None),
                chq_date=_date(r.get('chq_date')),
                party_bank_name=(bank_nm or None),
                voucher_type=voucher_type,
                status=(status or None),
            ))

        if total_dr != total_cr:
            return {
                'imbalanced': True, 'debit': total_dr, 'credit': total_cr,
                'imbalance_info': {
                    'legacy_key': legacy_key, 'debit': str(total_dr),
                    'credit': str(total_cr), 'tot_amt': str(amount),
                },
            }
        if amount == 0:
            amount = total_dr  # legacy header total missing -> use balanced sum

        if apply:
            vm = VoucherMain.objects.create(
                date=date, voucher_no=voucher_no, narration=narration,
                amount=amount, voucher_type=voucher_type, status=status,
                retail=retail, branch_ref=branch, fiscal_year=fy,
                legacy_key=legacy_key,
            )
            VoucherDetail.objects.bulk_create([
                VoucherDetail(voucher_main=vm, voucher_no=voucher_no, **ln)
                for ln in lines
            ])

        return {'imbalanced': False, 'unresolved': unresolved}

    # ------------------------------------------------------------------ #
    def _build_org_maps(self, main_df, det_df):
        errors = []
        rt_codes = set(det_df['rt_code'].dropna().map(str.strip))
        br_codes = set(det_df['br_code'].dropna().map(str.strip))
        ac_years = set(det_df['ac_yr'].dropna().map(str.strip))

        retail_map = {r.retail_code: r for r in RetailMaster.objects.all()}
        branch_map = {b.branch_code: b for b in BranchMaster.objects.all()}
        fy_map = {f.fy_code: f for f in FiscalYearMaster.objects.all()}

        for c in rt_codes:
            if c and c not in retail_map:
                errors.append(
                    f"retail code {c!r} has no RetailMaster "
                    f"(have: {sorted(retail_map)})"
                )
        for c in br_codes:
            if c and c not in branch_map:
                self.stdout.write(self.style.WARNING(
                    f"branch code {c!r} has no BranchMaster — branch_ref left null"
                ))
        for c in ac_years:
            short = _fy_short(c)
            if short and short not in fy_map:
                # A missing FiscalYearMaster is created on demand per retail in
                # _resolve_fy(), so vouchers always land in the correct year.
                self.stdout.write(self.style.WARNING(
                    f"fiscal year {c!r} (-> {short!r}) not found — will be auto-created per retail"
                ))
        return (retail_map, branch_map, fy_map), errors

    @staticmethod
    def _key(row):
        return tuple(_clean(row[c]) for c in GROUP_COLS)

    @staticmethod
    def _legacy_key(row):
        return (f"{_clean(row['v_typ'])}:{norm_id(row['v_id'])}:"
                f"{_clean(row['ac_yr'])}:{_clean(row['rt_code'])}")

    @staticmethod
    def _voucher_no(voucher_type, rt_code, ac_yr, v_id):
        fy = _fy_short(ac_yr)
        try:
            seq = f"{int(float(v_id)):05d}"  # '368.0' -> '00368'
        except (ValueError, TypeError):
            seq = norm_id(v_id)
        vn = f"LEG/{voucher_type}/{rt_code}/{fy}/{seq}"
        if len(vn) > 30:
            # fall back to a compact, still-deterministic form
            vn = f"LEG/{voucher_type}/{seq}"[:30]
        return vn

    def _write_reports(self, report_dir, unresolved_rows, imbalance_rows):
        os.makedirs(report_dir, exist_ok=True)
        if unresolved_rows:
            path = os.path.join(report_dir, 'unresolved_vouchers.csv')
            pd.DataFrame(unresolved_rows).to_csv(path, index=False)
            self.stdout.write(self.style.WARNING(
                f"{len(unresolved_rows)} unresolved row(s) -> {path}"
            ))
        if imbalance_rows:
            path = os.path.join(report_dir, 'imbalanced_vouchers.csv')
            pd.DataFrame(imbalance_rows).to_csv(path, index=False)
            self.stdout.write(self.style.WARNING(
                f"{len(imbalance_rows)} imbalanced voucher(s) -> {path}"
            ))
