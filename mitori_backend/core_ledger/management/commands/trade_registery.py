from django.core.management.base import BaseCommand
import redis
import time
import json
from django.db import transaction, utils
from core_ledger.models import LedgerTransaction , Portfolio, TransactionType,Status

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

                            try:
                                with transaction.atomic():

                                    LedgerTransaction.objects.create(portfolio = transaction_data['buyer_id'],
                                                                    transaction_type=TransactionType.BUY,
                                                                    amount=transaction_data['price'],
                                                                    quantity=transaction_data['quantity'],
                                                                    status=Status.COMPLETED,
                                                                    asset_symbol=transaction_data['ticker']
                                                                    )
                                    
                                    LedgerTransaction.objects.create(portfolio = transaction_data['seller_id'],
                                                                    transaction_type=TransactionType.SELL,
                                                                    amount=transaction_data['price'],
                                                                    quantity=transaction_data['quantity'],
                                                                    status=Status.COMPLETED,
                                                                    asset_symbol=transaction_data['ticker']
                                                                    )
                                    print(f"Order ${id} processed and added to database properly") 
                            except (utils.OperationalError, LedgerTransaction.DoesNotExist) as e:
                                self.stdout.write(self.style.ERROR("Settelment failed because {e}"))
                time.sleep(30)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"error : {e}"))
                time.sleep(5)


if __name__ == "__tade_registery__":
    Command()