"""
Management command to backfill RawMaterialInventory and RawMaterialTransaction
from historical purchase vouchers, purchase returns, karigar gold/stone issues,
and karigar stone receives.

Signals only fire on newly created records, so existing data needs this
one-time replay.

Usage:
    python manage.py backfill_raw_material          # dry-run (default)
    python manage.py backfill_raw_material --apply   # actually write to DB
    python manage.py backfill_raw_material --apply --clear  # wipe existing data first
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import RawMaterialInventory, RawMaterialTransaction
from manufacturing.models import (
    KarigarGoldIssue, KarigarStoneIssue, KarigarStoneReceive,
)
from purchase.models import (
    PurchaseVoucherItems, PurchaseVoucherDetails,
    PurchaseReturnItems, PurchaseReturnDetails,
)


def _d(v):
    """Safely convert to Decimal, treating None as 0."""
    return Decimal(str(v)) if v else Decimal('0')


class Command(BaseCommand):
    help = 'Backfill RawMaterialInventory and RawMaterialTransaction from historical data.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Actually write to database (default is dry-run)')
        parser.add_argument('--clear', action='store_true', help='Clear existing raw material data before backfill')

    def handle(self, *args, **options):
        dry_run = not options['apply']
        clear = options['clear']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no data will be written. Use --apply to persist.'))

        # Collect all events into a single list, then sort chronologically
        events = []

        # ── Purchase voucher items (non-finished) ────────────────────────
        for pvi in PurchaseVoucherItems.objects.filter(is_finished=False).select_related('item', 'purity', 'billno'):
            if not pvi.item:
                continue
            date = pvi.billno.date1 if pvi.billno else None
            events.append({
                'date': date,
                'item': pvi.item,
                'packet': None,
                'purity': pvi.purity,
                'retail': pvi.retail,
                'trans_type': 'PURCHASE',
                'pcs': pvi.pcs or 0,
                'ct': Decimal('0'),
                'gw': _d(pvi.gw),
                'rate': _d(pvi.item_value),
                'amt': _d(pvi.item_value),
                'billno': pvi.billno.billno if pvi.billno else '',
            })

        # ── Purchase voucher details (sub-items of non-finished) ─────────
        for pvd in PurchaseVoucherDetails.objects.select_related('sub_item', 'packet', 'metal_purity', 'main_item', 'billno'):
            if not pvd.sub_item:
                continue
            if pvd.main_item and pvd.main_item.is_finished:
                continue
            date = pvd.billno.date1 if pvd.billno else None
            events.append({
                'date': date,
                'item': pvd.sub_item,
                'packet': pvd.packet,
                'purity': pvd.metal_purity,
                'retail': pvd.retail,
                'trans_type': 'PURCHASE',
                'pcs': pvd.sub_pcs or 0,
                'ct': _d(pvd.sub_ct),
                'gw': _d(pvd.sub_gw),
                'rate': _d(pvd.rate),
                'amt': _d(pvd.value),
                'billno': pvd.billno.billno if pvd.billno else '',
            })

        # ── Purchase return items ────────────────────────────────────────
        for pri in PurchaseReturnItems.objects.select_related('item', 'purity', 'billno'):
            if not pri.item:
                continue
            date = pri.billno.date1 if pri.billno else None
            events.append({
                'date': date,
                'item': pri.item,
                'packet': None,
                'purity': pri.purity,
                'retail': pri.retail,
                'trans_type': 'PURCHASE_RETURN',
                'pcs': -(pri.pcs or 0),
                'ct': Decimal('0'),
                'gw': -_d(pri.gw),
                'rate': Decimal('0'),
                'amt': Decimal('0'),
                'billno': pri.billno.billno if pri.billno else '',
            })

        # ── Purchase return details ──────────────────────────────────────
        for prd in PurchaseReturnDetails.objects.select_related('sub_item', 'packet', 'metal_purity', 'billno'):
            if not prd.sub_item:
                continue
            date = prd.billno.date1 if prd.billno else None
            events.append({
                'date': date,
                'item': prd.sub_item,
                'packet': prd.packet,
                'purity': prd.metal_purity,
                'retail': prd.retail,
                'trans_type': 'PURCHASE_RETURN',
                'pcs': -(prd.sub_pcs or 0),
                'ct': -_d(prd.sub_ct),
                'gw': -_d(prd.sub_gw),
                'rate': _d(prd.rate),
                'amt': -_d(prd.value),
                'billno': prd.billno.billno if prd.billno else '',
            })

        # ── Karigar gold issues ──────────────────────────────────────────
        for gi in KarigarGoldIssue.objects.select_related('item', 'metal_purity', 'header'):
            if not gi.item:
                continue
            events.append({
                'date': gi.header.date1 if gi.header else None,
                'item': gi.item,
                'packet': None,
                'purity': gi.metal_purity,
                'retail': gi.header.retail if gi.header else None,
                'trans_type': 'KR_GOLD_ISSUE',
                'pcs': 0,
                'ct': Decimal('0'),
                'gw': -_d(gi.item_gw),
                'rate': Decimal('0'),
                'amt': Decimal('0'),
                'billno': gi.header.billno if gi.header else '',
            })

        # ── Karigar stone issues ─────────────────────────────────────────
        for si in KarigarStoneIssue.objects.select_related('item', 'packet', 'header'):
            if not si.item:
                continue
            events.append({
                'date': si.header.date1 if si.header else None,
                'item': si.item,
                'packet': si.packet,
                'purity': None,
                'retail': si.header.retail if si.header else None,
                'trans_type': 'KR_STONE_ISSUE',
                'pcs': -si.pcs,
                'ct': -_d(si.ct),
                'gw': -_d(si.gw),
                'rate': _d(si.rate),
                'amt': -_d(si.tot_val),
                'billno': si.header.billno if si.header else '',
            })

        # ── Karigar stone receives ───────────────────────────────────────
        for sr in KarigarStoneReceive.objects.select_related('item', 'packet', 'header'):
            if not sr.item:
                continue
            events.append({
                'date': sr.header.date1 if sr.header else None,
                'item': sr.item,
                'packet': sr.packet,
                'purity': None,
                'retail': sr.header.retail if sr.header else None,
                'trans_type': 'KR_STONE_RETURN',
                'pcs': sr.return_pcs,
                'ct': _d(sr.return_ct),
                'gw': _d(sr.return_gw),
                'rate': _d(sr.rate),
                'amt': _d(sr.tot_val),
                'billno': sr.header.billno if sr.header else '',
            })

        # Sort chronologically (None dates sort first)
        events.sort(key=lambda e: e['date'] or '0000-01-01')

        self.stdout.write(f'Collected {len(events)} events to replay.')

        if dry_run:
            # Print summary by type
            from collections import Counter
            counts = Counter(e['trans_type'] for e in events)
            for tt, cnt in sorted(counts.items()):
                self.stdout.write(f'  {tt}: {cnt}')
            return

        with transaction.atomic():
            if clear:
                deleted_inv = RawMaterialInventory.objects.all().delete()[0]
                deleted_txn = RawMaterialTransaction.objects.all().delete()[0]
                self.stdout.write(f'Cleared {deleted_inv} inventory rows, {deleted_txn} transaction rows.')

            # Build inventory in memory, bulk-create transactions
            inventory = {}  # (item_id, packet_id, purity_id, retail_id) -> {pcs, ct, gw}
            txn_batch = []

            for e in events:
                key = (
                    e['item'].pk,
                    e['packet'].pk if e['packet'] else None,
                    e['purity'].pk if e['purity'] else None,
                    e['retail'].pk if e['retail'] else None,
                )
                if key not in inventory:
                    inventory[key] = {'pcs': 0, 'ct': Decimal('0'), 'gw': Decimal('0'),
                                      'item': e['item'], 'packet': e['packet'],
                                      'purity': e['purity'], 'retail': e['retail']}
                inv = inventory[key]
                inv['pcs'] += e['pcs']
                inv['ct'] += e['ct']
                inv['gw'] += e['gw']

                txn_batch.append(RawMaterialTransaction(
                    item=e['item'], packet=e['packet'], purity=e['purity'], retail=e['retail'],
                    trans_type=e['trans_type'], pcs=e['pcs'], ct=e['ct'], gw=e['gw'],
                    rate=e['rate'], amt=e['amt'], billno=e['billno'],
                ))

            # Bulk create transactions
            RawMaterialTransaction.objects.bulk_create(txn_batch, batch_size=500)
            self.stdout.write(f'Created {len(txn_batch)} transaction records.')

            # Upsert inventory rows
            created_count = 0
            updated_count = 0
            for key, inv in inventory.items():
                obj, created = RawMaterialInventory.objects.get_or_create(
                    item=inv['item'], packet=inv['packet'],
                    purity=inv['purity'], retail=inv['retail'],
                    defaults={'pcs': inv['pcs'], 'ct': inv['ct'], 'gw': inv['gw']},
                )
                if not created:
                    obj.pcs += inv['pcs']
                    obj.ct += inv['ct']
                    obj.gw += inv['gw']
                    obj.save()
                    updated_count += 1
                else:
                    created_count += 1

            self.stdout.write(self.style.SUCCESS(
                f'Inventory: {created_count} created, {updated_count} updated. '
                f'Total: {len(inventory)} items.'
            ))
