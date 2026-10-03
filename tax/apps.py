from django.apps import AppConfig


class TaxConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tax"

    def ready(self):
        from . import seeding

        seeding.register()
        seeding.register_templates()
