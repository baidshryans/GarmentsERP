"""The home launchpad: the few jobs done most days, in plain words, each opening the screen where that job is done.
A button is offered only when the user's role passes the same permission check the target view enforces."""
from django.urls import reverse

# (island title, icon, [(url_name, label, screen, action), ...])
HOME_ACTIONS = [
    ("Buy", "i-purchases", [
        ("po_new", "Order fabric or material", "purchases.po", "create"),
        ("grn_new", "Receive goods", "purchases.grn", "create"),
    ]),
    ("Make", "i-production", [
        ("order_new", "Start a production order", "production.order", "create"),
        ("challan_new", "Send to fabricator", "jobwork.challan", "create"),
        ("challan_list", "Receive from fabricator", "jobwork.challan", "view"),
    ]),
    ("Sell", "i-sales", [
        ("saleorder_new", "Take an order", "sales.order", "create"),
        ("billing", "Make a bill", "sales.invoice", "create"),
    ]),
    ("Money", "i-accounts", [
        ("voucher_receipt", "Money received", "ledger.voucher", "create"),
        ("voucher_payment", "Money paid", "ledger.voucher", "create"),
    ]),
]


# A button that opens its screen already filtered: (url_name, label) -> query string.
HOME_QUERY = {
    ("challan_list", "Receive from fabricator"): "status=out",   # only what is out; the Next step of each row is Receive
}


def _url(url_name, label):
    query = HOME_QUERY.get((url_name, label))
    return reverse(url_name) + (f"?{query}" if query else "")


def home_actions(user):
    """Islands of permitted buttons for this user, in display order. Empty islands are left out."""
    islands = []
    for title, icon, actions in HOME_ACTIONS:
        allowed = [{"label": label, "url": _url(url_name, label)}
                   for url_name, label, screen, action in actions if user.has_screen_perm(screen, action)]
        if allowed:
            islands.append({"title": title, "icon": icon, "actions": allowed})
    return islands
