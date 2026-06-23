"""
Shared helpers for legacy-ERP CSV migration management commands
(import_sales, import_purchases, import_voucher_allocations).

Kept deliberately dependency-light: pandas for parsing, plain Django ORM for
lookups. All value parsing is NaN/blank tolerant because legacy MySQL exports
use '0000-00-00' dates, empty strings and stringified numbers throughout.
"""
from decimal import Decimal, InvalidOperation

import pandas as pd

from mastersconfig.models import RetailMaster, BranchMaster, FiscalYearMaster
from goldrates.models import PurityMaster
from accounting.models import VoucherMain


def clean(val):
    """Stripped string, or '' for NaN/None."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ''
    return str(val).strip()


def dec(val, default='0'):
    s = clean(val)
    if s == '':
        return Decimal(default)
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def to_int(val, default=0):
    s = clean(val)
    if s == '':
        return default
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return default


def parse_date(val):
    s = clean(val)
    if s == '' or s.startswith('0000'):
        return None
    ts = pd.to_datetime(s, errors='coerce', dayfirst=False)
    return None if pd.isna(ts) else ts.date()


def fy_short(ac_yr):
    """'2025-2026' -> '25-26'; '25-26' -> '25-26'."""
    s = clean(ac_yr)
    if '-' not in s:
        return s
    a, b = s.split('-', 1)
    return f"{a[-2:]}-{b[-2:]}"


class OrgResolver:
    """Resolves legacy rt_code/br_code/ac_yr to master FKs.

    Retail is a hard requirement (every voucher needs one). Branch and fiscal
    year are optional — a missing master yields None (with a warning), never an
    abort, because FiscalYearMaster rows for historical years may not exist yet.
    """

    def __init__(self, stdout=None, style=None):
        self.retail = {r.retail_code: r for r in RetailMaster.objects.all()}
        self.branch = {b.branch_code: b for b in BranchMaster.objects.all()}
        self.fy = {f.fy_code: f for f in FiscalYearMaster.objects.all()}
        self._stdout = stdout
        self._style = style
        self._warned = set()

    def _warn(self, msg):
        if self._stdout and msg not in self._warned:
            self._warned.add(msg)
            line = self._style.WARNING(msg) if self._style else msg
            self._stdout.write(line)

    def validate_retail(self, rt_codes):
        """Return a list of error strings for any rt_code lacking a RetailMaster."""
        errors = []
        for c in rt_codes:
            c = clean(c)
            if c and c not in self.retail:
                errors.append(
                    f"retail code {c!r} has no RetailMaster (have: {sorted(self.retail)})"
                )
        return errors

    def get(self, rt_code, br_code, ac_yr):
        rt = clean(rt_code)
        retail = self.retail[rt]  # KeyError only if validate_retail was skipped
        branch = self.branch.get(clean(br_code))
        if clean(br_code) and branch is None:
            self._warn(f"branch code {clean(br_code)!r} has no BranchMaster — branch_ref null")
        short = fy_short(ac_yr)
        fy = self.fy.get(short)
        if short and fy is None:
            self._warn(f"fiscal year {clean(ac_yr)!r} (-> {short!r}) has no FiscalYearMaster — fiscal_year null")
        return retail, branch, fy


class PurityResolver:
    """Resolves a legacy purity string (e.g. '14', '916', '22K') to a
    PurityMaster, creating it on miss (per user decision: match-else-create)."""

    def __init__(self):
        self.cache = {p.purity.strip(): p for p in PurityMaster.objects.all()}
        self.created = []

    # legacy sentinels meaning "no purity" (e.g. stone/diamond lines)
    _NONE_VALUES = {'', '0', '0.0', '0.00', '0.000'}

    def resolve(self, value, apply):
        s = clean(value)
        if s in self._NONE_VALUES:
            return None
        if s in self.cache:
            return self.cache[s]
        if apply:
            p = PurityMaster.objects.create(purity=s[:10], gw_per=Decimal('0'))
            self.cache[s] = p
            self.created.append(s)
            return p
        # dry-run: record the would-be create, return None
        if s not in self.created:
            self.created.append(s)
        return None


def resolve_ac_voucher(v_typ, v_id, ac_yr, rt_code):
    """Resolve a legacy (v_typ, v_id, ac_yr, rt_code) GL voucher to its
    imported VoucherMain via legacy_key. Returns None if not found."""
    if not clean(v_id):
        return None
    key = f"{clean(v_typ)}:{clean(v_id)}:{clean(ac_yr)}:{clean(rt_code)}"
    return VoucherMain.objects.filter(legacy_key=key).first()
