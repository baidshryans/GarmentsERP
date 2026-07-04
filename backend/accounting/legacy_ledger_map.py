"""Resolve legacy (old-ERP) ledger names to canonical seeded ledgers during the
MySQL sync, so TDS/TCS/PF/ESI ledgers fold onto their seeded equivalents instead
of importing as ungrouped duplicates.

See docs/superpowers/specs/2026-07-04-legacy-ledger-aliasing-design.md
"""

import re

# Legacy ledger name (normalized: lowercase, single-spaced) -> canonical seeded
# ledger name (normalized). Merged into the sync's system_by_name lookup so these
# fold via the existing alias path. Section-based TDS/TCS are handled separately.
EXTRA_SYNONYMS = {
    "provident fund (employee)": "pf payable",
    "esic employee contribution a/c": "esi payable",
}


def parse_tds_tcs_section(legacy_name):
    """Parse a legacy TDS/TCS ledger name into (kind, canonical_section_code).

    Returns ('TDS', '194C') / ('TCS', '206C1H'), or None if the name is not a
    section-based TDS/TCS ledger.

    Normalization: a short TDS code beginning with '9' gains a leading '1'
    (94C->194C, 92B->192B); already-canonical codes (194Q, 195) pass through;
    any TCS 206* code maps to the seeded 206C1H. Trailing parentheticals such
    as '(1026)' are ignored.
    """
    if not legacy_name:
        return None
    compact = re.sub(r"[^A-Za-z0-9]", "", legacy_name).upper()
    if compact.startswith("TDS"):
        kind, rest = "TDS", compact[3:]
    elif compact.startswith("TCS"):
        kind, rest = "TCS", compact[3:]
    else:
        return None
    m = re.match(r"(\d{2,3}[A-Z]?)", rest)
    if not m:
        return None
    tok = m.group(1)
    if kind == "TCS":
        # Only one TCS section (206C1H) is seeded today, so all 206* codes collapse
        # onto it. Revisit this if more 206-series subsections are added.
        section = "206C1H" if tok.startswith("206") else tok
    else:
        section = "1" + tok if re.match(r"^9\d", tok) else tok
    return (kind, section)


def resolve_section_ledger(legacy_name):
    """Return the seeded canonical Ledger for a legacy TDS/TCS ledger name, or
    None if the name isn't TDS/TCS or its section isn't seeded."""
    parsed = parse_tds_tcs_section(legacy_name)
    if not parsed:
        return None
    kind, section = parsed
    from mastersconfig.models import TDSSectionMaster, TCSSectionMaster
    model = TDSSectionMaster if kind == "TDS" else TCSSectionMaster
    sec = model.objects.filter(section_code=section).first()
    return sec.ledger if sec else None
