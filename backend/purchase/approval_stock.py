"""Inventory effect of a purchase approval.

An approved-but-unbought line holds stock exactly as a purchase voucher line would
(raw-material inventory for the main item and each sub-item) but posts nothing to the
ledger. `stock_applied` records whether the line currently holds that stock, which keeps
every transition idempotent:

    create / undo-return / its purchase-voucher line deleted -> apply
    return / bought on a purchase voucher / delete / edit     -> reverse

When a line is bought, the purchase voucher line posts its own stock, so the approval
reverses its copy and the net effect is a single purchase.
"""
from decimal import Decimal

from .signals import _log_raw_txn, _update_raw_material


def _post(line, sign, trans_type):
    billno = line.billno.billno
    retail = line.billno.retail
    pcs, gw = (line.pcs or 0) * sign, (line.gw or Decimal('0')) * sign
    _update_raw_material(item=line.item, packet=None, purity=line.purity, retail=retail, pcs=pcs, gw=gw)
    _log_raw_txn(item=line.item, packet=None, purity=line.purity, retail=retail, trans_type=trans_type,
                 pcs=pcs, gw=gw, rate=Decimal(str(line.amount or 0)), amt=Decimal(str(line.amount or 0)) * sign,
                 billno=billno)
    for d in line.details.all():
        sub_pcs, sub_ct, sub_gw = (d.sub_pcs or 0) * sign, (d.sub_ct or Decimal('0')) * sign, (d.sub_gw or Decimal('0')) * sign
        _update_raw_material(item=d.sub_item, packet=d.packet, purity=d.metal_purity, retail=retail,
                             pcs=sub_pcs, ct=sub_ct, gw=sub_gw)
        _log_raw_txn(item=d.sub_item, packet=d.packet, purity=d.metal_purity, retail=retail, trans_type=trans_type,
                     pcs=sub_pcs, ct=sub_ct, gw=sub_gw, rate=d.rate or Decimal('0'),
                     amt=Decimal(str(d.value or 0)) * sign, billno=billno)


def apply_stock(line, trans_type='PURCHASE_APPR'):
    """Put the line's stock into inventory (no-op if already there)."""
    if line.stock_applied:
        return
    _post(line, 1, trans_type)
    line.stock_applied = True
    line.save(update_fields=['stock_applied'])


def reverse_stock(line, trans_type):
    """Take the line's stock back out of inventory (no-op if not there)."""
    if not line.stock_applied:
        return
    _post(line, -1, trans_type)
    line.stock_applied = False
    line.save(update_fields=['stock_applied'])
