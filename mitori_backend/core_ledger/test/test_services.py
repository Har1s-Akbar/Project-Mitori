import redis
from django.test import TransactionTestCase
from unittest.mock import patch
from core_ledger.services import redis_positions_portfolio_service
from django.contrib.auth import get_user_model
import uuid
from core_ledger.models import Portfolio,Position,LedgerTransaction
from django.utils import timezone

user = get_user_model()

test_redis_client = redis.Redis(
    host='redis',
    port=6379,
    db=1,
    decode_responses=True
)

class redis_positions_portfolio_test(TransactionTestCase):
    def setUp(self):
        test_redis_client.flushdb()

        self.trader =  user.objects.create(id=uuid.uuid4(), email="trader@gmail.com", date_of_birth="1999-09-08", full_name="tarder",
                                              is_kyc_verified="True")
        # self.portfolio_of_trader = Portfolio.objects.create(user=self.trader,cash_balance=10000.00)
        # position_of_trader = Position.objects.create(portfolio=portfolio_of_trader, asset_symbol='APP', quantity=1000.00)
        
                
    @patch('core_ledger.services.redis_client',test_redis_client)
    def test_cache_initialization_redis_for_no_position(self):
        redis_positions_portfolio_service(str(self.trader.id))

        portfolio_key = f'cache:portfolio:{self.trader.id}'
        cached_cash = test_redis_client.hget(portfolio_key,'available_cash')
        cached_locked_cash = test_redis_client.hget(portfolio_key,'locked_balance')
        self.assertEqual(float(cached_cash),10000.00)
        self.assertEqual(float(cached_locked_cash),0.00)

        positions_key = f'cache:positions:{self.trader.id}'
        positions_exits = test_redis_client.exists(positions_key)

        self.assertEqual(positions_exits,0)

    @patch('core_ledger.services.redis_client',test_redis_client)
    def test_cache_initialization_redis_with__positions(self):
        get_trader_instance = Portfolio.objects.get(user_id=self.trader)
        Position.objects.create(portfolio=get_trader_instance,asset_symbol='APP',quantity=130,average_entry_price=160.00)
        Position.objects.create(portfolio=get_trader_instance,asset_symbol='TSLA',quantity=50,average_entry_price=90.00)

        redis_positions_portfolio_service(str(self.trader.id))

        postions_key = f'cache:positions:{self.trader.id}'

        portfolio_key = f'cache:portfolio:{self.trader.id}'

        cached_cash = test_redis_client.hget(portfolio_key,'available_cash')
        cached_locked_cash = test_redis_client.hget(portfolio_key,'locked_balance')

        self.assertEqual(float(cached_locked_cash),0.00)
        self.assertEqual(float(cached_cash),10000.00)

        cached_position_APP = test_redis_client.hget(postions_key,'APP')
        cached_position_TSLA = test_redis_client.hget(postions_key,'TSLA')

        self.assertEqual(float(cached_position_APP),130.00)
        self.assertEqual(float(cached_position_TSLA),50.00)

    @patch('core_ledger.services.redis_client',test_redis_client)
    def test_cache_initialization_for_relogin(self):
        redis_positions_portfolio_service(self.trader.id)

        postions_key = f'cache:positions:{self.trader.id}'

        portfolio_key = f'cache:portfolio:{self.trader.id}'


        # when the user buys the cash in portfolio is locked we are locking the funds replicating that
        locking_portfolio_cash_in_cache= test_redis_client.hincrbyfloat(portfolio_key, 'available_cash',-200)
        adding_to_locked_portfolio_cache= test_redis_client.hincrbyfloat(portfolio_key,'locked_balance',200)

        getting_cache_cash = test_redis_client.hget(portfolio_key,'available_cash')
        getting_locked_cache_cash = test_redis_client.hget(portfolio_key,'locked_balance')
        self.assertEqual(float(getting_cache_cash),9800)
        self.assertEqual(float(getting_locked_cache_cash),200)

        redis_positions_portfolio_service(self.trader.id)

        getting_cache_cash_after_relogin = test_redis_client.hget(portfolio_key,'available_cash')
        getting_locked_cash_after_relogin = test_redis_client.hget(portfolio_key,'locked_balance')

        self.assertEqual(float(getting_cache_cash_after_relogin),9800)
        self.assertEqual(float(getting_locked_cash_after_relogin),200)

        #This test fails  it  shows that the architecture can not support relogin cache hydration
        #If a user has an ongoing trade and for any reason he refreshes his/her browser or relogs in
        #That trade willl exist in the system but the cached funds/funds will be reinitialized giving him the funds that are available in the postgres
        #creating a really catastrophic bug more will be in readme