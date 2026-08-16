import sys
from pathlib import Path
import time
import uuid
from decimal import Decimal
from core.models import Trade, Order
from typing import Optional

BUILD_DIR = Path(__file__).resolve().parent.parent / "core_cpp" / "build"
sys.path.append(str(BUILD_DIR))

import mitori_engine_cpp as engine



class MitoriGateway:
    def __init__(self, ticker: str):
        self.book = engine.OrderBook(ticker)
        self.PRECISION_MULTIPLIER = Decimal("100000000");
        self.ticker = ticker

    def _split_uuid(self, uid: uuid.UUID) -> tuple[int, int]:
        if uid is None:
            return (0, 0)
        int_val = uid.int
        high = int_val >> 64
        low = int_val & 0xFFFFFFFFFFFFFFFF
        return (high, low)

    def _merge_uuid(self, high: int, low: int) -> uuid.UUID:
        return uuid.UUID(int=(high << 64) | low)

    def _to_decimal(self, raw_val: int) -> Decimal:
        return Decimal(raw_val) / self.PRECISION_MULTIPLIER

    def submit_order(self, order_id: uuid.UUID, owner_id: uuid.UUID, 
                     side: engine.Side, type: engine.Type, price: Optional[Decimal],
                     shares: Decimal, max_funds: Optional[Decimal] = None):
        
        oid_high, oid_low = self._split_uuid(order_id)
        own_high, own_low = self._split_uuid(owner_id)

        price_scaled = int(price * self.PRECISION_MULTIPLIER) if price is not None else 0
        shares_scaled = int(shares * self.PRECISION_MULTIPLIER)
        max_funds_scaled = int(max_funds * self.PRECISION_MULTIPLIER) if max_funds is not None  else None

        raw_trades = self.book.process_order(
            order_id_high=oid_high,
            order_id_low=oid_low,
            order_owner_id_high=own_high,
            order_owner_id_low=own_low,
            side=side,
            type=type,
            is_canceled=False,
            price=price_scaled,
            number_of_shares=shares_scaled,
            max_authorized_funds=max_funds_scaled
        )
        
        execution_timestamp = time.time_ns() 

        processed_trades = []
        for t in raw_trades:
            trade_object = Trade(
                ticker= t.ticker,
                quantity= self._to_decimal(t.quantity),
                price_setteled_at= self._to_decimal(t.price_setteled_at),
                price_locked_by_user= self._to_decimal(t.price_locked_by_user),
                buyer_id= self._merge_uuid(t.buyer_id_high, t.buyer_id_low),
                seller_id= self._merge_uuid(t.seller_id_high, t.seller_id_low)
            )
            processed_trades.append(trade_object)
            
        return processed_trades

    def cancel_order(self, order_id: uuid.UUID) -> Optional[Order]:
        oid_high, oid_low = self._split_uuid(order_id)

        canceled_data = self.book.tombstone_delete(
            order_id_high=oid_high,
            order_id_low=oid_low
        )

        if not canceled_data:
            return None
 
        return Order(
            order_id=order_id,
            ticker=self.ticker,
            side=canceled_data["side"],
            type=canceled_data["type"],
            # Apply exact Decimal reconstruction 
            price=self._to_decimal(canceled_data["price"]),
            number_of_shares=self._to_decimal(canceled_data["number_of_shares"]),
            order_owner_id=self._merge_uuid(
                canceled_data["owner_id_high"], 
                canceled_data["owner_id_low"]
            ),
            is_canceled=True
        )
    
    def get_bbo(self) -> dict[str, int]:
        raw_bbo = self.book.get_current_bbo()

        return {
            "best_ask_price" : self._to_decimal(raw_bbo.get("best_ask_price"),int(0)),
            "best_bid_price":self._to_decimal(raw_bbo.get("best_bid_price"), int(0))
        }
        
    def reset_engine(self):
        engine.reset_memory()