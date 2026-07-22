from fastapi import HTTPException, status
from fastapi import Request
from api.security import is_user_Authenticated, AuthenticatedUser
from fastapi import Depends
from schemas.schema import OrderReq
from decimal import Decimal
import redis.exceptions as exp

async def have_funds(request:Request,user:AuthenticatedUser=Depends(is_user_Authenticated) ,order:OrderReq=None ):
    order_side = order.side
    order_quantity = order.number_of_shares
    order_price = order.price
    order_ticker = order.ticker
    order_user_id = user.user_id

    retry_counter = 3

    redis_connection_port = request.app.state.redis

    async with redis_connection_port.pipeline() as pipeline:
        while retry_counter>0:
            try:
                if order_side == "buy":
                    await pipeline.watch(f'cache:portfolio:{order_user_id}')
                    available_cash = await pipeline.hget(f'cache:portfolio:{order_user_id}','available_cash')
                    locked_cash = await pipeline.hget(f'cache:portfolio:{order_user_id}','locked_balance')
                    safe_available_cash = Decimal(available_cash or 0)
                    safe_locked_cash = Decimal(locked_cash or 0)

                    total = order_quantity*order_price
                    if total > safe_available_cash:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Not enough funds available for this trade you have {safe_available_cash}")
                    else:
                        safe_available_cash -= total
                        safe_locked_cash += total
                        updates={
                            'available_cash' : str(safe_available_cash),
                            'locked_balance' : str(safe_locked_cash)
                        }
                        pipeline.multi()
                        pipeline.hset(f'cache:portfolio:{order_user_id}', mapping=updates)
                        await pipeline.execute()
                        break
                if order_side == "sell":
                    await pipeline.watch(f'cache:position:{order_user_id}')
                    available_shares = await pipeline.hget(f'cache:positions:{order_user_id}', order_ticker)
                    locked_shares = await pipeline.hget(f'cache:positions:{order_user_id}', f'locked_{order_ticker}')

                    safe_available_shares = int(Decimal(available_shares or 0))
                    safe_locked_shares = int(Decimal(locked_shares or 0))
                    if order_quantity > safe_available_shares:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Not enough shares available for trade shares you have {safe_available_shares} with user id {order_user_id}")
                    else:
                        safe_available_shares -= order_quantity
                        safe_locked_shares += order_quantity

                        updates ={
                            f'{order_ticker}' : safe_available_shares,
                            f'locked_{order_ticker}' : safe_locked_shares, 
                        }
                        pipeline.multi()
                        pipeline.hset(f'cache:position:{order_user_id}', mapping=updates)
                        await pipeline.execute()
                        break
            except exp.WatchError:
                retry_counter -=1
                if retry_counter == 0:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Retry your order in few seconds")
                continue