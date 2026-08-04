from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status, Request
from pydantic import Field
import uuid
import uvicorn
import redis.asyncio as redis
from infrastructure.client import create_redis_pool
from api.security import AuthenticatedUser , is_user_Authenticated
from api.check_ownership import check_owner_ship
from api.dependencies import get_redis
import json
import dataclasses
from api.have_funds import have_funds
from schemas.schema import MARKET, OrderReq
from core.models import Order, Side
import os
from dotenv import load_dotenv
from decimal import Decimal
from .logger import configure_fastapi_logging
import structlog
import time 

load_dotenv()

@asynccontextmanager
async def lifespan(app:FastAPI):
    configure_fastapi_logging()
    logger = structlog.getLogger(__name__)
    logger.info("Mitori_Engine_Booting")

    pool = create_redis_pool()
    app.state.redis = redis.Redis(connection_pool=pool)
    
    yield

    logger.info("Mitori_Engine_Shutting_Down")
    await app.state.redis.aclose()

app = FastAPI(
    title ="mitori-engine",
    discription = "fast paced matching engine for project mitori",
    version = "1.0.0",
    lifespan=lifespan
)

logger = structlog.getLogger(__name__)

@app.middleware("httpx")
async def logging_middleware(request:Request, call_next):
    if request.url.path in ["/health", "/metrics", "/docs", "/openapi.json"]:
        return call_next(request)

    structlog.contextvars.clear_contextvars()
    correlation_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id,
        path = request.url.path
    )
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        process_time = time.perf_counter() = start_time
        logger.info(
            "http_request_processed",
            status_code = response.status_code,
            duration_ms= round(process_time*1000,2)
        )
        return response
    except Exception as e:
        process_time = time.perf_counter() - start_time
        logger.exception(
            "http_request_failed",
            duration_ms=round(process_time*1000,2)
        )
        raise


@app.post("/order")
async def place_order(order:OrderReq, 
                      redis_client : redis.Redis = Depends(get_redis)
                      ,current_user : AuthenticatedUser=Depends(have_funds)):

    target_book = MARKET[order.ticker]
    multiplier = Decimal(os.getenv('SYSTEM_PRECISION_MULTIPLIER'))

    price_scaled_up = int(order.price* multiplier)
    shares_scaled_up = int(order.number_of_shares * multiplier)

    new_order = Order(
        ticker =  order.ticker,
        side = order.side,
        price = price_scaled_up,
        number_of_shares = shares_scaled_up,
        order_owner_id = uuid.UUID(current_user.user_id),
        is_canceled=False,
    )


    target_book.add_order(new_order)
    executed_trades = target_book.execute()

    if executed_trades:
        current_context = structlog.contextvars.get_contextvars()
        correlation_id = current_context("correlation_id", "fallback_id")


        for trade in executed_trades:
            trade_dict = dataclasses.asdict(trade)
            trade-dict['correlation_id'] = correlation_id
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
            logger.info("trade_pushed_to_stream", trade_id=trade.trade_id, ticker=order.ticker)
    return {
        "message":"Order Accepted",
        "order Id" : new_order.order_id,
        "trades":executed_trades
    }


@app.delete("/order/{ticker}/{order_id}")
async def delete_order(order_id : str, ticker:str,redis_client : redis.Redis = Depends(get_redis), 
                       current_user : AuthenticatedUser = Depends(check_owner_ship)):

    multiplier = Decimal(os.getenv('SYSTEM_PRECISION_MULTIPLIER'))
    market = MARKET.get(ticker,None)
    order_canceled = market.tombstone_delete(order_id)

    if not order_canceled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order does not exist")

    user_id = str(order_canceled.order_owner_id)
    pipeline = redis_client.pipeline()
    async with pipeline:
        cancelled_trade_dict = dataclasses.asdict(order_canceled)
        cancelled_trade_data = {
            "ticker" : ticker,
            "data": json.dumps(cancelled_trade_dict, default=str)
        }
        if order_canceled.side == Side.SELL:
                number_of_shares_safe = int(order_canceled.number_of_shares)
                pipeline.hincrby(f'cache:positions:{user_id}',ticker,number_of_shares_safe)
                pipeline.hincrby(f'cache:positions:{user_id}',f'locked_{ticker}', -number_of_shares_safe)
        elif order_canceled.side == Side.BUY:
            
            total_price = int((order_canceled.price/multiplier) * (order_canceled.number_of_shares/multiplier)* multiplier)
            pipeline.hincrby(f'cache:portfolio:{user_id}','available_cash', total_price)
            pipeline.hincrby(f'cache:portfolio:{user_id}',f'locked_balance', -total_price)

        pipeline.xadd(name="cancelled_order_stream", 
                            fields=cancelled_trade_data, 
                            maxlen=100000,
                            approximate=True)
            
        await pipeline.execute()

    return{
        "message" : f'Order with id {order_id} was cancelled and funds are returned',
        "status": status.HTTP_200_OK
    }

            
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)