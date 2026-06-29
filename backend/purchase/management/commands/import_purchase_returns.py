"""
Import legacy purchase returns into PurchaseReturn / PurchaseReturnItems /
PurchaseReturnDetails.

Legacy tables (CSV exports):
  purchase_return         -> PurchaseReturn         (header)
  purchase_return_main    -> PurchaseReturnItems    (main item lines)
  purchase_return_detail  -> PurchaseReturnDetails  (stone/sub-item lines)

Legacy PKs are preserved (id=...), so detail.main_id wires directly to the
imported PurchaseReturnItems. Each pass is idempotent (skip if PK exists).
GST amounts are taken from the legacy columns directly (PurchaseReturn has no
HSN/voucher-type to recompute from). The GL voucher (v_typ:v_id:ac_yr:rt_code)
must already be imported — it is linked as ac_voucher.

Usage:
  python manage.py import_purchase_returns --header h.csv --items i.csv --details d.csv \
      [--apply] [--continue-on-error] [--report-dir DIR]
"""
import os
import contextlib

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models.signals import pre_save, post_save, pre_delete, post_delete

from purchase.models import PurchaseReturn, PurchaseReturnItems, PurchaseReturnDetails
from mastersconfig.models import Item, Packet
from accounting.migration_utils import (
    clean, dec, to_int, parse_date, OrgResolver, PurityResolver, resolve_ac_voucher, resolve_ledger,
)


@contextlib.contextmanager
def _muted_signals():
    """Mute per-row save/delete signals during the bulk import — they recompute
    stock / raw-material inventory and crash on legacy data quirks. One-off
    migration; current stock comes from the opening-stock / barcode sync."""
    saved = {}
    for sig in (pre_save, post_save, pre_delete, post_delete):
        saved[sig] = sig.receivers
        sig.receivers = []
        sig.sender_receivers_cache.clear()
    try:
        yield
    finally:
        for sig, recv in saved.items():
            sig.receivers = recv
            sig.sender_receivers_cache.clear()


class Command(BaseCommand):
    help = "Import legacy purchase returns (header + items + details CSVs)."

    def add_arguments(self, parser):
        parser.add_argument('--header', required=True, help='purchase_return CSV')
        parser.add_argument('--items', required=True, help='purchase_return_main CSV')
        parser.add_argument('--details', required=True, help='purchase_return_detail CSV')
        parser.add_argument('--apply', action='store_true', help='Persist (default: dry-run).')
        parser.add_argument('--continue-on-error', action='store_true')
        parser.add_argument('--report-dir', default='.')

    def handle(self, *args, **opts):
        for k in ('header', 'items', 'details'):
            if not os.path.exists(opts[k]):
                raise CommandError(f"File not found: {opts[k]}")

        self.apply = opts['apply']
        self.cont = opts['continue_on_error']

        hdr = self._read(opts['header'])
        itm = self._read(opts['items'])
        det = self._read(opts['details'])

        self.org = OrgResolver(self.stdout, self.style, apply=self.apply)
        errs = self.org.validate_retail(set(hdr.get('rt_code', pd.Series(dtype=str)).dropna()))
        if errs:
            for e in errs:
                self.stderr.write(self.style.ERROR(e))
            raise CommandError("Unresolved retail codes — import masters first.")
        self.purity = PurityResolver()
        self.unresolved = []

        with _muted_signals():
            counts = {
                'header':  self._pass(hdr, self._import_header, 'PurchaseReturn', PurchaseReturn),
                'items':   self._pass(itm, self._import_item, 'PurchaseReturnItems', PurchaseReturnItems),
                'details': self._pass(det, self._import_detail, 'PurchaseReturnDetails', PurchaseReturnDetails),
            }

        self._report(opts['report_dir'])
        mode = "APPLIED" if self.apply else "DRY-RUN (no writes)"
        for name, (c, s, e) in counts.items():
            self.stdout.write(self.style.SUCCESS(
                f"[{mode}] {name}: created={c} skipped(existing)={s} errored={e}"))
        if self.purity.created:
            verb = "created" if self.apply else "would create"
            self.stdout.write(self.style.WARNING(
                f"PurityMaster {verb}: {sorted(set(self.purity.created))}"))
        if not self.apply:
            self.stdout.write(self.style.WARNING("Dry run — re-run with --apply to persist."))

    # ------------------------------------------------------------------ #
    def _read(self, path):
        df = pd.read_csv(path, dtype=str)
        df.columns = [c.strip() for c in df.columns]
        return df

    def _pass(self, df, fn, label, model):
        created = skipped = errored = 0
        for _, row in df.iterrows():
            pk = to_int(row.get('id'))
            if pk and model.objects.filter(id=pk).exists():
                skipped += 1
                continue
            try:
                with transaction.atomic():
                    fn(row)
                created += 1
            except Exception as exc:
                errored += 1
                self.unresolved.append({'table': label, 'id': clean(row.get('id')), 'error': str(exc)})
                self.stderr.write(self.style.ERROR(f"{label} id={clean(row.get('id'))}: {exc}"))
                if not self.cont:
                    raise CommandError(str(exc))
        return created, skipped, errored

    # ------------------------------------------------------------------ #
    def _import_header(self, r):
        retail, branch, fy = self.org.get(r.get('rt_code'), r.get('br_code'), r.get('ac_yr'))
        ldgr = resolve_ledger(r.get('customer_ldgr'))
        if ldgr is None:
            raise ValueError(f"ledger {clean(r.get('customer_ldgr'))!r} not found")
        v_typ = clean(r.get('v_typ'))
        total = dec(r.get('total'))
        obj = PurchaseReturn(
            id=to_int(r.get('id')),
            billno=clean(r.get('billno'))[:30],
            ldgr=ldgr,
            discount=dec(r.get('dis_amt')),
            cgst_amt=dec(r.get('cgst_amt')),
            sgst_amt=dec(r.get('sgst_amt')),
            igst_amt=dec(r.get('igst_amt')),
            tcs_amt=dec(r.get('tcs_amt')),
            narration=clean(r.get('narration'))[:100],
            mode_of_transport=clean(r.get('mot'))[:20],
            round_off=dec(r.get('rnd_off')),
            bill_value=total,
            ac_voucher=resolve_ac_voucher(v_typ, r.get('v_id'), r.get('ac_yr'), r.get('rt_code')),
            retail=retail, branch_ref=branch, fiscal_year=fy,
        )
        if self.apply:
            obj.save(force_insert=True)
            # date1 is auto_now_add — set the real legacy date after insert.
            PurchaseReturn.objects.filter(id=obj.id).update(date1=parse_date(r.get('date1')))

    def _import_item(self, r):
        retail, _, _ = self.org.get(r.get('rt_code'), '', r.get('ac_yr'))
        header = self._header_by_billno(r.get('billno'))
        obj = PurchaseReturnItems(
            id=to_int(r.get('id')),
            billno=header,
            sl_no=to_int(r.get('sl_id')),
            item=self._item(r.get('item_id')),
            pcs=to_int(r.get('pcs')),
            gw=dec(r.get('gw')),
            purity=self.purity.resolve(r.get('purity'), self.apply),
            making=dec(r.get('making')),
            making_type=clean(r.get('making_type'))[:20],
            making_value=to_int(r.get('making_value')),
            remarks=clean(r.get('remarks'))[:100] or None,
            retail=retail,
        )
        if self.apply:
            obj.save(force_insert=True)

    def _import_detail(self, r):
        retail, _, _ = self.org.get(r.get('rt_code'), r.get('br_code'), r.get('ac_yr'))
        header = self._header_by_billno(r.get('billno'))
        main_id = to_int(r.get('main_id'))
        main_item = PurchaseReturnItems.objects.filter(id=main_id).first() if main_id else None
        obj = PurchaseReturnDetails(
            id=to_int(r.get('id')),
            main_item=main_item,
            billno=header,
            sub_item=self._item(r.get('item_id')),
            sub_pcs=to_int(r.get('pcs')),
            sub_ct=dec(r.get('ct')),
            sub_gw=dec(r.get('gw')),
            loss=dec(r.get('loss')),
            tunch=dec(r.get('tunch')),
            packet=(Packet.objects.filter(id=to_int(r.get('packet_id'))).first() if to_int(r.get('packet_id')) else None),
            metal_purity=self.purity.resolve(r.get('metal_purity'), self.apply),
            rate=dec(r.get('rate')),
            value=dec(r.get('value')),
            retail=retail,
        )
        if self.apply:
            obj.save(force_insert=True)

    # ------------------------------------------------------------------ #
    def _item(self, item_id):
        i = to_int(item_id)
        obj = Item.objects.filter(id=i).first() if i else None
        if i and obj is None:
            self.unresolved.append({'table': 'item', 'id': str(i), 'error': 'Item not found'})
        return obj

    def _header_by_billno(self, billno):
        b = clean(billno)
        h = PurchaseReturn.objects.filter(billno=b).first() if b else None
        if b and h is None:
            raise ValueError(f"no PurchaseReturn header for billno {b!r}")
        return h

    def _report(self, report_dir):
        if not self.unresolved:
            return
        os.makedirs(report_dir, exist_ok=True)
        path = os.path.join(report_dir, 'unresolved_purchase_returns.csv')
        pd.DataFrame(self.unresolved).to_csv(path, index=False)
        self.stdout.write(self.style.WARNING(f"{len(self.unresolved)} unresolved row(s) -> {path}"))
