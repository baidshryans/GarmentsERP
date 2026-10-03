from django.apps import AppConfig


class MastersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "masters"

    def ready(self):
        from . import seeding

        seeding.register()
