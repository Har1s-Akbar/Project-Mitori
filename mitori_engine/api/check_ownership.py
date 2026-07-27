from fastapi import Request, Depends, HTTPException, status
from ..core.engine import OrderBook
from .security import AuthenticatedUser, is_user_Authenticated
from ..schemas.schema import MARKET
from uuid import UUID

def check_owner_ship(delete_order_uuid:str, ticker:str, user:AuthenticatedUser=Depends(is_user_Authenticated)) -> AuthenticatedUser:

    try:
        valid_uuid = UUID(delete_order_uuid)
    except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format")
    
    if ticker not in MARKET:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Such ticker does not exist")
    
    market = MARKET[ticker]
    object_to_be_delted = market.get_specific_order_by_id(str(delete_order_uuid))
    if not object_to_be_delted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Such order does not exist")
    if str(object_to_be_delted.order_owner_id) != str(user.user_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="A user can only cancel the trade which belongs to his account")

    return AuthenticatedUser