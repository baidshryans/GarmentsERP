"""
Import legacy customer orders into CustomerOrder / CustomerOrderItems.

Legacy tables (CSV exports / MySQL):
  customer_order       -> CustomerOrder        (order header, keyed by orderno)
  customer_order_main  -> CustomerOrderItems   (order line items)

Headers are matched by order_no (unique); items preserve their legacy id.
Idempotent (skip if already present). Import after masters + ledgers, and
before sales (sales link to a customer order by order_no).

Usage:
  python manage.py import_customer_orders --header co.csv --items com.csv \
      [--apply] [--continue-on-error] [--report-dir DIR]
"""
import os

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sales.models import CustomerOrder, CustomerOrderItems
from mastersconfig.models import Item, SalesPersonMaster
from accounting.migration_utils import (
    clean, dec, to_int, parse_date, OrgResolver, PurityResolver, resolve_ledger,
)


class Command(BaseCommand):
    help = "Import legacy customer orders (header + items CSVs)."

    def add_arguments(self, parser):
        parser.add_argument('--header', required=True, help='customer_order CSV')
        parser.add_argument('--items', required=True, help='customer_order_main CSV')
        parser.add_argument('--apply', action='store_true', help='Persist (default: dry-run).')
        parser.add_argument('--continue-on-error', action='store_true')
        parser.add_argument('--report-dir', default='.')

    def handle(self, *args, **opts):
        for k in ('header', 'items'):
            if not os.path.exists(opts[k]):
                raise CommandError(f"File not found: {opts[k]}")

        self.apply = opts['apply']
        self.cont = opts['continue_on_error']
        report_dir = opts['report_dir']

        hdr = self._read(opts['header'])
        itm = self._read(opts['items'])

        self.org = OrgResolver(self.stdout, self.style, apply=self.apply)
        errs = self.org.validate_retail(set(hdr.get('rt_code', pd.Series(dtype=str)).dropna()))
        if errs:
            for e in errs:
                self.stderr.write(self.style.ERROR(e))
            raise CommandError("Unresolved retail codes — import masters first.")
        self.purity = PurityResolver()
        self.unresolved = []
        self._sl = {}  # order_no -> running line serial

        counts = {
            'header': self._pass(hdr, self._import_header, 'CustomerOrder', CustomerOrder, key='orderno'),
            'items':  self._pass(itm, self._import_item, 'CustomerOrderItems', CustomerOrderItems, key='id'),
        }

        self._report(report_dir)
        mode = "APPLIED" if self.apply else "DRY-RUN (no writes)"
        for name, (c, s, e) in counts.items():
            self.stdout.write(self.style.SUCCESS(
                f"[{mode}] {name}: created={c} skipped(existing)={s} errored={e}"
            ))
        if not self.apply:
            self.stdout.write(self.style.WARNING("Dry run — re-run with --apply to persist."))

    # ------------------------------------------------------------------ #
    def _read(self, path):
        df = pd.read_csv(path, dtype=str)
        df.columns = [c.strip() for c in df.columns]
        return df

    def _pass(self, df, fn, label, model, key):
        created = skipped = errored = 0
        for _, row in df.iterrows():
            try:
                if self._exists(model, key, row):
                    skipped += 1
                    continue
                with transaction.atomic():
                    fn(row)
                created += 1
            except Exception as exc:
                errored += 1
                self.unresolved.append({'table': label, 'key': clean(row.get(key)), 'error': str(exc)})
                self.stderr.write(self.style.ERROR(f"{label} {clean(row.get(key))}: {exc}"))
                if not self.cont:
                    raise CommandError(str(exc))
        return created, skipped, errored

    def _exists(self, model, key, row):
        if key == 'orderno':
            return CustomerOrder.objects.filter(order_no=clean(row.get('orderno'))).exists()
        # customer_order_main.id is the per-order line serial (not a unique PK),
        # so idempotency keys on (order_no, sl_no=that serial).
        return CustomerOrderItems.objects.filter(
            order_no__order_no=clean(row.get('order_no')),
            sl_no=to_int(row.get('id')),
        ).exists()

    # ------------------------------------------------------------------ #
    def _import_header(self, r):
        retail, branch, fy = self.org.get(r.get('rt_code'), '', r.get('ac_yr'))
        order_no = clean(r.get('orderno'))[:30]
        if not order_no:
            raise ValueError("blank order number")
        r18, r22 = to_int(r.get('18kt')), to_int(r.get('22kt'))
        sp1 = SalesPersonMaster.objects.filter(id=to_int(r.get('salesman1'))).first() if to_int(r.get('salesman1')) else None
        sp2 = SalesPersonMaster.objects.filter(id=to_int(r.get('salesman2'))).first() if to_int(r.get('salesman2')) else None

        obj = CustomerOrder(
            order_no=order_no,
            date1=parse_date(r.get('date1')),
            ldgr=resolve_ledger(r.get('customer_ldgr')),
            gold_rate_date=parse_date(r.get('gold_rate_date')),
            fix_gold_rate=bool((r18 or 0) or (r22 or 0)),
            rate_18kt=r18 or 0,
            rate_22kt=r22 or 0,
            salesman_1=sp1,
            salesman_2=sp2,
            est_amount=0,
            nature='New Booking',
            delivery_status='pending',
            remarks=(clean(r.get('remarks'))[:100] or None),
            retail=retail, fiscal_year=fy,
        )
        if self.apply:
            obj.save(force_insert=True)

    def _import_item(self, r):
        retail, _, _ = self.org.get(r.get('rt_code'), '', r.get('ac_yr'))
        order_no = clean(r.get('order_no'))
        order = CustomerOrder.objects.filter(order_no=order_no).first()
        if order is None:
            raise ValueError(f"no CustomerOrder header for order_no {order_no!r}")
        sl_no = to_int(r.get('id'))  # legacy per-order line serial
        if not sl_no:
            self._sl[order_no] = self._sl.get(order_no, 0) + 1
            sl_no = self._sl[order_no]
        obj = CustomerOrderItems(
            order_no=order,
            sl_no=sl_no,
            item_id=(Item.objects.filter(id=to_int(r.get('item_id'))).first() if to_int(r.get('item_id')) else None),
            pcs=to_int(r.get('pcs')),
            gw=dec(r.get('gw')),
            size=(clean(r.get('item_size'))[:10] or None),
            purity=self.purity.resolve(r.get('purity'), self.apply),
            making_type=clean(r.get('making_type'))[:20],
            making_amt=to_int(r.get('making')),
            other_chg=to_int(r.get('other_making')),
            iss_status=(to_int(r.get('iss_status')) > 0),
            rec_status=(to_int(r.get('rec_status')) > 0),
            del_status=(to_int(r.get('delivery_status')) > 0),
            sale_status=(to_int(r.get('sale_status')) > 0),
            remarks=(clean(r.get('remarks'))[:100] or None),
            retail=retail,
        )
        if self.apply:
            obj.save(force_insert=True)

    # ------------------------------------------------------------------ #
    def _report(self, report_dir):
        if not self.unresolved:
            return
        os.makedirs(report_dir, exist_ok=True)
        path = os.path.join(report_dir, 'unresolved_customer_orders.csv')
        pd.DataFrame(self.unresolved).to_csv(path, index=False)
        self.stdout.write(self.style.WARNING(f"{len(self.unresolved)} unresolved row(s) -> {path}"))
