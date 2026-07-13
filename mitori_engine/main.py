from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn
from .core.models import Side, Order
from .core.engine import OrderBook

app = FastAPI(
    title ="mitori-engine",
    discription = "fast paced matching engine for project mitori",
    version = "1.0.0"
)

MARKET ={
    "APP": OrderBook("APP"),
    "TSLA": OrderBook("TSLA"),
    "AUX":OrderBook("AUX")
}

class OrderReq(BaseModel):
    ticker:str = Field(min_length=1, max_length=10, title="Ticker", description="Ticker is required", strict=True)
    side:Side = Field(title="side" , description="Side is required", strict=True)
    price:float = Field(ge=1, lt=1000000000.0, allow_inf_nan=False, strict=True)
    number_of_shares:int = Field(ge=1, lt=2000, allow_inf_nan=False, strict=True)

@app.post("/order")
async def place_order(order:OrderReq):
    if order.ticker not in MARKET:
        raise HTTPException(status_code=404,detail="Ticker does not exist")
    target_book = MARKET[order.ticker]

    new_order = Order(
        ticker =  order.ticker,
        side = order.side,
        price = order.price,
        number_of_shares = order.number_of_shares
    )

    target_book.add_order(new_order)
    executed_trades = target_book.execute()

    return {
        "message":"Order Accepted",
        "trades":executed_trades
    }




if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)