import os
import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from enum import Enum
import jwt
import redis
import numpy as np
import orjson

class Type(str, Enum):
    MARKET = "market"
    LIMIT = "limit"

class Side(str, Enum):
    SELL = "sell"
    BUY = "buy"

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "mitori_shared_secret")
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

OUTPUT_DIR = "benchmark/data_for_test"

def connect_and_sterilize_redis() -> redis.Redis:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=1, decode_responses=True)
    print("Redis cache (FLUSHALL)...")
    r.flushall()
    return r

def mint_users_and_seed_cache(r: redis.Redis) -> list[str]:
    print(f"Minting {NUM_USERS} users and pipelining balances to Redis cache...")
    user_tokens = []
    pipeline = r.pipeline(transaction=False)
    
    static_exp = datetime.now(timezone.utc) + timedelta(days=30)
    
    for i in range(1, NUM_USERS + 1):
        user_uuid = str(uuid.uuid4())
        
        payload = {
            "token_type": "access",
            "jti": str(uuid.uuid4()),
            "user_id": user_uuid,
            "kyc_verified": True,
            "exp": static_exp
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
        user_tokens.append(token)
        
        # Hydrate cash liquidity (1,000,000.00 cash)
        pipeline.hset(f"cache:portfolio:{user_uuid}", mapping={
            "balance": "1000000.00000000",
            "locked_balance": "0.00000000"
        })
        # Hydrate asset liquidity (10,000 shares of APP)
        pipeline.hset(f"cache:positions:{user_uuid}:{TICKER}", mapping={
            "shares": "10000.00000000",
            "locked_shares": "0.00000000"
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
            safe_price = (CENTER_VALUE - abs_diff - 0.01) if side == Side.BUY.value else (CENTER_VALUE + abs_diff + 0.01)
            payload["price"] = safe_price
            
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
    with open(f"{OUTPUT_DIR}/warmup.json", "wb") as f:
        f.write(orjson.dumps(warmup_data, option=orjson.OPT_APPEND_NEWLINE))
        
    print(f"Generating {TEST_ORDERS} test orders...")
    test_data = generate_order_stream(user_tokens, TEST_ORDERS, rng)
    with open(f"{OUTPUT_DIR}/test.json", "wb") as f:
        f.write(orjson.dumps(test_data, option=orjson.OPT_APPEND_NEWLINE))
        
    print(f"Phase A successfully written to {OUTPUT_DIR}/")

if __name__ == "__main__":
    main()