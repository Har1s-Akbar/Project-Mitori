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