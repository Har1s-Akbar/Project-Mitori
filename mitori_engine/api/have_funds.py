
from pydantic import BaseModel
from fastapi import Request
from typing import Annotated
from api.security import is_user_Authenticated, AuthenticatedUser
from fastapi import Depends
from schemas.schema import OrderReq

async def have_funds(request:Request,user:AuthenticatedUser=Depends(is_user_Authenticated) ,order:OrderReq=None ):
    order_side = order.side
    order_quantity = order.number_of_shares
    order_price = order.price
    order_ticker = order.ticker
    order_user_id = user.user_id

    redis_connection_port = request.app.state.redis

    portfolio = await redis_connection_port.get(f'cache:portfolio:{order_user_id}')
    print(portfolio)