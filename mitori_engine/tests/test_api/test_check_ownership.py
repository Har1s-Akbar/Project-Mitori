import pytest
from fastapi import HTTPException
from core_python.models import Side, Order, Type
from api.security import AuthenticatedUser
from api.check_ownership import check_owner_ship
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_Invalid_uuid():
    user_id = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id), kyc_verified=True)
    order_id = "1637267"  
    ticker = 'APP'
    
    mock_engine = MagicMock()
    
    with pytest.raises(HTTPException) as exep_info:
        check_owner_ship(order_id=order_id, ticker=ticker, user=user, engine=mock_engine)
        
    assert exep_info.value.status_code == 400
    assert "Invalid UUID format" in exep_info.value.detail
    mock_engine.cancel_order.assert_not_called()

@pytest.mark.asyncio
async def test_Invalid_ticker():
    user_id = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id), kyc_verified=True)
    order_id = str(uuid.uuid4())
    ticker = 'gibberish'
    
    mock_engine = MagicMock()
    
    with pytest.raises(HTTPException) as exep_info:
        check_owner_ship(order_id=order_id, ticker=ticker, user=user, engine=mock_engine)
        
    assert exep_info.value.status_code == 400
    assert "Such ticker does not exist" in exep_info.value.detail
    mock_engine.cancel_order.assert_not_called()

@pytest.mark.asyncio
async def test_mismatch_orderUUID():
    user_id = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id), kyc_verified=True)
    fake_order_id = str(uuid.uuid4())

    mock_engine = MagicMock()
    mock_engine.cancel_order.return_value = None
    
    with pytest.raises(HTTPException) as exep_info:
        check_owner_ship(order_id=fake_order_id, ticker='APP', user=user, engine=mock_engine)
        
    assert exep_info.value.status_code == 404
    assert "Such order does not exist" in exep_info.value.detail
    mock_engine.cancel_order.assert_called_once_with(uuid.UUID(fake_order_id))

@pytest.mark.asyncio
async def test_someone_else_trying_to_delete_order():
    user_id_owner = uuid.uuid4()
    user_id_someone_else = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id_someone_else), kyc_verified=True)
    order_id = uuid.uuid4()

    order = Order(
        ticker='APP',
        side=Side.BUY,
        type=Type.LIMIT, 
        price=Decimal("1500000000"),
        number_of_shares=Decimal("400000000"),
        order_owner_id=user_id_owner, 
        is_canceled=False,
        order_id=order_id
    )

    mock_engine = MagicMock()
    mock_engine.cancel_order.return_value = order

    with pytest.raises(HTTPException) as exep_info:
        check_owner_ship(order_id=str(order_id), ticker='APP', user=user, engine=mock_engine)
        
    assert exep_info.value.status_code == 401
    assert "A user can only cancel the trade which belongs to his account" in exep_info.value.detail
    
    mock_engine.cancel_order.assert_called_once_with(order_id)

@pytest.mark.asyncio
async def test_successful_ownership_check():
    user_id = uuid.uuid4()
    user = AuthenticatedUser(user_id=str(user_id), kyc_verified=True)
    order_id = uuid.uuid4()

    order = Order(
        ticker='APP',
        side=Side.BUY,
        type=Type.LIMIT,
        price=Decimal("1500000000"),
        number_of_shares=Decimal("400000000"),
        order_owner_id=user_id,
        is_canceled=False,
        order_id=order_id
    )

    mock_engine = MagicMock()
    mock_engine.cancel_order.return_value = order

    result = check_owner_ship(order_id=str(order_id), ticker='APP', user=user, engine=mock_engine)
    
    assert result.user_id == str(user_id)
    mock_engine.cancel_order.assert_called_once_with(order_id)