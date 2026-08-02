import redis.asyncio as redis
from redis.asyncio import BlockingConnectionPool
import os 
from dotenv import load_dotenv

load_dotenv()

def create_redis_pool () -> BlockingConnectionPool:
    REDIS_HOST = os.getenv("REDIS_HOST") or os.getenv("REDIS") or "localhost"
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    db_index = int(os.getenv("REDIS_DB_INDEX", 0))
    return BlockingConnectionPool(
        host = REDIS_HOST,
        port = REDIS_PORT,
        db = db_index,
        decode_responses=True,
        max_connections=15,
        socket_connect_timeout=2.0,
        socket_timeout=5.0,
        retry_on_timeout=True,
        health_check_interval=30,
    )

