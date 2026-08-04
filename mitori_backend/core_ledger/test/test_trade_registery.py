import uuid
import json
from decimal import Decimal
from django.test import TransactionTestCase
from django.conf import settings
from django.db import connection
import concurrent.futures
from unittest.mock import patch
from core_ledger.models import Portfolio, Position, LedgerTransaction, TransactionType, Status
from django.contrib.auth import get_user_model
from core_ledger.management.commands.trade_registery import Command
from core_ledger.services import redis_positions_portfolio_service
import structlog

from core_ledger.test.test_services import test_redis_client

logging = structlog.getLogger(__name__)
user = get_user_model()


class TradeRegistryDaemonIntegrationTest(TransactionTestCase):
    def setUp(self):
        test_redis_client.flushdb()

        # Creating the user automatically fires your routine to create the Portfolio with 10,000 cash
        self.buyer = user.objects.create(id=uuid.uuid4(), email="buyer@test.com", is_kyc_verified=True, date_of_birth="1999-09-08", full_name="tarder")
        self.seller = user.objects.create(id=uuid.uuid4(), email="seller@test.com", is_kyc_verified=True, date_of_birth="1999-09-08", full_name="tarder")

        self.buyer_portfolio = Portfolio.objects.get(user=self.buyer)
        self.seller_portfolio = Portfolio.objects.get(user=self.seller)

        self.seller_position = Position.objects.create(
            portfolio=self.seller_portfolio, 
            asset_symbol='APP', 
            quantity=Decimal('200.00'), 
            average_entry_price=Decimal('5.00')
        )

        self.multiplier = settings.SYSTEM_PRECISION_MULTIPLIER
        self.stream_name = "executed_trades_stream"
        self.group_name = "django_workers"
        self.worker_name = "test_worker"


        self.raw_data = {
            'ticker': 'APP',
            'seller_id': str(self.seller.id),
            'buyer_id': str(self.buyer.id),
            'quantity': int(Decimal("150") * self.multiplier),
            'price_locked_by_user': int(Decimal("8") * self.multiplier),
            'price_setteled_at': int(Decimal("6") * self.multiplier)
        }
        self.message_data = {'data': json.dumps(self.raw_data)}

        self.log = logging.bind(service="testing_trade_registery")

        self.cmd = Command()
    @patch('core_ledger.services.redis_client', test_redis_client)
    def test_happy_path_real_redis_integration(self):
        """
        End-to-end integration test with a real Redis database.
        Verifies Postgres, the Redis Cache, and the Redis Stream PEL state.
        """
        
        redis_positions_portfolio_service(self.buyer.id)
        redis_positions_portfolio_service(self.seller.id)

        total_lock_amount = int(Decimal("150") * Decimal("8") * self.multiplier)
        test_redis_client.hincrby(f'cache:portfolio:{self.buyer.id}', 'available_cash', -total_lock_amount)
        test_redis_client.hincrby(f'cache:portfolio:{self.buyer.id}', 'locked_balance', total_lock_amount)

        test_redis_client.hincrby(f'cache:positions:{self.seller.id}', 'APP', -int(Decimal("150") * self.multiplier))
        test_redis_client.hincrby(f'cache:positions:{self.seller.id}', 'locked_APP', int(Decimal("150") * self.multiplier))


        real_message_id = test_redis_client.xadd(self.stream_name, self.message_data)
        
        test_redis_client.xgroup_create(self.stream_name, self.group_name, id=0, mkstream=True)
        test_redis_client.xreadgroup(self.group_name, self.worker_name, {self.stream_name: ">"})

        self.cmd.process_stream_message(
            real_message_id, self.message_data, test_redis_client, 
            self.stream_name, self.group_name, self.multiplier, self.log
        )

        self.buyer_portfolio.refresh_from_db()
        self.assertEqual(self.buyer_portfolio.cash_balance, Decimal('9100.00')) 

        buyer_cash_cache = test_redis_client.hget(f'cache:portfolio:{self.buyer.id}', 'available_cash')
        safe_cash = Decimal(str(buyer_cash_cache)) / self.multiplier
        self.assertEqual(safe_cash, Decimal('9100.00'))

        buyer_locked_cache = test_redis_client.hget(f'cache:portfolio:{self.buyer.id}', 'locked_balance')
        safe_locked = Decimal(str(buyer_locked_cache or 0)) / self.multiplier
        self.assertEqual(safe_locked, Decimal('0.00'))

        pending_info = test_redis_client.xpending(self.stream_name, self.group_name)
        self.assertEqual(pending_info['pending'], 0)

    @patch('core_ledger.services.redis_client', test_redis_client)
    def test_idempotency_guard_with_real_redis(self):
        """
        Tests that a duplicate stream message bounces off the DB guard 
        and does NOT double-deduct from the real Redis cache.
        """
        redis_positions_portfolio_service(self.buyer.id)
        redis_positions_portfolio_service(self.seller.id)

        total_lock_amount = int(Decimal("150") * Decimal("8") * self.multiplier)
        test_redis_client.hincrby(f'cache:portfolio:{self.buyer.id}', 'available_cash', -total_lock_amount)
        test_redis_client.hincrby(f'cache:portfolio:{self.buyer.id}', 'locked_balance', total_lock_amount)

        test_redis_client.hincrby(f'cache:positions:{self.seller.id}', 'APP', -int(Decimal("150") * self.multiplier))
        test_redis_client.hincrby(f'cache:positions:{self.seller.id}', 'locked_APP', int(Decimal("150") * self.multiplier))

        real_message_id = test_redis_client.xadd(self.stream_name, self.message_data)
        test_redis_client.xgroup_create(self.stream_name, self.group_name, id=0, mkstream=True)
        test_redis_client.xreadgroup(self.group_name, self.worker_name, {self.stream_name: ">"})

        LedgerTransaction.objects.create(
            portfolio=self.seller_portfolio,
            stream_order_id=f'{real_message_id}_{TransactionType.SELL.value}',
            transaction_type=TransactionType.SELL,
            price_setteled_at=Decimal('6.00'),
            price_locked_by_user=Decimal('8.00'),
            quantity=Decimal('150.00'),
            status=Status.COMPLETED,
            asset_symbol='APP'
        )

        self.cmd.process_stream_message(
            real_message_id, self.message_data, test_redis_client, 
            self.stream_name, self.group_name, self.multiplier, self.log
        )

        self.assertEqual(LedgerTransaction.objects.count(), 1)
        self.buyer_portfolio.refresh_from_db()
        self.assertEqual(self.buyer_portfolio.cash_balance, Decimal('10000.00')) 

        buyer_cash_cache = test_redis_client.hget(f'cache:portfolio:{self.buyer.id}', 'available_cash')
        safe_cash = Decimal(str(buyer_cash_cache)) / self.multiplier
        self.assertEqual(safe_cash, Decimal('8800.00')) # Only the setup lock remains

        pending_info = test_redis_client.xpending(self.stream_name, self.group_name)
        self.assertEqual(pending_info['pending'], 0)


    @patch('core_ledger.services.redis_client', test_redis_client)
    def test_database_row_locking_concurrency_with_real_redis(self):
        """
        STRETCH GOAL: Concurrency Test
        Simulates two threads processing partial fills for the SAME buyer 
        at the exact same microsecond.
        Proves `select_for_update` prevents the "lost update" anomaly.
        """
        redis_positions_portfolio_service(self.buyer.id)
        redis_positions_portfolio_service(self.seller.id)
        
        # We are simulating a 150 share order that got split into two partial fills.
        total_lock_amount = int(Decimal("150") * Decimal("8") * self.multiplier)
        test_redis_client.hincrby(f'cache:portfolio:{self.buyer.id}', 'available_cash', -total_lock_amount)
        test_redis_client.hincrby(f'cache:portfolio:{self.buyer.id}', 'locked_balance', total_lock_amount)
        test_redis_client.hincrby(f'cache:positions:{self.seller.id}', 'APP', -int(Decimal("150") * self.multiplier))
        test_redis_client.hincrby(f'cache:positions:{self.seller.id}', 'locked_APP', int(Decimal("150") * self.multiplier))

        # 3. SETUP TRADE 1 (100 shares @ $6 = $600 cost)
        message_1 = "1626000000001-0"
        data_1 = {'data': json.dumps({
            'ticker': 'APP', 'seller_id': str(self.seller.id), 'buyer_id': str(self.buyer.id),
            'quantity': int(Decimal("100") * self.multiplier),
            'price_locked_by_user': int(Decimal("8") * self.multiplier),
            'price_setteled_at': int(Decimal("6") * self.multiplier)
        })}

        # 4. SETUP TRADE 2 (50 shares @ $6 = $300 cost)
        message_2 = "1626000000002-0"
        data_2 = {'data': json.dumps({
            'ticker': 'APP', 'seller_id': str(self.seller.id), 'buyer_id': str(self.buyer.id),
            'quantity': int(Decimal("50") * self.multiplier),
            'price_locked_by_user': int(Decimal("8") * self.multiplier),
            'price_setteled_at': int(Decimal("6") * self.multiplier)
        })}

        # 5. THE THREAD TARGET
        def run_trade(message_id, data):
            # Crucial for testing: Force the Python thread to get its own DB connection
            # If they share a connection, Django queues them naturally and ruins the test.
            connection.close() 
            self.cmd.process_stream_message(
                message_id, data, test_redis_client, 
                self.stream_name, self.group_name, self.multiplier, self.log
            )
            connection.close()

        # 6. FIRE BOTH CONCURRENTLY
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(run_trade, message_1, data_1)
            future2 = executor.submit(run_trade, message_2, data_2)
            
            # Wait for both threads to finish execution
            future1.result()
            future2.result()

        # 7. ASSERT: Did select_for_update() work?
        self.buyer_portfolio.refresh_from_db()
        
        # If the locks FAILED, one thread would overwrite the other.
        # The balance would be either 9400 (Trade 1 won) or 9700 (Trade 2 won).
        # If the locks SUCCEEDED, they serialize, and deduct $600 + $300 cleanly.
        self.assertEqual(self.buyer_portfolio.cash_balance, Decimal('9100.00'))