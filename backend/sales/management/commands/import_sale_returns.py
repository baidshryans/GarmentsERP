"""
Import legacy sale returns into SaleReturn / SaleReturnItem / SaleReturnDetails.

Legacy tables (CSV exports):
  sale_return         -> SaleReturn         (credit-note header)
  sale_return_main    -> SaleReturnItem     (main item lines)
  sale_return_detail  -> SaleReturnDetails  (stone/sub-item lines)

Keyed by billno (legacy ids aren't globally unique across the A/C series). Each
pass is idempotent and re-syncing refreshes a header's lines. GST percentages are
recomputed from the item HSN master (mirrors import_sales). The GL voucher is the
SALE-RET voucher (sale_return.voucher_id) and must already be imported.

Usage:
  python manage.py import_sale_returns --header h.csv --items i.csv --details d.csv \
      [--apply] [--continue-on-error] [--report-dir DIR]
"""
import os
from decimal import Decimal

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sales.models import SaleReturn, SaleReturnItem, SaleReturnDetails, SalesVou
from inventory.models import BarcodeMain
from mastersconfig.models import Item, Packet
from accounting.migration_utils import (
    clean, dec, to_int, parse_date, OrgResolver, PurityResolver,
    resolve_ac_voucher, resolve_ledger, hsn_for_voucher_items,
)


class Command(BaseCommand):
    help = "Import legacy sale returns (header + items + details CSVs)."

    def add_arguments(self, parser):
        parser.add_argument('--header', required=True, help='sale_return CSV')
        parser.add_argument('--items', required=True, help='sale_return_main CSV')
        parser.add_argument('--details', required=True, help='sale_return_detail CSV')
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
        self._new_billnos = set()
        self._item_map = {}  # (billno, legacy sale_return_main.id) -> SaleReturnItem

        counts = {
            'header':  self._pass(hdr, self._import_header, 'SaleReturn'),
            'items':   self._pass(itm, self._import_item, 'SaleReturnItem',
                                  skip_fn=lambda r: clean(r.get('billno')) not in self._new_billnos),
            'details': self._pass(det, self._import_detail, 'SaleReturnDetails',
                                  skip_fn=lambda r: clean(r.get('billno')) not in self._new_billnos),
        }
        gst_updated = self._apply_gst(set(self._new_billnos))
        self.stdout.write(self.style.SUCCESS(f"GST recomputed from HSN for {gst_updated} return(s)"))

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

    def _pass(self, df, fn, label, skip_fn=None):
        created = skipped = errored = 0
        for _, row in df.iterrows():
            if skip_fn and skip_fn(row):
                skipped += 1
                continue
            try:
                with transaction.atomic():
                    fn(row)
                created += 1
            except Exception as exc:
                errored += 1
                self.unresolved.append({'table': label, 'billno': clean(row.get('billno')), 'error': str(exc)})
                self.stderr.write(self.style.ERROR(f"{label} billno={clean(row.get('billno'))}: {exc}"))
                if not self.cont:
                    raise CommandError(str(exc))
        return created, skipped, errored

    # ------------------------------------------------------------------ #
    def _import_header(self, r):
        retail, branch, fy = self.org.get(r.get('rt_code'), r.get('br_code'), r.get('ac_yr'))
        ldgr = resolve_ledger(r.get('ldgr'))
        if ldgr is None:
            raise ValueError(f"ledger {clean(r.get('ldgr'))!r} not found")
        billno = clean(r.get('billno'))[:30]
        defaults = dict(
            date1=parse_date(r.get('date1')),
            ldgr=ldgr,
            mrp=dec(r.get('total_gross_amount')),
            discount=dec(r.get('dis')),
            sgst_per=dec(r.get('sgst_per')),
            cgst_per=dec(r.get('cgst_per')),
            igst_per=dec(r.get('igst_per')),
            tcs_per=dec(r.get('tcs_per')),
            ac_voucher=resolve_ac_voucher('SALE-RET', r.get('voucher_id'), r.get('ac_yr'), r.get('rt_code')),
            retail=retail, fiscal_year=fy,
        )
        if self.apply:
            # Upsert + refresh: re-syncing converges to the source / completes partials.
            obj, created = SaleReturn.objects.update_or_create(billno=billno, defaults=defaults)
            if not created:
                obj.salereturnitem_set.all().delete()  # cascades the detail rows
        self._new_billnos.add(billno)

    def _import_item(self, r):
        retail, _, _ = self.org.get(r.get('rt_code'), '', r.get('ac_yr'))
        billno = clean(r.get('billno'))
        header = SaleReturn.objects.filter(billno=billno).order_by('id').first()
        if header is None:
            if not self.apply:
                return
            raise ValueError(f"no SaleReturn header for billno {billno!r}")
        # Original sale invoice this return is against.
        sale_bill = clean(r.get('sale_bill'))
        sale_vou = SalesVou.objects.filter(billno=sale_bill).order_by('id').first() if sale_bill else None
        if sale_vou and self.apply and header.sales_voucher_ref_id is None:
            header.sales_voucher_ref = sale_vou
            header.original_sale_gst_billno = (sale_vou.gst_billno or '')[:20]
            header.save(update_fields=['sales_voucher_ref', 'original_sale_gst_billno'])
        bc = clean(r.get('barcode'))
        obj = SaleReturnItem(
            billno=header,
            sale_billno=sale_vou,
            barcode=(BarcodeMain.objects.filter(barcode=bc).first() if bc else None),
            item=self._item(r.get('item_id'), required=True),
            pcs=to_int(r.get('pcs')),
            gw=dec(r.get('gw')),
            purity=self.purity.resolve(r.get('purity'), self.apply),
            making=dec(r.get('making')),
            making_type=clean(r.get('making_type'))[:10],
            making_value=dec(r.get('making_value')),
            remarks=clean(r.get('remarks'))[:200] or None,
            retail=retail,
        )
        if self.apply:
            obj.save()
        self._item_map[(billno, to_int(r.get('id')))] = obj

    def _import_detail(self, r):
        retail, _, _ = self.org.get(r.get('rt_code'), r.get('br_code'), r.get('ac_yr'))
        billno = clean(r.get('billno'))
        header = SaleReturn.objects.filter(billno=billno).order_by('id').first()
        if header is None:
            if not self.apply:
                return
            raise ValueError(f"no SaleReturn header for billno {billno!r}")
        main_item = self._item_map.get((billno, to_int(r.get('main_id'))))
        if main_item is None and self.apply:
            raise ValueError(f"no parent return item for billno {billno!r} main_id {clean(r.get('main_id'))}")
        obj = SaleReturnDetails(
            main_item=main_item,
            item=self._item(r.get('item_id')),  # SET_NULL — optional
            pcs=to_int(r.get('pcs')),
            ct=dec(r.get('ct')),
            gw=dec(r.get('gw')),
            tunch=dec(r.get('tunch')),
            metal_purity=self.purity.resolve(r.get('metal_purity'), self.apply),
            rate=dec(r.get('rate')),
            amount=dec(r.get('amount')),
            packet=(Packet.objects.filter(id=to_int(r.get('packet_id'))).first() if to_int(r.get('packet_id')) else None),
            retail=retail,
        )
        if self.apply:
            obj.save()

    def _apply_gst(self, billnos):
        """Recompute each return's GST percentages from its item's HSN rate,
        mirroring import_sales (local cgst/sgst vs interstate igst by which legacy
        rate was non-zero)."""
        updated = 0
        for billno in billnos:
            sr = SaleReturn.objects.filter(billno=billno).order_by('id').first()
            if sr is None:
                continue
            main_items = [it.item for it in
                          SaleReturnItem.objects.filter(billno=sr).select_related('item__hsn_no')]
            detail_items = [d.item for d in
                            SaleReturnDetails.objects.filter(main_item__billno=sr).select_related('item__hsn_no') if d.item]
            hsn = hsn_for_voucher_items(main_items, detail_items)
            if hsn is None:
                self.unresolved.append({'table': 'gst', 'billno': billno, 'error': 'no HSN on any item'})
                continue
            is_central = bool(sr.igst_per) and not (sr.cgst_per or sr.sgst_per)
            if is_central:
                sr.cgst_per = Decimal('0')
                sr.sgst_per = Decimal('0')
                sr.igst_per = Decimal(str(hsn.igst or 0))
            else:
                sr.cgst_per = Decimal(str(hsn.cgst or 0))
                sr.sgst_per = Decimal(str(hsn.sgst or 0))
                sr.igst_per = Decimal('0')
            if self.apply:
                sr.save(update_fields=['cgst_per', 'sgst_per', 'igst_per'])
            updated += 1
        return updated

    # ------------------------------------------------------------------ #
    def _item(self, item_id, required=False):
        i = to_int(item_id)
        obj = Item.objects.filter(id=i).first() if i else None
        if i and obj is None:
            if required:
                raise ValueError(f"Item {i} not found")
            self.unresolved.append({'table': 'item', 'id': str(i), 'error': 'Item not found'})
        return obj

    def _report(self, report_dir):
        if not self.unresolved:
            return
        os.makedirs(report_dir, exist_ok=True)
        path = os.path.join(report_dir, 'unresolved_sale_returns.csv')
        pd.DataFrame(self.unresolved).to_csv(path, index=False)
        self.stdout.write(self.style.WARNING(f"{len(self.unresolved)} unresolved row(s) -> {path}"))
