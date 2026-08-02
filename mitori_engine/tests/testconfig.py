import os
import uuid
import pytest
import pytest_asyncio
import redis.asyncio as redisasync
import jwt
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from dotenv import load_dotenv

from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport

from main import app
from schemas.schema import OrderReq
from core.models import Side

load_dotenv()

# BUG FIX 1: Cast the string environment variable to an integer
MULTIPLIER = int(os.getenv("SYSTEM_PRECISION_MULTIPLIER", 100000000))

@pytest_asyncio.fixture(scope="function")
async def test_redis():
    """Single source of truth for the DB 1 test Redis client."""
    client = redisasync.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)), 
        db=1, 
        decode_responses=True
    )
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
def test_request(test_redis):
    """
    Brilliant mock of the FastAPI Request object.
    Injects the test_redis client cleanly into app.state.redis.
    """
    class MockState:
        def __init__(self, redis_conn):
            self.redis = redis_conn

    class MockApp:
        def __init__(self, redis_conn):
            self.state = MockState(redis_conn)

    class MockRequest:
        def __init__(self, redis_conn):
            self.app = MockApp(redis_conn)

    return MockRequest(test_redis)


@pytest.fixture
def order_factory():
    def _order_create(ticker: str, side: Side, price: Decimal, number_of_shares: Decimal, order_owner_id: uuid.UUID):
        return OrderReq(
            ticker=ticker,
            side=side,  
            price=price,
            number_of_shares=number_of_shares,
            order_owner_id=order_owner_id
        )
    return _order_create

@pytest.fixture
def token_factory():
    def _generate(user_id: str = "user-12345", kyc_verified: bool = True, expires_in_minutes: int = 15) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "token_type": "access",
            "exp": now + timedelta(minutes=expires_in_minutes),
            "iat": now,
            "jti": "mock_jti_string",
            "user_id": user_id,
            "is_kyc_verified": kyc_verified 
        }
        secret = os.getenv("JWT_SECRET_KEY", "fallback_secret")
        algorithm = os.getenv("ALGORITHM", "HS256")
        return jwt.encode(payload, secret, algorithm=algorithm)
    return _generate

@pytest_asyncio.fixture
async def seed_cash_factory(test_redis):
    async def _seeding(owner_id: str, available_cash: Decimal):
        stream_key = f'cache:portfolio:{owner_id}'
        set_values = {
            'available_cash': int(available_cash * MULTIPLIER),
            'locked_balance': int(0)
        }
        await test_redis.hset(stream_key, mapping=set_values)
    return _seeding

@pytest_asyncio.fixture
async def seed_shares_factory(test_redis):
    async def _seeding(owner_id: str, shares: Decimal, ticker: str):
        stream_key = f'cache:positions:{owner_id}'
        set_values = {
            f'{ticker}': int(shares * MULTIPLIER),
            f'locked_{ticker}': int(0)
        }
        await test_redis.hset(stream_key, mapping=set_values)
    return _seeding


@pytest_asyncio.fixture(scope="function")
async def async_client():
    # BUG FIX 4: Patch os.environ, not os.getenv
    with patch.dict(os.environ, {"REDIS_DB_INDEX": "1"}):
        async with LifespanManager(app) as manager:
            transport = ASGITransport(app=manager.app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                yield client