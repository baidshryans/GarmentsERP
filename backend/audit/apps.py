from django.apps import AppConfig


class AuditConfig(AppConfig):
    name = 'audit'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'Audit Log'

    def ready(self):
        # Import inside ready() to avoid AppRegistryNotReady on import.
        from . import signals
        signals.connect_all()
