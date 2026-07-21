from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from pydantic import Field
import uuid
import uvicorn
import redis.asyncio as redis
from infrastructure.client import create_redis_pool
from api.security import AuthenticatedUser , is_user_Authenticated
from api.dependencies import get_redis
import json
import dataclasses
from api.have_funds import have_funds
from schemas.schema import MARKET, OrderReq
from core.models import Order

@asynccontextmanager
async def lifespan(app:FastAPI):
    pool = create_redis_pool()
    app.state.redis = redis.Redis(connection_pool=pool)

    yield

    await app.state.redis.close();

app = FastAPI(
    title ="mitori-engine",
    discription = "fast paced matching engine for project mitori",
    version = "1.0.0",
    lifespan=lifespan
)


@app.post("/order", dependencies=[Depends(have_funds)])
async def place_order(order:OrderReq, 
                      redis_client : redis.Redis = Depends(get_redis)
                      ,current_user : AuthenticatedUser=Depends(is_user_Authenticated)):
    if order.ticker not in MARKET:
        raise HTTPException(status_code=404,detail="Ticker does not exist")
    target_book = MARKET[order.ticker]

    new_order = Order(
        ticker =  order.ticker,
        side = order.side,
        price = order.price,
        number_of_shares = order.number_of_shares,
        order_owner_id = uuid.UUID(current_user.user_id),
    )

    print(f"new order id {new_order.order_id}" )
    print(f" owner id is {new_order.order_owner_id}")

    target_book.add_order(new_order)
    executed_trades = target_book.execute()

    if executed_trades:
        for trade in executed_trades:
            trade_dict = dataclasses.asdict(trade)
            trade_data = {
                "ticker" : order.ticker,
                "data": json.dumps(trade_dict, default=str)
            }
            await redis_client.xadd(
                name="executed_trades_stream",
                fields=trade_data,
                maxlen=100000,
                approximate=True
            )

    return {
        "message":"Order Accepted",
        "trades":executed_trades
    }




if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)