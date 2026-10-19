"""The lot diary (owner, 19 Oct 2026): every step recorded on a lot, oldest first, in plain words, with who did it.
Only the newest step carries Delete. Journal entries are linked only for those who may see money (BR-15)."""
from dataclasses import dataclass, field

from django.urls import reverse

from production.models import ProductionAction, ProductionActionItem
from production.services import actions


@dataclass
class DiaryEntry:
    date: object
    text: str
    who: str
    action: object
    link: str | None = None
    voucher_links: list = field(default_factory=list)      # [(number, url)]
    can_delete: bool = False


def entries(lot, user) -> list:
    from ledger.models import Voucher

    see_cost = user.can_view_field("cost")
    rows = sorted(actions.listed(user, limit=1000, lot=lot, undone=False), key=lambda a: (a.date, a.pk))
    vouchers = {}
    if see_cost:
        items = ProductionActionItem.objects.filter(action__in=rows, role=ProductionActionItem.Role.VOUCHER)
        found = {v.pk: v for v in Voucher.objects.filter(pk__in=items.values_list("object_id", flat=True))}
        for i in items:
            if i.object_id in found:
                v = found[i.object_id]
                vouchers.setdefault(i.action_id, []).append((v.number, reverse("voucher_detail", args=[v.pk])))
    out = []
    for a in rows:
        out.append(DiaryEntry(
            date=a.date, text=f"{a.get_kind_display()}: {a.summary}",
            who=a.created_by.username if a.created_by_id else "", action=a, link=_link(a),
            voucher_links=vouchers.get(a.pk, []), can_delete=a.can))
    return out


def _link(action) -> str | None:
    pages = {"jobwork.jobworkchallan": "challan_detail", "jobwork.receipt": "receipt_detail"}
    name = pages.get(action.doc_type)
    return reverse(name, args=[action.doc_id]) if name and action.doc_id else None
