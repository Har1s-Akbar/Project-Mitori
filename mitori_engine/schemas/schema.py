from core.models import Side, Order
from core.engine import OrderBook
import uuid
from pydantic import BaseModel,Field
from decimal import Decimal

MARKET ={
    "APP": OrderBook("APP"),
    "TSLA": OrderBook("TSLA"),
    "AUX":OrderBook("AUX")
}

class OrderReq(BaseModel):
    ticker:str = Field(min_length=1, max_length=10, title="Ticker", description="Ticker is required", strict=True)
    side:Side = Field(title="side" , description="Side is required")
    price:Decimal = Field(max_digits=40, decimal_places=8, gt=0, lt=100000000000000)
    number_of_shares:Decimal = Field(max_digits=40, decimal_places=8, gt=0, lt=1000000)
    order_owner_id :uuid.UUID | None  = None