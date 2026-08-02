import pytest
from decimal import Decimal
import json
from tests.testconfig import test_redis, test_request, order_factory, token_factory,seed_cash_factory,seed_shares_factory, async_client
import uuid
from core.models import Side

@pytest.mark.parametrize(
        "kyc_status , expires_in, expected_outcome",
        [
            (True, 15, 200),
            (False,15,403),
            (None,15,403),
            (True,-15,401)
        ],
        ids=["for_token_true", "for_token_false","for_token_None","for_token_expired"]
)
@pytest.mark.asyncio
async def test_secirity_features(
    async_client,
    order_factory,
    token_factory,
    seed_cash_factory,
    kyc_status , expires_in, expected_outcome
):
    user_id = str(uuid.uuid4())

    ticker = 'APP'
    price = Decimal("10")
    number_of_shares = Decimal("150")

    
    await seed_cash_factory(owner_id=user_id,available_cash=Decimal("2000"))
    valid_token = token_factory(user_id=user_id,kyc_verified=kyc_status, expires_in_minutes=expires_in)

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


    assert response.status_code == expected_outcome, f"Route failed: {response.text}"

@pytest.mark.parametrize(
    "side , set_cash, set_shares, expected_outcome",
    [
        (Side.BUY, "10000", "0", 200),
        (Side.SELL, "0", "200", 200),
        (Side.BUY, "10","0",400),
        (Side.SELL, "0","10",400)
    ],
    ids=["happy_path_for_buy","happy_path_for_sell", "insuficient_buy_side", "insuficient_sell_side"]
)

@pytest.mark.asyncio
async def testing_order_route_with_happy_paths_and_edgecase(
    async_client,
    order_factory,
    token_factory,
    seed_shares_factory,
    side,
    set_cash,
    set_shares,
    expected_outcome,
    seed_cash_factory
):
    user_id = str(uuid.uuid4())

    ticker = 'APP'
    price = Decimal("10")
    number_of_shares = Decimal("150")

    await seed_cash_factory(owner_id=user_id,available_cash=Decimal(set_cash))    
    await seed_shares_factory(owner_id=user_id,shares=Decimal(set_shares),ticker=ticker)
    valid_token = token_factory(user_id=user_id,kyc_verified=True)

    order = order_factory(
        ticker=ticker,
        side=side,
        price=price,
        number_of_shares=number_of_shares,
        order_owner_id=user_id
    )

    response = await async_client.post(
        "/order",
        json=order.model_dump(mode="json"),
        headers={"Authorization": f"Bearer {valid_token}"}
    )


    assert response.status_code == expected_outcome, f"Route failed: {response.text}"


