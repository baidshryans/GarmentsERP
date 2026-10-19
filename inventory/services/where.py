"""Where is my stock (owner, 19 Oct 2026): the places people see (Godown, Ready Goods, Rejects, showrooms) with
what is in them, and pieces being made by lot and step, with whoever has them. The bookkeeping places for work in
progress (cutting floor, process area, in transit, a fabricator's premises) are never named."""
from dataclasses import dataclass

from core.models import Location
from inventory.models import StockBalance
from production.models import Bundle


@dataclass
class WipRow:
    lot: object
    step_name: str
    with_whom: str
    pieces: int


def _with_whom(location) -> str:
    if location.loc_type == Location.Type.FABRICATOR:
        return location.party.name if location.party_id else location.name
    if location.loc_type == Location.Type.TRANSIT:
        return f"on the way to {location.factory.name}"
    return location.factory.name


def summary(user, factory=None) -> dict:
    """{"places": [(location, [(item, qty, value)])], "wip": [WipRow]} for the factories the user may see.
    Values are left as None when the user may not see cost."""
    see_cost = user.can_view_field("cost")
    balances = (StockBalance.objects.for_user(user).filter(location__loc_type__in=Location.VISIBLE_TYPES)
                .exclude(qty=0).select_related("location", "location__factory", "material", "material__unit", "sku",
                                               "sku__style", "sku__colour", "sku__size"))
    if factory is not None:
        balances = balances.filter(factory=factory)
    places = {}
    for b in balances.order_by("location__factory__code", "location__loc_type", "location__name"):
        places.setdefault(b.location, []).append((b.item, b.qty, b.value if see_cost else None))

    allowed = user.allowed_factory_ids()
    bundles = Bundle.objects.filter(status__in=Bundle.LIVE, qty__gt=0).select_related(
        "lot", "current_step__process", "location", "location__factory", "location__party")
    if allowed is not None:
        bundles = bundles.filter(lot__factory_id__in=allowed)
    if factory is not None:
        bundles = bundles.filter(lot__factory=factory)
    wip = {}
    for b in bundles.order_by("lot_id", "current_step__sequence"):
        step = b.current_step.process.name if b.current_step_id else "Cut, not yet moved"
        key = (b.lot_id, step, _with_whom(b.location))
        if key in wip:
            wip[key].pieces += b.qty
        else:
            wip[key] = WipRow(b.lot, step, key[2], b.qty)
    return {"places": list(places.items()), "wip": list(wip.values()), "see_cost": see_cost}
