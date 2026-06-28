"""
Rebuild sales and/or purchase `due_amt` from the General Ledger (FIFO across
each party's open bills). Dry-run by default; pass --apply to persist.

This is both a one-time repair for drifted data and the canonical step the
import/sync pipeline runs so a fresh database sync yields correct due_amt.
"""
from accounting.due_rebuild import rebuild_sales_due, rebuild_purchase_due


from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Re-derive sales/purchase due_amt from GL balances (FIFO). Dry-run unless --apply."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist (default: dry run).")
        parser.add_argument("--retail", default=None, help="Limit to a retail_code (e.g. R001).")
        parser.add_argument("--kind", choices=["sales", "purchase", "both"], default="both")
        parser.add_argument("--show", type=int, default=20, help="How many changed bills to list.")

    def handle(self, *args, **opts):
        retail = None
        if opts["retail"]:
            from mastersconfig.models import RetailMaster
            retail = RetailMaster.objects.filter(retail_code=opts["retail"]).first()
            if not retail:
                self.stderr.write(self.style.ERROR(f"retail {opts['retail']} not found"))
                return

        runners = []
        if opts["kind"] in ("sales", "both"):
            runners.append(("sales", rebuild_sales_due))
        if opts["kind"] in ("purchase", "both"):
            runners.append(("purchase", rebuild_purchase_due))

        scope = opts["retail"] or "ALL retails"
        mode = "APPLY" if opts["apply"] else "DRY RUN"
        for label, fn in runners:
            res = fn(retail=retail, as_of=None, apply=opts["apply"])
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n{label} due_amt from GL — {scope} — {mode}"))
            self.stdout.write(f"  bills changed   : {res['changed']}")
            self.stdout.write(f"  bills unchanged : {res['unchanged']}")
            self.stdout.write(f"  due_amt total   : {res['old_sum']:,.2f} -> {res['new_sum']:,.2f}")
            self.stdout.write(self.style.WARNING(f"  net change      : {res['delta']:,.2f}"))
            shown = sorted(res["changes"], key=lambda c: abs(c[2] - c[1]), reverse=True)[:opts["show"]]
            for b, old, new in shown:
                arrow = "UP  " if new > old else "DOWN"
                self.stdout.write(
                    f"    {b.billno:<14} {arrow} {float(old):>12,.2f} -> {float(new):>12,.2f}")

        if not opts["apply"]:
            self.stdout.write(self.style.NOTICE("\nDry run — re-run with --apply to persist."))
