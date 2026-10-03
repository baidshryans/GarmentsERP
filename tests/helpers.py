from decimal import Decimal

from ledger.services.posting import LineSpec

D = Decimal


def simple_lines(ledgers, amount="1000.00"):
    amount = D(amount)
    return [
        LineSpec(ledger=ledgers("cash"), debit=amount),
        LineSpec(ledger=ledgers("sales_stock"), credit=amount),
    ]
