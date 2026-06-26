"""
Merge duplicate RawMaterialInventory rows.

RawMaterialInventory.unique_together = (item, packet, purity, retail) but packet
and purity are nullable, and SQL treats NULL as distinct — so duplicate rows for
the same item/retail with NULL packet/purity can slip in. Those break the
get_or_create in the stock signals (MultipleObjectsReturned).

This folds each duplicate group into its lowest-pk row (summing pcs/ct/gw) and
deletes the extras. Dry-run by default.

  python manage.py dedupe_raw_material [--apply]
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from inventory.models import RawMaterialInventory


class Command(BaseCommand):
    help = "Merge duplicate RawMaterialInventory rows (NULL packet/purity dupes)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Persist (default: dry-run).')

    def handle(self, *args, **opts):
        apply = opts['apply']
        groups = list(
            RawMaterialInventory.objects
            .values('item', 'packet', 'purity', 'retail')
            .annotate(n=Count('id')).filter(n__gt=1)
        )

        removed = 0
        with transaction.atomic():
            for g in groups:
                rows = list(RawMaterialInventory.objects.filter(
                    item=g['item'], packet=g['packet'], purity=g['purity'], retail=g['retail']
                ).order_by('pk'))
                keep, extras = rows[0], rows[1:]
                for e in extras:
                    keep.pcs += e.pcs
                    keep.ct += e.ct
                    keep.gw += e.gw
                if apply:
                    keep.save(update_fields=['pcs', 'ct', 'gw'])
                    RawMaterialInventory.objects.filter(pk__in=[e.pk for e in extras]).delete()
                removed += len(extras)
            if not apply:
                transaction.set_rollback(True)

        mode = "APPLIED" if apply else "DRY-RUN (no writes)"
        self.stdout.write(self.style.SUCCESS(
            f"[{mode}] duplicate groups={len(groups)} extra rows removed={removed}"
        ))
        if not apply:
            self.stdout.write(self.style.WARNING("Dry run — re-run with --apply to persist."))
