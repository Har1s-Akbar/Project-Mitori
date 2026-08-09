from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from datetime import datetime
import uuid
from typing import Optional

class Side(str,Enum):
    SELL="sell"
    BUY ="buy"

class Type(str,Enum):
    MARKET = "market"
    LIMIT = "limit"

@dataclass(slots=True)
class Order():
    ticker:str
    side:Side
    type: Type

    number_of_shares:Decimal
    order_owner_id : uuid.UUID
    is_canceled : bool
    price:Optional[Decimal] = None

    max_authorized_funds : Optional[Decimal] = None
    date_time:str = field(default_factory=lambda: str(datetime.now()))
    order_id: uuid.UUID =field(default_factory=lambda:uuid.uuid4())

    @property
    def is_filled(self) ->bool:
        return self.number_of_shares <=0


@dataclass(slots=True)
class Trade():
    ticker:str
    quantity:Decimal
    price_setteled_at:Decimal
    price_locked_by_user:Optional[Decimal]
    buyer_id :uuid.UUID
    seller_id : uuid.UUID
    date_time:str = field(default_factory=lambda:str(datetime.now()))
    order_id:uuid.UUID=field(default_factory=lambda:uuid.uuid4())