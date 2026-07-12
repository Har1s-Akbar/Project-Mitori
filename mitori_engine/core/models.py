from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from datetime import datetime
from uuid import uuid4

class Side(str,Enum):
    SELL="sell"
    BUY ="buy"

@dataclass(slots=True)
class Order():
    ticker:str
    side:Side
    price:float
    number_of_shares:int
    date_time:str = field(default_factory=lambda: str(datetime.now()))
    id:str=field(default_factory=lambda:str(uuid4()))

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
    id:str=field(default_factory=lambda:str(uuid4()))

