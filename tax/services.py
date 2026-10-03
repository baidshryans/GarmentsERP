from django.db import transaction

from .models import TaxSetting


def _effective(company, kind, on_date, factory=None):
    qs = TaxSetting.objects.filter(company=company, kind=kind, effective_from__lte=on_date)
    if factory is not None:
        specific = qs.filter(factory=factory).order_by("-effective_from").first()
        if specific:
            return specific
    return qs.filter(factory__isnull=True).order_by("-effective_from").first()


def is_enabled(company, kind, on_date, factory=None) -> bool:
    setting = _effective(company, kind, on_date, factory)
    return bool(setting and setting.enabled)


def gst_enabled(company, on_date, factory=None) -> bool:
    return is_enabled(company, TaxSetting.Kind.GST, on_date, factory)


def tds_enabled(company, on_date, factory=None) -> bool:
    return is_enabled(company, TaxSetting.Kind.TDS, on_date, factory)


@transaction.atomic
def set_tax_status(*, company, kind, enabled, effective_from, registration_number="", factory=None):
    """Switch GST or TDS on/off from a date. Earlier documents are untouched (E1.9)."""
    setting = TaxSetting(
        company=company, factory=factory, kind=kind, enabled=enabled,
        effective_from=effective_from, registration_number=registration_number.strip().upper(),
    )
    setting.full_clean(exclude=["id"], validate_unique=False)
    obj, _ = TaxSetting.objects.update_or_create(
        company=company, factory=factory, kind=kind, effective_from=effective_from,
        defaults={"enabled": enabled, "registration_number": setting.registration_number},
    )
    return obj


def gst_rate_for(hsn, value_per_piece, on_date):
    """Suggested GST % for an HSN at a per-piece value on a date, or None if no slab applies.

    Uses the slabs of the latest effective_from on or before the date, so older documents
    keep the rate that applied to them (TAX-03).
    """
    from .models import HsnSlab

    slabs = HsnSlab.objects.filter(hsn=hsn, effective_from__lte=on_date)
    latest = slabs.order_by("-effective_from").values_list("effective_from", flat=True).first()
    if latest is None:
        return None
    for slab in slabs.filter(effective_from=latest).order_by("value_from"):
        if value_per_piece >= slab.value_from and (slab.value_to is None or value_per_piece <= slab.value_to):
            return slab.gst_rate
    return None
