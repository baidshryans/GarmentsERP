"""Opening stock rows for the Excel import (kept apart from imports.py to avoid a circular import)."""
from django.core.exceptions import ValidationError
from django.db import transaction

from core.exceptions import BusinessRuleError
from masters.models import SKU, Material


def import_opening_stock(rows, result, company, user, factory, location, *, text, dec):
    from inventory.services.opening import OpeningItem, post_opening_stock

    if factory is None or location is None:
        raise BusinessRuleError("Choose the factory and location this stock is in.")
    entries = []
    for n, v in rows:
        try:
            code = text(v["item"])
            item = Material.objects.filter(code__iexact=code).first() or SKU.objects.filter(barcode=code).first()
            if item is None:
                raise ValueError(f"No material with code, or SKU with barcode, '{code}'.")
            gsm = text(v["gsm"])
            entries.append(OpeningItem(
                item=item, qty=dec(v["qty"], "qty"), rate=dec(v["rate"], "rate"), vendor_roll_no=text(v["roll_no"]),
                lot_no=text(v["lot"]), gsm=int(dec(v["gsm"], "gsm")) if gsm else None,
                width_cm=dec(v["width_cm"], "width_cm") if text(v["width_cm"]) else None,
                length_m=dec(v["length_m"], "length_m") if text(v["length_m"]) else None,
            ))
            result.ok += 1
        except ValueError as exc:
            result.errors.append((n, str(exc)))
    if not result.errors:
        try:
            with transaction.atomic():
                post_opening_stock(company=company, factory=factory, location=location, entries=entries, user=user)
        except (BusinessRuleError, ValidationError) as exc:
            result.errors.append((0, "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)))
