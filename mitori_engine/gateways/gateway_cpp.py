import sys
from pathlib import Path
import time
import uuid
from decimal import Decimal
from core_python.models import Trade, Order, Side,Type
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

    def submit_order(self, ticker:str ,order_id: uuid.UUID, order_owner_id: uuid.UUID,
                     side: Side, type: Type,is_canceled:bool,
                     number_of_shares: Decimal, price: Optional[Decimal],max_authorized_funds: Optional[Decimal] = None)-> tuple[list,int]:
        
        oid_high, oid_low = self._split_uuid(order_id)
        own_high, own_low = self._split_uuid(order_owner_id)

        price_scaled = int(price * self.PRECISION_MULTIPLIER) if price is not None else 0
        shares_scaled = int(number_of_shares * self.PRECISION_MULTIPLIER)
        max_funds_scaled = int(max_authorized_funds * self.PRECISION_MULTIPLIER) if max_authorized_funds is not None  else None

        starting_time = time.perf_counter_ns()
        raw_trades = self.book.process_order(
            order_id_high=oid_high,
            order_id_low=oid_low,
            order_owner_id_high=own_high,
            order_owner_id_low=own_low,
            side=engine.Side.BUY if side.value == "buy" else engine.Side.SELL,
            type=engine.Type.LIMIT if type.value == "limit" else engine.Type.MARKET,
            is_canceled=False,
            price=price_scaled,
            number_of_shares=shares_scaled,
            max_authorized_funds=max_funds_scaled
        )
        ending_time = time.perf_counter_ns()
        engine_latency = starting_time - ending_time

        processed_trades = []
        for t in raw_trades:
            trade_object = Trade(
                ticker= t.ticker,
                quantity= t.quantity,
                price_setteled_at= t.price_setteled_at,
                price_locked_by_user= t.price_locked_by_user,
                buyer_id= self._merge_uuid(t.buyer_id_high, t.buyer_id_low),
                seller_id= self._merge_uuid(t.seller_id_high, t.seller_id_low)
            )
            processed_trades.append(trade_object)
            
        return processed_trades, engine_latency

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
            side= Side.SELL if canceled_data["side"]==1 else Side.BUY,
            type= Type.MARKET if canceled_data['type'] == 1 else Type.LIMIT,

            price=canceled_data["price"],
            number_of_shares=canceled_data["number_of_shares"],
            order_owner_id=self._merge_uuid(
                canceled_data["owner_id_high"], 
                canceled_data["owner_id_low"]
            ),
            is_canceled=True
        )
    
    def get_bbo(self) -> dict[str, int]:
        raw_bbo = self.book.get_current_bbo()

        return {
            "best_ask_price" : int(raw_bbo.get("best_ask_price")),
            "best_bid_price":int(raw_bbo.get("best_bid_price"))
        }
        
    def reset_engine(self):
        self.book.reset_engine()