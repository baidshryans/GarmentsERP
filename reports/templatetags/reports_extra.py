"""Small filters for the drill-down reports."""
from django import template

register = template.Library()


@register.filter
def indent(depth):
    """Left padding for a drill-down row at this depth."""
    return 8 + 20 * int(depth or 0)
