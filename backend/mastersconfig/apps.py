from django.apps import AppConfig
import os


class MastersconfigConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mastersconfig'

    def ready(self):
        import mastersconfig.signals

        # Enable SQLite WAL mode on every new connection.
        # WAL allows concurrent readers + one writer, eliminating most
        # "database is locked" errors that occur with the dev-server autoreloader
        # (which runs two processes sharing the same db.sqlite3 file).
        from django.db.backends.signals import connection_created

        def _set_wal(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                connection.cursor().execute('PRAGMA journal_mode=WAL;')
                connection.cursor().execute('PRAGMA synchronous=NORMAL;')

        connection_created.connect(_set_wal)

        # CRM automation is driven by the `run_due_crm` management command
        # (scheduled by the OS every minute) which enqueues send tasks onto the
        # django-tasks worker. The old in-process APScheduler thread was removed.
