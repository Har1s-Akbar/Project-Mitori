import pytest
from decimal import Decimal
import json
from tests.testconfig import test_redis, test_request, order_factory, token_factory,seed_cash_factory,seed_shares_factory, async_client
import uuid
from core.models import Side

@pytest.mark.asyncio
async def test_order_route_happy_path_buyer(
    async_client,
    order_factory,
    token_factory,
    seed_cash_factory,
):
    user_id = str(uuid.uuid4())

    ticker = 'APP'
    price = Decimal("10")
    number_of_shares = Decimal("150")

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



@pytest.mark.asyncio
async def test_order_route_happy_path(
    async_client,
    order_factory,
    token_factory,
    seed_shares_factory
):
    user_id = str(uuid.uuid4())

    ticker = 'APP'
    price = Decimal("10")
    number_of_shares = Decimal("150")

    
    await seed_shares_factory(owner_id=user_id,shares=Decimal("200"),ticker=ticker)
    valid_token = token_factory(user_id=user_id,kyc_verified=True)

    order = order_factory(
        ticker=ticker,
        side=Side.SELL,
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

@pytest.mark.asyncio
async def test_kyc_false(
    async_client,
    order_factory,
    token_factory,
    seed_cash_factory,
):
    user_id = str(uuid.uuid4())

    ticker = 'APP'
    price = Decimal("10")
    number_of_shares = Decimal("150")

    
    await seed_cash_factory(owner_id=user_id,available_cash=Decimal("2000"))
    valid_token = token_factory(user_id=user_id,kyc_verified=False)

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


    assert response.status_code == 403, f"Route failed: {response.text}"


@pytest.mark.asyncio
async def test_kyc_None(
    async_client,
    order_factory,
    token_factory,
    seed_cash_factory,
):
    user_id = str(uuid.uuid4())

    ticker = 'APP'
    price = Decimal("10")
    number_of_shares = Decimal("150")

    
    await seed_cash_factory(owner_id=user_id,available_cash=Decimal("2000"))
    valid_token = token_factory(user_id=user_id,kyc_verified=None)

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


    assert response.status_code == 403, f"Route failed: {response.text}"


@pytest.mark.asyncio
async def test_token_expired(
    async_client,
    order_factory,
    token_factory,
    seed_cash_factory,
):
    user_id = str(uuid.uuid4())

    ticker = 'APP'
    price = Decimal("10")
    number_of_shares = Decimal("150")

    
    await seed_cash_factory(owner_id=user_id,available_cash=Decimal("2000"))
    valid_token = token_factory(user_id=user_id,kyc_verified=True ,expires_in_minutes=-10)

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


    assert response.status_code == 401, f"Route failed: {response.text}"


@pytest.mark.asyncio
async def test_order_route_induffient_funds(
    async_client,
    order_factory,
    token_factory,
    seed_shares_factory
):
    user_id = str(uuid.uuid4())

    ticker = 'APP'
    price = Decimal("10")
    number_of_shares = Decimal("150")

    
    await seed_shares_factory(owner_id=user_id,shares=Decimal("120"),ticker=ticker)
    valid_token = token_factory(user_id=user_id,kyc_verified=True)

    order = order_factory(
        ticker=ticker,
        side=Side.SELL,
        price=price,
        number_of_shares=number_of_shares,
        order_owner_id=user_id
    )

    response = await async_client.post(
        "/order",
        json=order.model_dump(mode="json"),
        headers={"Authorization": f"Bearer {valid_token}"}
    )


    assert response.status_code == 400, f"Route failed: {response.text}"

@pytest.mark.asyncio
async def test_order_route_induffient_funds(
    async_client,
    order_factory,
    token_factory,
    seed_cash_factory
):
    user_id = str(uuid.uuid4())

    ticker = 'APP'
    price = Decimal("10")
    number_of_shares = Decimal("150")

    
    await seed_cash_factory(owner_id=user_id,available_cash=Decimal("20"))
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


    assert response.status_code == 400, f"Route failed: {response.text}"
