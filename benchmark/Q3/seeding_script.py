import os
import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from enum import Enum
import jwt
import redis
import numpy as np
import orjson
import sys

class Type(str, Enum):
    MARKET = "market"
    LIMIT = "limit"

class Side(str, Enum):
    SELL = "sell"
    BUY = "buy"

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
raw_db_index = os.getenv("REDIS_DB_INDEX", 1)

try:
    REDIS_DB_INDEX = int(raw_db_index)
except ValueError:
    REDIS_DB_INDEX = 1

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "mitori_shared_secret_super_secure_32bytes_key!")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

NUM_USERS = 20_000
WARMUP_ORDERS = 5_000
TEST_ORDERS = 150_000

TICKER = "APP"
CENTER_VALUE = 100.00
THETA = 0.10
SIGMA = 0.50
DT = 1.0
SEED = 39

OUTPUT_DIR = "benchmark/data/data_for_test"

USER_NAMESPACE = uuid.UUID('12345678-1234-5678-1234-567812345678')

def connect_and_sterilize_redis() -> redis.Redis:
    r = redis.Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        db=REDIS_DB_INDEX, 
        decode_responses=True
    )
    try:
        r.ping()
    except redis.ConnectionError as e:
        print(f"ERROR: Cannot connect to Redis at {REDIS_HOST}:{REDIS_PORT} - {e}", file=sys.stderr)
        sys.exit(1)
        
    print(f"Sterilizing Redis (FLUSHALL) on {REDIS_HOST}:{REDIS_PORT}...")
    r.flushall()
    return r

def mint_users_and_seed_cache(r: redis.Redis) -> list[str]:
    print(f"Minting {NUM_USERS} deterministic users and populating balances...")
    SYSTEM_MULTIPLIER = 100_000_000  # 10^8

    raw_cash = 1_000_000 * SYSTEM_MULTIPLIER     
    raw_shares = 10_000 * SYSTEM_MULTIPLIER      
    user_tokens = []
    pipeline = r.pipeline(transaction=False)
    static_exp = datetime.now(timezone.utc) + timedelta(days=30)
    
    for i in range(1, NUM_USERS + 1):
        user_uuid = str(uuid.uuid5(USER_NAMESPACE, f"user_{i}"))
        
        payload = {
            "token_type": "access",
            "jti": str(uuid.uuid5(USER_NAMESPACE, f"jti_{i}")),
            "user_id": user_uuid,
            "is_kyc_verified": True,
            "exp": static_exp
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
        user_tokens.append(token)
        
        pipeline.hset(f"cache:portfolio:{user_uuid}", mapping={
            "available_cash": str(raw_cash),
            "locked_balance": "0"
        })
        pipeline.hset(f"cache:positions:{user_uuid}", mapping={
            "APP": str(raw_shares),
            "locked_APP": "0"
        })
        
        if i % 5000 == 0:
            pipeline.execute()
            
    pipeline.execute()
    print("Redis cache pre-hydration complete.")
    return user_tokens

def generate_order_stream(tokens: list[str], count: int, rng: np.random.Generator) -> list[dict]:
    """
    Synthesizes a realistic, reproducible order sequence using an Ornstein-Uhlenbeck
    stochastic process and tight share distributions to protect resting liquidity.
    """
    prices = np.zeros(count)
    prices[0] = CENTER_VALUE
    shocks = rng.normal(0, 1, count)
    
    for t in range(1, count):
        prices[t] = prices[t-1] + THETA * (CENTER_VALUE - prices[t-1]) * DT + SIGMA * shocks[t] * np.sqrt(DT)
        
    types = rng.choice([Type.MARKET.value, Type.LIMIT.value], size=count, p=[0.5, 0.5])
    sides = rng.choice([Side.BUY.value, Side.SELL.value], size=count)
    quantities = rng.integers(1, 26, size=count) 
    assigned_tokens = rng.choice(tokens, size=count)
    
    if count >= 1000:
        types[:1000] = Type.LIMIT.value
        
    orders = []
    for i in range(count):
        order_type = types[i]
        side = sides[i]
        
        payload = {
            "ticker": TICKER,
            "type": order_type,
            "side": side,
            "number_of_shares": str(quantities[i])
        }
        
        if order_type == Type.LIMIT.value:
            abs_diff = abs(prices[i] - CENTER_VALUE)
            raw_price = (CENTER_VALUE - abs_diff - 0.01) if side == Side.BUY.value else (CENTER_VALUE + abs_diff + 0.01)
            d_price = Decimal(str(raw_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            payload["price"] = str(d_price)

        orders.append({
            "token": assigned_tokens[i],
            "payload": payload
        })
        
    return orders

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    r = connect_and_sterilize_redis()
    user_tokens = mint_users_and_seed_cache(r)
    
    rng = np.random.default_rng(SEED)
    
    print(f"Generating {WARMUP_ORDERS} warmup orders...")
    warmup_data = generate_order_stream(user_tokens, WARMUP_ORDERS, rng)
    warmup_path = os.path.join(OUTPUT_DIR, "warmup.json")
    with open(warmup_path, "wb") as f:
        f.write(orjson.dumps(warmup_data, option=orjson.OPT_APPEND_NEWLINE))
    print(f"  -> Wrote {warmup_path}")
        
    print(f"Generating {TEST_ORDERS} test orders...")
    test_data = generate_order_stream(user_tokens, TEST_ORDERS, rng)
    test_path = os.path.join(OUTPUT_DIR, "test.json")
    with open(test_path, "wb") as f:
        f.write(orjson.dumps(test_data, option=orjson.OPT_APPEND_NEWLINE))
    print(f"  -> Wrote {test_path}")
        
    print(f"Phase A data seeding complete. Files ready in {OUTPUT_DIR}/")

if __name__ == "__main__":
    main()