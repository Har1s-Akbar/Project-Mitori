from fastapi import HTTPException, status
from pydantic import BaseModel
from fastapi import Request
from typing import Annotated
from api.security import is_user_Authenticated, AuthenticatedUser
from fastapi import Depends
from schemas.schema import OrderReq
from decimal import Decimal

async def have_funds(request:Request,user:AuthenticatedUser=Depends(is_user_Authenticated) ,order:OrderReq=None ):
    order_side = order.side
    order_quantity = order.number_of_shares
    order_price = order.price
    order_ticker = order.ticker
    order_user_id = user.user_id

    redis_connection_port = request.app.state.redis

    if order_side == "buy":
        available_cash = await redis_connection_port.hget(f'cache:portfolio:{order_user_id}','available_cash')
        locked_cash = await redis_connection_port.hget(f'cache:portfolio:{order_user_id}','locked_balance')
        safe_available_cash = Decimal(available_cash or 0)
        safe_locked_cash = Decimal(locked_cash or 0)
        total = order_quantity*order_price
        if total > safe_available_cash:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough funds available for this trade")
        else:
            safe_available_cash -= total
            safe_locked_cash += total
            updates={
                'available_cash' : str(safe_available_cash),
                'locked_balance' : str(safe_locked_cash)
            }
            await redis_connection_port.hset(f'cache:portfolio:{order_user_id}', mapping=updates)

    if order_side == "sell":
        available_shares = await redis_connection_port.hget(f'cache:position:{order_user_id}', order_ticker)
        locked_shares = await redis_connection_port.hget(f'cache:position:{order_user_id}', f'locked_{order_ticker}')

        safe_available_shares = int(available_shares or 0)
        safe_locked_shares = int(locked_shares or 0)
        if order_quantity > safe_available_shares:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough shares available for trade")
        else:
            safe_available_shares -= order_quantity
            safe_locked_shares += order_quantity

            updates ={
                f'{order_ticker}' : safe_available_shares,
                f'locked_{order_ticker}' : safe_locked_shares, 
            }
            await redis_connection_port.hset(f'cache:position:{order_user_id}', mapping=updates)