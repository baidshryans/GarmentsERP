from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import models, transaction

from mastersconfig.models import RetailMaster


def _model_has_retail_fk(model):
    for f in model._meta.get_fields():
        if (
            isinstance(f, models.ForeignKey)
            and f.name == 'retail'
            and f.related_model is RetailMaster
        ):
            return True
    return False


def _parent_fks_with_retail(model):
    out = []
    for f in model._meta.get_fields():
        if not isinstance(f, models.ForeignKey):
            continue
        if f.name == 'retail':
            continue
        target = f.related_model
        if target is None or not _model_has_retail_fk(target):
            continue
        out.append(f)
    return out


class Command(BaseCommand):
    help = (
        "Backfill the `retail` FK on rows where it is null, by copying from "
        "any parent FK whose target also carries a retail FK. Safe to re-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be updated without writing.',
        )
        parser.add_argument(
            '--app',
            default=None,
            help='Limit to a single app label (e.g. manufacturing).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        app_filter = options['app']

        # Multi-pass: a child may only become fillable after its parent is
        # fixed in an earlier pass. Iterate until a pass yields zero fixes.
        grand_fixed = 0
        for pass_no in range(1, 6):
            pass_fixed, pass_skipped, pass_models = self._run_pass(dry_run, app_filter)
            self.stdout.write(self.style.NOTICE(
                f"\nPass {pass_no}: models_touched={pass_models} fixed={pass_fixed} skipped={pass_skipped}"
            ))
            grand_fixed += pass_fixed
            if pass_fixed == 0 or dry_run:
                break

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. total_fixed={grand_fixed}" + (" (dry-run)" if dry_run else "")
        ))

    def _run_pass(self, dry_run, app_filter):
        total_fixed = 0
        total_skipped = 0
        total_models = 0

        for model in apps.get_models():
            if app_filter and model._meta.app_label != app_filter:
                continue
            if not _model_has_retail_fk(model):
                continue
            parent_fields = _parent_fks_with_retail(model)
            if not parent_fields:
                continue

            qs = model._default_manager.filter(retail__isnull=True)
            count = qs.count()
            if count == 0:
                continue

            total_models += 1
            self.stdout.write(
                f"\n{model._meta.app_label}.{model._meta.model_name}: "
                f"{count} row(s) with null retail; parents={[f.name for f in parent_fields]}"
            )

            fixed_for_model = 0
            skipped_for_model = 0
            with transaction.atomic():
                for obj in qs.only('pk', *(f.attname for f in parent_fields)):
                    inferred = None
                    for field in parent_fields:
                        parent_id = getattr(obj, field.attname, None)
                        if not parent_id:
                            continue
                        parent_retail_id = (
                            field.related_model._default_manager
                            .filter(pk=parent_id)
                            .values_list('retail_id', flat=True)
                            .first()
                        )
                        if parent_retail_id:
                            inferred = parent_retail_id
                            break
                    if inferred is None:
                        skipped_for_model += 1
                        continue
                    if not dry_run:
                        model._default_manager.filter(pk=obj.pk).update(retail_id=inferred)
                    fixed_for_model += 1

            total_fixed += fixed_for_model
            total_skipped += skipped_for_model
            self.stdout.write(
                f"  fixed={fixed_for_model} skipped={skipped_for_model}"
                + (" (dry-run)" if dry_run else "")
            )

        return total_fixed, total_skipped, total_models
