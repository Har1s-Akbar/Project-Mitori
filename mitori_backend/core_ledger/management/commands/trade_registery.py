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

load_dotenv()

class Command(BaseCommand):
    help = "Custom Daemon for registering trades in postgres"

    def process_stream_message(self, message_id, data, redis_server, stream_name, group_name, multiplier):
        """
        Processes a single trade event from the Redis stream.
        Extracted for isolated unit testing.
        """
        transaction_data = json.loads(data['data'])  
        
        price_scaled_down = Decimal(str(transaction_data['price_setteled_at'])) / Decimal(str(multiplier))
        quantity_scaled_down = Decimal(str(transaction_data['quantity'])) / Decimal(str(multiplier))
        price_locked = Decimal(str(transaction_data['price_locked_by_user'])) / Decimal(str(multiplier))
        
        total = quantity_scaled_down * price_scaled_down
        self.stdout.write(self.style.SUCCESS(f"Received Trade with ID {message_id} | ticker {transaction_data['ticker']}"))  

        try:
            with transaction.atomic():
                # 1. THE IDEMPOTENCY GUARD
                if LedgerTransaction.objects.filter(stream_order_id=f'{message_id}_{TransactionType.SELL.value}').exists():
                    self.stdout.write(self.style.ERROR(f"Trade already settled, rejecting duplicate stream message with id {message_id}"))
                    redis_server.xack(stream_name, group_name, message_id)
                    return # Exit early, avoiding double settlement

                # 2. ACQUIRE LOCKS
                buyer_portfolio = Portfolio.objects.select_for_update().get(user_id=transaction_data['buyer_id'])
                seller_portfolio = Portfolio.objects.select_for_update().get(user_id=transaction_data['seller_id'])

                # 3. SETTLE CASH
                buyer_portfolio.cash_balance -= total
                buyer_portfolio.save()
                seller_portfolio.cash_balance += total
                seller_portfolio.save()

                # 4. SETTLE SELLER POSITIONS
                seller_position = Position.objects.select_for_update().get(portfolio=seller_portfolio, asset_symbol=transaction_data['ticker'])
                seller_position.quantity -= quantity_scaled_down
                seller_position.save()

                # 5. SETTLE BUYER POSITIONS
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
                
                # 6. CREATE AUDIT LOGS
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

                # 7. QUEUE POST-COMMIT HOOKS
                transaction.on_commit(lambda mid=message_id: redis_server.xack(stream_name, group_name, mid))
                transaction.on_commit(lambda d=transaction_data: settle_cache(d, redis_server))
                transaction.on_commit(lambda mid=message_id: self.stdout.write(self.style.SUCCESS(f"Order {mid} properly settled in database")))

        except IntegrityError as e:
            self.stdout.write(self.style.WARNING(f'Race condition averted for {message_id}'))
            redis_server.xack(stream_name, group_name, message_id)
        except (utils.OperationalError, LedgerTransaction.DoesNotExist) as e:
            self.stdout.write(self.style.ERROR(f"Settlement failed because {e}")) 

    def handle(self, *args, **options):
        REDIS_HOST = os.getenv("REDIS_HOST") or os.getenv("REDIS") or "localhost"
        REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
        redis_server = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        stream_name = "executed_trades_stream"
        group_name = "django_workers"
        worker_name = "django_database_worker"
        multiplier = settings.SYSTEM_PRECISION_MULTIPLIER

        try:
            redis_server.xgroup_create(name=stream_name, groupname=group_name, id=0, mkstream=True)
            self.stdout.write(self.style.SUCCESS(f"Created with consumer group {group_name}"))
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP Consumer Group name already exists" not in str(e):
                raise e
                
        self.stdout.write(self.style.SUCCESS(f"Starting Streaming consumer loop"))
        
        while True:
            try:
                executed_trades = redis_server.xreadgroup(groupname=group_name, consumername=worker_name, streams={stream_name: '>'}, block=3000)
                if executed_trades:
                    for stream_key, messages in executed_trades:
                        print(f"{stream_key} is stream key with message below")
                        for message_id, data in messages:
                            # The infinite loop now just delegates to the testable function
                            self.process_stream_message(message_id, data, redis_server, stream_name, group_name, multiplier)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"error : {e}"))
                time.sleep(5)