import re

from django.core.exceptions import ValidationError

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
TAN_RE = re.compile(r"^[A-Z]{4}[0-9]{5}[A-Z]$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def validate_pan(value):
    if value and not PAN_RE.match(value):
        raise ValidationError("Enter a valid PAN, for example ABCDE1234F.")


def validate_tan(value):
    if value and not TAN_RE.match(value):
        raise ValidationError("Enter a valid TAN, for example LDHA12345B.")


def validate_gstin(value):
    if value and not GSTIN_RE.match(value):
        raise ValidationError("Enter a valid 15-character GSTIN.")
