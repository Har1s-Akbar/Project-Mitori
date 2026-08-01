import pytest
from decimal import Decimal
import json
from tests.testconfig import test_redis, test_request, order_factory, token_factory,seed_cash_factory,seed_shares_factory, async_client
import uuid
from core.models import Side

@pytest.mark.asyncio
async def test_order_route(
    async_client,
    test_request,
    test_redis,
    order_factory,
    token_factory,
    seed_cash_factory,
    seed_shares_factory
):
    multiplier = Decimal("100000000")
    user_id = str(uuid.uuid4())
    kyc_verified = True

    ticker = 'APP'
    price = Decimal("10")
    sacled_price = int(Decimal("10")*multiplier)
    number_of_shares = Decimal("150")
    scaled_number_of_shares = int(Decimal("150")*multiplier)

    required_cash = int(price*number_of_shares)

    await seed_cash_factory(owner_id=user_id,available_cash=Decimal("2000"))
    valid_token = token_factory(user_id=user_id,kyc_verified=True)

    order = order_factory(
        ticker=ticker,
        side=Side.BUY,
        price=price,
        number_of_shares=number_of_shares,
        order_owner_id=user_id
    )

    response = await async_client.post(
        "/order",
        json=order.model_dump(mode="json"),
        headers={"Authorization": f"Bearer {valid_token}"}
    )


    assert response.status_code == 200, f"Route failed: {response.text}"