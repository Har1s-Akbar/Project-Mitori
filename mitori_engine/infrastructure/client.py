import redis.asyncio as redis
from redis.asyncio import BlockingConnectionPool

def create_redis_pool () -> BlockingConnectionPool:
    return BlockingConnectionPool(
        host = "localhost",
        port = 6379,
        db = 0,
        decode_responses=True,
        max_connections=15,
        socket_connect_timeout=2.0,
        socket_timeout=5.0,
        retry_on_timeout=True,
        health_check_interval=30,
    )

