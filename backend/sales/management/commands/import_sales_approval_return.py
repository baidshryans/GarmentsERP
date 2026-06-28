"""
Import legacy sale-approval-return vouchers into
SalesApprovalReturn / SalesApprovalReturnItem / SalesApprovalReturnItemDetails.

Legacy tables (CSV exports):
  sales_vou_appr_return        -> SalesApprovalReturn            (return header)
  sales_vou_appr_return_main   -> SalesApprovalReturnItem        (main item lines)
  sales_vou_appr_return_detail -> SalesApprovalReturnItemDetails (stone/sub-item lines)

Keyed by billno (legacy ids aren't globally unique). Each pass is idempotent.
The return links back to its approval: the header's ref_approval is set from the
items' appr_billno, and each item's approval_item is matched within that approval
by barcode (best-effort; left null if not found).

Usage:
  python manage.py import_sales_approval_return --header h.csv --items i.csv --details d.csv \
      [--apply] [--continue-on-error] [--report-dir DIR]
"""
import os

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sales.models import (
    SalesApprovalReturn, SalesApprovalReturnItem, SalesApprovalReturnItemDetails,
    SalesApproval, SalesApprovalItem,
)
from inventory.models import BarcodeMain
from mastersconfig.models import Item, Packet
from accounting.migration_utils import clean, dec, to_int, parse_date, OrgResolver


class Command(BaseCommand):
    help = "Import legacy sale-approval-return vouchers (header + items + details CSVs)."

    def add_arguments(self, parser):
        parser.add_argument('--header', required=True, help='sales_vou_appr_return CSV')
        parser.add_argument('--items', required=True, help='sales_vou_appr_return_main CSV')
        parser.add_argument('--details', required=True, help='sales_vou_appr_return_detail CSV')
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
        self._item_map = {}  # (billno, legacy sales_vou_appr_return_main.id) -> SalesApprovalReturnItem

        counts = {
            'header':  self._pass(hdr, self._import_header, 'SalesApprovalReturn'),
            'items':   self._pass(itm, self._import_item, 'SalesApprovalReturnItem',
                                  skip_fn=lambda r: clean(r.get('billno')) not in self._new_billnos),
            'details': self._pass(det, self._import_detail, 'SalesApprovalReturnItemDetails',
                                  skip_fn=lambda r: clean(r.get('billno')) not in self._new_billnos),
        }
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
        billno = clean(r.get('billno'))[:30]
        defaults = dict(
            date1=parse_date(r.get('date1')),
            ref_approval=None,  # re-set from the items' appr_billno
            narration=clean(r.get('narration'))[:100],
            retail=retail, fiscal_year=fy,
        )
        if self.apply:
            # Upsert + refresh: re-syncing converges to the source / completes partials.
            obj, created = SalesApprovalReturn.objects.update_or_create(billno=billno, defaults=defaults)
            if not created:
                obj.items.all().delete()
                SalesApprovalReturnItemDetails.objects.filter(billno=obj).delete()
        self._new_billnos.add(billno)

    def _import_item(self, r):
        retail, _, _ = self.org.get(r.get('rt_code'), '', r.get('ac_yr'))
        billno = clean(r.get('billno'))
        header = SalesApprovalReturn.objects.filter(billno=billno).order_by('id').first()
        if header is None:
            if not self.apply:
                return
            raise ValueError(f"no SalesApprovalReturn header for billno {billno!r}")
        appr_billno = clean(r.get('appr_billno'))
        approval = SalesApproval.objects.filter(billno=appr_billno).order_by('id').first() if appr_billno else None
        # Link the return header back to its approval (first one wins).
        if approval and self.apply and header.ref_approval_id is None:
            header.ref_approval = approval
            header.save(update_fields=['ref_approval'])
        bc = clean(r.get('barcode'))
        barcode = BarcodeMain.objects.filter(barcode=bc).first() if bc else None
        # Best-effort: match the original approval line by barcode within the approval.
        approval_item = (SalesApprovalItem.objects.filter(billno=approval, barcode__barcode=bc).first()
                         if (approval and bc) else None)
        obj = SalesApprovalReturnItem(
            billno=header,
            barcode=barcode,
            approval_item=approval_item,
            item=self._item(r.get('item_id')),
            pcs=to_int(r.get('pcs')),
            gw=dec(r.get('gw')),
            purity=clean(r.get('purity'))[:10],
            amount=dec(r.get('amount')),
            retail=retail,
        )
        if self.apply:
            obj.save()
        self._item_map[(billno, to_int(r.get('id')))] = obj

    def _import_detail(self, r):
        retail, _, _ = self.org.get(r.get('rt_code'), r.get('br_code'), r.get('ac_yr'))
        billno = clean(r.get('billno'))
        header = SalesApprovalReturn.objects.filter(billno=billno).order_by('id').first()
        if header is None:
            if not self.apply:
                return
            raise ValueError(f"no SalesApprovalReturn header for billno {billno!r}")
        main_item = self._item_map.get((billno, to_int(r.get('main_id'))))
        if main_item is None and self.apply:
            raise ValueError(f"no parent return item for billno {billno!r} main_id {clean(r.get('main_id'))}")
        obj = SalesApprovalReturnItemDetails(
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
        path = os.path.join(report_dir, 'unresolved_sales_approval_return.csv')
        pd.DataFrame(self.unresolved).to_csv(path, index=False)
        self.stdout.write(self.style.WARNING(f"{len(self.unresolved)} unresolved row(s) -> {path}"))
