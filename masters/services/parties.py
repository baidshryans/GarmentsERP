"""Parties: customers, vendors, fabricators, agents, transporters (E3.1, CRM, MST-08)."""
import re

from django.core.exceptions import ValidationError
from django.db import transaction

from core.exceptions import BusinessRuleError
from core.validators import validate_gstin, validate_pan
from ledger.models import AccountGroup, Ledger
from masters.models import Party
from masters.services.codes import next_code

ROLE_FIELDS = ("is_customer", "is_vendor", "is_fabricator", "is_agent", "is_transporter")
PAYABLE_ROLES = ("is_vendor", "is_fabricator", "is_agent", "is_transporter")
EDITABLE_FIELDS = (
    "name", "contact_person", *ROLE_FIELDS, "mobile", "mobile2", "mobile3", "landline", "email", "gstin", "pan",
    "state_code", "category", "price_list", "discount_pct", "credit_limit", "credit_days", "payment_terms",
    "agent", "transporter", "destination", "tds_section", "is_active",
)
MOBILE_RE =re.compile(r"^[6-9][0-9]{9}$")


def normalise_mobile(raw, *, required=True, label="Mobile"):
    digits = re.sub(r"\D", "", raw or "")[-10:]
    if not digits:
        if required:
            raise ValidationError(f"{label} is required.")
        return ""
    if not MOBILE_RE.match(digits):
        raise ValidationError(f"{label} must be a 10-digit Indian mobile number.")
    return digits


def _clean(fields, party=None):
    """Validate and derive fields. Returns a cleaned copy."""
    f = dict(fields)
    f["mobile"] = normalise_mobile(f.get("mobile"))
    f["mobile2"] = normalise_mobile(f.get("mobile2"), required=False, label="Alternate mobile")
    f["mobile3"] = normalise_mobile(f.get("mobile3"), required=False, label="Alternate mobile 2")
    gstin = (f.get("gstin") or "").strip().upper()
    validate_gstin(gstin)
    f["gstin"] = gstin
    pan = (f.get("pan") or "").strip().upper()
    if gstin:
        f["state_code"] = gstin[:2]  # the GSTIN decides the State (CRM-03)
        pan = pan or gstin[2:12]
    validate_pan(pan)
    f["pan"] = pan
    if not any(f.get(r) for r in ROLE_FIELDS):
        raise ValidationError("Choose at least one role: customer, vendor, fabricator, agent or transporter.")
    if f.get("discount_pct") is not None and not 0 <= f["discount_pct"] <= 100:
        raise ValidationError("Discount % must be between 0 and 100.")
    return f


def _check_duplicate_mobile(company, f, party=None):
    others = Party.objects.filter(company=company, mobile=f["mobile"])
    if party is not None:
        others = others.exclude(pk=party.pk)
    if f.get("is_customer"):
        clash = others.filter(is_customer=True).first()
        if clash:
            raise BusinessRuleError(f"Mobile {f['mobile']} already belongs to customer {clash.name}.")
    if f.get("is_fabricator"):
        clash = others.filter(is_fabricator=True).first()
        if clash:
            raise BusinessRuleError(f"Mobile {f['mobile']} already belongs to fabricator {clash.name}.")


def _ledger_name(base, code, suffix=""):
    name = f"{base}{suffix}"
    if Ledger.objects.filter(name=name).exists():
        name = f"{base}{suffix} [{code}]"
    return name


def _group(company, name):
    return AccountGroup.objects.get(company=company, name=name)


def sync_ledgers(party):
    """Each party gets a bill-wise debtor ledger and/or creditor ledger according to its roles."""
    company = party.company
    if party.is_customer:
        if party.customer_ledger_id is None:
            party.customer_ledger = Ledger.objects.create(
                company=company, group=_group(company, "Sundry Debtors"), bill_wise=True,
                name=_ledger_name(party.name, party.code),
            )
        elif party.customer_ledger.name != party.name and not Ledger.objects.filter(name=party.name).exists():
            party.customer_ledger.name = party.name
            party.customer_ledger.save(update_fields=["name"])
    if any(getattr(party, r) for r in PAYABLE_ROLES):
        if party.payable_ledger_id is None:
            suffix = " (Payable)" if party.customer_ledger_id else ""
            party.payable_ledger = Ledger.objects.create(
                company=company, group=_group(company, "Sundry Creditors"), bill_wise=True,
                name=_ledger_name(party.name, party.code, suffix),
            )
    for ledger in (party.customer_ledger, party.payable_ledger):
        if ledger is not None and ledger.is_active != party.is_active:
            ledger.is_active = party.is_active
            ledger.save(update_fields=["is_active"])
    party.save(update_fields=["customer_ledger", "payable_ledger"])


@transaction.atomic
def create_party(*, company, **fields) -> Party:
    f = _clean(fields)
    _check_duplicate_mobile(company, f)
    party = Party(company=company, code=next_code(company, "party"), **f)
    party.full_clean(exclude=["customer_ledger", "payable_ledger"])
    party.save()
    sync_ledgers(party)
    return party


@transaction.atomic
def update_party(party, **fields) -> Party:
    current = {name: getattr(party, name) for name in EDITABLE_FIELDS}
    f = _clean({**current, **fields})
    _check_duplicate_mobile(party.company, f, party)
    for k, v in f.items():
        setattr(party, k, v)
    party.full_clean(exclude=["customer_ledger", "payable_ledger"])
    party.save()
    sync_ledgers(party)
    return party
