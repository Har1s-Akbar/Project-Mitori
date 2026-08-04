import uuid
import json
from decimal import Decimal
from django.test import TransactionTestCase
from django.conf import settings

from core_ledger.models import Portfolio, CancelledOrders, TransactionType, Status
from django.contrib.auth import get_user_model
from core_ledger.management.commands.settle_cancelled_orders import Command 
import structlog

from core_ledger.test.test_services import test_redis_client 

user = get_user_model()
logging = structlog.getLogger(__name__)

class CancelledOrderDaemonIntegrationTest(TransactionTestCase):
    def setUp(self):
        test_redis_client.flushdb()

        self.trader = user.objects.create(id=uuid.uuid4(), email="trader_cancel@test.com", is_kyc_verified=True, date_of_birth="1999-09-08", full_name="tarder")
        self.trader_portfolio = Portfolio.objects.get(user=self.trader)

        self.multiplier = Decimal(settings.SYSTEM_PRECISION_MULTIPLIER)
        self.stream_name = "cancelled_order_stream"
        self.group_name = "django_cancel_workers"
        self.worker_name = "test_cancel_worker"

        self.raw_data = {
            'order_owner_id': str(self.trader.id),
            'price': int(Decimal("8.50") * self.multiplier),
            'number_of_shares': int(Decimal("100") * self.multiplier),
            'side': 'sell',
            'ticker': 'APP'
        }
        self.message_data = {'data': json.dumps(self.raw_data)}

        self.log = logging.bind(service="testing_canceelled_orders")

        self.cmd = Command()

    def test_happy_path_cancelled_order_logging(self):
        """
        1. Happy Path: A cancelled-order message in, one CancelledOrders row out 
        with the right ticker/side/status/price/quantity, message acked.
        """
        real_message_id = test_redis_client.xadd(self.stream_name, self.message_data)
        test_redis_client.xgroup_create(self.stream_name, self.group_name, id=0, mkstream=True)
        test_redis_client.xreadgroup(self.group_name, self.worker_name, {self.stream_name: ">"})

        self.cmd.process_cancelled_trades_stream(
            self.message_data, self.multiplier, real_message_id, 
            test_redis_client, self.stream_name, self.group_name, self.log
        )

        self.assertEqual(CancelledOrders.objects.count(), 1)
        logged_order = CancelledOrders.objects.first()
        
        self.assertEqual(logged_order.stream_order_id, real_message_id)
        self.assertEqual(logged_order.portfolio, self.trader_portfolio)
        self.assertEqual(logged_order.transaction_type, TransactionType.SELL)
        self.assertEqual(logged_order.status, Status.Cancelled)
        self.assertEqual(logged_order.price_locked_by_user, Decimal("8.50"))
        self.assertEqual(logged_order.quantity, Decimal("100.00"))
        self.assertEqual(logged_order.asset_symbol, 'APP')

        pending_info = test_redis_client.xpending(self.stream_name, self.group_name)
        self.assertEqual(pending_info['pending'], 0)

    def test_portfolio_does_not_exist_acks_message(self):
        """
        2. Portfolio.DoesNotExist path: Verify the existing except-branch actually 
        acks the message rather than leaving it stuck.
        """
        ghost_user_id = str(uuid.uuid4())
        ghost_data = self.raw_data.copy()
        ghost_data['order_owner_id'] = ghost_user_id
        ghost_message = {'data': json.dumps(ghost_data)}

        real_message_id = test_redis_client.xadd(self.stream_name, ghost_message)
        test_redis_client.xgroup_create(self.stream_name, self.group_name, id=0, mkstream=True)
        test_redis_client.xreadgroup(self.group_name, self.worker_name, {self.stream_name: ">"})

        self.cmd.process_cancelled_trades_stream(
            ghost_message, self.multiplier, real_message_id, 
            test_redis_client, self.stream_name, self.group_name, self.log
        )

        self.assertEqual(CancelledOrders.objects.count(), 0)

        pending_info = test_redis_client.xpending(self.stream_name, self.group_name)
        self.assertEqual(pending_info['pending'], 0)

    def test_idempotency_guard_blocks_duplicate_cancels(self):
        """
        3. Idempotency Guard Verification: Proves duplicates do not create 
        duplicate rows and are safely acked.
        """
        real_message_id = test_redis_client.xadd(self.stream_name, self.message_data)
        test_redis_client.xgroup_create(self.stream_name, self.group_name, id=0, mkstream=True)
        test_redis_client.xreadgroup(self.group_name, self.worker_name, {self.stream_name: ">"})

        CancelledOrders.objects.create(
            portfolio=self.trader_portfolio,
            stream_order_id=real_message_id,
            transaction_type=TransactionType.SELL,
            status=Status.Cancelled,
            price_locked_by_user=Decimal("8.50"),
            quantity=Decimal("100.00"),
            asset_symbol='APP'
        )

        self.cmd.process_cancelled_trades_stream(
            self.message_data, self.multiplier, real_message_id, 
            test_redis_client, self.stream_name, self.group_name, self.log
        )

        self.assertEqual(CancelledOrders.objects.count(), 1)

        pending_info = test_redis_client.xpending(self.stream_name, self.group_name)
        self.assertEqual(pending_info['pending'], 0)