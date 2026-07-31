import pytest
from tests.testconfig import redis_client, test_request
from api.have_funds import have_funds
from schemas.schema import OrderReq
from core.models import Side
from decimal import Decimal
import uuid
from api.security import AuthenticatedUser
from fastapi import HTTPException

@pytest.mark.asyncio
#for  invalid ticker
async def test_for_invalid_ticker(redis_client, test_request):

    user_id = uuid.uuid4()
    user = AuthenticatedUser(user_id= str(user_id), kyc_verified=True)

    order = OrderReq(
        ticker='gibberish',
        side='buy',
        price=Decimal(10),
        number_of_shares=Decimal(20),
        order_owner_id=user_id
    )

    with pytest.raises(HTTPException) as exec_info:
        async for authenticated_user in have_funds(request=test_request, user=user,order=order):
            assert authenticated_user.user_id == user.user_id
    assert exec_info.value.status_code == 404
    assert "Ticker does not exist" in exec_info.value.detail 

#test for successful buy side order
@pytest.mark.asyncio
async def test_for_buy_order(redis_client,test_request):
    multiplier = Decimal(100000000)
    user_id = uuid.uuid4()
    #here when we are setting the user equal to Authenticated user we are basically bbypassing our 
    #security.py because if you'll look closely at the is_user_Authenticated function in security.py
    #it is returning user object which we are setting in our function call bypassing the security.py and
    # testing have_funds.py in isolation, so even if you'll include kyc false the trader  will be allowed to trade because we 
    # are bypassing our secuirty dependency 
    
    user = AuthenticatedUser(user_id= str(user_id), kyc_verified=True)

    buyer_cache_portfolio_key_redis = f'cache:portfolio:{user.user_id}'
    initial_balance = Decimal(str(4000))*multiplier
    buyer_portfolio_dict={
        'available_cash': int(initial_balance),
        'locked_balance':int(0)
    }
    await redis_client.hset(buyer_cache_portfolio_key_redis,mapping=buyer_portfolio_dict)

    order = OrderReq(
        ticker='APP',
        side=Side.BUY,
        price=Decimal(str(10)),
        number_of_shares=Decimal(str(20)),
        order_owner_id=user_id
    )

    
    async for authenticated_user in have_funds(request=test_request, user=user,order=order):
        assert authenticated_user.user_id == user.user_id

    checking_result_available_balance = int(await redis_client.hget(buyer_cache_portfolio_key_redis, 'available_cash'))
    checking_result_locked_balance = int(await redis_client.hget(buyer_cache_portfolio_key_redis, 'locked_balance'))

    expected_total = int((Decimal("20"))*Decimal("10") * multiplier)
    assert checking_result_available_balance == buyer_portfolio_dict['available_cash'] - expected_total
    assert checking_result_locked_balance == expected_total

    #because of this i caught a bug in my have_funds.py which was i was setting decimal in
    # in the redis stream when updating the redis stream after evaluating the order , without casting
    #the value to int | bug found and fixed |

#test for selling the shares
@pytest.mark.asyncio
async def test_for_selling_shares(redis_client, test_request):
    multiplier = Decimal(100000000)
    user_id = uuid.uuid4()
        
    user = AuthenticatedUser(user_id= str(user_id), kyc_verified=True)
    
    seller_cache_positions_key_redis = f'cache:positions:{user.user_id}'
    initial_shares = Decimal(str(2000))*multiplier
    seller_shares_dict={
        'APP': int(initial_shares),
        'locked_APP':0
        }
    await redis_client.hset(str(seller_cache_positions_key_redis),mapping=seller_shares_dict)

    order_quantity = Decimal(str(1500))
    order = OrderReq(
        ticker='APP',
        side=Side.SELL,
        price=Decimal(str(10)),
        number_of_shares=order_quantity,
        order_owner_id=user_id
    )
    
        
    async for authenticated_user in have_funds(request=test_request, user=user,order=order):
        assert authenticated_user.user_id == user.user_id

    checking_shares_available_balance = int(await redis_client.hget(seller_cache_positions_key_redis, 'APP'))
    checking_shares_locked_balance = int(await redis_client.hget(seller_cache_positions_key_redis, 'locked_APP'))
    
    assert checking_shares_available_balance == int(initial_shares - order_quantity*multiplier)
    assert checking_shares_locked_balance == order_quantity*multiplier
