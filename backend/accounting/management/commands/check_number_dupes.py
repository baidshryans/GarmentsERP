"""
check_number_dupes — scan voucher-number models for scope-level duplicates.

Exit code 0  → no duplicates found (safe to add UniqueConstraints).
Exit code 1  → at least one duplicate group detected (STOP before adding constraints).

The MODEL_CHECKS constant is the single source of truth consumed by Tasks 17/18 as
well; extend it there when new models are converted.
"""
import sys
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.models import Count

# ---------------------------------------------------------------------------
# Single source of truth — extend here when adding new converted models.
# Each entry: (app_label.ModelName, [scope_fields], number_field)
# ---------------------------------------------------------------------------
MODEL_CHECKS = [
    # purchase
    ("purchase.PurchaseVoucher",           ["retail", "fiscal_year", "voucher_type"], "billno"),
    ("purchase.PurchaseReturn",             ["retail", "fiscal_year"],                 "billno"),
    ("purchase.PurchaseOrder",              ["retail", "fiscal_year"],                 "po_no"),
    # sales
    ("sales.Quotation",                     ["retail", "fiscal_year"],                 "quotation_no"),
    # manufacturing — refinery
    ("manufacturing.RefinaryIssue",         ["retail", "fiscal_year"],                 "billno"),
    ("manufacturing.RefinaryReceive",       ["retail", "fiscal_year"],                 "billno"),
    # manufacturing — melting
    ("manufacturing.MeltingIssue",          ["retail", "fiscal_year"],                 "billno"),
    ("manufacturing.MeltingReceive",        ["retail", "fiscal_year"],                 "billno"),
    # manufacturing — hallmark
    ("manufacturing.HallmarkIssue",         ["retail", "fiscal_year"],                 "issue_slip_no"),
    ("manufacturing.HallmarkReceive",       ["retail", "fiscal_year"],                 "receive_slip_no"),
    # manufacturing — repair
    ("manufacturing.RepairJobCard",         ["retail", "fiscal_year"],                 "rjc_no"),
    # manufacturing — sample
    ("manufacturing.SampleIssue",           ["retail", "fiscal_year"],                 "billno"),
    # manufacturing — karigar gold/stone
    ("manufacturing.KarigarGoldIssueHeader",   ["retail", "fiscal_year"],             "billno"),
    ("manufacturing.KarigarStoneIssueHeader",  ["retail", "fiscal_year"],             "billno"),
    ("manufacturing.KarigarStoneReceiveHeader",["retail", "fiscal_year"],             "billno"),
    # manufacturing — karigar issue / receive (header models, not line items)
    ("manufacturing.KarigarIssue",          ["retail", "fiscal_year"],                 "issue_slip_no"),
    ("manufacturing.KarigarReceive",        ["retail", "fiscal_year"],                 "receive_slip_no"),
    # -----------------------------------------------------------------------
    # Already-race-safe models — added for dup pre-check before constraints
    # -----------------------------------------------------------------------
    # sales
    ("sales.SalesVou",                      ["retail", "fiscal_year"],                 "billno"),
    ("sales.SaleReturn",                    ["retail", "fiscal_year"],                 "billno"),
    ("sales.SalesApproval",                 ["retail", "fiscal_year"],                 "billno"),
    ("sales.SalesApprovalReturn",           ["retail", "fiscal_year"],                 "billno"),
    ("sales.CustomerOrder",                 ["retail", "fiscal_year"],                 "order_no"),
    # inventory
    ("inventory.StockTransfer",             ["retail", "fiscal_year"],                 "billno"),
    # InterRetailTransferVoucher skipped — no retail field
    ("inventory.StockJournal",              ["retail", "fiscal_year"],                 "billno"),
    # accounting
    ("accounting.VoucherMain",              ["retail", "fiscal_year"],                 "voucher_no"),
    ("accounting.CreditDebitNote",          ["retail", "fiscal_year"],                 "note_no"),
    ("accounting.CashGoldConversion",       ["retail", "fiscal_year"],                 "billno"),
    # goldscheme
    ("goldscheme.SchemeEnrollment",         ["retail", "fiscal_year"],                 "enrollment_no"),
    ("goldscheme.SchemePayment",            ["retail", "fiscal_year"],                 "payment_no"),
]


class Command(BaseCommand):
    help = (
        "Pre-flight check: find duplicate voucher numbers within their scoping "
        "fields. Exits 1 if any duplicates are found so a subsequent migration "
        "won't crash on UniqueConstraint violations."
    )

    def handle(self, *args, **options):
        any_dupes = False

        for model_path, scope_fields, number_field in MODEL_CHECKS:
            app_label, model_name = model_path.split(".")
            try:
                Model = apps.get_model(app_label, model_name)
            except LookupError:
                self.stderr.write(
                    self.style.WARNING(f"  [SKIP] {model_path} — model not found")
                )
                continue

            # Build the GROUP BY list: scope FK ids + the number field.
            # Django stores FK columns as <field>_id; we group by that.
            group_by = []
            for f in scope_fields:
                field_obj = Model._meta.get_field(f)
                if field_obj.many_to_one or field_obj.one_to_one:
                    group_by.append(f"{f}_id")
                else:
                    group_by.append(f)
            group_by.append(number_field)

            dupes_qs = (
                Model.objects
                .values(*group_by)
                .annotate(cnt=Count("id"))
                .filter(cnt__gt=1)
                .order_by(*group_by)
            )

            dupe_count = dupes_qs.count()
            if dupe_count == 0:
                self.stdout.write(
                    self.style.SUCCESS(f"  OK   {model_path} ({number_field})")
                )
            else:
                any_dupes = True
                self.stdout.write(
                    self.style.ERROR(
                        f"  DUPE {model_path} ({number_field}) — {dupe_count} duplicate group(s):"
                    )
                )
                for row in dupes_qs[:50]:  # cap output at 50 rows
                    # Collect the pks for this duplicate group
                    filter_kwargs = {k: row[k] for k in group_by}
                    pks = list(
                        Model.objects.filter(**filter_kwargs).values_list("id", flat=True)
                    )
                    self.stdout.write(
                        f"    scope={{{', '.join(f'{k}={row[k]}' for k in group_by[:-1])}}}"
                        f"  {number_field}={row[number_field]!r}"
                        f"  count={row['cnt']}  pks={pks}"
                    )

        self.stdout.write("")
        if any_dupes:
            self.stdout.write(
                self.style.ERROR(
                    "RESULT: duplicates found — do NOT add UniqueConstraints until resolved."
                )
            )
            sys.exit(1)
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "RESULT: no duplicates — safe to add scoped UniqueConstraints."
                )
            )
