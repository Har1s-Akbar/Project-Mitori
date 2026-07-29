import redis
from django.test import TransactionTestCase
from unittest.mock import patch
from core_ledger.services import redis_positions_portfolio_service, settle_cache
from django.contrib.auth import get_user_model
import uuid
from core_ledger.models import Portfolio,Position,LedgerTransaction
from django.utils import timezone
from decimal import Decimal
from django.conf import settings

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

        self.multiplier = Decimal(settings.SYSTEM_PRECISION_MULTIPLIER)
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

        safe_cached_cash = Decimal(str(cached_cash))/self.multiplier

        self.assertEqual(safe_cached_cash,10000.00000)
        self.assertEqual(int(cached_locked_cash),0)

        positions_key = f'cache:positions:{self.trader.id}'
        positions_exits = test_redis_client.exists(positions_key)

        self.assertEqual(positions_exits,0)

    @patch('core_ledger.services.redis_client',test_redis_client)
    def test_cache_initialization_redis_with_positions(self):
        get_trader_instance = Portfolio.objects.get(user_id=self.trader)
        Position.objects.create(portfolio=get_trader_instance,asset_symbol='APP',quantity=130,average_entry_price=160.00)
        Position.objects.create(portfolio=get_trader_instance,asset_symbol='TSLA',quantity=50,average_entry_price=90.00)

        redis_positions_portfolio_service(str(self.trader.id))

        postions_key = f'cache:positions:{self.trader.id}'

        portfolio_key = f'cache:portfolio:{self.trader.id}'

        cached_cash = test_redis_client.hget(portfolio_key,'available_cash')
        cached_locked_cash = test_redis_client.hget(portfolio_key,'locked_balance')

        safe_cached_cash = Decimal(str(cached_cash))/self.multiplier

        self.assertEqual(safe_cached_cash,10000)
        self.assertEqual(int(cached_locked_cash),0)

        cached_position_APP = test_redis_client.hget(postions_key,'APP')
        cached_position_TSLA = test_redis_client.hget(postions_key,'TSLA')

        safe_cache_position_APP = Decimal(str(cached_position_APP))/self.multiplier
        safe_cache_position_TSLA = Decimal(str(cached_position_TSLA))/self.multiplier

        self.assertEqual(safe_cache_position_APP,130.00)
        self.assertEqual(safe_cache_position_TSLA,50.00)

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

    @patch('core_ledger.services.redis_client',test_redis_client)
    def test_decimal_precision_in_database(self):

        redis_positions_portfolio_service(self.trader.id)

        portfolio_key = f'cache:portfolio:{self.trader.id}'
        test_redis_client.hset(portfolio_key,'available_cash',0.0)

        test_redis_client.hincrbyfloat(portfolio_key, 'available_cash',0.2)
        test_redis_client.hincrbyfloat(portfolio_key,'available_cash',0.1)

        get_cash = test_redis_client.hget(portfolio_key,'available_cash')
        self.assertEqual(Decimal(get_cash), Decimal('0.3'))



class redis_cache_setlement_test(TransactionTestCase):
    def setUp(self):
        test_redis_client.flushdb()

        self.trader = user.objects.create(id=uuid.uuid4(), email="trader@gmail.com", date_of_birth="1999-09-08", full_name="tarder",
                                              is_kyc_verified="True")
        self.trader1 = user.objects.create(id=uuid.uuid4(),email="trader1@gmail.com", date_of_birth="1999-09-08", full_name="tarder",
                                              is_kyc_verified="True")

        self.portfolio_of_trader = Portfolio.objects.get(user=self.trader.id)
        self.portfolio_of_trader1 = Portfolio.objects.get(user=self.trader1.id)

        self.traderCacheKey_portfolio = f'cache:portfolio:{self.trader.id}'
        self.traderCacheKey_positions = f'cache:positions:{self.trader.id}'

        self.trader1CacheKey_portfolio = f'cache:portfolio:{self.trader1.id}'
        self.trader1CacheKey_positions = f'cache:positions:{self.trader1.id}'

        Position.objects.create(portfolio=self.portfolio_of_trader, asset_symbol='APP',quantity=Decimal('200.000000'), average_entry_price=Decimal('200.000000'))
        Position.objects.create(portfolio=self.portfolio_of_trader1, asset_symbol='TSLA',quantity=Decimal('200.000000'), average_entry_price=Decimal('200.000000'))

        self.multiplier = Decimal(settings.SYSTEM_PRECISION_MULTIPLIER)
        safe_quantity = Decimal("150.00000000")  * self.multiplier
        safe_price_locked_by_user = Decimal("8.00000000") * self.multiplier
        safe_price_settled_at = Decimal("6.00000000") * self.multiplier

        self.transaction_data = {
            'ticker':'APP',
            'seller_id': str(self.trader),
            'buyer_id':str(self.trader1),
            'quantity':int(safe_quantity),
            'price_locked_by_user':int(safe_price_locked_by_user),
            'price_setteled_at':int(safe_price_settled_at)
        }

    @patch('core_ledger.services.redis_client',test_redis_client)
    def test_proper_cache_for_buyer(self):
        redis_positions_portfolio_service(self.trader.id)
        redis_positions_portfolio_service(self.trader1.id)

        total = (self.transaction_data['quantity']/self.multiplier)  * self.transaction_data['price_locked_by_user']/self.multiplier

        update_portfolio_value ={
            'available_cash': int((self.portfolio_of_trader.cash_balance -total)*self.multiplier),
            'locked_balance': int(total * self.multiplier)
        }

        test_redis_client.hset(self.trader1CacheKey_portfolio, mapping=update_portfolio_value)

        settle_cache(self.transaction_data,test_redis_client)

        get_buy_trader_cache_shares = test_redis_client.hget(self.trader1CacheKey_portfolio,'available_cash')
        get_buy_trader_cache_locked_shares = test_redis_client.hget(self.trader1CacheKey_portfolio  ,'locked_balance')

        safe_get_buy_trader_cache_shares = Decimal(str(get_buy_trader_cache_shares))/self.multiplier
        safe_get_buy_trader_locked_shares = Decimal(str(get_buy_trader_cache_locked_shares))/self.multiplier

        self.assertEqual(safe_get_buy_trader_cache_shares, Decimal(str(9100)))
        self.assertEqual(safe_get_buy_trader_locked_shares, Decimal(str(900)))