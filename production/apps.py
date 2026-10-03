from django.apps import AppConfig


class ProductionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "production"

    def ready(self):
        from masters.services import boms

        from .models import Lot

        # A BOM version that a lot was cut with is never edited in place: changes make a new version (BR-18).
        boms.register_usage_check(lambda version: Lot.objects.filter(bom_version=version).exists())
