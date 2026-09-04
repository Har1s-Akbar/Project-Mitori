import requests
import redis
from seeding_script import mint_users_and_seed_cache, connect_and_sterilize_redis

def sterilize_environment():
    requests.post("http://localhost:8000/admin/reset", timeout=5.0)
    connect_and_sterilize_redis()
    r = redis.Redis
    mint_users_and_seed_cache(r)