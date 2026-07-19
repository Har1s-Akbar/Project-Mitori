from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from datetime import datetime
import uuid

class Side(str,Enum):
    SELL="sell"
    BUY ="buy"

@dataclass(slots=True)
class Order():
    ticker:str
    side:Side
    price:float
    number_of_shares:int
    order_owner_id : uuid.UUID
    date_time:str = field(default_factory=lambda: str(datetime.now()))
    order_id: uuid.UUID =field(default_factory=lambda:uuid.uuid4())

    @property
    def is_filled(self) ->bool:
        return self.number_of_shares <=0


@dataclass(slots=True)
class Trade():
    ticker:str
    quantity:int
    price:float
    buyer_id:str
    seller_id:str
    date_time:str = field(default_factory=lambda:str(datetime.now()))
    id:uuid.UUID=field(default_factory=lambda:uuid.uuid4())