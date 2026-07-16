from fastapi import Request
import redis.asyncio as redis

async def get_redis(requests:Request) ->redis.Redis:
    return requests.app.state.redis