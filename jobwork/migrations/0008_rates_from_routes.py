"""Rates move to the one rate list (owner, 19 Oct 2026). Route-step and lot-step rates become rates on Rates
before the fields are dropped:

* each process on a route gets an In-house rate at its most common route-step rate (ties: the higher);
* every other process gets an In-house rate of 0, so in-house work is never blocked on release;
* a subcontracted lot step whose fabricator had no rate of its own (it was paid the step's rate) gets that rate
  as the fabricator's rate, from its first challan.
"""
import datetime
from collections import Counter
from decimal import Decimal

from django.db import migrations

EARLIEST = datetime.date(2000, 1, 1)


def to_rate_list(apps, schema_editor):
    LabourRate = apps.get_model("jobwork", "LabourRate")
    Process = apps.get_model("masters", "Process")
    RouteStep = apps.get_model("masters", "RouteStep")
    LotStep = apps.get_model("production", "LotStep")
    Challan = apps.get_model("jobwork", "JobWorkChallan")
    FinancialYear = apps.get_model("core", "FinancialYear")
    first_year = FinancialYear.objects.order_by("start_date").first()
    since = first_year.start_date if first_year else EARLIEST
    report = []
    for process in Process.objects.all():
        if LabourRate.objects.filter(party__isnull=True, process=process).exists():
            continue
        seen = Counter(RouteStep.objects.filter(process=process).values_list("rate", flat=True))
        if seen:
            top = max(seen.values())
            rate = max(r for r, n in seen.items() if n == top)
            if len(seen) > 1:
                report.append(f"{process.name}: routes had {', '.join(str(r) for r in sorted(seen))}; In-house rate set to {rate}")
        else:
            rate = Decimal("0.00")
        LabourRate.objects.create(party=None, process=process, rate=rate, effective_from=since)
    for step in LotStep.objects.filter(assignment="subcontract", party__isnull=False, rate__gt=0):
        if LabourRate.objects.filter(party_id=step.party_id, process_id=step.process_id).exists():
            continue
        first = Challan.objects.filter(party_id=step.party_id, step__process_id=step.process_id).order_by("date").first()
        LabourRate.objects.create(party_id=step.party_id, process_id=step.process_id, rate=step.rate,
                                  effective_from=first.date if first else since)
        report.append(f"rate {step.rate} for fabricator #{step.party_id} on process #{step.process_id} carried over from lot {step.lot_id}")
    for line in report:
        print(f"  Rates: {line}")


class Migration(migrations.Migration):

    dependencies = [
        ("jobwork", "0007_one_rate_list"),
        ("masters", "0005_bomline_process"),
        ("production", "0010_lot_cost_step_backfill"),
        ("core", "0007_cutting_variance_label"),
    ]

    operations = [migrations.RunPython(to_rate_list, migrations.RunPython.noop)]
