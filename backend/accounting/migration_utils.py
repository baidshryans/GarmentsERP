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


def fy_dates(ac_yr):
    """Indian FY date range from a legacy ac_yr. '2025-2026' / '25-26' ->
    (date(2025,4,1), date(2026,3,31)). Returns (None, None) if unparseable."""
    from datetime import date
    s = clean(ac_yr)
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


class OrgResolver:
    """Resolves legacy rt_code/br_code/ac_yr to master FKs.

    Retail is a hard requirement (every voucher needs one). Branch is optional
    (null when missing). Fiscal year is GET-OR-CREATED per retail when `apply`
    is set, so vouchers always land in the correct year; dry-run resolves only
    what already exists.
    """

    def __init__(self, stdout=None, style=None, apply=False):
        self.retail = {r.retail_code: r for r in RetailMaster.objects.all()}
        self.branch = {b.branch_code: b for b in BranchMaster.objects.all()}
        self.apply = apply
        self._fy_cache = {}  # fy_code -> FiscalYearMaster (FY is company-wide)
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
        return retail, branch, self._resolve_fy(retail, ac_yr)

    def _resolve_fy(self, retail, ac_yr):
        # FY is company-wide (identified by fy_code, not per retail): reuse any
        # existing row for the code; create one only when none exists.
        short = fy_short(ac_yr)
        if not short:
            return None
        if short in self._fy_cache:
            return self._fy_cache[short]
        fy = FiscalYearMaster.objects.filter(fy_code=short).first()
        if fy is None and self.apply:
            start, end = fy_dates(ac_yr)
            if start is not None:
                fy = FiscalYearMaster.objects.create(
                    fy_code=short, fy_start=start, fy_end=end,
                )
                self._warn(f"created FiscalYearMaster {short} ({start}–{end})")
        self._fy_cache[short] = fy
        return fy


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


def hsn_for_voucher_items(main_items, detail_items):
    """Pick the HSN for a voucher: the first main-line item that has an HSN
    (Item.hsn_no), falling back to the first detail/component item with an HSN.
    `main_items`/`detail_items` are iterables of Item-or-None. Returns Hsn|None."""
    for it in main_items:
        hsn = getattr(it, 'hsn_no', None) if it is not None else None
        if hsn is not None:
            return hsn
    for it in detail_items:
        hsn = getattr(it, 'hsn_no', None) if it is not None else None
        if hsn is not None:
            return hsn
    return None


def split_gst(taxable, hsn, is_central):
    """(cgst, sgst, igst) amounts for a taxable value given an Hsn row and whether
    the supply is interstate (IGST) vs local (CGST+SGST)."""
    from decimal import Decimal, ROUND_HALF_UP
    t = Decimal(str(taxable or 0))

    def q(rate):
        return (t * Decimal(str(rate or 0)) / 100).quantize(Decimal('0.01'), ROUND_HALF_UP)

    if is_central:
        return Decimal('0.00'), Decimal('0.00'), q(hsn.igst)
    return q(hsn.cgst), q(hsn.sgst), Decimal('0.00')


def resolve_ledger(code):
    """Resolve a legacy ledger code to a Django Ledger.

    Checks the LedgerAlias map first (legacy GST/TCS/TDS and other system
    ledgers are folded onto their canonical ledger there), then falls back to
    the preserved-PK convention (Ledger.id == legacy code). Returns None if
    neither resolves. Tolerates float-formatted codes ('1038.0')."""
    from contacts.models import Ledger, LedgerAlias
    s = clean(code)
    if not s:
        return None
    i = to_int(s)
    key = str(i) if i is not None else s
    alias = LedgerAlias.objects.filter(legacy_code=key).first()
    if alias:
        return alias.ledger
    return Ledger.objects.filter(id=i).first() if i is not None else None


def norm_id(v):
    """Normalize an id-ish value to a clean integer string ('368.0' -> '368');
    pymysql returns ints as floats, so this keeps legacy keys/numbers tidy.
    Returns the cleaned original when not numeric."""
    i = to_int(v)
    return str(i) if i is not None else clean(v)


def resolve_ac_voucher(v_typ, v_id, ac_yr, rt_code):
    """Resolve a legacy (v_typ, v_id, ac_yr, rt_code) GL voucher to its
    imported VoucherMain via legacy_key. Returns None if not found."""
    if not clean(v_id):
        return None
    key = f"{clean(v_typ)}:{norm_id(v_id)}:{clean(ac_yr)}:{clean(rt_code)}"
    return VoucherMain.objects.filter(legacy_key=key).first()
