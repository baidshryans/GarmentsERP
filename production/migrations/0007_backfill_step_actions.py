"""Steps recorded before the action log existed get their action now, so that they too can be edited or undone.

Only the steps whose postings can be told apart for certain are covered: fabric issues, lays, and the bundles of a
lay as long as none of them has moved, been split or gone on a challan. Later steps of older lots (moves, challans,
receipts, QC, packing) stay as they are.
"""
import datetime
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import migrations


class _Exact(DjangoJSONEncoder):
    def default(self, o):                                  # times in full, as production.services.actions keeps them
        if isinstance(o, (datetime.datetime, datetime.time)):
            return o.isoformat()
        return super().default(o)


def _snap(obj, **changed):
    data = {f.attname: getattr(obj, f.attname) for f in obj._meta.concrete_fields}
    data.update(changed)
    return json.loads(json.dumps(data, cls=_Exact))


def backfill(apps, schema_editor=None):
    get = apps.get_model
    Action, Item = get("production", "ProductionAction"), get("production", "ProductionActionItem")
    FabricIssue, CuttingEntry, Bundle = get("production", "FabricIssue"), get("production", "CuttingEntry"), get("production", "Bundle")
    StageMovement, LotCostEntry = get("production", "StageMovement"), get("production", "LotCostEntry")
    StockMovement, Voucher, ChallanBundle = get("inventory", "StockMovement"), get("ledger", "Voucher"), get("jobwork", "ChallanBundle")

    def known(kind, label, pk):
        return Action.objects.filter(kind=kind, doc_type=label, doc_id=pk).exists()

    def add(doc, kind, label, summary, rows):
        action = Action.objects.create(
            company_id=doc.company_id, factory_id=doc.factory_id, lot_id=doc.lot_id, kind=kind, date=doc.date,
            summary=summary[:255], created_by_id=doc.created_by_id, doc_type=label, doc_id=doc.pk)
        Item.objects.bulk_create([Item(action=action, role=role, model=model, object_id=pk, label=text[:80], before=before, after=after)
                                  for role, model, pk, text, before, after in rows])

    def posted(label, pk, with_bundle):
        moves = StockMovement.objects.filter(source_type=label, source_id=pk, bundle__isnull=not with_bundle).order_by("id")
        return [("movement", "inventory.stockmovement", m.pk, f"Stock movement #{m.pk}", None, None) for m in moves]

    docs = [(i.created_at, 0, i) for i in FabricIssue.objects.all()] + [(e.created_at, 1, e) for e in CuttingEntry.objects.all()]
    for _, is_lay, doc in sorted(docs, key=lambda d: (d[0], d[1], d[2].pk)):
        if not is_lay:
            label = "production.fabricissue"
            if known("fabric", label, doc.pk):
                continue
            lines = list(doc.lines.order_by("id"))
            rows = posted(label, doc.pk, False) + [("created", label, doc.pk, f"Fabric issue #{doc.pk}", None, _snap(doc))]
            rows += [("created", "production.fabricissueline", l.pk, f"Fabric issue line #{l.pk}", None, _snap(l)) for l in lines]
            add(doc, "fabric", label, f"{len(lines)} roll(s), {sum(l.qty for l in lines).normalize():f} to the cutting floor", rows)
            continue

        label = "production.cuttingentry"
        sizes, rolls = list(doc.sizes.order_by("id")), list(doc.rolls.order_by("id"))
        if not known("cutting", label, doc.pk):
            rows = posted(label, doc.pk, False)
            rows += [("voucher", "ledger.voucher", v.pk, v.number or "", None, None)
                     for v in Voucher.objects.filter(source_type=label, source_id=doc.pk, reverses__isnull=True).order_by("id")]
            rows += [("cost", "production.lotcostentry", c.pk, c.note, None, None)
                     for c in LotCostEntry.objects.filter(source_type=label, source_id=doc.pk).order_by("id")]
            rows.append(("created", label, doc.pk, f"Cutting {doc.lay_no}", None, _snap(doc, bundled=False)))
            rows += [("created", "production.cuttingsize", s.pk, f"Cutting {doc.lay_no} size", None, _snap(s)) for s in sizes]
            rows += [("created", "production.cuttingrolluse", r.pk, f"Cutting {doc.lay_no} roll", None, _snap(r)) for r in rolls]
            add(doc, "cutting", label, f"Cutting {doc.lay_no}: {sum(s.pieces for s in sizes)} pieces cut", rows)

        bundles = list(Bundle.objects.filter(entry_id=doc.pk).order_by("id"))
        ids = [b.pk for b in bundles]
        untouched = (all(b.status == "cut" and b.qty == b.original_qty and b.split_from_id is None for b in bundles)
                     and not StageMovement.objects.filter(bundle_id__in=ids).exists()
                     and not ChallanBundle.objects.filter(bundle_id__in=ids).exists()
                     and not Bundle.objects.filter(split_from_id__in=ids).exists())
        if doc.bundled and untouched and not known("bundles", label, doc.pk):
            rows = posted(label, doc.pk, True)
            rows.append(("changed", label, doc.pk, f"Cutting {doc.lay_no}", _snap(doc, bundled=False), _snap(doc)))
            rows += [("changed", "production.cuttingsize", s.pk, f"Cutting {doc.lay_no} size", _snap(s), _snap(s)) for s in sizes]
            rows += [("created", "production.bundle", b.pk, b.bundle_no, None, _snap(b)) for b in bundles]
            add(doc, "bundles", label, f"Cutting {doc.lay_no}: {len(bundles)} bundle(s), {sum(b.qty for b in bundles)} pieces", rows)


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0006_action_log_and_voided_bundles"),
        ("inventory", "0005_seed_stock_adjustment_ledger"),
        ("ledger", "0002_voucher_vendor_invoice_no"),
        ("jobwork", "0005_pay_qty_from_accepted"),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
