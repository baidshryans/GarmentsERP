"""The home launchpad: the everyday jobs in plain words, each opening the screen where that job is done.
A button is offered only when the user's role passes the same permission check the target view enforces."""
from django.urls import reverse

# (island title, icon, [(url_name, label, screen, action), ...])
HOME_ACTIONS = [
    ("Buy", "i-purchases", [
        ("po_new", "Order fabric or material", "purchases.po", "create"),
        ("grn_new", "Receive goods", "purchases.grn", "create"),
        ("invoice_new", "Enter a supplier bill", "purchases.invoice", "create"),
    ]),
    ("Make", "i-production", [
        ("order_new", "Start a production order", "production.order", "create"),
        ("order_list", "Cut a lot", "production.order", "view"),
        ("challan_new", "Send to fabricator", "jobwork.challan", "create"),
        ("challan_list", "Receive from fabricator", "jobwork.challan", "view"),
    ]),
    ("Sell", "i-sales", [
        ("saleorder_new", "Take an order", "sales.order", "create"),
        ("billing", "Make a bill", "sales.invoice", "create"),
        ("packing_list", "Pack and dispatch", "sales.packing", "view"),
    ]),
    ("Money", "i-accounts", [
        ("voucher_receipt", "Money received", "ledger.voucher", "create"),
        ("voucher_payment", "Money paid", "ledger.voucher", "create"),
        ("ageing_debtors", "Who owes me", "ledger.report", "view"),
        ("ageing_creditors", "Whom I owe", "ledger.report", "view"),
    ]),
    ("Masters", "i-masters", [
        ("style_new", "New style", "masters.style", "create"),
        ("material_new", "New material", "masters.material", "create"),
        ("party_new", "New party", "masters.party", "create"),
    ]),
]


def home_actions(user):
    """Islands of permitted buttons for this user, in display order. Empty islands are left out."""
    islands = []
    for title, icon, actions in HOME_ACTIONS:
        allowed = [{"label": label, "url": reverse(url_name)}
                   for url_name, label, screen, action in actions if user.has_screen_perm(screen, action)]
        if allowed:
            islands.append({"title": title, "icon": icon, "actions": allowed})
    return islands
