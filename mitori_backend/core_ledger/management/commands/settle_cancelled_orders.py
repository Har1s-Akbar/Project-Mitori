from django.core.management.base import BaseCommand
import redis
from core_ledger.models import CancelledOrders, TransactionType, Status, Portfolio
from decimal import Decimal 
import time
import json
from django.db import transaction, utils

class Command(BaseCommand):
    help = "Custom Daemon for settlement of cancelled orders"

    def handle(self, *args, **options):
        redis_server = redis.Redis(host='redis',port=6379, db=0, decode_responses=True)
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
                    for stream_name,message in cancelled_trades:
                        # print(stream_name, message)
                        for stream_id , data in message:
                            cancelled_order_data = json.loads(data['data'])
                            price_str = str(cancelled_order_data['price'])
                            safe_price = Decimal(price_str)
                            quantity_str = str(cancelled_order_data['number_of_shares'])
                            safe_quantity = Decimal(quantity_str)
                            order_side = cancelled_order_data['side']

                            try:
                                with transaction.atomic():
                                    portfolio_id_of_cancelled_order = Portfolio.objects.get(user_id = cancelled_order_data['order_owner_id'])
                                    CancelledOrders.objects.create(
                                        portfolio = portfolio_id_of_cancelled_order,
                                        transaction_type = TransactionType.SELL if order_side == "sell" else TransactionType.BUY,
                                        status = Status.Cancelled,
                                        price_locked_by_user = safe_price,
                                        quantity = safe_quantity,
                                        asset_symbol = cancelled_order_data['ticker']
                                    )

                                    transaction.on_commit(
                                        lambda message_id = stream_id : redis_server.xack(stream_name, group_name, message_id)
                                    )
                            except Portfolio.DoesNotExist:
                                self.stdout.write(self.style.ERROR("such portfolio id does not exist"))
                                redis_server.xack(stream_name, group_name, stream_id)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'an error {e} occuered'))


if __name__ == "__settle_cancelled_orders__":
    Command()