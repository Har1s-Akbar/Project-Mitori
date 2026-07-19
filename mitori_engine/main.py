from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
import uuid
import uvicorn
from core.models import Side, Order
from core.engine import OrderBook
import redis.asyncio as redis
from infrastructure.client import create_redis_pool
from api.security import AuthenticatedUser , is_user_Authenticated
from api.dependencies import get_redis
import json
import dataclasses

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

MARKET ={
    "APP": OrderBook("APP"),
    "TSLA": OrderBook("TSLA"),
    "AUX":OrderBook("AUX")
}

class OrderReq(BaseModel):
    order_id :uuid.UUID = Field(default_factory=uuid.uuid4) 
    ticker:str = Field(min_length=1, max_length=10, title="Ticker", description="Ticker is required", strict=True)
    side:Side = Field(title="side" , description="Side is required")
    price:float = Field(ge=1, lt=1000000000.0, allow_inf_nan=False, strict=True)
    number_of_shares:int = Field(ge=1, lt=2000, allow_inf_nan=False, strict=True)
    order_owner_id :uuid.UUID | None  = None


@app.post("/order")
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
        order_id = order.order_id,
    )

    print(new_order.order_id )
    print(new_order.order_owner_id)

    target_book.add_order(new_order)
    executed_trades = target_book.execute()

    if executed_trades:
        for trade in executed_trades:
            trade_dict = dataclasses.asdict(trade)
            trade_data = {
                "ticker" : order.ticker,
                "data": json.dumps(trade_dict)
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