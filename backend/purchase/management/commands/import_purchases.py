"""
Import legacy purchase vouchers into PurchaseVoucher / PurchaseVoucherItems /
PurchaseVoucherDetails.

Legacy tables (CSV exports):
  purchase_voucher          -> PurchaseVoucher        (header)
  purchase_voucher_main     -> PurchaseVoucherItems   (main item lines)
  purchase_voucher_details  -> PurchaseVoucherDetails  (stone/sub-item lines)

Legacy PKs are preserved (id=...), so detail.main_id wires directly to the
imported PurchaseVoucherItems. Each pass is idempotent: a row whose PK already
exists is skipped, so re-runs are safe.

Usage:
  python manage.py import_purchases --header pv.csv --items pvm.csv --details pvd.csv \
      [--apply] [--continue-on-error] [--report-dir DIR]
"""
import os

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from purchase.models import PurchaseVoucher, PurchaseVoucherItems, PurchaseVoucherDetails
from contacts.models import Ledger
from inventory.models import BarcodeMain
from mastersconfig.models import Item, Packet
from accounting.migration_utils import (
    clean, dec, to_int, parse_date, OrgResolver, PurityResolver, resolve_ac_voucher, resolve_ledger,
)

# v_typ -> (voucher_type, is_rcm). PURC-SC = supplier/vendor purchase;
# PURC-CO = purchase from customer (old gold, reverse charge).
VTYPE_MAP = {
    'PURC-SC': ('Vendor', False),
    'PURC-CO': ('Customer', True),
}


def _first_barcode(raw):
    """Legacy barcode cell may be empty, a single code, or 'a#b' (multiple)."""
    s = clean(raw)
    if s == '':
        return None
    return s.split('#', 1)[0].strip()


class Command(BaseCommand):
    help = "Import legacy purchase vouchers (header + items + details CSVs)."

    def add_arguments(self, parser):
        parser.add_argument('--header', required=True, help='purchase_voucher CSV')
        parser.add_argument('--items', required=True, help='purchase_voucher_main CSV')
        parser.add_argument('--details', required=True, help='purchase_voucher_details CSV')
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
        self.purity = PurityResolver()
        self.unresolved = []

        counts = {
            'header': self._pass(hdr, self._import_header, 'PurchaseVoucher', PurchaseVoucher),
            'items':  self._pass(itm, self._import_item, 'PurchaseVoucherItems', PurchaseVoucherItems),
            'details': self._pass(det, self._import_detail, 'PurchaseVoucherDetails', PurchaseVoucherDetails),
        }

        self._report(report_dir)
        mode = "APPLIED" if self.apply else "DRY-RUN (no writes)"
        for name, (c, s, e) in counts.items():
            self.stdout.write(self.style.SUCCESS(
                f"[{mode}] {name}: created={c} skipped(existing)={s} errored={e}"
            ))
        if self.purity.created:
            verb = "created" if self.apply else "would create"
            self.stdout.write(self.style.WARNING(
                f"PurityMaster {verb}: {sorted(set(self.purity.created))}"
            ))
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
        v_typ = clean(r.get('v_typ'))
        voucher_type, is_rcm = VTYPE_MAP.get(v_typ, ('Vendor', False))
        is_return = 'RET' in v_typ.upper()
        retail, branch, fy = self.org.get(r.get('rt_code'), r.get('br_code'), r.get('ac_yr'))
        ldgr = self._ledger(r.get('ldgr'))
        total = dec(r.get('total'))
        obj = PurchaseVoucher(
            id=to_int(r.get('id')),
            date1=parse_date(r.get('date1')),
            billno=clean(r.get('billno'))[:30],
            voucher_type=voucher_type,
            is_rcm=is_rcm,
            is_return=is_return,
            ldgr=ldgr,
            hallmark_charge=dec(r.get('hallmark_chrg')),
            freight_amt=dec(r.get('freight_chrg')),
            item_total=dec(r.get('sub_total')),
            discount_amt=dec(r.get('dis_amt')),
            sgst=dec(r.get('sgst_amt')),
            cgst=dec(r.get('cgst_amt')),
            igst=dec(r.get('igst_amt')),
            tcs_amt=dec(r.get('tcs_amt')),
            round_off=dec(r.get('rnd_off')),
            total_incl_gst=total,
            bill_value=total,
            ref_no=clean(r.get('ref_no'))[:10] or None,
            narration=clean(r.get('narration'))[:100] or None,
            source='standalone',
            ac_voucher=resolve_ac_voucher(v_typ, r.get('v_id'), r.get('ac_yr'), r.get('rt_code')),
            retail=retail, branch_ref=branch, fiscal_year=fy,
        )
        if self.apply:
            obj.save(force_insert=True)

    def _import_item(self, r):
        retail, _, _ = self.org.get(r.get('rt_code'), r.get('br_code') if 'br_code' in r else '', r.get('ac_yr'))
        header = self._header_by_billno(r.get('billno'))
        bc_code = _first_barcode(r.get('barcode'))
        obj = PurchaseVoucherItems(
            id=to_int(r.get('id')),
            billno=header,
            date1=parse_date(r.get('date1')),
            sl_no=to_int(r.get('sl_id')),
            item=self._item(r.get('item_id')),
            barcode=(BarcodeMain.objects.filter(barcode=bc_code).first() if bc_code else None),
            barcode_txt=(clean(r.get('barcode'))[:20] or None),
            pcs=to_int(r.get('pcs')),
            gw=dec(r.get('gw')),
            purity=self.purity.resolve(r.get('purity'), self.apply),
            making=dec(r.get('making')),
            making_type=clean(r.get('making_type'))[:20],
            making_value=to_int(r.get('making_value')),
            item_value=dec(r.get('value')),
            remarks=clean(r.get('remarks'))[:100] or None,
            is_return=(header.is_return if header else False),
            retail=retail,
        )
        if self.apply:
            obj.save(force_insert=True)

    def _import_detail(self, r):
        retail, _, _ = self.org.get(r.get('rt_code'), r.get('br_code'), r.get('ac_yr'))
        header = self._header_by_billno(r.get('billno'))
        main_id = to_int(r.get('main_id'))
        main_item = PurchaseVoucherItems.objects.filter(id=main_id).first() if main_id else None
        obj = PurchaseVoucherDetails(
            id=to_int(r.get('id')),
            main_item=main_item,
            billno=header,
            date1=parse_date(r.get('date1')),
            sub_item=self._item(r.get('item_id')),
            sub_pcs=to_int(r.get('pcs')),
            sub_ct=dec(r.get('ct')),
            sub_gw=dec(r.get('gw')),
            loss=dec(r.get('loss')),
            tunch=dec(r.get('tunch')),
            fine_wt=dec(r.get('fine_wt')),
            packet=(Packet.objects.filter(id=to_int(r.get('packet_id'))).first() if to_int(r.get('packet_id')) else None),
            metal_purity=self.purity.resolve(r.get('metal_purity'), self.apply),
            rate=dec(r.get('rate')),
            value=dec(r.get('value')),
            retail=retail,
        )
        if self.apply:
            obj.save(force_insert=True)

    # ------------------------------------------------------------------ #
    def _ledger(self, code):
        return resolve_ledger(code)

    def _item(self, item_id):
        i = to_int(item_id)
        obj = Item.objects.filter(id=i).first() if i else None
        if i and obj is None:
            self.unresolved.append({'table': 'item', 'id': str(i), 'error': 'Item not found'})
        return obj

    def _header_by_billno(self, billno):
        b = clean(billno)
        h = PurchaseVoucher.objects.filter(billno=b).first() if b else None
        if b and h is None:
            raise ValueError(f"no PurchaseVoucher header for billno {b!r}")
        return h

    def _report(self, report_dir):
        if not self.unresolved:
            return
        os.makedirs(report_dir, exist_ok=True)
        path = os.path.join(report_dir, 'unresolved_purchases.csv')
        pd.DataFrame(self.unresolved).to_csv(path, index=False)
        self.stdout.write(self.style.WARNING(f"{len(self.unresolved)} unresolved row(s) -> {path}"))
