"""Helpers for delete tests: the books before and after, and proof that nothing of a deleted document is left."""
from collections import defaultdict
from decimal import Decimal

from inventory.models import RollBalance, StockBalance, StockMovement
from ledger.models import Voucher, VoucherLine


def books(company) -> dict:
    """Ledger balances, stock balances and roll balances, with zero rows left out so a row made and emptied again
    compares equal to one never made."""
    ledgers = defaultdict(Decimal)
    for l in VoucherLine.objects.filter(voucher__company=company, voucher__status="posted"):
        ledgers[(l.ledger_id, l.factory_id)] += l.debit - l.credit
    stock = {(b.location_id, b.material_id, b.sku_id): (b.qty, b.value) for b in StockBalance.objects.all()
             if b.qty or b.value}
    rolls = {(r.roll_id, r.location_id): (r.qty, r.value) for r in RollBalance.objects.all() if r.qty or r.value}
    return {"ledgers": {k: v for k, v in ledgers.items() if v}, "stock": stock, "rolls": rolls}


def assert_no_trace(source_type, source_id):
    assert not StockMovement.objects.filter(source_type=source_type, source_id=source_id).exists()
    assert not Voucher.objects.filter(source_type=source_type, source_id=source_id).exists()
    assert not Voucher.history.filter(source_type=source_type, source_id=source_id).exists()
