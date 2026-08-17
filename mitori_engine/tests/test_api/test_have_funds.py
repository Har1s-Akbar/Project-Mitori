import pytest
import uuid
from decimal import Decimal
from fastapi import HTTPException
from unittest.mock import patch
import redis.exceptions as exp

from schemas.schema import OrderReq
from core_python.models import Side, Type 
from api.security import AuthenticatedUser
from api.have_funds import have_funds

MULTIPLIER = Decimal("100000000")
TICKER = "APP"

@pytest.mark.asyncio
async def test_for_invalid_ticker(test_request, order_factory):
    user_id_obj = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id_obj), kyc_verified=True)
    
    order = order_factory(
        ticker='gibberish', side=Side.BUY, order_type=Type.LIMIT, 
        price=Decimal("10"), number_of_shares=Decimal("20"), order_owner_id=user_id_obj
    )

    with pytest.raises(HTTPException) as exec_info:
        async for _ in have_funds(request=test_request, user=user, order=order):
            pass
            
    assert exec_info.value.status_code == 404
    assert "Ticker does not exist" in exec_info.value.detail 

@pytest.mark.asyncio
async def test_for_buy_order(test_redis, test_request, order_factory, seed_cash_factory):
    user_id_obj = uuid.uuid4()
    user_id_str = str(user_id_obj)
    user = AuthenticatedUser(user_id=user_id_str, kyc_verified=True)

    await seed_cash_factory(owner_id=user_id_str, available_cash=Decimal("4000"), ticker=TICKER)
    order = order_factory(
        ticker=TICKER, side=Side.BUY, order_type=Type.LIMIT, 
        price=Decimal("10"), number_of_shares=Decimal("20"), order_owner_id=user_id_obj
    )
    
    async for authenticated_user in have_funds(request=test_request, user=user, order=order):
        assert authenticated_user.user_id == user.user_id

    final_available = int(await test_redis.hget(f'cache:portfolio:{user_id_str}', 'available_cash'))
    final_locked = int(await test_redis.hget(f'cache:portfolio:{user_id_str}', 'locked_balance'))

    expected_cost = int(Decimal("200") * MULTIPLIER)
    assert final_available == int(Decimal("3800") * MULTIPLIER)
    assert final_locked == expected_cost

@pytest.mark.asyncio
async def test_for_selling_shares(test_redis, test_request, order_factory, seed_shares_factory):
    user_id_obj = uuid.uuid4()
    user_id_str = str(user_id_obj)
    user = AuthenticatedUser(user_id=user_id_str, kyc_verified=True)
    
    await seed_shares_factory(owner_id=user_id_str, shares=Decimal("2000"), ticker=TICKER)
    order = order_factory(
        ticker=TICKER, side=Side.SELL, order_type=Type.LIMIT, 
        price=Decimal("10"), number_of_shares=Decimal("1500"), order_owner_id=user_id_obj
    )
        
    async for authenticated_user in have_funds(request=test_request, user=user, order=order):
        assert authenticated_user.user_id == user.user_id

    final_available = int(await test_redis.hget(f'cache:positions:{user_id_str}', TICKER))
    final_locked = int(await test_redis.hget(f'cache:positions:{user_id_str}', f'locked_{TICKER}'))
    
    expected_locked = int(Decimal("1500") * MULTIPLIER)
    assert final_available == int(Decimal("500") * MULTIPLIER)
    assert final_locked == expected_locked

@pytest.mark.asyncio
async def test_for_shares_exceeding_users_holding(test_request, order_factory, seed_shares_factory):
    user_id_obj = uuid.uuid4()
    user_id_str = str(user_id_obj)
    user = AuthenticatedUser(user_id=user_id_str, kyc_verified=True)

    await seed_shares_factory(owner_id=user_id_str, shares=Decimal("1000"), ticker=TICKER)
    order = order_factory(
        ticker=TICKER, side=Side.SELL, order_type=Type.LIMIT, 
        price=Decimal("10"), number_of_shares=Decimal("1500"), order_owner_id=user_id_obj
    )
    
    with pytest.raises(HTTPException) as exec_info:
        async for _ in have_funds(request=test_request, user=user, order=order):
            pass

    assert exec_info.value.status_code == 400
    assert "You do not have enough shares" in exec_info.value.detail 

@pytest.mark.asyncio
async def test_for_buy_order_exceeding_user_cash(test_request, order_factory, seed_cash_factory):
    user_id_obj = uuid.uuid4()
    user_id_str = str(user_id_obj)
    user = AuthenticatedUser(user_id=user_id_str, kyc_verified=True)

    await seed_cash_factory(owner_id=user_id_str, available_cash=Decimal("1000"), ticker=TICKER)
    order = order_factory(
        ticker=TICKER, side=Side.BUY, order_type=Type.LIMIT, 
        price=Decimal("10"), number_of_shares=Decimal("200"), order_owner_id=user_id_obj
    )

    with pytest.raises(HTTPException) as exec_info:    
        async for _ in have_funds(request=test_request, user=user, order=order):
            pass

    assert exec_info.value.status_code == 400
    assert "Not enough funds" in exec_info.value.detail

@pytest.mark.asyncio
async def test_market_buy_slippage_exceeds_cash(test_request, order_factory, seed_cash_factory):
    """Proves Market BUY drops a 400 if the 1% buffer pushes cost past available cash."""
    user_id_obj = uuid.uuid4()
    user_id_str = str(user_id_obj)
    user = AuthenticatedUser(user_id=user_id_str, kyc_verified=True)

    # Base cost is 100 (10 shares * 10 BBO). Buffer brings it to 101. User only has 100.
    await seed_cash_factory(owner_id=user_id_str, available_cash=Decimal("100"), ticker=TICKER)
    order = order_factory(
        ticker=TICKER, side=Side.BUY, order_type=Type.MARKET, 
        price=None, number_of_shares=Decimal("10"), order_owner_id=user_id_obj
    )

    with pytest.raises(HTTPException) as exec_info:    
        async for _ in have_funds(request=test_request, user=user, order=order):
            pass

    assert exec_info.value.status_code == 400
    assert "Not enough funds" in exec_info.value.detail

@pytest.mark.asyncio
async def test_buy_order_rollback_on_server_crash(test_redis, test_request, order_factory, seed_cash_factory):
    user_id_obj = uuid.uuid4()
    user_id_str = str(user_id_obj)
    user = AuthenticatedUser(user_id=user_id_str, kyc_verified=True)
    
    await seed_cash_factory(owner_id=user_id_str, available_cash=Decimal("4000"), ticker=TICKER)
    order = order_factory(
        ticker=TICKER, side=Side.BUY, order_type=Type.LIMIT, 
        price=Decimal("10"), number_of_shares=Decimal("20"), order_owner_id=user_id_obj
    )
    
    gen = have_funds(request=test_request, user=user, order=order)
    await anext(gen) 
        
    with pytest.raises(RuntimeError, match="Simulated 500"):
        await gen.athrow(RuntimeError("Simulated 500"))
    
    final_available = int(await test_redis.hget(f'cache:portfolio:{user_id_str}', 'available_cash'))
    final_locked = int(await test_redis.hget(f'cache:portfolio:{user_id_str}', 'locked_balance'))
    
    assert final_available == int(Decimal("4000") * MULTIPLIER)
    assert final_locked == 0

@pytest.mark.asyncio
async def test_sell_order_rollback_on_server_crash(test_redis, test_request, order_factory, seed_shares_factory):
    user_id_obj = uuid.uuid4()
    user_id_str = str(user_id_obj)
    user = AuthenticatedUser(user_id=user_id_str, kyc_verified=True)
    
    await seed_shares_factory(owner_id=user_id_str, shares=Decimal("2000"), ticker=TICKER)
    order = order_factory(
        ticker=TICKER, side=Side.SELL, order_type=Type.LIMIT, 
        price=Decimal("10"), number_of_shares=Decimal("1500"), order_owner_id=user_id_obj
    )

    gen = have_funds(request=test_request, user=user, order=order)
    await anext(gen)
    
    with pytest.raises(RuntimeError, match="Simulated 500"):
        await gen.athrow(RuntimeError("Simulated 500"))

    final_available = int(await test_redis.hget(f'cache:positions:{user_id_str}', TICKER))
    final_locked = int(await test_redis.hget(f'cache:positions:{user_id_str}', f'locked_{TICKER}'))
    
    assert final_available == int(Decimal("2000") * MULTIPLIER)
    assert final_locked == 0

@pytest.mark.asyncio
async def test_buy_order_watch_error_exhaustion_raises_409(test_request, order_factory, seed_cash_factory):
    user_id_obj = uuid.uuid4()
    user_id_str = str(user_id_obj)
    user = AuthenticatedUser(user_id=user_id_str, kyc_verified=True)

    await seed_cash_factory(owner_id=user_id_str, available_cash=Decimal("100"), ticker=TICKER)
    order = order_factory(
        ticker=TICKER, side=Side.BUY, order_type=Type.LIMIT, 
        price=Decimal("10"), number_of_shares=Decimal("5"), order_owner_id=user_id_obj
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
async def test_invalid_market_ticker_raises_404(test_request, order_factory):
    user_id_obj = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id_obj), kyc_verified=True)
    order = order_factory(
        ticker='FAKECOIN', side=Side.BUY, order_type=Type.MARKET, 
        price=None, number_of_shares=Decimal("1"), order_owner_id=user_id_obj
    )
    
    with pytest.raises(HTTPException) as exc_info:
        async for _ in have_funds(request=test_request, user=user, order=order):
            pass
            
    assert exc_info.value.status_code == 404
    assert "Ticker does not exist" in exc_info.value.detail

@pytest.mark.asyncio
async def test_market_buy_locks_buffered_bbo_and_injects_ceiling(test_redis, test_request, order_factory, seed_cash_factory):
    user_id_obj = uuid.uuid4()
    user_id_str = str(user_id_obj)
    user = AuthenticatedUser(user_id=user_id_str, kyc_verified=True)

    # Factory provides a BBO Ask of 10.00
    await seed_cash_factory(owner_id=user_id_str, available_cash=Decimal("5000"), ticker=TICKER)
    order = order_factory(
        ticker=TICKER, side=Side.BUY, order_type=Type.MARKET, 
        price=None, number_of_shares=Decimal("10"), order_owner_id=user_id_obj
    )

    async for authenticated_user in have_funds(request=test_request, user=user, order=order):
        pass # Pauses at yield

    # 10 shares * 10 BBO Ask * 1.01 buffer = 101
    expected_cost = Decimal("101")
    
    final_available = int(await test_redis.hget(f'cache:portfolio:{user_id_str}', 'available_cash'))
    final_locked = int(await test_redis.hget(f'cache:portfolio:{user_id_str}', 'locked_balance'))
    
    assert final_locked == int(expected_cost * MULTIPLIER)
    assert final_available == int((Decimal("5000") - expected_cost) * MULTIPLIER)
    assert order.max_authorized_funds == expected_cost

@pytest.mark.asyncio
async def test_market_sell_locks_shares(test_redis, test_request, order_factory, seed_shares_factory):
    user_id_obj = uuid.uuid4()
    user_id_str = str(user_id_obj)
    user = AuthenticatedUser(user_id=user_id_str, kyc_verified=True)

    await seed_shares_factory(owner_id=user_id_str, shares=Decimal("50"), ticker=TICKER)
    order = order_factory(
        ticker=TICKER, side=Side.SELL, order_type=Type.MARKET, 
        price=None, number_of_shares=Decimal("10"), order_owner_id=user_id_obj
    )

    async for authenticated_user in have_funds(request=test_request, user=user, order=order):
        pass 

    final_available = int(await test_redis.hget(f'cache:positions:{user_id_str}', TICKER))
    final_locked = int(await test_redis.hget(f'cache:positions:{user_id_str}', f'locked_{TICKER}'))
    
    assert final_locked == int(Decimal("10") * MULTIPLIER)
    assert final_available == int(Decimal("40") * MULTIPLIER)

@pytest.mark.asyncio
async def test_market_buy_circuit_breaker_empty_asks(test_redis, test_request, order_factory, seed_cash_factory):
    user_id_obj = uuid.uuid4()
    user_id_str = str(user_id_obj)
    user = AuthenticatedUser(user_id=user_id_str, kyc_verified=True)

    await seed_cash_factory(owner_id=user_id_str, available_cash=Decimal("1000"), ticker=TICKER)
    await test_redis.delete(f'ticker:{TICKER}:bbo') # Sabotage liquidity

    order = order_factory(
        ticker=TICKER, side=Side.BUY, order_type=Type.MARKET, 
        price=None, number_of_shares=Decimal("10"), order_owner_id=user_id_obj
    )

    with pytest.raises(HTTPException) as exec_info:
        async for _ in have_funds(request=test_request, user=user, order=order):
            pass

    assert exec_info.value.status_code == 406
    assert "Market does not have enough liquidity" in exec_info.value.detail

@pytest.mark.asyncio
async def test_market_sell_circuit_breaker_empty_bids(test_redis, test_request, order_factory, seed_shares_factory):
    user_id_obj = uuid.uuid4()
    user_id_str = str(user_id_obj)
    user = AuthenticatedUser(user_id=user_id_str, kyc_verified=True)

    await seed_shares_factory(owner_id=user_id_str, shares=Decimal("1000"), ticker=TICKER)
    await test_redis.delete(f'ticker:{TICKER}:bbo') # Sabotage liquidity

    order = order_factory(
        ticker=TICKER, side=Side.SELL, order_type=Type.MARKET, 
        price=None, number_of_shares=Decimal("10"), order_owner_id=user_id_obj
    )

    with pytest.raises(HTTPException) as exec_info:
        async for _ in have_funds(request=test_request, user=user, order=order):
            pass

    assert exec_info.value.status_code == 406
    assert "Market does not have enough liquidity" in exec_info.value.detail