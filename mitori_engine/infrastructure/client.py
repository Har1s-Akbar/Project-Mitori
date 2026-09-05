import redis.asyncio as redis
from redis.asyncio import ConnectionPool
import os 
from dotenv import load_dotenv

load_dotenv()

def create_redis_pool() -> ConnectionPool:
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    try:
        REDIS_DB_INDEX = int(os.getenv("REDIS_DB_INDEX", 1))
    except ValueError:
        REDIS_DB_INDEX = 1

    return ConnectionPool(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB_INDEX,
        decode_responses=True,
        max_connections=3000,          
        socket_connect_timeout=5.0,     
        socket_timeout=10.0,
        retry_on_timeout=True,
        health_check_interval=30,
    )