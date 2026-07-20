from django.apps import AppConfig


class CoreLedgerConfig(AppConfig):
    name = 'core_ledger'

    def ready(self):
        import core_ledger.signals
