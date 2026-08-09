from core.models import Side, Type
from core.engine import OrderBook
from typing import Optional
import uuid
from pydantic import BaseModel,Field, model_validator
from decimal import Decimal

MARKET ={
    "APP": OrderBook("APP"),
    "TSLA": OrderBook("TSLA"),
    "AUX":OrderBook("AUX"),
    "GOOGL":OrderBook("GOOGL")
}

class OrderReq(BaseModel):
    ticker:str = Field(min_length=1, max_length=10, title="Ticker", description="Ticker is required", strict=True)
    side:Side = Field(title="Side" , description="Side is required")
    type:Type = Field(title="Type", description="Type is required")
    # Field(max_digits=40, decimal_places=8, gt=0, lt=100000000000000)
    number_of_shares:Decimal = Field(max_digits=40, decimal_places=8, gt=0, lt=1000000)
    order_owner_id :uuid.UUID | None  = None
    price:Optional[Decimal]= Field(max_digits=40, decimal_places=8, gt=0, lt=100000000000000)

    max_authorized_funds: Optional[Decimal] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def type_check(self) -> OrderReq:
        if self.type==Type.LIMIT and self.price is None:
            raise ValueError("For order Type LIMIT , price field is required")

        if self.type == Type.MARKET and not self.price is None:
            raise ValueError("For order Type MARKET, price field is not acceptible")

        return self