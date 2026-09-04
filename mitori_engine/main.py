from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status, Request, Response
from pydantic import Field
import uuid
import uvicorn
import redis.asyncio as redis
from infrastructure.client import create_redis_pool
from api.security import AuthenticatedUser
from api.check_ownership import check_owner_ship

from api.dependencies import get_redis, get_matching_engine
from core_python.interfaces import EngineProtocol
from core_python.config import ALLOWED_TICKERS

import json
import dataclasses
from api.have_funds import have_funds
from schemas.schema import MARKET, OrderReq
from core_python.models import Order, Side

from dotenv import load_dotenv
from logger import configure_fastapi_logging
import structlog
import time


load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
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
    description = "fast paced matching engine for project mitori",
    version = "1.0.0",
    lifespan=lifespan
)

logger = structlog.getLogger(__name__)

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    if request.url.path in ["/health", "/metrics", "/docs", "/openapi.json"]:
        return await call_next(request)

    structlog.contextvars.clear_contextvars()
    correlation_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id,
        path = request.url.path
    )
    start_time = time.perf_counter_ns()
    try:
        response = await call_next(request)
        process_time = time.perf_counter_ns() - start_time
        response.headers["X-Total-Process-NS"] = str(process_time)
        
        logger.info(
            "http_request_processed",
            status_code = response.status_code,
            duration_ns= process_time
        )
        return response
    except Exception as e:
        process_time = time.perf_counter_ns() - start_time
        logger.exception(
            "http_request_failed",
            duration_ns=process_time
        )
        raise

@app.post("/order")
async def place_order(
    order: OrderReq,
    response: Response,
    # engine : EngineProtocol = Depends(get_matching_engine),
    redis_client: redis.Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(have_funds),
):
    ticker = order.ticker
    engine = get_matching_engine(ticker=ticker)
    new_order_id = uuid.uuid4()

    executed_trades, engine_latency_ns = engine.submit_order(
            ticker = order.ticker,
            side = order.side,
            order_id=new_order_id,
            type = order.type,
            price = order.price,
            number_of_shares = order.number_of_shares,
            order_owner_id = uuid.UUID(current_user.user_id),
            is_canceled=False,
            max_authorized_funds=order.max_authorized_funds
        )
    response.headers["X-Engine-Latency-NS"] = str(engine_latency_ns)

    if executed_trades:
        current_context = structlog.contextvars.get_contextvars()
        correlation_id = current_context.get("correlation_id", "fallback_id")

        async with redis_client.pipeline() as pipe:
            for trade in executed_trades:
                trade_dict = dataclasses.asdict(trade)
                trade_dict['correlation_id'] = correlation_id
                trade_data = {
                    "ticker": order.ticker,
                    "data": json.dumps(trade_dict, default=str)
                }
                
                pipe.xadd(
                    name="executed_trades_stream",
                    fields=trade_data,
                    maxlen=100000,
                    approximate=True
                )
                
            current_bbo = engine.get_bbo()
            pipe.hset(f'ticker:{order.ticker}:bbo', mapping=current_bbo)
            
            await pipe.execute()
            
        logger.info("trades_pushed_to_stream", order_id=new_order_id, ticker=order.ticker, trade_count=len(executed_trades))
        
    return {
        "message": "Order Accepted",
        "order_id": new_order_id,
        "trades": executed_trades
    }

@app.delete("/order/{ticker}/{order_id}")
async def delete_order(
    order_id: str, 
    ticker: str,
    engine : EngineProtocol = Depends(get_matching_engine),
    redis_client: redis.Redis = Depends(get_redis), 
    current_user: AuthenticatedUser = Depends(check_owner_ship)
):
    
    order_canceled = engine.cancel_order(uuid.UUID(order_id))

    if not order_canceled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order does not exist")
    current_context = structlog.contextvars.get_contextvars()
    correlation_id = current_context.get("correlation_id", "fallback_id")
    user_id = str(order_canceled.order_owner_id)
    
    async with redis_client.pipeline() as pipeline:
        cancelled_trade_dict = dataclasses.asdict(order_canceled)
        cancelled_trade_dict['correlation_id'] = correlation_id

        cancelled_trade_data = {
            "ticker": ticker,
            "data": json.dumps(cancelled_trade_dict, default=str)
        }
        
        if order_canceled.side == Side.SELL:
            number_of_shares_safe = order_canceled.number_of_shares
            pipeline.hincrby(f'cache:positions:{user_id}', ticker, number_of_shares_safe)
            pipeline.hincrby(f'cache:positions:{user_id}', f'locked_{ticker}', -number_of_shares_safe)
            
        elif order_canceled.side == Side.BUY:
            total_price = (order_canceled.price * order_canceled.number_of_shares) // 100000000
            
            pipeline.hincrby(f'cache:portfolio:{user_id}', 'available_cash', total_price)
            pipeline.hincrby(f'cache:portfolio:{user_id}', 'locked_balance', -total_price)

        pipeline.xadd(
            name="cancelled_order_stream", 
            fields=cancelled_trade_data, 
            maxlen=100000,
            approximate=True
        )
            
        await pipeline.execute()
        
    logger.info("cancelled_trade_pushed_to_stream", order_id=order_id, ticker=ticker)
    
    return {
        "message": f'Order with id {order_id} was cancelled and funds are returned',
        "status": status.HTTP_200_OK
    }

@app.post("/admin/reset")
async def reset_engine_state():
    for ticker in ALLOWED_TICKERS:
        engine = get_matching_engine(ticker=ticker)
        engine.reset_engine()
    return {"status": "cleared"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)