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
import contextlib

from django.db import transaction, models
from django.db.models.signals import pre_save, post_save, pre_delete, post_delete

from purchase.models import PurchaseVoucher, PurchaseVoucherItems, PurchaseVoucherDetails
from contacts.models import Ledger
from inventory.models import BarcodeMain
from mastersconfig.models import Item, Packet
from decimal import Decimal, ROUND_HALF_UP

from accounting.migration_utils import (
    clean, dec, to_int, parse_date, OrgResolver, PurityResolver, resolve_ac_voucher, resolve_ledger,
    hsn_for_voucher_items, split_gst,
)

@contextlib.contextmanager
def _muted_signals():
    """Mute per-row save/delete signals during the bulk import. They recompute
    stock / raw-material inventory per detail row — which we don't want for a
    historical migration (current stock comes from the opening-stock / barcode
    sync), and which crash on legacy data quirks (e.g. duplicate
    RawMaterialInventory -> get_or_create MultipleObjectsReturned). One-off admin
    import, not run concurrently with normal use."""
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

        with _muted_signals():
            counts = {
                'header': self._pass(hdr, self._import_header, 'PurchaseVoucher', PurchaseVoucher),
                'items':  self._pass(itm, self._import_item, 'PurchaseVoucherItems', PurchaseVoucherItems),
                'details': self._pass(det, self._import_detail, 'PurchaseVoucherDetails', PurchaseVoucherDetails),
            }
            billnos = {clean(b) for b in hdr.get('billno', pd.Series(dtype=str)).dropna()} - {''}
            gst_updated = self._apply_gst(billnos)
        self.stdout.write(self.style.SUCCESS(f"GST recomputed from HSN for {gst_updated} voucher(s)"))

        barcode_linked = self._backfill_barcode_pur_voucher(billnos)
        self.stdout.write(self.style.SUCCESS(f"Barcode pur_voucher resolved for {barcode_linked} barcode(s)"))

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
        header = self._header_by_billno(r.get('billno'), r.get('v_typ'))
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
            # Reciprocal link: the barcode points back to this purchase-voucher
            # line (so BarcodeMain.pur_voucher resolves once purchases are synced).
            if obj.barcode_id and obj.barcode.pur_voucher_id is None:
                obj.barcode.pur_voucher = obj
                obj.barcode.save(update_fields=['pur_voucher'])

    def _import_detail(self, r):
        retail, _, _ = self.org.get(r.get('rt_code'), r.get('br_code'), r.get('ac_yr'))
        main_id = to_int(r.get('main_id'))
        main_item = PurchaseVoucherItems.objects.filter(id=main_id).first() if main_id else None
        # A component/stone line belongs to the same voucher as its parent main
        # item. The main item is matched by PK, so its header is unambiguous even
        # when billnos collide (and even if this line row carries no v_typ).
        # Main-less lines (e.g. old-gold customer purchases) fall back to the
        # (billno, v_typ) match.
        if main_item is not None and main_item.billno_id:
            header = main_item.billno
        else:
            header = self._header_by_billno(r.get('billno'), r.get('v_typ'))
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

    def _apply_gst(self, billnos):
        """Recompute each voucher's GST from its item's HSN master rate (not the
        legacy amounts). Only PURC-SC (Vendor) purchases carry GST; PURC-CO
        (Customer / old-gold) purchases get zero GST. HSN = first main-line item
        with an HSN, else the component (stock_inward_detail) item's HSN. The rate
        is split CGST+SGST (local) or IGST (interstate) per which legacy GST
        column was non-zero. Bill total is recomputed to stay consistent."""
        updated = 0
        # Iterate over voucher objects, not billno strings: a colliding billno
        # maps to two vouchers (Customer + Vendor), and a per-billno .first()
        # would recompute only one of them and silently skip the other.
        for pv in PurchaseVoucher.objects.filter(billno__in=billnos):
            taxable = pv.item_total or Decimal('0')
            cgst = sgst = igst = Decimal('0')

            # Bare line-item subtotal (excl. hallmark/freight/discount) — this is
            # what the print template shows as "Subtotal" (d.tds_taxable_value) and
            # then adds charges / subtracts discount to reach Total Before Tax. The
            # live add-form sets the same field, so migrated vouchers must match or
            # the printed Subtotal renders as 0.
            item_sum = (PurchaseVoucherItems.objects.filter(billno=pv)
                        .aggregate(s=models.Sum('item_value'))['s']) or Decimal('0')
            pv.tds_taxable_value = item_sum

            if pv.voucher_type == 'Customer':
                # PURC-CO (purchase from customer / old gold) — no GST.
                pv.hsn = None
            else:
                # PURC-SC (vendor) — derive GST from the HSN master.
                main_items = [it.item for it in
                              PurchaseVoucherItems.objects.filter(billno=pv).select_related('item__hsn_no')]
                detail_items = [d.sub_item for d in
                                PurchaseVoucherDetails.objects.filter(billno=pv).select_related('sub_item__hsn_no')]
                hsn = hsn_for_voucher_items(main_items, detail_items)
                if hsn is None:
                    self.unresolved.append({'table': 'gst', 'id': pv.billno, 'error': 'no HSN on any item'})
                    # Still persist the subtotal so the print isn't left at 0.
                    if self.apply:
                        pv.save(update_fields=['tds_taxable_value'])
                    continue
                # interstate if the legacy voucher carried IGST and no CGST/SGST
                is_central = bool(pv.igst) and not (pv.cgst or pv.sgst)
                pv.hsn = hsn

            # GST base = bare items + all charges − discount (matches print's "Total Before Tax").
            # We use item_sum (tds_taxable_value) rather than item_total because the
            # old ERP's sub_total (→ item_total) already included hallmark charges.
            # Using item_total here would cause hallmark to be counted twice in the total.
            gst_base = (item_sum
                        + (pv.hallmark_charge or Decimal('0'))
                        + (pv.freight_amt or Decimal('0'))
                        + (pv.add_chrg_amt1 or Decimal('0'))
                        + (pv.add_chrg_amt2 or Decimal('0'))
                        - (pv.discount_amt or Decimal('0')))
            if pv.voucher_type != 'Customer':
                raw_cgst, raw_sgst, raw_igst = split_gst(gst_base, hsn, is_central)
                # The legacy ERP posts each GST line to the nearest whole rupee
                # (matching its ledger entries) rather than keeping paise.
                cgst = raw_cgst.to_integral_value(rounding=ROUND_HALF_UP)
                sgst = raw_sgst.to_integral_value(rounding=ROUND_HALF_UP)
                igst = raw_igst.to_integral_value(rounding=ROUND_HALF_UP)
            pv.cgst, pv.sgst, pv.igst = cgst, sgst, igst
            # total_incl_gst = gst_base + tax (excludes TCS and round_off, consistent with live form)
            # bill_value     = total_incl_gst + tcs + round_off (gross payable, drives due_amt)
            total_incl_gst = gst_base + cgst + sgst + igst
            pre_round_bill_value = total_incl_gst + (pv.tcs_amt or Decimal('0'))
            # cgst/sgst/igst are already whole rupees above, so this only sweeps
            # up any residual paise still in gst_base (e.g. from item_total)
            # into round_off, landing bill_value on a whole rupee like the
            # legacy ERP always did.
            bill_value = pre_round_bill_value.to_integral_value(rounding=ROUND_HALF_UP)
            pv.round_off = bill_value - pre_round_bill_value
            pv.total_incl_gst = total_incl_gst
            pv.bill_value = bill_value
            if self.apply:
                pv.save(update_fields=['hsn', 'cgst', 'sgst', 'igst', 'round_off', 'total_incl_gst', 'bill_value', 'tds_taxable_value'])
            updated += 1
        return updated

    def _backfill_barcode_pur_voucher(self, billnos):
        """A barcode's pur_voucher is normally resolved from its own
        voucher_no (see inventory.api_views._build_barcode_main_kwargs) at
        barcode-sync time — but the full sync runs 'barcode' before
        'purchases' (see mastersconfig.views MySQLSyncView._TX_TABLES
        ordering), so on a single combined sync the matching PurchaseVoucher
        doesn't exist yet when barcodes are processed. Re-attempt the same
        resolution now that purchases have just been imported, scoped to
        just the bills from this run, so it resolves within one sync pass
        instead of needing a second run."""
        from inventory.models import BarcodeMain
        if not billnos:
            return 0
        updated = 0
        qs = BarcodeMain.objects.filter(
            pur_voucher__isnull=True, voucher_no__in=billnos
        )
        for b in qs:
            pv_qs = PurchaseVoucher.objects.filter(billno=b.voucher_no, voucher_type='Vendor')
            pv = pv_qs.filter(retail_id=b.retail_id).first() or pv_qs.first()
            if not pv:
                continue
            pv_items = PurchaseVoucherItems.objects.filter(billno=pv)
            pv_item = pv_items.filter(item_id=b.item_id).first() or pv_items.first()
            if not pv_item:
                continue
            b.pur_voucher = pv_item
            if self.apply:
                b.save(update_fields=['pur_voucher'])
            updated += 1
        return updated

    # ------------------------------------------------------------------ #
    def _ledger(self, code):
        return resolve_ledger(code)

    def _item(self, item_id):
        i = to_int(item_id)
        obj = Item.objects.filter(id=i).first() if i else None
        if i and obj is None:
            self.unresolved.append({'table': 'item', 'id': str(i), 'error': 'Item not found'})
        return obj

    def _header_by_billno(self, billno, v_typ=None):
        b = clean(billno)
        if not b:
            return None
        qs = PurchaseVoucher.objects.filter(billno=b)
        # Disambiguate colliding billnos. The Customer (PURC-CO) and Vendor
        # (PURC-SC) series both number from C..../00001, so one billno can map
        # to two different vouchers. Match the same voucher_type / is_return the
        # header import derives from v_typ, so each line lands on its own
        # voucher instead of whichever happens to share the number (.first()).
        vt = clean(v_typ)
        if vt:
            voucher_type, _ = VTYPE_MAP.get(vt, ('Vendor', False))
            is_return = 'RET' in vt.upper()
            typed = qs.filter(voucher_type=voucher_type, is_return=is_return)
            if typed.exists():
                qs = typed
        h = qs.first()
        if h is None:
            raise ValueError(f"no PurchaseVoucher header for billno {b!r} (v_typ={vt!r})")
        return h

    def _report(self, report_dir):
        if not self.unresolved:
            return
        os.makedirs(report_dir, exist_ok=True)
        path = os.path.join(report_dir, 'unresolved_purchases.csv')
        pd.DataFrame(self.unresolved).to_csv(path, index=False)
        self.stdout.write(self.style.WARNING(f"{len(self.unresolved)} unresolved row(s) -> {path}"))
