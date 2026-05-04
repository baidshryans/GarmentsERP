from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'common'

    def ready(self):
        # Wire the signal handler that stamps history_retail and
        # history_transaction_id onto every historical record at creation time.
        from . import signals  # noqa: F401
