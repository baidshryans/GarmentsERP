"""
Import legacy opening stock (barcode_detail_rawstone) into OpeningInventory.

Legacy table `barcode_detail_rawstone` holds the old ERP's opening stock as raw
item/stone lots. Relevant columns (ID-based):
  item_id, type, ldgr, qty, ct, gw, rate_stock, packet_id, metal_purity, rt_code

Mapping -> OpeningInventory:
  item_id    -> item (Item by id)            qty        -> pcs
  type       -> type (SH/KR/CO)              ct/gw      -> ct/gw
  ldgr       -> ldgr (resolve_ledger)        rate_stock -> wtd_avg_rate
  packet_id  -> packet (Packet by id)        rt_code    -> retail
  metal_purity -> purity (PurityMaster by value)

Upserts on (item, type, ldgr, purity, packet, retail) — idempotent re-runs update
pcs/ct/gw/rate. rate_stock is already the per-primary-unit rate (per ct for S
items, per gw for R/M items), matching OpeningInventory.wtd_avg_rate.

Usage:
  python manage.py import_opening_stock --file rawstone.csv [--apply] \
      [--continue-on-error] [--report-dir DIR]
"""
import os
from decimal import Decimal

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import OpeningInventory
from mastersconfig.models import Item, Packet
from goldrates.models import PurityMaster
from accounting.migration_utils import clean, dec, to_int, OrgResolver, resolve_ledger

# Legacy type code / synonym -> OpeningInventory.type
TYPE_MAP = {
    'SH': 'SH', 'SHOWROOM': 'SH',
    'KR': 'KR', 'KARIGAR': 'KR',
    'CO': 'CO', 'CUSTOMER': 'CO',
}


class Command(BaseCommand):
    help = "Import legacy opening stock (barcode_detail_rawstone) into OpeningInventory."

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='barcode_detail_rawstone CSV')
        parser.add_argument('--apply', action='store_true', help='Persist (default: dry-run).')
        parser.add_argument('--continue-on-error', action='store_true')
        parser.add_argument('--report-dir', default='.')

    def handle(self, *args, **opts):
        if not os.path.exists(opts['file']):
            raise CommandError(f"File not found: {opts['file']}")
        self.apply = opts['apply']
        self.cont = opts['continue_on_error']

        df = pd.read_csv(opts['file'], dtype=str)
        df.columns = [c.strip() for c in df.columns]

        self.org = OrgResolver(self.stdout, self.style, apply=self.apply)
        errs = self.org.validate_retail(set(df.get('rt_code', pd.Series(dtype=str)).dropna()))
        if errs:
            for e in errs:
                self.stderr.write(self.style.ERROR(e))
            raise CommandError("Unresolved retail codes — import masters first.")

        self.unresolved = []
        purities = {str(p.purity).strip().lower(): p for p in PurityMaster.objects.all()}

        # Opening stock is a snapshot — the legacy rawstone is authoritative. Clear
        # any existing opening stock for the retails in this file first, so seed /
        # stale / prior-run rows don't accumulate alongside the synced ones.
        if self.apply:
            retail_ids = set()
            for rt in {clean(x) for x in df.get('rt_code', pd.Series(dtype=str)).dropna()} - {''}:
                r, _, _ = self.org.get(rt, '', '')
                if r:
                    retail_ids.add(r.id)
            if retail_ids:
                cleared = OpeningInventory.objects.filter(retail_id__in=retail_ids).delete()[0]
                if cleared:
                    self.stdout.write(self.style.WARNING(
                        f"cleared {cleared} existing opening-stock row(s) for the synced retail(s)"))

        created = updated = errored = 0
        for _, r in df.iterrows():
            if not any((str(v) or '').strip() for v in r.values):
                continue  # blank line
            try:
                with transaction.atomic():
                    res = self._import_row(r, purities)
                if res == 'created':
                    created += 1
                else:
                    updated += 1
            except Exception as exc:
                errored += 1
                self.unresolved.append({'item_id': clean(r.get('item_id')), 'error': str(exc)})
                self.stderr.write(self.style.ERROR(f"item_id={clean(r.get('item_id'))}: {exc}"))
                if not self.cont:
                    raise CommandError(str(exc))

        self._report(opts['report_dir'])
        mode = "APPLIED" if self.apply else "DRY-RUN (no writes)"
        self.stdout.write(self.style.SUCCESS(
            f"[{mode}] opening stock: created={created} updated={updated} errored={errored}"))
        if not self.apply:
            self.stdout.write(self.style.WARNING("Dry run — re-run with --apply to persist."))

    # ------------------------------------------------------------------ #
    def _import_row(self, r, purities):
        retail, _, _ = self.org.get(r.get('rt_code'), '', '')
        item_id = to_int(r.get('item_id'))
        item = Item.objects.filter(id=item_id).first() if item_id else None
        if item is None:
            raise ValueError(f"Item {clean(r.get('item_id'))!r} not found")

        entry_type = TYPE_MAP.get((clean(r.get('type')) or 'SH').upper(), 'SH')
        ldgr = resolve_ledger(r.get('ldgr')) if clean(r.get('ldgr')) else None
        pkt_id = to_int(r.get('packet_id'))
        packet = Packet.objects.filter(id=pkt_id).first() if pkt_id else None
        mp = clean(r.get('metal_purity'))
        purity = purities.get(mp.lower()) if mp else None

        pcs = to_int(r.get('qty'))
        ct = dec(r.get('ct'))
        gw = dec(r.get('gw'))
        rate = dec(r.get('rate_stock'))
        # S items are quoted/held per carat; derive gw if the source left it blank.
        if (item.item_type or '').upper() == 'S' and gw == 0 and ct > 0:
            gw = (ct / Decimal('5')).quantize(Decimal('0.001'))

        if not self.apply:
            return 'created'
        obj, created = OpeningInventory.objects.update_or_create(
            item=item, type=entry_type, ldgr=ldgr, purity=purity, packet=packet, retail=retail,
            defaults={'pcs': pcs, 'ct': ct, 'gw': gw, 'wtd_avg_rate': rate},
        )
        return 'created' if created else 'updated'

    def _report(self, report_dir):
        if not self.unresolved:
            return
        os.makedirs(report_dir, exist_ok=True)
        path = os.path.join(report_dir, 'unresolved_opening_stock.csv')
        pd.DataFrame(self.unresolved).to_csv(path, index=False)
        self.stdout.write(self.style.WARNING(f"{len(self.unresolved)} unresolved row(s) -> {path}"))
