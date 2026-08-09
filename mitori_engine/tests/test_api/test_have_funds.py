import pytest
from tests.testconfig import test_redis, test_request
from api.have_funds import have_funds
from schemas.schema import OrderReq
from core.models import Side, Type  # ADDED: Type import
from decimal import Decimal
import uuid
from api.security import AuthenticatedUser
from fastapi import HTTPException
from unittest.mock import patch
import redis.exceptions as exp

@pytest.mark.asyncio
async def test_for_invalid_ticker(test_redis, test_request):
    user_id = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id), kyc_verified=True)

    order = OrderReq(
        ticker='gibberish',
        side=Side.BUY,
        type=Type.LIMIT, 
        price=Decimal(10),
        number_of_shares=Decimal(20),
        order_owner_id=user_id
    )

    with pytest.raises(HTTPException) as exec_info:
        async for authenticated_user in have_funds(request=test_request, user=user, order=order):
            assert authenticated_user.user_id == user.user_id
    assert exec_info.value.status_code == 404
    assert "Ticker does not exist" in exec_info.value.detail 

@pytest.mark.asyncio
async def test_for_buy_order(test_redis, test_request):
    multiplier = Decimal(100000000)
    user_id = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id), kyc_verified=True)

    buyer_cache_portfolio_key_redis = f'cache:portfolio:{user.user_id}'
    initial_balance = Decimal(str(4000)) * multiplier
    buyer_portfolio_dict = {
        'available_cash': int(initial_balance),
        'locked_balance': 0
    }

    await test_redis.hset(buyer_cache_portfolio_key_redis, mapping=buyer_portfolio_dict)

    order = OrderReq(
        ticker='APP',
        side=Side.BUY,
        type=Type.LIMIT,
        price=Decimal(str(10)),
        number_of_shares=Decimal(str(20)),
        order_owner_id=user_id
    )
    
    async for authenticated_user in have_funds(request=test_request, user=user, order=order):
        assert authenticated_user.user_id == user.user_id

    checking_result_available_balance = int(await test_redis.hget(buyer_cache_portfolio_key_redis, 'available_cash'))
    checking_result_locked_balance = int(await test_redis.hget(buyer_cache_portfolio_key_redis, 'locked_balance'))

    expected_total = int((Decimal("20")) * Decimal("10") * multiplier)
    assert checking_result_available_balance == buyer_portfolio_dict['available_cash'] - expected_total
    assert checking_result_locked_balance == expected_total

@pytest.mark.asyncio
async def test_for_selling_shares(test_redis, test_request):
    multiplier = Decimal(100000000)
    user_id = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id), kyc_verified=True)
    
    seller_cache_positions_key_redis = f'cache:positions:{user.user_id}'
    initial_shares = Decimal(str(2000)) * multiplier
    seller_shares_dict = {
        'APP': int(initial_shares),
        'locked_APP': 0
    }
    await test_redis.hset(seller_cache_positions_key_redis, mapping=seller_shares_dict)

    order_quantity = Decimal(str(1500))
    order = OrderReq(
        ticker='APP',
        side=Side.SELL,
        type=Type.LIMIT,  # FIX: Added required type
        price=Decimal(str(10)),
        number_of_shares=order_quantity,
        order_owner_id=user_id
    )
        
    async for authenticated_user in have_funds(request=test_request, user=user, order=order):
        assert authenticated_user.user_id == user.user_id

    checking_shares_available_balance = int(await test_redis.hget(seller_cache_positions_key_redis, 'APP'))
    checking_shares_locked_balance = int(await test_redis.hget(seller_cache_positions_key_redis, 'locked_APP'))
    
    assert checking_shares_available_balance == int(initial_shares - order_quantity * multiplier)
    assert checking_shares_locked_balance == int(order_quantity * multiplier)

@pytest.mark.asyncio
async def test_for_shares_exceeding_users_holding(test_redis, test_request):
    multiplier = Decimal(100000000)
    user_id = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id), kyc_verified=True)

    seller_cache_positions_key_redis = f'cache:positions:{user.user_id}'
    initial_shares = Decimal(str(1000)) * multiplier
    seller_shares_dict = {
        'APP': int(initial_shares),
        'locked_APP': 0
    }
    await test_redis.hset(seller_cache_positions_key_redis, mapping=seller_shares_dict)

    order_quantity = Decimal(str(1500))
    order = OrderReq(
        ticker='APP',
        side=Side.SELL,
        type=Type.LIMIT,
        price=Decimal(str(10)),
        number_of_shares=order_quantity,
        order_owner_id=user_id
    )
    
    with pytest.raises(HTTPException) as execp_info:
        async for authenticated_user in have_funds(request=test_request, user=user, order=order):
            pass

    assert execp_info.value.status_code == 400
    assert f"You do not have enough shares" in execp_info.value.detail 

@pytest.mark.asyncio
async def test_for_buy_order_exceeding_user_cash(test_redis, test_request):
    multiplier = Decimal(100000000)
    user_id = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id), kyc_verified=True)

    buyer_cache_portfolio_key_redis = f'cache:portfolio:{user.user_id}'
    initial_balance = Decimal(str(1000)) * multiplier
    buyer_portfolio_dict = {
        'available_cash': int(initial_balance),
        'locked_balance': 0
    }
    await test_redis.hset(buyer_cache_portfolio_key_redis, mapping=buyer_portfolio_dict)

    order = OrderReq(
        ticker='APP',
        side=Side.BUY,
        type=Type.LIMIT,
        price=Decimal(str(10)),
        number_of_shares=Decimal(str(200)),
        order_owner_id=user_id
    )

    with pytest.raises(HTTPException) as exec_info:    
        async for authenticated_user in have_funds(request=test_request, user=user, order=order):
            pass

    assert exec_info.value.status_code == 400
    assert "Not enough funds" in exec_info.value.detail

@pytest.mark.asyncio
async def test_buy_order_rollback_on_server_crash(test_redis, test_request):
    multiplier = Decimal("100000000")
    user_id = str(uuid.uuid4())
    ticker = 'APP'
    
    user = AuthenticatedUser(user_id=user_id, kyc_verified=True)
    buyer_cache_key = f'cache:portfolio:{user.user_id}'
    
    initial_balance_int = int(Decimal("4000") * multiplier)
    await test_redis.hset(buyer_cache_key, mapping={'available_cash': initial_balance_int, 'locked_balance': 0})
    
    order = OrderReq(
        ticker=ticker,
        side=Side.BUY,
        type=Type.LIMIT,
        price=Decimal("10"),
        number_of_shares=Decimal("20"),
        order_owner_id=user_id
    )
    
    gen = have_funds(request=test_request, user=user, order=order)
    await anext(gen) 
        
    with pytest.raises(RuntimeError, match="Simulated 500 Internal Server Error"):
        await gen.athrow(RuntimeError("Simulated 500 Internal Server Error"))
    
    final_available = int(await test_redis.hget(buyer_cache_key, 'available_cash'))
    final_locked = int(await test_redis.hget(buyer_cache_key, 'locked_balance'))
    
    assert final_available == initial_balance_int
    assert final_locked == 0

@pytest.mark.asyncio
async def test_sell_order_rollback_on_server_crash(test_redis, test_request):
    multiplier = Decimal("100000000")
    user_id = str(uuid.uuid4())
    ticker = 'APP'
    
    user = AuthenticatedUser(user_id=user_id, kyc_verified=True)
    seller_cache_key = f'cache:positions:{user.user_id}'
    
    initial_shares_int = int(Decimal("2000") * multiplier)
    await test_redis.hset(seller_cache_key, mapping={ticker: initial_shares_int, f'locked_{ticker}': 0})
    
    order = OrderReq(
        ticker=ticker,
        side=Side.SELL,
        type=Type.LIMIT,
        price=Decimal("10"),
        number_of_shares=Decimal("1500"),
        order_owner_id=user_id
    )

    gen = have_funds(request=test_request, user=user, order=order)
    await anext(gen)
    
    with pytest.raises(RuntimeError, match="Simulated 500 Internal Server Error"):
        await gen.athrow(RuntimeError("Simulated 500 Internal Server Error"))

    final_available = int(await test_redis.hget(seller_cache_key, ticker))
    final_locked = int(await test_redis.hget(seller_cache_key, f'locked_{ticker}'))
    
    assert final_available == initial_shares_int
    assert final_locked == 0

@pytest.mark.asyncio
async def test_buy_order_watch_error_exhaustion_raises_409(test_redis, test_request):
    multiplier = Decimal("100000000")
    user_id = "user-race-123"
    
    await test_redis.hset(
        f"cache:portfolio:{user_id}", 
        mapping={"available_cash": int(Decimal("100") * multiplier), "locked_balance": 0}
    )
    
    user = AuthenticatedUser(user_id=user_id, kyc_verified=True)
    order = OrderReq(
        ticker='APP', 
        side=Side.BUY, 
        type=Type.LIMIT,
        price=Decimal("10"), 
        number_of_shares=Decimal("5")
    )

    async def mock_execute_with_cleanup(pipeline_instance, *args, **kwargs):
        await pipeline_instance.reset()  
        raise exp.WatchError("Simulated Collision")

    with patch("redis.asyncio.client.Pipeline.execute", autospec=True, side_effect=mock_execute_with_cleanup):
        with pytest.raises(HTTPException) as exc_info:
            async for _ in have_funds(request=test_request, user=user, order=order):
                pass

    assert exc_info.value.status_code == 409
    assert "Retry your order" in exc_info.value.detail

@pytest.mark.asyncio
async def test_invalid_market_ticker_raises_404(test_request):
    user = AuthenticatedUser(user_id="user-123", kyc_verified=True)
    order = OrderReq(
        ticker='FAKECOIN', 
        side=Side.BUY, 
        type=Type.LIMIT,
        price=Decimal("10"), 
        number_of_shares=Decimal("1")
    )
    
    with pytest.raises(HTTPException) as exc_info:
        async for _ in have_funds(request=test_request, user=user, order=order):
            pass
            
    assert exc_info.value.status_code == 404
    assert "Ticker does not exist" in exc_info.value.detail

@pytest.mark.asyncio
async def test_market_buy_locks_buffered_bbo_and_injects_ceiling(test_redis, test_request):
    multiplier = Decimal("100000000")
    user_id = str(uuid.uuid4())
    user = AuthenticatedUser(user_id=user_id, kyc_verified=True)

    portfolio_key = f'cache:portfolio:{user_id}'
    await test_redis.hset(portfolio_key, mapping={'available_cash': int(Decimal("5000") * multiplier), 'locked_balance': 0})
    
    await test_redis.hset('ticker:APP:bbo', mapping={'best_ask_price': int(Decimal("100.00")*multiplier), 'best_bid_price': int(Decimal("99.00")*multiplier)})

    order = OrderReq(
        ticker='APP',
        side=Side.BUY,
        type=Type.MARKET,
        price=None,
        number_of_shares=Decimal("10"),
        order_owner_id=user_id
    )

    async for authenticated_user in have_funds(request=test_request, user=user, order=order):
        pass # Execution pauses here during the yield

    expected_cost = Decimal("1010")
    expected_cost_int = int(expected_cost * multiplier)
    
    available_cash = int(await test_redis.hget(portfolio_key, 'available_cash'))
    locked_balance = int(await test_redis.hget(portfolio_key, 'locked_balance'))
    
    assert locked_balance == expected_cost_int
    assert available_cash == int((Decimal("5000") - expected_cost) * multiplier)
    
    assert order.max_authorized_funds == expected_cost

@pytest.mark.asyncio
async def test_market_sell_locks_shares(test_redis, test_request):
    multiplier = Decimal("100000000")
    user_id = str(uuid.uuid4())
    user = AuthenticatedUser(user_id=user_id, kyc_verified=True)

    positions_key = f'cache:positions:{user_id}'
    await test_redis.hset(positions_key, mapping={'APP': int(Decimal("50") * multiplier), 'locked_APP': 0})
    
    await test_redis.hset('ticker:APP:bbo', mapping={'best_bid_price': "99.00"})

    order = OrderReq(
        ticker='APP',
        side=Side.SELL,
        type=Type.MARKET,
        price=None,
        number_of_shares=Decimal("10"),
        order_owner_id=user_id
    )

    async for authenticated_user in have_funds(request=test_request, user=user, order=order):
        pass 

    expected_locked_int = int(Decimal("10") * multiplier)
    
    available_shares = int(await test_redis.hget(positions_key, 'APP'))
    locked_shares = int(await test_redis.hget(positions_key, 'locked_APP'))
    
    assert locked_shares == expected_locked_int
    assert available_shares == int(Decimal("40") * multiplier)

@pytest.mark.asyncio
async def test_market_buy_circuit_breaker_empty_asks(test_redis, test_request):
    """Proves Market BUY drops a 406 Error if there are no sellers."""
    user_id = str(uuid.uuid4())
    user = AuthenticatedUser(user_id=user_id, kyc_verified=True)

    await test_redis.hset(f'cache:portfolio:{user_id}', mapping={'available_cash': 10000000000, 'locked_balance': 0})
    await test_redis.delete('ticker:APP:bbo')

    order = OrderReq(
        ticker='APP',
        side=Side.BUY,
        type=Type.MARKET,
        price=None,
        number_of_shares=Decimal("10"),
        order_owner_id=user_id
    )

    with pytest.raises(HTTPException) as exec_info:
        async for _ in have_funds(request=test_request, user=user, order=order):
            pass

    assert exec_info.value.status_code == 406
    assert "Market does not have enough liquidity" in exec_info.value.detail

@pytest.mark.asyncio
async def test_market_sell_circuit_breaker_empty_bids(test_redis, test_request):
    """Proves Market SELL drops a 406 Error if there are no buyers."""
    user_id = str(uuid.uuid4())
    user = AuthenticatedUser(user_id=user_id, kyc_verified=True)

    await test_redis.hset(f'cache:positions:{user_id}', mapping={'APP': 10000000000, 'locked_APP': 0})
    await test_redis.delete('ticker:APP:bbo')

    order = OrderReq(
        ticker='APP',
        side=Side.SELL,
        type=Type.MARKET,
        price=None,
        number_of_shares=Decimal("10"),
        order_owner_id=user_id
    )

    with pytest.raises(HTTPException) as exec_info:
        async for _ in have_funds(request=test_request, user=user, order=order):
            pass

    assert exec_info.value.status_code == 406
    assert "Market does not have enough liquidity" in exec_info.value.detail