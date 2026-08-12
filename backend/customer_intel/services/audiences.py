"""
Meta Custom Audience export.

What this does and does not do
------------------------------
You cannot look a customer up on Facebook or Instagram from their phone number
— no compliant API exposes that, and vendors claiming to are a DPDP liability.
What IS supported is a *matched audience*: you upload SHA-256 hashes of contact
details, Meta matches them against its own users on its side, and you can then
advertise to that group (and to lookalikes of it). No per-person data comes back.

Normalisation is the whole game. Meta hashes its side using a fixed
normalisation, so a mismatch in case, spacing or country code silently produces
a 0% match rate rather than an error. Hence `test_audiences.py`'s golden vectors.

Privacy note: hashing makes the file pseudonymous, not anonymous — that is the
point of a matched audience. Exporting is therefore recorded in AudienceExport,
gated behind its own permission, and skips anyone who has opted out.
"""

import csv
import hashlib
import re

from contacts.crm_utils import clean_mobile, dial_code_for_retail

# Column order Meta's uploader understands when values are pre-hashed.
SCHEMA = ["phone", "email", "fn", "ln", "ct", "country"]

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def sha256_hex(value):
    """Meta expects lowercase hex SHA-256 of the normalised value."""
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalise_phone(raw, dial_code="91"):
    """
    Digits only, country code included, no '+' and no separators.

    '+91 98765 43210' → '919876543210'
    """
    local = clean_mobile(raw) or ""
    if not local:
        return ""
    digits = "".join(c for c in str(local) if c.isdigit())
    if not digits:
        return ""
    dial = "".join(c for c in str(dial_code or "") if c.isdigit())
    if dial and digits.startswith(dial) and len(digits) > 10:
        return digits
    return f"{dial}{digits}" if dial else digits


def normalise_email(raw):
    """Trimmed and lowercased. '  Foo@Bar.COM ' → 'foo@bar.com'"""
    if not raw:
        return ""
    return str(raw).strip().lower()


def normalise_name(raw):
    """Lowercase, punctuation and whitespace stripped."""
    if not raw:
        return ""
    return _NON_ALNUM.sub("", str(raw).strip().lower())


def normalise_city(raw):
    return normalise_name(raw)


def normalise_country(raw="IN"):
    """ISO-3166 alpha-2, lowercase."""
    return (str(raw or "IN").strip().lower())[:2]


def _split_name(full_name):
    parts = [p for p in str(full_name or "").split() if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[-1]


def hashed_row(ledger, dial_code="91", country="IN"):
    """One export row: every value already SHA-256 hashed."""
    first, last = _split_name(ledger.ac_name)
    phone = normalise_phone(
        ledger.mobile1 or ledger.mobile2 or ledger.phone1, dial_code,
    )
    return {
        "phone": sha256_hex(phone),
        "email": sha256_hex(normalise_email(ledger.email)),
        "fn": sha256_hex(normalise_name(first)),
        "ln": sha256_hex(normalise_name(last)),
        "ct": sha256_hex(normalise_city(ledger.city)),
        # Note: Indian PIN codes are 6 digits where Meta documents 5 for US
        # ZIPs. `zip` is therefore deliberately not exported — a truncated PIN
        # would depress the match rate rather than help it.
        "country": sha256_hex(normalise_country(country)),
    }


def build_rows(snapshots, retail):
    """
    Hashed rows for a segment's members, minus anyone unreachable.

    Returns (rows, stats). Opted-out customers are dropped here as well as at
    send time — an audience export is marketing, and consent applies to it just
    as much as to a message.
    """
    from customer_intel.models import CustomerSocialProfile

    dial = dial_code_for_retail(retail)
    ledger_ids = [s.ledger_id for s in snapshots]

    from django.db.models import Q

    opted_out = set(
        CustomerSocialProfile.objects
        .filter(ledger_id__in=ledger_ids)
        .filter(Q(opt_out_at__isnull=False) | Q(whatsapp_opt_in=False))
        .values_list("ledger_id", flat=True)
    )

    rows, stats = [], {"total": len(snapshots), "opted_out": 0, "no_identifier": 0}
    for snapshot in snapshots:
        if snapshot.ledger_id in opted_out:
            stats["opted_out"] += 1
            continue
        row = hashed_row(snapshot.ledger, dial_code=dial)
        if not row["phone"] and not row["email"]:
            stats["no_identifier"] += 1
            continue
        rows.append(row)

    stats["exported"] = len(rows)
    return rows, stats


def write_csv(file_obj, rows):
    """Write the pre-hashed rows in Meta's expected column order."""
    writer = csv.DictWriter(file_obj, fieldnames=SCHEMA)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return file_obj
