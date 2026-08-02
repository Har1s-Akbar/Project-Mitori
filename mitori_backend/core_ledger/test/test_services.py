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
import os
from dotenv import load_dotenv

load_dotenv()
user = get_user_model()

REDIS_HOST = os.getenv("REDIS_HOST") or os.getenv("REDIS") or "localhost"
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

test_redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=1,
    decode_responses=True
)

class redis_positions_portfolio_test(TransactionTestCase):
    def setUp(self):
        test_redis_client.flushdb()

        self.multiplier = Decimal(settings.SYSTEM_PRECISION_MULTIPLIER)
        self.trader =  user.objects.create(id=uuid.uuid4(), email="trader@gmail.com", date_of_birth="1999-09-08", full_name="tarder",
                                              is_kyc_verified="True")
        
                
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
        locking_portfolio_cash_in_cache= test_redis_client.hincrby(portfolio_key, 'available_cash',-int(Decimal("200")*self.multiplier))
        adding_to_locked_portfolio_cache= test_redis_client.hincrby(portfolio_key,'locked_balance',int(Decimal("200")*self.multiplier))

        getting_cache_cash = test_redis_client.hget(portfolio_key,'available_cash')
        getting_locked_cache_cash = test_redis_client.hget(portfolio_key,'locked_balance')
        self.assertEqual(Decimal(str(getting_cache_cash)),Decimal(9800)*self.multiplier)
        self.assertEqual(Decimal((getting_locked_cache_cash)),Decimal(200)*self.multiplier)

        redis_positions_portfolio_service(self.trader.id)

        getting_cache_cash_after_relogin = test_redis_client.hget(portfolio_key,'available_cash')
        getting_locked_cash_after_relogin = test_redis_client.hget(portfolio_key,'locked_balance')

        self.assertEqual(int(getting_cache_cash_after_relogin), int(Decimal("9800") * self.multiplier))
        self.assertEqual(int(getting_locked_cash_after_relogin), int(Decimal("200") * self.multiplier))

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
            'seller_id': str(self.trader.id),
            'buyer_id':str(self.trader1.id),
            'quantity':int(safe_quantity),
            'price_locked_by_user':int(safe_price_locked_by_user),
            'price_setteled_at':int(safe_price_settled_at)
        }

        #This order is used for the test where price is equal (settled price and locked_price rest is same)
        safe_price_settled_at_for_equal_price_order = Decimal("8.00000000") * self.multiplier
        self.transaction_data_price_equal = {
            'ticker':'APP',
            'seller_id': str(self.trader.id),
            'buyer_id':str(self.trader1.id),
            'quantity':int(safe_quantity),
            'price_locked_by_user':int(safe_price_locked_by_user),
            'price_setteled_at':int(safe_price_settled_at_for_equal_price_order)
        }

    @patch('core_ledger.services.redis_client',test_redis_client)
    def test_proper_cache_for_buyer_for_price_settled_greater_than_locked(self):
        redis_positions_portfolio_service(self.trader.id)
        redis_positions_portfolio_service(self.trader1.id)

        total = (self.transaction_data['quantity']/self.multiplier)  * self.transaction_data['price_locked_by_user']/self.multiplier

        update_portfolio_value ={
            'available_cash': int((self.portfolio_of_trader1.cash_balance -total)*self.multiplier),
            'locked_balance': int(total * self.multiplier)
        }

        total_shares_in_portfolio = Position.objects.get(portfolio=self.portfolio_of_trader, asset_symbol='APP')
        safe_total_shares_in_portfolio = int(total_shares_in_portfolio.quantity * self.multiplier)
        update_position_value = {
            'APP': safe_total_shares_in_portfolio-self.transaction_data['quantity'],
            'locked_APP':self.transaction_data['quantity']
        }
        test_redis_client.hset(self.traderCacheKey_positions, mapping=update_position_value)
        test_redis_client.hset(self.trader1CacheKey_portfolio, mapping=update_portfolio_value)

        settle_cache(self.transaction_data,test_redis_client)

        #Buyer portion testing the buyer portfolio and positions
        get_buy_trader_cache_portfolio = test_redis_client.hget(self.trader1CacheKey_portfolio,'available_cash')
        get_buy_trader_cache_locked_portfolio = test_redis_client.hget(self.trader1CacheKey_portfolio  ,'locked_balance')

        get_buy_trader_cache_positions = test_redis_client.hget(self.trader1CacheKey_positions,'APP')
        get_buy_trader_cache_locked_positions = test_redis_client.hget(self.trader1CacheKey_positions,'locked_APP')

        safe_get_buy_trader_cache_positions = Decimal(str(get_buy_trader_cache_positions))/self.multiplier

        safe_get_buy_trader_cache_locked_positions = Decimal(str(get_buy_trader_cache_locked_positions or 0))/self.multiplier

        safe_get_buy_trader_cache_portfolio = Decimal(str(get_buy_trader_cache_portfolio))/self.multiplier
        safe_get_buy_trader_locked_portfolio = Decimal(str(get_buy_trader_cache_locked_portfolio))/self.multiplier

        self.assertEqual(safe_get_buy_trader_cache_portfolio, Decimal(str(9100)))
        self.assertEqual(safe_get_buy_trader_locked_portfolio, Decimal(str(0)))

        self.assertEqual(safe_get_buy_trader_cache_positions,Decimal(str(150)))
        self.assertEqual(safe_get_buy_trader_cache_locked_positions,Decimal(str(0)))

        #Testing Seller portfolio and seller positions
        get_seller_cache_position = test_redis_client.hget(self.traderCacheKey_positions, 'APP')
        get_seller_cache_locked_position = test_redis_client.hget(self.traderCacheKey_positions, 'locked_APP')

        get_seller_cache_portfolio = test_redis_client.hget(self.traderCacheKey_portfolio, 'available_cash')
        get_seller_cache_locked_portfolio = test_redis_client.hget(self.traderCacheKey_portfolio,'locked_balance')

        safe_get_seller_cache_position = Decimal(str(get_seller_cache_position))/self.multiplier
        safe_get_seller_cache_locked_position = Decimal(str(get_seller_cache_locked_position))/self.multiplier

        safe_get_seller_cache_portfolio = Decimal(str(get_seller_cache_portfolio))/self.multiplier
        safe_get_seller_cache_locked_portfolio = Decimal(str(get_seller_cache_locked_portfolio or 0))/self.multiplier

        self.assertEqual(safe_get_seller_cache_position,Decimal(str(50)))
        self.assertEqual(safe_get_seller_cache_locked_position,0)

        self.assertEqual(safe_get_seller_cache_portfolio,Decimal(str(10900)))
        self.assertEqual(safe_get_seller_cache_locked_portfolio, Decimal(str(0)))

    @patch('core_ledger.services.redis_client',test_redis_client)
    def test_settlement_for_price_equals_locked(self):
        redis_positions_portfolio_service(self.trader.id)
        redis_positions_portfolio_service(self.trader.id)

        total = (self.transaction_data_price_equal['quantity']/self.multiplier)  * self.transaction_data_price_equal['price_locked_by_user']/self.multiplier

        update_portfolio_value ={
            'available_cash': int((self.portfolio_of_trader1.cash_balance -total)*self.multiplier),
            'locked_balance': int(total * self.multiplier)
        }

        total_shares_in_portfolio = Position.objects.get(portfolio=self.portfolio_of_trader, asset_symbol='APP')
        safe_total_shares_in_portfolio = int(total_shares_in_portfolio.quantity * self.multiplier)
        update_position_value = {
            'APP': safe_total_shares_in_portfolio-self.transaction_data_price_equal['quantity'],
            'locked_APP':self.transaction_data_price_equal['quantity']
        }
        test_redis_client.hset(self.traderCacheKey_positions, mapping=update_position_value)
        test_redis_client.hset(self.trader1CacheKey_portfolio, mapping=update_portfolio_value)

        settle_cache(self.transaction_data_price_equal,test_redis_client)

        #Buyer portion testing the buyer portfolio and positions
        get_buy_trader_cache_portfolio = test_redis_client.hget(self.trader1CacheKey_portfolio,'available_cash')
        get_buy_trader_cache_locked_portfolio = test_redis_client.hget(self.trader1CacheKey_portfolio  ,'locked_balance')

        get_buy_trader_cache_positions = test_redis_client.hget(self.trader1CacheKey_positions,'APP')
        get_buy_trader_cache_locked_positions = test_redis_client.hget(self.trader1CacheKey_positions,'locked_APP')

        safe_get_buy_trader_cache_positions = Decimal(str(get_buy_trader_cache_positions))/self.multiplier

        safe_get_buy_trader_cache_locked_positions = Decimal(str(get_buy_trader_cache_locked_positions or 0))/self.multiplier

        safe_get_buy_trader_cache_portfolio = Decimal(str(get_buy_trader_cache_portfolio))/self.multiplier
        safe_get_buy_trader_locked_portfolio = Decimal(str(get_buy_trader_cache_locked_portfolio))/self.multiplier

        self.assertEqual(safe_get_buy_trader_cache_portfolio, Decimal(str(8800)))
        self.assertEqual(safe_get_buy_trader_locked_portfolio, Decimal(str(0)))

        self.assertEqual(safe_get_buy_trader_cache_positions,Decimal(str(150)))
        self.assertEqual(safe_get_buy_trader_cache_locked_positions,Decimal(str(0)))

        #Testing Seller portfolio and seller positions
        get_seller_cache_position = test_redis_client.hget(self.traderCacheKey_positions, 'APP')
        get_seller_cache_locked_position = test_redis_client.hget(self.traderCacheKey_positions, 'locked_APP')

        get_seller_cache_portfolio = test_redis_client.hget(self.traderCacheKey_portfolio, 'available_cash')
        get_seller_cache_locked_portfolio = test_redis_client.hget(self.traderCacheKey_portfolio,'locked_balance')

        safe_get_seller_cache_position = Decimal(str(get_seller_cache_position))/self.multiplier
        safe_get_seller_cache_locked_position = Decimal(str(get_seller_cache_locked_position))/self.multiplier

        safe_get_seller_cache_portfolio = Decimal(str(get_seller_cache_portfolio))/self.multiplier
        safe_get_seller_cache_locked_portfolio = Decimal(str(get_seller_cache_locked_portfolio or 0))/self.multiplier

        self.assertEqual(safe_get_seller_cache_position,Decimal(str(50)))
        self.assertEqual(safe_get_seller_cache_locked_position,0)   

        self.assertEqual(safe_get_seller_cache_portfolio,Decimal(str(11200)))
        self.assertEqual(safe_get_seller_cache_locked_portfolio, Decimal(str(0)))
    @patch('core_ledger.services.redis_client', test_redis_client)
    def test_cumulative_partial_fills_for_single_order(self):
        """
        Tests that a single large order (150 shares locked at $8) 
        can be correctly settled in multiple smaller chunks (100 shares @ $6, then 50 shares @ $7).
        """
        redis_positions_portfolio_service(self.trader.id)
        redis_positions_portfolio_service(self.trader1.id)

        total_lock_amount = Decimal("150") * Decimal("8")
        update_portfolio_value = {
            'available_cash': int((self.portfolio_of_trader1.cash_balance - total_lock_amount) * self.multiplier),
            'locked_balance': int(total_lock_amount * self.multiplier)
        }
        
        total_shares = Position.objects.get(portfolio=self.portfolio_of_trader, asset_symbol='APP').quantity
        update_position_value = {
            'APP': int((total_shares - Decimal("150")) * self.multiplier),
            'locked_APP': int(Decimal("150") * self.multiplier)
        }
        
        test_redis_client.hset(self.trader1CacheKey_portfolio, mapping=update_portfolio_value)
        test_redis_client.hset(self.traderCacheKey_positions, mapping=update_position_value)

        fill_1 = {
            'ticker': 'APP', 'seller_id': str(self.trader.id), 'buyer_id': str(self.trader1.id),
            'quantity': int(Decimal("100") * self.multiplier),
            'price_locked_by_user': int(Decimal("8") * self.multiplier),
            'price_setteled_at': int(Decimal("6") * self.multiplier)
        }
        
        fill_2 = {
            'ticker': 'APP', 'seller_id': str(self.trader.id), 'buyer_id': str(self.trader1.id),
            'quantity': int(Decimal("50") * self.multiplier),
            'price_locked_by_user': int(Decimal("8") * self.multiplier),
            'price_setteled_at': int(Decimal("7") * self.multiplier)
        }

        settle_cache(fill_1, test_redis_client)
        settle_cache(fill_2, test_redis_client)

        buyer_cash = Decimal(str(test_redis_client.hget(self.trader1CacheKey_portfolio, 'available_cash') or 0)) / self.multiplier
        buyer_locked = Decimal(str(test_redis_client.hget(self.trader1CacheKey_portfolio, 'locked_balance') or 0)) / self.multiplier
        buyer_shares = Decimal(str(test_redis_client.hget(self.trader1CacheKey_positions, 'APP') or 0)) / self.multiplier

        # Assertions: 
        # Total cost = (100 * $6) + (50 * $7) = $600 + $350 = $950. 
        # Refund = $1200 (lock) - $950 = $250.
        # Buyer Cash: 10000 - 1200 + 250 = 9050
        self.assertEqual(buyer_cash, Decimal("9050.00"))
        self.assertEqual(buyer_locked, Decimal("0.00"))
        self.assertEqual(buyer_shares, Decimal("150.00"))

    @patch('core_ledger.services.redis_client', test_redis_client)
    def test_idempotency_vulnerability_of_settle_cache(self):
        """
        DOCUMENTATION TEST: Proves `settle_cache` does NOT have internal idempotency.
        If the stream consumer accidentally passes the same trade twice, the cache 
        will double-apply the settlement, corrupting the ledger.
        Idempotency MUST be enforced by checking PostgreSQL LedgerTransaction IDs upstream.
        """
        redis_positions_portfolio_service(self.trader.id)
        redis_positions_portfolio_service(self.trader1.id)

        total_lock = Decimal("1200")
        test_redis_client.hset(self.trader1CacheKey_portfolio, mapping={
            'available_cash': int((self.portfolio_of_trader1.cash_balance - total_lock) * self.multiplier),
            'locked_balance': int(total_lock * self.multiplier)
        })
        test_redis_client.hset(self.traderCacheKey_positions, mapping={
            'APP': int((Decimal("200") - Decimal("150")) * self.multiplier),
            'locked_APP': int(Decimal("150") * self.multiplier)
        })

        settle_cache(self.transaction_data, test_redis_client)
        settle_cache(self.transaction_data, test_redis_client)

        buyer_locked = Decimal(str(test_redis_client.hget(self.trader1CacheKey_portfolio, 'locked_balance') or 0)) / self.multiplier
        buyer_shares = Decimal(str(test_redis_client.hget(self.trader1CacheKey_positions, 'APP') or 0)) / self.multiplier

        self.assertEqual(buyer_shares, Decimal("300.00"))
        self.assertEqual(buyer_locked, Decimal("-1200.00"))

    @patch('core_ledger.services.redis_client', test_redis_client)
    def test_defensive_behavior_on_negative_slippage(self):
        """
        Tests engine behavior if a trade settles worse than the locked limit price.
        Currently, `settle_cache` silently absorbs the shortfall to prevent the buyer's 
        available cash from going negative, dropping the difference entirely.
        """
        
        redis_positions_portfolio_service(self.trader.id)
        redis_positions_portfolio_service(self.trader1.id)

        total_lock = Decimal("1200")
        test_redis_client.hset(self.trader1CacheKey_portfolio, mapping={
            'available_cash': int((self.portfolio_of_trader1.cash_balance - total_lock) * self.multiplier),
            'locked_balance': int(total_lock * self.multiplier)
        })

        bad_transaction_data = self.transaction_data.copy()
        bad_transaction_data['price_setteled_at'] = int(Decimal("10.00000000") * self.multiplier)

        
        settle_cache(bad_transaction_data, test_redis_client)

        
        buyer_cash = Decimal(str(test_redis_client.hget(self.trader1CacheKey_portfolio, 'available_cash') or 0)) / self.multiplier
        buyer_locked = Decimal(str(test_redis_client.hget(self.trader1CacheKey_portfolio, 'locked_balance') or 0)) / self.multiplier

        self.assertEqual(buyer_locked, Decimal("0.00"))
        
        self.assertEqual(buyer_cash, Decimal("8800.00"))