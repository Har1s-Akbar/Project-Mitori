from django.core.management.base import BaseCommand
import redis
import time
import json
from django.db import transaction, utils, IntegrityError
from core_ledger.models import LedgerTransaction, Portfolio, TransactionType, Status, Position
from decimal import Decimal
from core_ledger.services import settle_cache
import os
from dotenv import load_dotenv
from django.conf import settings
import structlog

load_dotenv()
logger = structlog.get_logger(__name__)

class Command(BaseCommand):
    help = "Custom Daemon for registering trades in postgres"

    def process_stream_message(self, message_id, data, redis_server, stream_name, group_name, multiplier, log):
        """
        Processes a single trade event from the Redis stream.
        Extracted for isolated unit testing.
        """
        transaction_data = json.loads(data['data'])  
        
        price_scaled_down = Decimal(str(transaction_data['price_setteled_at'])) / Decimal(str(multiplier))
        quantity_scaled_down = Decimal(str(transaction_data['quantity'])) / Decimal(str(multiplier))
        price_locked = Decimal(str(transaction_data['price_locked_by_user'])) / Decimal(str(multiplier))
        
        total = quantity_scaled_down * price_scaled_down
        log.info("settled_trade_received", message_id , transaction_data['ticker'])

        try:
            with transaction.atomic():
                if LedgerTransaction.objects.filter(stream_order_id=f'{message_id}_{TransactionType.SELL.value}').exists():
                    log.warning("duplication_rejection", {message_id}, reason="Trade already settled in the database , rejecting duplication.")
                    redis_server.xack(stream_name, group_name, message_id)
                    return 

                
                buyer_portfolio = Portfolio.objects.select_for_update().get(user_id=transaction_data['buyer_id'])
                seller_portfolio = Portfolio.objects.select_for_update().get(user_id=transaction_data['seller_id'])

            
                buyer_portfolio.cash_balance -= total
                buyer_portfolio.save()
                seller_portfolio.cash_balance += total
                seller_portfolio.save()

                
                seller_position = Position.objects.select_for_update().get(portfolio=seller_portfolio, asset_symbol=transaction_data['ticker'])
                seller_position.quantity -= quantity_scaled_down
                seller_position.save()

                
                try:
                    buyer_position = Position.objects.select_for_update().get(portfolio=buyer_portfolio, asset_symbol=transaction_data['ticker'])
                    buyer_position.average_entry_price = (buyer_position.average_entry_price * buyer_position.quantity + price_scaled_down * quantity_scaled_down) / (buyer_position.quantity + quantity_scaled_down)
                    buyer_position.quantity += quantity_scaled_down
                    buyer_position.save()
                except Position.DoesNotExist:
                    Position.objects.create(
                        portfolio=buyer_portfolio,
                        asset_symbol=transaction_data['ticker'],
                        quantity=quantity_scaled_down,
                        average_entry_price=price_scaled_down
                    )
                
                
                LedgerTransaction.objects.create(
                    portfolio=buyer_portfolio,
                    stream_order_id=f'{message_id}_{TransactionType.BUY.value}',
                    transaction_type=TransactionType.BUY,
                    price_setteled_at=price_scaled_down,
                    price_locked_by_user=price_locked,
                    quantity=quantity_scaled_down,
                    status=Status.COMPLETED,
                    asset_symbol=transaction_data['ticker']
                )
                
                LedgerTransaction.objects.create(
                    portfolio=seller_portfolio,
                    stream_order_id=f'{message_id}_{TransactionType.SELL.value}',
                    transaction_type=TransactionType.SELL,
                    price_setteled_at=price_scaled_down,
                    price_locked_by_user=price_locked,
                    quantity=quantity_scaled_down,
                    status=Status.COMPLETED,
                    asset_symbol=transaction_data['ticker']
                )

                
                transaction.on_commit(lambda mid=message_id: redis_server.xack(stream_name, group_name, mid))
                transaction.on_commit(lambda d=transaction_data: settle_cache(d, redis_server))
                transaction.on_commit(lambda mid=message_id: log.info("Trade_settled_successfully", message_id = message_id, execution_price=price_scaled_down))

        except IntegrityError as e:
            log.warning("Race_condition", message_id=message_id, reason=f"Race condition averted for {message_id}")
            redis_server.xack(stream_name, group_name, message_id)
        except (utils.OperationalError, LedgerTransaction.DoesNotExist) as e:
            log.error("Trade_settlement_error", error=e , error=f"Error occuered settlement failed {e}") 

    def handle(self, *args, **options):
        REDIS_HOST = os.getenv("REDIS_HOST") or os.getenv("REDIS") or "localhost"
        REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
        redis_server = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        stream_name = "executed_trades_stream"
        group_name = "django_workers"
        worker_name = "django_database_worker"
        multiplier = settings.SYSTEM_PRECISION_MULTIPLIER
        log = logger.bind(service="trade_registery")
        try:
            redis_server.xgroup_create(name=stream_name, groupname=group_name, id=0, mkstream=True)
            log.info("Stream_initialization", stream_name=stream_name, info=f'initialized {stream_name}')
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP Consumer Group name already exists" not in str(e):
                raise e
                
        log.info("Consumer_loop", info="Starting Streaming consumer loop")
        while True:
            try:
                executed_trades = redis_server.xreadgroup(groupname=group_name, consumername=worker_name, streams={stream_name: '>'}, block=3000)
                if executed_trades:
                    for stream_key, messages in executed_trades:
                        print(f"{stream_key} is stream key with message below")
                        for message_id, data in messages:
                            self.process_stream_message(message_id, data, redis_server, stream_name, group_name, multiplier,log)
            except Exception as e:
                log.error("Daemon_down", error_detail=e ,error=f'Daemon shutting down because of Error : {e}')
                time.sleep(2)