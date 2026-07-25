from django.core.management.base import BaseCommand
import redis
from core_ledger.models import CancelledOrders, TransactionType, Status
from decimal import Decimal 
import time

class Command(BaseCommand):
    help = "Custom Daemon for settlement of cancelled orders"

    def handle(self, *args, **options):
        redis_server = redis.Redis(host="localhost",port=6379, db=0, decode_responses=True)
        stream_name = "cancelled_order_stream"
        group_name = "django_cancel_workers"
        worker_name = "django_database_worker"

        try:
            redis_server.xgroup_create(stream_name,groupname=group_name, id=0, mkstream=True)
            self.stdout.write(self.style.SUCCESS(f"Stream Created {stream_name}"))
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP Consumer Group name already exists" not in str(e):
                raise e
        self.stdout.write(self.style.SUCCESS(f"Starting Stream Consumer Group"))

        while True:
            try:
                cancelled_trades = redis_server.xreadgroup(groupname=group_name,consumername=worker_name,streams={stream_name:'>'}, block=3000)
                if cancelled_trades:
                    for stream_key,message in cancelled_trades:
                        print(stream_key)
                time.sleep(2000)    
            except:
                pass