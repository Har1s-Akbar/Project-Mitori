from django.core.management.base import BaseCommand
import redis
from core_ledger.models import CancelledOrders, TransactionType, Status, Portfolio
from decimal import Decimal 
import time
import json
from django.db import transaction, utils
import os
from dotenv import load_dotenv
from django.conf import settings
from decimal import Decimal
import structlog

logger = structlog.get_logger(__name__)

load_dotenv()

class Command(BaseCommand):
    help = "Custom Daemon for settlement of cancelled orders"

    def process_cancelled_trades_stream(self, data, multiplier, stream_id,redis_server, stream_name, group_name, log):

        cancelled_order_data = json.loads(data['data'])
        scaled_down_price = Decimal(str(cancelled_order_data['price']))/multiplier
                            
        scaled_down_quantity = Decimal(str(cancelled_order_data['number_of_shares']))/multiplier
        order_side = cancelled_order_data['side']

        try:
            with transaction.atomic():

                if CancelledOrders.objects.filter(stream_order_id=stream_id).exists():
                    log.warning("duplication_rejection", message_id=stream_id, reason="Trade already settled in the database , rejecting duplication.")
                    redis_server.xack(stream_name, group_name, stream_id)
                    return

                portfolio_id_of_cancelled_order = Portfolio.objects.get(user_id = cancelled_order_data['order_owner_id'])
                CancelledOrders.objects.create(
                portfolio = portfolio_id_of_cancelled_order,
                stream_order_id=stream_id,
                transaction_type = TransactionType.SELL if order_side == "sell" else TransactionType.BUY,
                status = Status.Cancelled,
                price_locked_by_user = scaled_down_price,
                quantity = scaled_down_quantity,
                asset_symbol = cancelled_order_data['ticker']
                )

                transaction.on_commit(
                    lambda message_id = stream_id : redis_server.xack(stream_name, group_name, message_id)
                    )
                transaction.on_commit(
                    lambda message_id =stream_id :log.info("Cancelled_order_settled", info="Cnacelled order settled in the database")
                )
        except Portfolio.DoesNotExist:
            # self.stdout.write(self.style.ERROR("such portfolio id does not exist"))
            log.error("Portfolio_DoesNotExist", error='Portfolio does not exist')
            redis_server.xack(stream_name, group_name, stream_id)


    def handle(self, *args, **options):
        REDIS_HOST = os.getenv("REDIS_HOST") or os.getenv("REDIS") or "localhost"
        REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
        redis_server = redis.Redis(host=REDIS_HOST,port=REDIS_PORT, db=0, decode_responses=True)
        stream_name = "cancelled_order_stream"
        group_name = "django_cancel_workers"
        worker_name = "django_database_worker"
        multiplier = Decimal(settings.SYSTEM_PRECISION_MULTIPLIER)

        log = logger.bind(service="cancelled_orders")

        try:
            redis_server.xgroup_create(stream_name,groupname=group_name, id=0, mkstream=True)
            # self.stdout.write(self.style.SUCCESS(f"Stream Created {stream_name}"))
            log.info("Stream_initialization", stream_name=stream_name, info=f'initialized {stream_name}')
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP Consumer Group name already exists" not in str(e):
                raise e
        log.info("Consumer_loop", info="Starting Streaming consumer loop")

        while True:
            try:
                cancelled_trades = redis_server.xreadgroup(groupname=group_name,consumername=worker_name,streams={stream_name:'>'}, block=3000)
                if cancelled_trades:
                    for stream_name,message in cancelled_trades:
                        # print(stream_name, message)
                        for stream_id , data in message:
                            self.process_cancelled_trades_stream(data,multiplier,stream_id,redis_server,stream_name,group_name, log)
            except Exception as e:
                log.error("Daemon_down", error_detail=e ,error=f'Daemon shutting down because of Error : {e}')

if __name__ == "__settle_cancelled_orders__":
    Command()