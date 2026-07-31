import pytest
from tests.testconfig import redis_client, test_request
from api.have_funds import have_funds
from schemas.schema import OrderReq
from core.models import Side
from decimal import Decimal
import uuid
from api.security import AuthenticatedUser
from fastapi import HTTPException

@pytest.mark.asyncio
async def test_for_invalid_ticker(redis_client, test_request):

    user_id = uuid.uuid4()
    multiplier = Decimal(100000000)

    user = AuthenticatedUser(user_id= str(user_id), kyc_verified=True)

    order = OrderReq(
        ticker='gibberish',
        side=Side.SELL,
        price=Decimal(10),
        number_of_shares=Decimal(20),
        order_owner_id=user_id
    )

    with pytest.raises(HTTPException) as exec_info:
        async for authenticated_user in have_funds(request=test_request, user=user,order=order):
            authenticated_user.user_id == user.user_id
    assert exec_info.value.status_code == 404
    assert "Ticker does not exist" in exec_info.value.detail 