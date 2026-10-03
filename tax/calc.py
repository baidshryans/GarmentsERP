"""Tax amounts from a template (E9.4): the system calculates, the user may override with a reason."""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from core.exceptions import BusinessRuleError

from .models import TaxTemplate

TWO = Decimal("0.01")
ZERO = Decimal("0.00")


@dataclass
class TaxAmount:
    component: str  # cgst, sgst, igst, tds, tcs
    rate: Decimal
    amount: Decimal
    is_override: bool = False
    reason: str = ""


def compute(template: TaxTemplate, base: Decimal) -> list:
    """Tax lines for a taxable base. Each component is rounded to paise on its own."""
    if template is None:
        return []
    return [
        TaxAmount(l.component, l.rate, (base * l.rate / 100).quantize(TWO, rounding=ROUND_HALF_UP))
        for l in template.lines.all().order_by("component")
    ]


def apply_overrides(lines, overrides):
    """overrides: {component: (amount, reason)}. A reason is mandatory for every override."""
    out = []
    for line in lines:
        if line.component in overrides:
            amount, reason = overrides[line.component]
            if not reason or not str(reason).strip():
                raise BusinessRuleError(f"Give a reason for changing the {line.component.upper()} amount.")
            line = TaxAmount(line.component, line.rate, Decimal(amount).quantize(TWO), True, str(reason).strip())
        out.append(line)
    return out


def manual_lines(entries):
    """Hand-entered tax lines: [(component, amount)] with no template."""
    return [TaxAmount(c, ZERO, Decimal(a).quantize(TWO), True, "Entered by hand") for c, a in entries]


def suggest_gst_template(*, party_state, place_state, rate, reverse_charge=False):
    """A suggestion only: intra-state when the party and the place of supply share a state. May return None."""
    inter = bool(party_state and place_state and party_state != place_state)
    candidates = TaxTemplate.objects.filter(
        kind="gst", is_active=True, is_interstate=inter, is_reverse_charge=reverse_charge
    )
    for t in candidates:
        if t.total_rate == Decimal(rate):
            return t
    return None
