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
    order_quantity = order.number_of_shares
    order_price = order.price
    order_ticker = order.ticker
    order_user_id = user.user_id

    total = int(order_price*order_quantity*multiplier)


    retry_counter = 3

    redis_connection_port = request.app.state.redis

    async with redis_connection_port.pipeline() as pipeline:
        while retry_counter>0:
            try:
                if order_side == "buy":
                    await pipeline.watch(f'cache:portfolio:{order_user_id}')
                    available_cash = await pipeline.hget(f'cache:portfolio:{order_user_id}','available_cash')
                    locked_cash = await pipeline.hget(f'cache:portfolio:{order_user_id}','locked_balance')
                    safe_available_cash = Decimal(str(available_cash or 0))
                    safe_locked_cash = Decimal(str(locked_cash or 0))

                    if total > safe_available_cash:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Not enough funds available for this trade you have {safe_available_cash/multiplier}")
                    else:
                        updates={
                            'available_cash' : safe_available_cash-total,
                            'locked_balance' : safe_locked_cash+total
                        }
                        pipeline.multi()
                        pipeline.hset(f'cache:portfolio:{order_user_id}', mapping=updates)
                        await pipeline.execute()
                        break
                if order_side == "sell":
                    await pipeline.watch(f'cache:positions:{order_user_id}')
                    available_shares = await pipeline.hget(f'cache:positions:{order_user_id}', order_ticker)
                    locked_shares = await pipeline.hget(f'cache:positions:{order_user_id}', f'locked_{order_ticker}')

                    safe_available_shares = Decimal(str(available_shares or 0))
                    safe_locked_shares = Decimal(str(locked_shares or 0))
                    order_quantity_scaled = order_quantity*multiplier

                    if order_quantity_scaled > safe_available_shares:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Not enough shares available for trade shares you have {safe_available_shares} with user id {order_user_id/multiplier}")
                    else:
                        updates ={
                            f'{order_ticker}' : safe_available_shares-order_quantity_scaled,
                            f'locked_{order_ticker}' : safe_locked_shares+order_quantity_scaled, 
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
                pipeline.hincrby(f'cache:positions:{order_user_id}', order_ticker,int(order_quantity*multiplier))
                pipeline.hincrby(f'cache:positions:{order_user_id}', f'locked_{order_ticker}',-int(order_quantity*multiplier))
            if order_side =="buy":
                pipeline.hincrby(f'cache:portfolio:{order_user_id}', 'available_cash',total)
                pipeline.hincrby(f'cache:portfolio:{order_user_id}', 'locked_balance', total)

            await pipeline.execute()

        raise route_error