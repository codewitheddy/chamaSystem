from django.apps import AppConfig


class LedgerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ledger'
    verbose_name = 'Double-Entry Ledger'

    def ready(self):
        import ledger.signals  # noqa
