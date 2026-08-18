import pytest
from decimal import Decimal
import json
from tests.testconfig import test_redis, test_request, order_factory, token_factory, seed_cash_factory, seed_shares_factory, async_client, engine_mode
import uuid
from core_python.models import Side, Type
import asyncio
import os
import importlib
import api.dependencies
import main

@pytest.mark.parametrize(
    "kyc_status , expires_in, expected_outcome",
    [
        (True, 15, 200),
        (False, 15, 403),
        (None, 15, 403),
        (True, -15, 401)
    ],
    ids=["for_token_true", "for_token_false", "for_token_None", "for_token_expired"]
)
@pytest.mark.asyncio
async def test_secirity_features(
    async_client,
    order_factory,
    token_factory,
    seed_cash_factory,
    kyc_status, expires_in, expected_outcome
):
    user_id = str(uuid.uuid4())

    ticker = 'APP'
    price = Decimal("10")
    number_of_shares = Decimal("150")
    
    await seed_cash_factory(owner_id=user_id, available_cash=Decimal("2000"), ticker=ticker)
    valid_token = token_factory(user_id=user_id, kyc_verified=kyc_status, expires_in_minutes=expires_in)

    order = order_factory(
        ticker=ticker,
        side=Side.BUY,
        number_of_shares=number_of_shares,
        order_owner_id=user_id,
        order_type=Type.LIMIT,
        price=price
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
        (Side.BUY, "10", "0", 400),
        (Side.SELL, "0", "10", 400)
    ],
    ids=["happy_path_for_buy", "happy_path_for_sell", "insuficient_buy_side", "insuficient_sell_side"]
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

    await seed_cash_factory(owner_id=user_id, available_cash=Decimal(set_cash), ticker=ticker)    
    await seed_shares_factory(owner_id=user_id, shares=Decimal(set_shares), ticker=ticker)
    valid_token = token_factory(user_id=user_id, kyc_verified=True)

    order = order_factory(
        ticker=ticker,
        side=side,
        number_of_shares=number_of_shares,
        order_owner_id=user_id,
        order_type=Type.LIMIT,
        price=price
    )

    response = await async_client.post(
        "/order",
        json=order.model_dump(mode="json"),
        headers={"Authorization": f"Bearer {valid_token}"}
    )

    assert response.status_code == expected_outcome, f"Route failed: {response.text}"

@pytest.mark.parametrize(
    "price_str, shares_str, expected_status",
    [
        ("0.00000001", "10", 200),     
        ("0", "100", 422),             
        ("100", "0", 422),             
        ("-50", "10", 422),            
        ("9999999999.99", "1", 200),   
    ],
    ids=["fractional_penny_accepted", "zero_price", "zero_shares", "negative_price", "massive_value"]
)
@pytest.mark.asyncio
async def test_order_mathematical_boundaries(
    async_client, token_factory, seed_cash_factory,
    price_str, shares_str, expected_status
):
    user_id = str(uuid.uuid4())

    await seed_cash_factory(owner_id=user_id, available_cash=Decimal("10000000000.00"), ticker="APP")
    valid_token = token_factory(user_id=user_id, kyc_verified=True)

    raw_malicious_payload = {
        "ticker": "APP",
        "side": "buy", 
        "type": "limit", 
        "price": price_str,
        "number_of_shares": shares_str,
        "order_owner_id": user_id
    }

    response = await async_client.post(
        "/order",
        json=raw_malicious_payload,
        headers={"Authorization": f"Bearer {valid_token}"}
    )

    assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}: {response.text}"

@pytest.mark.asyncio
async def test_matching_engine(
    async_client, token_factory, seed_cash_factory,
    seed_shares_factory, order_factory, test_redis
):
    user_id_1_buyer = str(uuid.uuid4())
    await seed_cash_factory(owner_id=user_id_1_buyer, available_cash=Decimal("10000"), ticker="APP")
    valid_token_for_user_1 = token_factory(user_id=user_id_1_buyer, kyc_verified=True)

    buy_order_by_user_1 = order_factory(
        ticker="APP",
        side=Side.BUY,
        number_of_shares=Decimal("100"),
        order_owner_id=user_id_1_buyer,
        order_type=Type.LIMIT,
        price=Decimal("10")
    )

    response1 = await async_client.post(
        "/order",
        json=buy_order_by_user_1.model_dump(mode="json"),
        headers={"Authorization": f"Bearer {valid_token_for_user_1}"}
    )
    assert response1.status_code == 200, f"Route failed: {response1.text}"

    user_id_2_seller = str(uuid.uuid4())
    await seed_shares_factory(owner_id=user_id_2_seller, shares=Decimal("10000"), ticker="APP")
    valid_token_for_user_2 = token_factory(user_id=user_id_2_seller, kyc_verified=True)

    sell_order_by_user_2 = order_factory(
        ticker="APP",
        side=Side.SELL,
        number_of_shares=Decimal("100"),
        order_owner_id=user_id_2_seller,
        order_type=Type.LIMIT,
        price=Decimal("10")
    )

    response2 = await async_client.post(
        "/order",
        json=sell_order_by_user_2.model_dump(mode="json"),
        headers={'Authorization': f"Bearer {valid_token_for_user_2}"}
    )
    assert response2.status_code == 200, f"Route Failed : {response2.text}"

    stream_name = "executed_trades_stream"
    getting_stream = await test_redis.xread({stream_name: "0-0"})
    assert len(getting_stream) > 0, "No streams returned"

    stream_name_returned, message_list = getting_stream[0]
    test_specific_trades = []
    
    for redis_id, raw_payload in message_list:
        trade_data = json.loads(raw_payload["data"])
        if trade_data["seller_id"] == user_id_2_seller: 
            test_specific_trades.append(trade_data)

    assert len(test_specific_trades) > 0, "Engine failed to match our specific test order"
    
    total_executed_qty = sum(trade["quantity"] for trade in test_specific_trades)
    
    expected_qty_scaled = int(Decimal("100") * Decimal(os.getenv("SYSTEM_PRECISION_MULTIPLIER", 100000000))) 
    assert total_executed_qty == expected_qty_scaled, "Engine did not fully fill the order"

    first_trade = test_specific_trades[0]
    assert first_trade["ticker"] == "APP"
    assert "price_setteled_at" in first_trade
    assert "order_id" in first_trade

@pytest.mark.asyncio
async def test_matching_engine_partial_fill(
    async_client, token_factory, seed_cash_factory,
    seed_shares_factory, order_factory, test_redis
):
    user_buyer = str(uuid.uuid4())
    user_seller = str(uuid.uuid4())
    multiplier = Decimal(os.getenv("SYSTEM_PRECISION_MULTIPLIER", 100000000))
    
    await seed_cash_factory(owner_id=user_buyer, available_cash=Decimal("10000"), ticker="AUX")
    await seed_shares_factory(owner_id=user_seller, shares=Decimal("40"), ticker="AUX")
    
    buyer_token = token_factory(user_id=user_buyer, kyc_verified=True)
    seller_token = token_factory(user_id=user_seller, kyc_verified=True)

    sell_order = order_factory(
        ticker="AUX", side=Side.SELL, number_of_shares=Decimal("40"), 
        order_owner_id=user_seller, order_type=Type.LIMIT, price=Decimal("10")
    )
    await async_client.post("/order", json=sell_order.model_dump(mode="json"), headers={'Authorization': f"Bearer {seller_token}"})
    
    buy_order = order_factory(
        ticker="AUX", side=Side.BUY, number_of_shares=Decimal("100"), 
        order_owner_id=user_buyer, order_type=Type.LIMIT, price=Decimal("10")
    )
    await async_client.post("/order", json=buy_order.model_dump(mode="json"), headers={"Authorization": f"Bearer {buyer_token}"})

    getting_stream = await test_redis.xread({"executed_trades_stream": "0-0"})
    assert getting_stream, "No executed trades stream found in Redis"
    
    _, message_list = getting_stream[0]
    test_trades = [json.loads(p["data"]) for _, p in message_list if json.loads(p["data"])["seller_id"] == user_seller]
    
    assert len(test_trades) > 0, "Engine failed to match the partial fill"
    
    expected_qty_scaled = int(Decimal("40") * multiplier)
    assert test_trades[0]["quantity"] == expected_qty_scaled, f"Engine over-filled! Expected {expected_qty_scaled}"

@pytest.mark.asyncio
async def test_matching_engine_price_time_priority(
    async_client, token_factory, seed_cash_factory,
    seed_shares_factory, order_factory, test_redis
):
    test_ticker = "TSLA" 

    user_seller_1 = str(uuid.uuid4())
    user_seller_2 = str(uuid.uuid4())
    user_buyer = str(uuid.uuid4())

    await seed_shares_factory(owner_id=user_seller_1, shares=Decimal("1000"), ticker=test_ticker)
    await seed_shares_factory(owner_id=user_seller_2, shares=Decimal("1000"), ticker=test_ticker)
    await seed_cash_factory(owner_id=user_buyer, available_cash=Decimal("10000"), ticker=test_ticker)

    token_s1 = token_factory(user_id=user_seller_1, kyc_verified=True)
    token_s2 = token_factory(user_id=user_seller_2, kyc_verified=True)
    token_b = token_factory(user_id=user_buyer, kyc_verified=True)

    sell_1 = order_factory(
        ticker=test_ticker, side=Side.SELL, number_of_shares=Decimal("10"), 
        order_owner_id=user_seller_1, order_type=Type.LIMIT, price=Decimal("10")
    )
    res1 = await async_client.post("/order", json=sell_1.model_dump(mode="json"), headers={'Authorization': f"Bearer {token_s1}"})
    assert res1.status_code == 200

    sell_2 = order_factory(
        ticker=test_ticker, side=Side.SELL, number_of_shares=Decimal("10"), 
        order_owner_id=user_seller_2, order_type=Type.LIMIT, price=Decimal("10")
    )
    res2 = await async_client.post("/order", json=sell_2.model_dump(mode="json"), headers={'Authorization': f"Bearer {token_s2}"})
    assert res2.status_code == 200

    buy = order_factory(
        ticker=test_ticker, side=Side.BUY, number_of_shares=Decimal("10"), 
        order_owner_id=user_buyer, order_type=Type.LIMIT, price=Decimal("10")
    )
    res3 = await async_client.post("/order", json=buy.model_dump(mode="json"), headers={"Authorization": f"Bearer {token_b}"})
    assert res3.status_code == 200

    await asyncio.sleep(0.2) 

    getting_stream = await test_redis.xread({"executed_trades_stream": "0-0"})
    _, message_list = getting_stream[0]

    buyer_trades = [
        json.loads(p["data"]) for _, p in message_list 
        if json.loads(p["data"])["buyer_id"] == user_buyer 
        and json.loads(p["data"])["ticker"] == test_ticker
    ]

    assert len(buyer_trades) > 0, "Engine failed to match trades"
    assert buyer_trades[0]["seller_id"] == user_seller_1, "Engine failed FIFO! Matched the wrong seller."

@pytest.mark.asyncio
async def test_matching_engine_price_improvement(
    async_client, token_factory, seed_cash_factory,
    seed_shares_factory, order_factory, test_redis
):
    test_ticker = "GOOGL" 

    user_seller = str(uuid.uuid4())
    user_buyer = str(uuid.uuid4())
    multiplier = Decimal(os.getenv("SYSTEM_PRECISION_MULTIPLIER", 100000000))

    await seed_shares_factory(owner_id=user_seller, shares=Decimal("1000"), ticker=test_ticker)
    await seed_cash_factory(owner_id=user_buyer, available_cash=Decimal("10000"), ticker=test_ticker)

    seller_token = token_factory(user_id=user_seller, kyc_verified=True)
    buyer_token = token_factory(user_id=user_buyer, kyc_verified=True)

    sell_order = order_factory(
        ticker=test_ticker, side=Side.SELL, number_of_shares=Decimal("10"), 
        order_owner_id=user_seller, order_type=Type.LIMIT, price=Decimal("10")
    )
    res1 = await async_client.post("/order", json=sell_order.model_dump(mode="json"), headers={'Authorization': f"Bearer {seller_token}"})
    assert res1.status_code == 200

    buy_order = order_factory(
        ticker=test_ticker, side=Side.BUY, number_of_shares=Decimal("10"), 
        order_owner_id=user_buyer, order_type=Type.LIMIT, price=Decimal("12")
    )
    res2 = await async_client.post("/order", json=buy_order.model_dump(mode="json"), headers={"Authorization": f"Bearer {buyer_token}"})
    assert res2.status_code == 200

    await asyncio.sleep(0.2)

    getting_stream = await test_redis.xread({"executed_trades_stream": "0-0"})
    _, message_list = getting_stream[0]

    test_trades = [
        json.loads(p["data"]) for _, p in message_list 
        if json.loads(p["data"])["buyer_id"] == user_buyer
        and json.loads(p["data"])["ticker"] == test_ticker
    ]

    assert len(test_trades) > 0, "Engine failed to cross the spread"
    
    expected_settled_price = int(Decimal("10") * multiplier)
    assert test_trades[0]["price_setteled_at"] == expected_settled_price, "Engine failed to provide price improvement!"

@pytest.mark.asyncio
async def test_market_order_end_to_end_route(
    async_client, token_factory, seed_cash_factory,
    seed_shares_factory, order_factory, test_redis
):
    """
    Proves the FastAPI route handles Market Orders correctly:
    Accepts the payload with no price, successfully injects the ceiling via have_funds,
    routes to process_market_orders_ioc, and publishes the correct data to Redis streams.
    """
    test_ticker = "AMD"
    multiplier = Decimal(os.getenv("SYSTEM_PRECISION_MULTIPLIER", 100000000))
    
    user_seller = str(uuid.uuid4())
    user_buyer = str(uuid.uuid4())
    
    await seed_shares_factory(owner_id=user_seller, shares=Decimal("100"), ticker=test_ticker)
    seller_token = token_factory(user_id=user_seller, kyc_verified=True)
    
    sell_order = order_factory(
        ticker=test_ticker, side=Side.SELL, order_type=Type.LIMIT, 
        price=Decimal("15"), number_of_shares=Decimal("10"), order_owner_id=user_seller
    )
    res_seller = await async_client.post("/order", json=sell_order.model_dump(mode="json"), headers={'Authorization': f"Bearer {seller_token}"})
    assert res_seller.status_code == 200
    
    await seed_cash_factory(owner_id=user_buyer, available_cash=Decimal("5000"), ticker=test_ticker)
    buyer_token = token_factory(user_id=user_buyer, kyc_verified=True)
    
    buy_market_order = order_factory(
        ticker=test_ticker, side=Side.BUY, order_type=Type.MARKET, 
        price=None, number_of_shares=Decimal("5"), order_owner_id=user_buyer
    )
    
    res_buyer = await async_client.post(
        "/order", 
        json=buy_market_order.model_dump(mode="json"), 
        headers={"Authorization": f"Bearer {buyer_token}"}
    )
    
    assert res_buyer.status_code == 200, f"Market Order API Route Failed: {res_buyer.text}"
    
    await asyncio.sleep(0.2)
    
    getting_stream = await test_redis.xread({"executed_trades_stream": "0-0"})
    _, message_list = getting_stream[0]
    
    market_trades = [
        json.loads(p["data"]) for _, p in message_list 
        if json.loads(p["data"])["buyer_id"] == user_buyer
        and json.loads(p["data"])["ticker"] == test_ticker
    ]
    
    assert len(market_trades) == 1, "Market order failed to hit the Redis stream"
    
    expected_settled_price = int(Decimal("15") * multiplier)
    expected_quantity = int(Decimal("5") * multiplier)
    
    assert market_trades[0]["price_setteled_at"] == expected_settled_price
    assert market_trades[0]["quantity"] == expected_quantity

@pytest.mark.asyncio
async def test_flow_parity_across_engines(
    async_client, token_factory, seed_cash_factory,
    seed_shares_factory, order_factory, test_redis, engine_mode
):
    """
    Parametrized order flow test running identical sequences against 
    whichever engine mode is active (Python vs C++ via Pybind11).
    """
    test_ticker = "APP"
    user_seller = str(uuid.uuid4())
    user_buyer = str(uuid.uuid4())

    await seed_shares_factory(owner_id=user_seller, shares=Decimal("100"), ticker=test_ticker)
    await seed_cash_factory(owner_id=user_buyer, available_cash=Decimal("5000"), ticker=test_ticker)

    seller_token = token_factory(user_id=user_seller, kyc_verified=True)
    buyer_token = token_factory(user_id=user_buyer, kyc_verified=True)

    
    sell_order = order_factory(
        ticker=test_ticker, side=Side.SELL, number_of_shares=Decimal("10"), 
        order_owner_id=user_seller, order_type=Type.LIMIT, price=Decimal("50")
    )
    res1 = await async_client.post(
        "/order", 
        json=sell_order.model_dump(mode="json"), 
        headers={'Authorization': f"Bearer {seller_token}"}
    )
    assert res1.status_code == 200

    buy_order = order_factory(
        ticker=test_ticker, side=Side.BUY, number_of_shares=Decimal("10"), 
        order_owner_id=user_buyer, order_type=Type.LIMIT, price=Decimal("55")
    )
    res2 = await async_client.post(
        "/order", 
        json=buy_order.model_dump(mode="json"), 
        headers={"Authorization": f"Bearer {buyer_token}"}
    )
    assert res2.status_code == 200


@pytest.mark.asyncio
async def test_direct_engine_mode_output_comparison(
    async_client, token_factory, seed_cash_factory,
    seed_shares_factory, order_factory, test_redis, monkeypatch
):
    """
    Explicit end-to-end comparison test: Executes identical order payloads 
    first through Python mode and then through CPP mode via HTTP routes, 
    asserting exact trade output data parity at the benchmark layer.
    """
    test_ticker = "APP"
    order_sequence = [
        (Side.SELL, Type.LIMIT, Decimal("100"), Decimal("10")),
        (Side.BUY, Type.LIMIT, Decimal("100"), Decimal("10")),
    ]

    results = {}

    for mode in ["python", "cpp"]:
        monkeypatch.setenv("ENGINE_MODE", mode)
        importlib.reload(api.dependencies)
        importlib.reload(main)

        user_seller = str(uuid.uuid4())
        user_buyer = str(uuid.uuid4())

        await seed_shares_factory(owner_id=user_seller, shares=Decimal("1000"), ticker=test_ticker)
        await seed_cash_factory(owner_id=user_buyer, available_cash=Decimal("10000"), ticker=test_ticker)

        seller_token = token_factory(user_id=user_seller, kyc_verified=True)
        buyer_token = token_factory(user_id=user_buyer, kyc_verified=True)

        sell_order = order_factory(
            ticker=test_ticker, side=Side.SELL, number_of_shares=Decimal("10"), 
            order_owner_id=user_seller, order_type=Type.LIMIT, price=Decimal("100")
        )
        await async_client.post(
            "/order", json=sell_order.model_dump(mode="json"), 
            headers={'Authorization': f"Bearer {seller_token}"}
        )

        buy_order = order_factory(
            ticker=test_ticker, side=Side.BUY, number_of_shares=Decimal("10"), 
            order_owner_id=user_buyer, order_type=Type.LIMIT, price=Decimal("100")
        )
        res = await async_client.post(
            "/order", json=buy_order.model_dump(mode="json"), 
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert res.status_code == 200

        messages = await test_redis.xrange("executed_trades_stream", min="-", max="+")
        results[mode] = [json.loads(p["data"]) for _, p in messages if json.loads(p["data"])["ticker"] == test_ticker]
        
        await test_redis.flushdb()

    assert len(results["python"]) == len(results["cpp"])
    assert len(results["python"]) > 0
    
    py_trade = results["python"][0]
    cpp_trade = results["cpp"][0]

    assert py_trade["price_setteled_at"] == cpp_trade["price_setteled_at"]
    assert py_trade["quantity"] == cpp_trade["quantity"]