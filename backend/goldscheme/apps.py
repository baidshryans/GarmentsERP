from django.apps import AppConfig


class GoldschemeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'goldscheme'

    def ready(self):
        import goldscheme.signals
        return super().ready()
