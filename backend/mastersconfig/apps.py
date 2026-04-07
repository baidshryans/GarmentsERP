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

        # Start CRM scheduler only in the main process (not in migrations / management commands)
        # RUN_MAIN is set by Django's autoreloader for the child process only.
        # We also guard against management commands (e.g. migrate, shell).
        import sys
        is_manage_py = any(arg in sys.argv for arg in ('migrate', 'makemigrations', 'shell', 'collectstatic', 'createsuperuser'))
        is_main_process = os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('RUN_MAIN')
        if not is_manage_py and is_main_process:
            from mastersconfig import scheduler
            scheduler.start()
