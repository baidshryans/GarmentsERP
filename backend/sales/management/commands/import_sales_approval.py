"""
Import legacy sale-approval vouchers into
SalesApproval / SalesApprovalItem / SalesApprovalItemDetails.

Legacy tables (CSV exports):
  sales_vou_appr        -> SalesApproval            (approval header)
  sales_vou_main_appr   -> SalesApprovalItem        (main item lines)
  sales_vou_detail_appr -> SalesApprovalItemDetails (stone/sub-item lines)

Keyed by billno (legacy ids aren't globally unique). Each pass is idempotent
(skip if the header billno already exists). GST percentages are recomputed from
the item HSN master, mirroring import_sales.

Usage:
  python manage.py import_sales_approval --header h.csv --items i.csv --details d.csv \
      [--apply] [--continue-on-error] [--report-dir DIR]
"""
import os

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal

from sales.models import SalesApproval, SalesApprovalItem, SalesApprovalItemDetails
from inventory.models import BarcodeMain
from mastersconfig.models import Item, Packet, SalesPersonMaster
from accounting.migration_utils import (
    clean, dec, to_int, parse_date, OrgResolver, resolve_ledger, hsn_for_voucher_items,
)


class Command(BaseCommand):
    help = "Import legacy sale-approval vouchers (header + items + details CSVs)."

    def add_arguments(self, parser):
        parser.add_argument('--header', required=True, help='sales_vou_appr CSV')
        parser.add_argument('--items', required=True, help='sales_vou_main_appr CSV')
        parser.add_argument('--details', required=True, help='sales_vou_detail_appr CSV')
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
        self.unresolved = []
        self._new_billnos = set()
        self._item_map = {}  # (billno, legacy sales_vou_main_appr.id) -> SalesApprovalItem

        counts = {
            'header':  self._pass(hdr, self._import_header, 'SalesApproval',
                                  skip_fn=lambda r: SalesApproval.objects.filter(billno=clean(r.get('billno'))).exists()),
            'items':   self._pass(itm, self._import_item, 'SalesApprovalItem',
                                  skip_fn=lambda r: clean(r.get('billno')) not in self._new_billnos),
            'details': self._pass(det, self._import_detail, 'SalesApprovalItemDetails',
                                  skip_fn=lambda r: clean(r.get('billno')) not in self._new_billnos),
        }
        gst_updated = self._apply_gst(set(self._new_billnos))
        self.stdout.write(self.style.SUCCESS(f"GST recomputed from HSN for {gst_updated} approval(s)"))

        self._report(opts['report_dir'])
        mode = "APPLIED" if self.apply else "DRY-RUN (no writes)"
        for name, (c, s, e) in counts.items():
            self.stdout.write(self.style.SUCCESS(
                f"[{mode}] {name}: created={c} skipped(existing)={s} errored={e}"))
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
        sp = SalesPersonMaster.objects.filter(id=to_int(r.get('sales_person'))).first() or self._default_sp(retail)
        if sp is None:
            raise ValueError("no salesperson available — import the salesperson master first")
        sp2 = SalesPersonMaster.objects.filter(id=to_int(r.get('sales_persons2'))).first() if to_int(r.get('sales_persons2')) else None

        billno = clean(r.get('billno'))[:30]
        obj = SalesApproval(
            date1=parse_date(r.get('date1')),
            billno=billno,
            ldgr=ldgr,
            narration=clean(r.get('narration'))[:100],
            sales_person=sp,
            sales_person2=sp2,
            place_of_supply=None,
            taxable_value=dec(r.get('total_gross_amount')),
            discount=dec(r.get('dis')),
            sgst_per=dec(r.get('sgst_per')),
            cgst_per=dec(r.get('cgst_per')),
            igst_per=dec(r.get('igst_per')),
            retail=retail, fiscal_year=fy,
        )
        if self.apply:
            obj.save()
        self._new_billnos.add(billno)

    def _default_sp(self, retail):
        cache = getattr(self, '_def_sp_cache', None)
        if cache is None:
            cache = self._def_sp_cache = {}
        key = retail.id if retail else None
        if key not in cache:
            cache[key] = (SalesPersonMaster.objects.filter(retail=retail).order_by('id').first()
                          or SalesPersonMaster.objects.order_by('id').first())
        return cache[key]

    def _import_item(self, r):
        retail, _, _ = self.org.get(r.get('rt_code'), '', r.get('ac_yr'))
        billno = clean(r.get('billno'))
        header = SalesApproval.objects.filter(billno=billno).order_by('id').first()
        if header is None:
            if not self.apply:
                return  # dry-run: header not persisted yet
            raise ValueError(f"no SalesApproval header for billno {billno!r}")
        bc = clean(r.get('barcode'))
        barcode = BarcodeMain.objects.filter(barcode=bc).first() if bc else None
        if barcode is None:
            raise ValueError(f"barcode {bc!r} not found (required) — import barcodes first")
        obj = SalesApprovalItem(
            billno=header,
            barcode=barcode,
            item=self._item(r.get('item_id')),
            pcs=to_int(r.get('pcs'), 1),
            gw=dec(r.get('gw')),
            making=dec(r.get('making')),
            making_type=clean(r.get('making_type'))[:20],
            making_value=dec(r.get('making_value')),
            purity=to_int(r.get('purity')),
            ret_status=(to_int(r.get('ret_status')) == 1),
            amount=dec(r.get('amount')),
            retail=retail,
        )
        if self.apply:
            obj.save()
        self._item_map[(billno, to_int(r.get('id')))] = obj

    def _import_detail(self, r):
        retail, _, _ = self.org.get(r.get('rt_code'), r.get('br_code'), r.get('ac_yr'))
        billno = clean(r.get('billno'))
        header = SalesApproval.objects.filter(billno=billno).order_by('id').first()
        if header is None:
            if not self.apply:
                return
            raise ValueError(f"no SalesApproval header for billno {billno!r}")
        main_item = self._item_map.get((billno, to_int(r.get('main_id'))))
        if main_item is None and self.apply:
            raise ValueError(f"no parent approval item for billno {billno!r} main_id {clean(r.get('main_id'))}")
        obj = SalesApprovalItemDetails(
            billno=header,
            main_item=main_item,
            item=self._item(r.get('item_id')),
            pcs=to_int(r.get('pcs')),
            ct=dec(r.get('ct')),
            gw=dec(r.get('gw')),
            metal_purity=(clean(r.get('metal_purity'))[:10]
                          if clean(r.get('metal_purity')) not in ('', '0', '0.0', '0.00') else None),
            rate=dec(r.get('rate')),
            amount=dec(r.get('amount')),
            packet=(Packet.objects.filter(id=to_int(r.get('packet_id'))).first() if to_int(r.get('packet_id')) else None),
            retail=retail,
        )
        if self.apply:
            obj.save()

    def _apply_gst(self, billnos):
        """Recompute each approval's GST percentages from its item's HSN rate,
        mirroring import_sales (local cgst/sgst vs interstate igst by which legacy
        rate was non-zero). Amounts are computed properties off these percentages."""
        updated = 0
        for billno in billnos:
            sa = SalesApproval.objects.filter(billno=billno).order_by('id').first()
            if sa is None:
                continue
            main_items = [it.item for it in sa.items.select_related('item__hsn_no').all()]
            detail_items = [d.item for d in sa.bill_set.select_related('item__hsn_no').all()]
            hsn = hsn_for_voucher_items(main_items, detail_items)
            if hsn is None:
                self.unresolved.append({'table': 'gst', 'billno': billno, 'error': 'no HSN on any item'})
                continue
            is_central = bool(sa.igst_per) and not (sa.cgst_per or sa.sgst_per)
            if is_central:
                sa.cgst_per = Decimal('0')
                sa.sgst_per = Decimal('0')
                sa.igst_per = Decimal(str(hsn.igst or 0))
            else:
                sa.cgst_per = Decimal(str(hsn.cgst or 0))
                sa.sgst_per = Decimal(str(hsn.sgst or 0))
                sa.igst_per = Decimal('0')
            if self.apply:
                sa.save(update_fields=['cgst_per', 'sgst_per', 'igst_per'])
            updated += 1
        return updated

    # ------------------------------------------------------------------ #
    def _item(self, item_id):
        i = to_int(item_id)
        obj = Item.objects.filter(id=i).first() if i else None
        if i and obj is None:
            raise ValueError(f"Item {i} not found")
        return obj

    def _report(self, report_dir):
        if not self.unresolved:
            return
        os.makedirs(report_dir, exist_ok=True)
        path = os.path.join(report_dir, 'unresolved_sales_approval.csv')
        pd.DataFrame(self.unresolved).to_csv(path, index=False)
        self.stdout.write(self.style.WARNING(f"{len(self.unresolved)} unresolved row(s) -> {path}"))
