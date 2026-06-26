"""
Import legacy sales vouchers into SalesVou / SalesVouItem / SalesVouItemDetails.

Legacy tables (CSV exports):
  sales_vou         -> SalesVou             (invoice header)
  sales_vou_main    -> SalesVouItem         (main item lines)
  sales_vou_detail  -> SalesVouItemDetails  (stone/sub-item lines)

Legacy PKs are preserved. Cancelled invoices (cancel_status) are skipped.
Each pass is idempotent (skip if PK exists).

Usage:
  python manage.py import_sales --header sv.csv --items svm.csv --details svd.csv \
      [--apply] [--continue-on-error] [--report-dir DIR]
"""
import os

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sales.models import SalesVou, SalesVouItem, SalesVouItemDetails, CustomerOrder
from contacts.models import Ledger
from inventory.models import BarcodeMain
from mastersconfig.models import Item, Packet, SalesPersonMaster
from decimal import Decimal

from accounting.migration_utils import (
    clean, dec, to_int, parse_date, OrgResolver, resolve_ac_voucher, resolve_ledger,
    hsn_for_voucher_items,
)


class Command(BaseCommand):
    help = "Import legacy sales vouchers (header + items + details CSVs)."

    def add_arguments(self, parser):
        parser.add_argument('--header', required=True, help='sales_vou CSV')
        parser.add_argument('--items', required=True, help='sales_vou_main CSV')
        parser.add_argument('--details', required=True, help='sales_vou_detail CSV')
        parser.add_argument('--apply', action='store_true', help='Persist (default: dry-run).')
        parser.add_argument('--continue-on-error', action='store_true')
        parser.add_argument('--report-dir', default='.')

    def handle(self, *args, **opts):
        for k in ('header', 'items', 'details'):
            if not os.path.exists(opts[k]):
                raise CommandError(f"File not found: {opts[k]}")

        self.apply = opts['apply']
        self.cont = opts['continue_on_error']
        report_dir = opts['report_dir']

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

        counts = {
            'header': self._pass(hdr, self._import_header, 'SalesVou', SalesVou, skip_cancelled=True),
            'items':  self._pass(itm, self._import_item, 'SalesVouItem', SalesVouItem),
            'details': self._pass(det, self._import_detail, 'SalesVouItemDetails', SalesVouItemDetails),
        }
        ids = {to_int(i) for i in hdr.get('id', pd.Series(dtype=str)).dropna()} - {None}
        gst_updated = self._apply_gst(ids)
        self.stdout.write(self.style.SUCCESS(f"GST recomputed from HSN for {gst_updated} voucher(s)"))

        self._report(report_dir)
        mode = "APPLIED" if self.apply else "DRY-RUN (no writes)"
        for name, (c, s, e, x) in counts.items():
            extra = f" cancelled-skipped={x}" if x else ""
            self.stdout.write(self.style.SUCCESS(
                f"[{mode}] {name}: created={c} skipped(existing)={s} errored={e}{extra}"
            ))
        if not self.apply:
            self.stdout.write(self.style.WARNING("Dry run — re-run with --apply to persist."))

    # ------------------------------------------------------------------ #
    def _read(self, path):
        df = pd.read_csv(path, dtype=str)
        df.columns = [c.strip() for c in df.columns]
        return df

    def _pass(self, df, fn, label, model, skip_cancelled=False):
        created = skipped = errored = cancelled = 0
        for _, row in df.iterrows():
            if skip_cancelled and to_int(row.get('cancel_status')) == 1:
                cancelled += 1
                continue
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
        return created, skipped, errored, cancelled

    # ------------------------------------------------------------------ #
    def _import_header(self, r):
        retail, branch, fy = self.org.get(r.get('rt_code'), r.get('br_code'), r.get('ac_yr'))
        ldgr = resolve_ledger(r.get('ldgr'))
        if ldgr is None:
            raise ValueError(f"ledger {clean(r.get('ldgr'))!r} not found")
        sp = SalesPersonMaster.objects.filter(id=to_int(r.get('sales_person'))).first()
        if sp is None:
            raise ValueError(f"sales_person {clean(r.get('sales_person'))!r} not found")
        sp2 = SalesPersonMaster.objects.filter(id=to_int(r.get('sales_persons2'))).first() if to_int(r.get('sales_persons2')) else None
        order = CustomerOrder.objects.filter(order_no=clean(r.get('order_no'))).first() if clean(r.get('order_no')) else None

        obj = SalesVou(
            id=to_int(r.get('id')),
            date1=parse_date(r.get('date1')),
            billno=clean(r.get('billno'))[:30],
            gst_billno=clean(r.get('gst_billno'))[:20],
            ldgr=ldgr,
            sales_person=sp,
            sales_person2=sp2,
            place_of_supply=clean(r.get('place_of_supply'))[:100],
            ret_status=(to_int(r.get('ret_status')) == 1),
            remarks=clean(r.get('narration'))[:200] or '',
            freight_charge=dec(r.get('freight_chrg')),
            other_charge=dec(r.get('total_oth_making_chg')),
            mrp=dec(r.get('total_gross_amount')),
            discount=dec(r.get('dis')),
            round_off=dec(r.get('rnd_off')),
            sgst_per=dec(r.get('sgst_per')),
            cgst_per=dec(r.get('cgst_per')),
            igst_per=dec(r.get('igst_per')),
            tcs_per=dec(r.get('tcs_per')),
            cash=to_int(r.get('cash_sale')),
            advance_deducted=dec(r.get('customer_advance')),
            customer_order=order,
            mode_of_transport=clean(r.get('mode_trans'))[:200] or None,
            vehicle_no=clean(r.get('vehicle_no'))[:20],
            ac_voucher=resolve_ac_voucher('SALE', r.get('voucher_id'), r.get('ac_yr'), r.get('rt_code')),
            ac_rec_voucher=resolve_ac_voucher('RCPT-SALE', r.get('rcpt_vid'), r.get('ac_yr'), r.get('rt_code')),
            retail=retail, branch_ref=branch, fiscal_year=fy,
        )
        if self.apply:
            obj.save(force_insert=True)

    def _import_item(self, r):
        retail, _, _ = self.org.get(r.get('rt_code'), '', r.get('ac_yr'))
        header = self._sales_by_billno(r.get('billno'))
        item = self._item(r.get('item_id'))
        bc = clean(r.get('barcode'))
        obj = SalesVouItem(
            id=to_int(r.get('id')),
            billno=header,
            barcode=(BarcodeMain.objects.filter(barcode=bc).first() if bc else None),
            item=item,
            pcs=to_int(r.get('pcs'), 1),
            gw=dec(r.get('gw')),
            making=dec(r.get('making')),
            making_type=clean(r.get('making_type'))[:30],
            making_value=to_int(r.get('making_value')),
            purity=to_int(r.get('purity')),
            ret_status=(to_int(r.get('ret_status')) == 1),
            amount=to_int(r.get('amount')),
            retail=retail,
        )
        if self.apply:
            obj.save(force_insert=True)

    def _import_detail(self, r):
        retail, _, _ = self.org.get(r.get('rt_code'), r.get('br_code'), r.get('ac_yr'))
        header = self._sales_by_billno(r.get('billno'))
        main_item = SalesVouItem.objects.filter(id=to_int(r.get('main_id'))).first() if to_int(r.get('main_id')) else None
        obj = SalesVouItemDetails(
            id=to_int(r.get('id')),
            billno=header,
            main_item=main_item,
            item=self._item(r.get('item_id')),
            pcs=to_int(r.get('pcs')),
            ct=dec(r.get('ct')),
            gw=dec(r.get('gw')),
            metal_purity=(clean(r.get('metal_purity'))[:10] if clean(r.get('metal_purity')) not in ('', '0', '0.0', '0.00') else None),
            tunch=dec(r.get('tunch')),
            rate=dec(r.get('rate')),
            amount=dec(r.get('amount')),
            packet=(Packet.objects.filter(id=to_int(r.get('packet_id'))).first() if to_int(r.get('packet_id')) else None),
            retail=retail,
        )
        if self.apply:
            obj.save(force_insert=True)

    def _apply_gst(self, ids):
        """Recompute each sale's GST percentages from its item's HSN master rate:
        pick the HSN (main item, then stone-detail fallback) and set cgst_per/
        sgst_per (local) or igst_per (interstate) per which legacy rate was
        non-zero. SalesVou amounts are computed properties off these percentages."""
        updated = 0
        for sid in ids:
            sv = SalesVou.objects.filter(id=sid).first()
            if sv is None:
                continue
            main_items = [it.item for it in sv.salesvouitem_set.select_related('item__hsn_no').all()]
            detail_items = [d.item for d in sv.salesvouitemdetails_set.select_related('item__hsn_no').all()]
            hsn = hsn_for_voucher_items(main_items, detail_items)
            if hsn is None:
                self.unresolved.append({'table': 'gst', 'id': sid, 'error': 'no HSN on any item'})
                continue
            is_central = bool(sv.igst_per) and not (sv.cgst_per or sv.sgst_per)
            if is_central:
                sv.cgst_per = Decimal('0')
                sv.sgst_per = Decimal('0')
                sv.igst_per = Decimal(str(hsn.igst or 0))
            else:
                sv.cgst_per = Decimal(str(hsn.cgst or 0))
                sv.sgst_per = Decimal(str(hsn.sgst or 0))
                sv.igst_per = Decimal('0')
            if self.apply:
                sv.save(update_fields=['cgst_per', 'sgst_per', 'igst_per'])
            updated += 1
        return updated

    # ------------------------------------------------------------------ #
    def _item(self, item_id):
        i = to_int(item_id)
        obj = Item.objects.filter(id=i).first() if i else None
        if i and obj is None:
            raise ValueError(f"Item {i} not found")
        return obj

    def _sales_by_billno(self, billno):
        b = clean(billno)
        h = SalesVou.objects.filter(billno=b).order_by('id').first() if b else None
        if b and h is None:
            raise ValueError(f"no SalesVou header for billno {b!r}")
        return h

    def _report(self, report_dir):
        if not self.unresolved:
            return
        os.makedirs(report_dir, exist_ok=True)
        path = os.path.join(report_dir, 'unresolved_sales.csv')
        pd.DataFrame(self.unresolved).to_csv(path, index=False)
        self.stdout.write(self.style.WARNING(f"{len(self.unresolved)} unresolved row(s) -> {path}"))
