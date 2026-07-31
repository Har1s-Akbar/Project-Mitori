import pytest
import redis.asyncio as redisasync
from fastapi import Request


@pytest.fixture(scope="function")
async def redis_client():
    client = redisasync.Redis(host='redis',port=6379, db=1, decode_responses=True)
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
