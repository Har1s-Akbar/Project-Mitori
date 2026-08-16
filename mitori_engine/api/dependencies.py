from fastapi import Request, HTTPException
import redis.asyncio as redis
from core.manager_cpp import engine_registry
from core.gateway import MitoriGateway
from schemas.schema import OrderReq

async def get_redis(requests:Request) ->redis.Redis:
    return requests.app.state.redis

def get_matching_engine(order: OrderReq) -> MitoriGateway:
    try:
        return engine_registry.get_engine(order.ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))