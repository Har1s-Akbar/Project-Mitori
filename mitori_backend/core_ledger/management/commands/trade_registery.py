from django.core.management.base import BaseCommand
import redis
import time
import json
from django.db import transaction
from core_ledger.models import LedgerTransaction , Portfolio, TransactionType

class Command(BaseCommand):
    help = "Custom Daemon for registering trades in postgres"

    def handle(self, *args,**options):

        redis_server = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        stream_name = "executed_trades_stream"
        group_name = "django_workers"
        worker_name = "django_database_worker"
        try:
            redis_server.xgroup_create(name=stream_name,groupname=group_name,id=0,mkstream=False)
            self.stdout(self.style.SUCCESS(f"Created with consumer group {group_name}"))
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP Consumer Group name already exists" not in str(e):
                raise e
        self.stdout.write(self.style.SUCCESS(f"Starting Streaming consumer loop"))
        while True:
            try:
                executed_trades = redis_server.xreadgroup(groupname=group_name,consumername=worker_name, streams={stream_name:'0'},block=3000)
                if executed_trades:
                    for stream_key,messages in executed_trades:
                        print(f"{stream_key} is stream key with message below")
                        for id , data in messages:
                            transaction_data = json.loads(data['data'])    
                            # print(f"{ticker} with quantity {data['data']['quantity']} with price {data['data']['price']}")
                            self.stdout.write(self.style.SUCCESS(f"Received Trade with ID {id} | ticker {transaction_data['ticker']}"))  

                # @transaction.atomic
                # def updateLedger(self):
                #     LedgerTransaction.portfolio = transaction_data.portfolio


                time.sleep(30)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"error : {e}"))
                time.sleep(5)


if __name__ == "__tade_registery__":
    Command()