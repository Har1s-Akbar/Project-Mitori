import uuid
import os
from typing import List, Optional
from decimal import Decimal

from core_python.models import Order , Side, Type
from core_python.engine import OrderBook

class PythonMitoriGateway:
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.book = OrderBook(ticker)
        self.PRECISION_MULTIPLIER = Decimal(os.getenv('SYSTEM_PRECISION_MULTIPLIER', '100000000'))

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
    ) -> List:
        
        
        price_scaled = int(price * self.PRECISION_MULTIPLIER) if price is not None else 0
        shares_scaled = int(number_of_shares * self.PRECISION_MULTIPLIER)
        funds_scaled = int(max_authorized_funds * self.PRECISION_MULTIPLIER) if max_authorized_funds is not None else None

        new_order = Order(
            order_id=order_id,
            ticker=self.ticker,
            side=side,
            type=type,
            price=price_scaled,
            number_of_shares=shares_scaled,
            order_owner_id=order_owner_id,
            max_authorized_funds=funds_scaled,
            is_canceled=is_canceled
        )

        executed_trades = self.book.process_order(new_order)
        return executed_trades

    def cancel_order(self, order_id: uuid.UUID):
        return self.book.tombstone_delete(str(order_id))
        
    def get_bbo(self):
        return self.book.get_current_bbo()