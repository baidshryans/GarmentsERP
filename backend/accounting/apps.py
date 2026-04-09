from django.apps import AppConfig


class AccountingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounting'

    def ready(self):
        # Register pre_delete reversal signals for VoucherMain
        from . import signals  # noqa: F401
