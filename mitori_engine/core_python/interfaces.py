from typing import Protocol, List, Optional
import uuid
from core_python.models import Side, Type, Order
from decimal import Decimal

class EngineProtocol(Protocol):
    def submit_order(
        self,
        ticker:str,
        order_id: uuid.UUID,
        order_owner_id: uuid.UUID,
        side:Side,
        type:Type,
        is_canceled:bool,
        number_of_shares: Decimal,
        price:Optional[Decimal],
        max_authorized_funds:Optional[Decimal]=None,
    )->List:
    
        ...

    def cancel_order(self, order_id: uuid.UUID)->Optional[Order]:
        ...
    def get_bbo(self)->dict:
        ...