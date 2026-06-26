from django.apps import AppConfig


class AGMConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agm'
    verbose_name = 'AGM'

    def ready(self):
        import agm.signals  # noqa
