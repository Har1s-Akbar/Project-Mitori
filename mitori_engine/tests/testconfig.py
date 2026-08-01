import pytest
import redis.asyncio as redisasync
from fastapi import Request
from schemas.schema import OrderReq
from core.models import Side
from decimal import Decimal
import uuid
import os
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from api.security import AuthenticatedUser, is_user_Authenticated

load_dotenv()

@pytest.fixture(scope="function")
async def redis_client():
    client = redisasync.Redis(host=os.getenv("REDIS_HOST"),port=os.getenv("RREDIS_PORT"), db=1, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()

#This is the exact structure our have_funds.py expect for the request or we can use 
# simpleNamespace for this purpose but i am going to leave this as it is.
@pytest.fixture
def test_request(redis_client):
    class Mockstate:
        def __init__(self,redis):
            self.redis = redis

    class MockApp:
        def __init__(self,redis):
            self.state = Mockstate(redis)

    class MockRequest:
        def __init__(self,redis):
            self.app = MockApp(redis)

    return MockRequest(redis_client)

@pytest.fixture(scope="function")
def testOrder(ticker:str, side:Side, price:Decimal,number_of_shares:Decimal, order_owner_id:uuid):
    order = OrderReq(
        ticker=ticker,
        side=side.BUY,
        price=price,
        number_of_shares=number_of_shares,
        order_owner_id=order_owner_id
    )

    return order

def generate_django_access_token(    
    user_id: str = "user-12345", 
    kyc_verified: bool = True or None, 
    expires_in_minutes: int = 15,
    secret: str = os.getenv("JWT_SECRET_KEY")) -> str:
    
        now = datetime.now(timezone.utc)
        payload = {
            "token_type": "access",
            "exp": now + timedelta(minutes=expires_in_minutes),
            "iat": now,
            "jti": "mock_jti_string",
            "user_id": user_id,
            "is_kyc_verified": kyc_verified  # Matches security.py expectation
        }
        return jwt.encode(payload, secret, algorithm=os.getenv("ALGORITHM"))

@pytest.fixture(scope="function")
def decode_jwt_token(
    user_id: str = "user-12345", 
    kyc_verified: bool = True or None, 
    expires_in_minutes: int = 15,
    ) -> AuthenticatedUser:
    valid_token = generate_django_access_token(user_id,kyc_verified)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer",credentials=valid_token)

    return is_user_Authenticated(credentials=credentials)
