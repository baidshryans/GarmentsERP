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
