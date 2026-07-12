"""Shared DRF serializer fields for mastersconfig references."""
from rest_framework import serializers

from mastersconfig.models import Item


class ItemRefField(serializers.SlugRelatedField):
    """Reference an Item by primary key (preferred) or short_code (legacy).

    ``short_code`` is unique, so both forms are unambiguous. Callers/UI that send
    the item id resolve by pk; anything else falls back to a short_code lookup.
    Output stays ``short_code`` (inherited) so existing read/display/print
    consumers are unaffected — the stored value is the FK id either way.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("slug_field", "short_code")
        kwargs.setdefault("queryset", Item.objects.all())
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        # An int (or numeric string) is an item id. No short_code is numeric, so
        # this never collides; if the pk lookup misses, fall back to short_code.
        if isinstance(data, bool):
            return super().to_internal_value(data)
        if isinstance(data, int) or (isinstance(data, str) and data.strip().isdigit()):
            try:
                return self.get_queryset().get(pk=int(data))
            except (Item.DoesNotExist, TypeError, ValueError):
                pass
        return super().to_internal_value(data)
