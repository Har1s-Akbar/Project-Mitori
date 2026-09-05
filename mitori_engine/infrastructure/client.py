import redis.asyncio as redis
from redis.asyncio import BlockingConnectionPool
import os 
from dotenv import load_dotenv

load_dotenv()

def create_redis_pool () -> BlockingConnectionPool:
    REDIS_HOST = os.getenv("REDIS_HOST") or os.getenv("REDIS") or "localhost"
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    db_index = os.getenv("REDIS_DB_INDEX", 0)
    try:
        REDIS_DB_INDEX = int(db_index)
    except ValueError:
        REDIS_DB_INDEX = 0

    max_conn = int(os.getenv("REDIS_MAX_CONNECTIONS", 100))
    
    return BlockingConnectionPool(
        host = REDIS_HOST,
        port = REDIS_PORT,
        db = REDIS_DB_INDEX,
        decode_responses=True,
        max_connections=max_conn,
        socket_connect_timeout=2.0,
        socket_timeout=5.0,
        retry_on_timeout=True,
        health_check_interval=30,
    )

