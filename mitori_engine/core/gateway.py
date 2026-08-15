import sys
from pathlib import Path
import time
import uuid
from decimal import Decimal
from core.models import Type , Side

BUILD_DIR = Path(__file__).resolve().parent.parent / "core_cpp" / "build"
sys.path.append(str(BUILD_DIR))

import mitori_engine_cpp
class MitoriGateway:
    def __init__(self, ticker: str):
        self.book = mitori_engine_cpp.OrderBook(ticker)

    def _split_uuid(self, uid: uuid.UUID) -> tuple[int, int]:
        uid_int = uid.int
        return uid_int >> 64, uid_int & 0xFFFFFFFFFFFFFFFF

    def _stitch_uuid(self, high: int, low: int) -> uuid.UUID:
        return uuid.UUID(int=((high << 64) | low))

    def submit_order(self, order_id: uuid.UUID, owner_id: uuid.UUID, 
                     side: mitori_engine_cpp.Side, order_type: mitori_engine_cpp.Type, price: Decimal,
                     shares: Decimal, max_funds: Decimal = None):
        
        oid_high, oid_low = self._split_uuid(order_id)
        own_high, own_low = self._split_uuid(owner_id)
        
        cpp_side = mitori_engine_cpp.Side.BUY if side.upper() == "BUY" else mitori_engine_cpp.Side.SELL
        cpp_type = mitori_engine_cpp.Type.LIMIT if order_type.upper() == "LIMIT" else mitori_engine_cpp.Type.MARKET

        raw_trades = self.book.process_order(
            order_id_high=oid_high,
            order_id_low=oid_low,
            owner_id_high=own_high,
            owner_id_low=own_low,
            side=side,
            type=order_type,
            is_canceled=False,
            price=price,
            number_of_shares=shares,
            max_authorized_funds=max_funds if max_funds is not None else 0.0
        )
        
        execution_timestamp = time.time_ns() 

        processed_trades = []
        for t in raw_trades:
            processed_trades.append({
                "order_id": uuid.uuid4(),
                "date_time": execution_timestamp,
                "ticker": t.ticker,
                "buyer_id": self._stitch_uuid(t.buyer_id_high, t.buyer_id_low),
                "seller_id": self._stitch_uuid(t.seller_id_high, t.seller_id_low),
                "quantity": t.quantity,
                "price_setteled_at": t.price_setteled_at,
                "price_locked_by_user": t.price_locked_by_user
            })
            
        return processed_trades

    def cancel_order(self, order_id: uuid.UUID):
        oid_high, oid_low = self._split_uuid(order_id)
        self.book.tombstone_delete(oid_high, oid_low)

    def get_bbo(self) -> dict:
        return self.book.get_current_bbo()
        
    def reset_engine(self):
        mitori_engine_cpp.reset_memory()