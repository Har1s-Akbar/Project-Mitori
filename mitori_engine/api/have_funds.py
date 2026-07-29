from fastapi import HTTPException, status, Request 
from api.security import is_user_Authenticated, AuthenticatedUser
from fastapi import Depends
from schemas.schema import OrderReq, MARKET
from decimal import Decimal
import redis.exceptions as exp
from typing import AsyncGenerator
import os
from dotenv import load_dotenv

load_dotenv()

async def have_funds(request:Request,user:AuthenticatedUser=Depends(is_user_Authenticated) ,order:OrderReq=None )-> AsyncGenerator[AuthenticatedUser,None]:

    if order.ticker not in MARKET:
        raise HTTPException(status_code=404,detail="Ticker does not exist")

    multiplier = Decimal(os.getenv('SYSTEM_PRECISION_MULTIPLIER'))

    order_side = order.side
    scaled_order_quantity = order.number_of_shares * multiplier
    scaled_order_price = order.price * multiplier
    order_ticker = order.ticker
    order_user_id = user.user_id


    scaled_total = scaled_order_price*scaled_order_quantity

    retry_counter = 3

    redis_connection_port = request.app.state.redis

    async with redis_connection_port.pipeline() as pipeline:
        while retry_counter>0:
            try:
                if order_side == "buy":
                    await pipeline.watch(f'cache:portfolio:{order_user_id}')
                    available_cash = await pipeline.hget(f'cache:portfolio:{order_user_id}','available_cash')
                    locked_cash = await pipeline.hget(f'cache:portfolio:{order_user_id}','locked_balance')
                    scaled_safe_available_cash = Decimal(str(available_cash or 0))
                    scaled_safe_locked_cash = Decimal(str(locked_cash or 0))

                    
                    if scaled_total > scaled_safe_available_cash:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Not enough funds available for this trade you have {scaled_safe_available_cash/multiplier}")
                    else:
                        scaled_safe_available_cash -= scaled_total
                        scaled_safe_locked_cash += scaled_total
                        updates={
                            'available_cash' : int(scaled_safe_available_cash),
                            'locked_balance' : int(scaled_safe_locked_cash)
                        }
                        pipeline.multi()
                        pipeline.hset(f'cache:portfolio:{order_user_id}', mapping=updates)
                        await pipeline.execute()
                        break
                if order_side == "sell":
                    await pipeline.watch(f'cache:positions:{order_user_id}')
                    available_shares = await pipeline.hget(f'cache:positions:{order_user_id}', order_ticker)
                    locked_shares = await pipeline.hget(f'cache:positions:{order_user_id}', f'locked_{order_ticker}')

                    scaled_safe_available_shares = Decimal(str(available_shares or 0))
                    scaled_safe_locked_shares = Decimal(str(locked_shares or 0))

                    if scaled_order_quantity > scaled_safe_available_shares:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Not enough shares available for trade shares you have {scaled_safe_available_shares/multiplier} with user id {order_user_id}")
                    else:
                        safe_scaled_available_shares -= scaled_order_quantity
                        safe_scaled_locked_shares += scaled_order_quantity

                        updates ={
                            f'{order_ticker}' : safe_scaled_available_shares,
                            f'locked_{order_ticker}' : safe_scaled_locked_shares, 
                        }
                        pipeline.multi()
                        pipeline.hset(f'cache:positions:{order_user_id}', mapping=updates)
                        await pipeline.execute()
                        break
            except exp.WatchError:
                retry_counter -=1
                if retry_counter == 0:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Retry your order in few seconds")
                continue
    try:
        yield user
    except Exception as route_error:
        async with redis_connection_port.pipeline() as pipeline:
            if order_side == "sell":
                
                pipeline.hincrby(f'cache:positions:{order_user_id}', order_ticker,int(scaled_order_quantity))
                pipeline.hincrby(f'cache:positions:{order_user_id}', f'locked_{order_ticker}',-int(scaled_order_quantity))
            if order_side =="buy":
                pipeline.hincrby(f'cache:portfolio:{order_user_id}', 'available_cash', int(scaled_total))
                pipeline.hincrby(f'cache:portfolio:{order_user_id}', 'locked_balance', -int(scaled_total))

            await pipeline.execute()

        raise route_error