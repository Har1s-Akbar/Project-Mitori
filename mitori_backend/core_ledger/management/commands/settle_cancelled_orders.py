from django.core.management.base import BaseCommand
import redis
from core_ledger.models import CancelledOrders, TransactionType, Status
from decimal import Decimal 

class Command(BaseCommand):
    help = "Custom Daemon for settlement of cancelled orders"

    def handle(self, *args, **options):
        print("Reaper up and running")