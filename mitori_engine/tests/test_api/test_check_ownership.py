import pytest
from fastapi import HTTPException
from schemas.schema import OrderReq, MARKET
from core.models import Side, Order, Type # ADDED: Type enum
from core.engine import OrderBook
from api.security import AuthenticatedUser
from api.check_ownership import check_owner_ship
import uuid
from decimal import Decimal
from unittest.mock import patch

@pytest.mark.asyncio
async def test_Invalid_uuid():
    #initializing user
    user_id = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id),kyc_verified=True)

    order_id = str(1637267)
    ticker = 'APP'
    with pytest.raises(HTTPException) as exep_info:
        check_owner_ship(order_id=order_id, ticker=ticker, user=user)
    assert  exep_info.value.status_code == 400
    assert "Invalid UUID format" in exep_info.value.detail


@pytest.mark.asyncio
async def test_Invalid_ticker():
    #initializing user
    user_id = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id),kyc_verified=True)

    order_id = str(uuid.uuid4())
    ticker = 'gibberish'
    with pytest.raises(HTTPException) as exep_info:
        check_owner_ship(order_id=order_id, ticker=ticker, user=user)
    assert  exep_info.value.status_code == 400
    assert "Such ticker does not exist" in exep_info.value.detail


@pytest.mark.asyncio
async def test_mismatch_orderUUID():
    #initializing user
    user_id = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id),kyc_verified=True)
    real_order_id = uuid.uuid4()
    order = Order(
        ticker='APP',
        side= Side.BUY,
        type=Type.LIMIT, 
        price=Decimal("15"),
        number_of_shares=Decimal("4"),
        order_owner_id=user.user_id,
        is_canceled=False,
        order_id=real_order_id
    )

    fake_order_id = str(uuid.uuid4())
    with patch.object(MARKET['APP'], 'get_specific_order_by_id', return_value=None):
        with pytest.raises(HTTPException) as exep_info:
            check_owner_ship(order_id=fake_order_id, ticker='APP', user=user)
        assert  exep_info.value.status_code == 404
        assert "Such order does not exist" in exep_info.value.detail


@pytest.mark.asyncio
async def test_someone_else_trying_to_delete_order():
    #initializing user
    user_id_owner = uuid.uuid4()
    user_id_someone_else = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id_someone_else),kyc_verified=True)

    order_id = uuid.uuid4()
    order = Order(
        ticker='APP',
        side= Side.BUY,
        type=Type.LIMIT, 
        price=Decimal("15"),
        number_of_shares=Decimal("4"),
        order_owner_id=user_id_owner,
        is_canceled=False,
        order_id=order_id
    )

    with patch.object(MARKET['APP'], 'get_specific_order_by_id', return_value=order):
        with pytest.raises(HTTPException) as exep_info:
            check_owner_ship(order_id=str(order_id), ticker='APP', user=user)
    assert  exep_info.value.status_code == 401
    assert "A user can only cancel the trade which belongs to his account" in exep_info.value.detail

@pytest.mark.asyncio
async def test_successful_ownership_check():
    user_id = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id), kyc_verified=True)
    order_id = uuid.uuid4()
    
    order = Order(
        ticker='APP',
        side=Side.BUY,
        type=Type.LIMIT, 
        price=Decimal("15"),
        number_of_shares=Decimal("4"),
        order_owner_id=user_id,
        is_canceled=False,
        order_id=order_id
    )

    with patch.object(MARKET['APP'], 'get_specific_order_by_id', return_value=order):
        result = check_owner_ship(order_id=str(order_id), ticker='APP', user=user)
        
    assert result.user_id == user.user_id
    assert result.kyc_verified is True