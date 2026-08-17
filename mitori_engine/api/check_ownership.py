from fastapi import Request, Depends, HTTPException, status
from api.security import AuthenticatedUser, is_user_Authenticated
from uuid import UUID
from core_python.config import ALLOWED_TICKERS
from api.dependencies import get_matching_engine
from core_python.interfaces import EngineProtocol

def check_owner_ship(order_id:str, ticker:str, user:AuthenticatedUser=Depends(is_user_Authenticated), engine:EngineProtocol= Depends(get_matching_engine)) -> AuthenticatedUser:
    try:
        valid_uuid = UUID(order_id)
    except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format")
    
    if ticker not in ALLOWED_TICKERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Such ticker does not exist")
    
    object_to_be_deleted = engine.cancel_order(UUID(order_id))
    if not object_to_be_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Such order does not exist")
    if str(object_to_be_deleted.order_owner_id) != str(user.user_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="A user can only cancel the trade which belongs to his account")

    return user