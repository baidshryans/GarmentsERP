"""Link the lot cost recorded before cost entries carried a step to the route step it belongs to, from the document
each entry already points to. An entry whose step cannot be told for certain (labour for bundles leaving a stage,
a bill covering two steps of one lot) is left for the whole lot and shown as "not linked to a step"."""
from django.db import migrations


def _first_cutting_step(LotStep, lot_id):
    steps = list(LotStep.objects.filter(lot_id=lot_id).select_related("process").order_by("sequence"))
    head = []
    for s in steps:
        if s.process.kind != "cutting":
            break
        head.append(s)
    return head


def _packing_step(LotStep, lot_id):
    for s in LotStep.objects.filter(lot_id=lot_id).exclude(status="skipped").select_related("process").order_by("-sequence"):
        if s.process.kind == "packing":
            return s
    return None


def backfill(apps, schema_editor):
    LotCostEntry = apps.get_model("production", "LotCostEntry")
    LotStep = apps.get_model("production", "LotStep")
    StepMaterialIssue = apps.get_model("production", "StepMaterialIssue")
    ProductionActionItem = apps.get_model("production", "ProductionActionItem")
    JobWorkChallan = apps.get_model("jobwork", "JobWorkChallan")
    Receipt = apps.get_model("jobwork", "Receipt")
    JobWorkBillLine = apps.get_model("jobwork", "JobWorkBillLine")
    JobWorkBillDeduction = apps.get_model("jobwork", "JobWorkBillDeduction")

    def step_of(e):
        src, pk = e.source_type, e.source_id
        if not pk:
            return None
        if src == "jobwork.jobworkchallan":
            return JobWorkChallan.objects.filter(pk=pk).values_list("step_id", flat=True).first()
        if src == "jobwork.receipt":
            return Receipt.objects.filter(pk=pk).values_list("challan__step_id", flat=True).first()
        if src == "jobwork.jobworkbill":
            steps = set(JobWorkBillLine.objects.filter(bill_id=pk, lot_id=e.lot_id).values_list("challan__step_id", flat=True))
            steps |= set(JobWorkBillDeduction.objects.filter(bill_id=pk, lot_id=e.lot_id).values_list("challan__step_id", flat=True))
            return steps.pop() if len(steps) == 1 else None
        if src == "production.stepmaterialissue":
            return StepMaterialIssue.objects.filter(pk=pk).values_list("step_id", flat=True).first()
        if src == "production.cuttingentry":
            head = _first_cutting_step(LotStep, e.lot_id)
            if e.kind == "fabric" and head:
                return head[0].pk
            if e.kind == "labour" and len(head) == 1:
                return head[0].pk
            return None
        if src == "production.lot" and e.kind == "labour" and e.note.startswith("Packing"):
            pack = _packing_step(LotStep, e.lot_id)
            return pack.pk if pack else None
        return None

    reversals = []
    for e in LotCostEntry.objects.filter(step__isnull=True).exclude(kind__in=("transfer", "relief", "write_off")).iterator():
        if e.source_type == "production.productionaction":
            reversals.append(e)
            continue
        step_id = step_of(e)
        if step_id:
            LotCostEntry.objects.filter(pk=e.pk).update(step_id=step_id)
    # an undo reverses the cost entries of its step: each reversal follows the entry it took back
    for e in reversals:
        originals = ProductionActionItem.objects.filter(action_id=e.source_id, role="cost").values_list("object_id", flat=True)
        match = (LotCostEntry.objects.filter(pk__in=list(originals), lot_id=e.lot_id, factory_id=e.factory_id, kind=e.kind,
                                             amount=-e.amount, step__isnull=False).values_list("step_id", flat=True).first())
        if match:
            LotCostEntry.objects.filter(pk=e.pk).update(step_id=match)


class Migration(migrations.Migration):
    dependencies = [
        ("production", "0009_lot_cost_step"),
        ("jobwork", "0006_held_for_rework"),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
