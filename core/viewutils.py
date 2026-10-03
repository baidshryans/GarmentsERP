"""Small helpers shared by the screens: parsing posted values and reporting service errors to the user."""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError

from .models import Company


def company():
    return Company.objects.get(setup_complete=True)


def report(request, exc):
    """Show a service error (or Django validation error) as messages."""
    if isinstance(exc, ValidationError):
        for m in exc.messages:
            messages.error(request, m)
    else:
        messages.error(request, str(exc))


def dec(text, label="Value", default=None):
    text = (text or "").strip().replace(",", "")
    if not text:
        if default is not None:
            return default
        raise ValueError(f"{label} is required.")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError(f"{label} '{text}' is not a number.")


def whole(text, label="Value", default=None) -> int:
    value = dec(text, label, None if default is None else Decimal(default))
    if value != value.to_integral_value() or value < 0:
        raise ValueError(f"{label} must be a whole number of zero or more.")
    return int(value)


def day(text, label="Date", default=None):
    if not text:
        if default is not None:
            return default
        raise ValueError(f"{label} is required.")
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{label} '{text}' is not a valid date (use YYYY-MM-DD).")
