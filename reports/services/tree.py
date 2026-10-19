"""Group drill-down for the trial balance, profit and loss and balance sheet (owner, 19 Oct 2026).

Ledger figures roll up into their account group, sub-groups into their parent, up to the top groups. The reports
show the top groups first; each opens into the level below. Groups with nothing in them are left out."""
from decimal import Decimal

from ledger.models import AccountGroup

ZERO = Decimal("0.00")


def build(company, items, *, width):
    """items = [{"ledger_id", "ledger", "group" (group name), "values": [Decimal] * width}]. Returns the top-level
    nodes: {"kind", "name", "id", "values", "children"}, groups first ordered as the chart is, then ledgers by name."""
    groups = {g.pk: g for g in AccountGroup.objects.filter(company=company)}
    by_name = {g.name: g for g in groups.values()}
    nodes = {}

    def node_for(group):
        if group.pk not in nodes:
            nodes[group.pk] = {"kind": "group", "name": group.name, "id": group.pk, "values": [ZERO] * width,
                               "children": [], "order": (group.sort_order, group.name), "parent": group.parent_id}
        return nodes[group.pk]

    for item in items:
        group = by_name[item["group"]]
        leaf = {"kind": "ledger", "name": item["ledger"], "id": item["ledger_id"], "values": list(item["values"]),
                "children": [], "order": (10 ** 6, item["ledger"]), **{k: v for k, v in item.items() if k not in ("values",)}}
        node_for(group)["children"].append(leaf)
        g = group
        while g is not None:                         # every group up the chain carries the ledger's figures
            n = node_for(g)
            n["values"] = [a + b for a, b in zip(n["values"], leaf["values"])]
            g = groups.get(g.parent_id)
    for n in list(nodes.values()):                   # hang each group under its parent
        if n["parent"] is not None and n["parent"] in nodes and n not in nodes[n["parent"]]["children"]:
            nodes[n["parent"]]["children"].append(n)
    for n in nodes.values():
        n["children"].sort(key=lambda c: (c["kind"] == "ledger", c["order"]))
    return sorted((n for n in nodes.values() if n["parent"] is None or n["parent"] not in nodes), key=lambda n: n["order"])


def flatten(roots):
    """The tree as table rows, depth first: {"key", "parent", "depth", "kind", "name", "id", "values", "has_children"}
    plus whatever else the ledger item carried."""
    out = []

    def walk(n, depth, parent):
        key = f"{n['kind'][0]}{n['id']}"
        row = {k: v for k, v in n.items() if k not in ("children", "order")}
        row.update(key=key, parent=parent, depth=depth, has_children=bool(n["children"]))
        out.append(row)
        for c in n["children"]:
            walk(c, depth + 1, key)

    for r in roots:
        walk(r, 0, "")
    return out


def rows(company, items, *, width):
    return flatten(build(company, items, width=width))


def with_cells(rows, formats):
    """Add each row's figures as display text: "plain" (blank for zero) or "drcr" (debit-positive as Dr / Cr)."""
    for r in rows:
        cells = []
        for v, fmt in zip(r["values"], formats):
            if not v:
                cells.append("")
            elif fmt == "drcr":
                cells.append(f"{abs(v):.2f} {'Dr' if v > 0 else 'Cr'}")
            else:
                cells.append(f"{v:.2f}")
        r["cells"] = cells
    return rows
