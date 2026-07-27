from fastapi import Request, Depends, HTTPException, status
from ..core.engine import OrderBook
from .security import AuthenticatedUser, is_user_Authenticated
from ..schemas.schema import MARKET


def check_owner_ship(delete_order_uuid:str, ticker:str, user:AuthenticatedUser=Depends(is_user_Authenticated)):
    if ticker not in MARKET:
        # raise HTTPException(status_code)
        pass