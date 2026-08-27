import heapq
from .models import Order, Trade, Side, Type
from uuid import UUID
import os
import gc
import threading

class OrderBook():
    ticker: str
    
    def __init__(self, ticker: str):
        self.bid = []
        self.ask = []
        self.ticker = ticker
        self.active_uuids = {}
        self.canceled_uuids = set()
        self.PRECISION_MULTIPLIER = int(os.getenv('SYSTEM_PRECISION_MULTIPLIER', '100000000'))
        self.lock = threading.Lock()

    def process_order(self, order: Order) -> list[Trade]:
        if order.type == Type.LIMIT.value:
            with self.lock:
                self.add_order(order)
                return self.execute()
            
        if order.type == Type.MARKET.value or getattr(order.type, "value", order.type) == Type.MARKET.value:
            with self.lock:
                return self.process_market_orders_ioc(order)

    def process_market_orders_ioc(self, order: Order) -> list[Trade]:
        executed_trades = []
        target_side = self.ask if order.side == Side.BUY else self.bid
        
        total_spent = 0

        while target_side and order.number_of_shares > 0:
            best_resting = target_side[0][3]
            resting_id_str = str(best_resting.order_id)

            if resting_id_str in self.canceled_uuids:
                heapq.heappop(target_side)
                self.canceled_uuids.remove(resting_id_str)
                continue

            transactioning_shares = min(order.number_of_shares, best_resting.number_of_shares)
            settled_price = best_resting.price

            if order.side == Side.BUY:
                trade_cost_scaled = transactioning_shares * settled_price
                trade_cost = trade_cost_scaled // self.PRECISION_MULTIPLIER
                
                if order.max_authorized_funds is not None and (total_spent + trade_cost) > order.max_authorized_funds:
                    break
                total_spent += trade_cost

            order.number_of_shares -= transactioning_shares
            best_resting.number_of_shares -= transactioning_shares

            buyer_id = order.order_owner_id if order.side == Side.BUY else best_resting.order_owner_id
            seller_id = order.order_owner_id if order.side == Side.SELL else best_resting.order_owner_id

            executed_trades.append(Trade(
                ticker=self.ticker,
                quantity=transactioning_shares,
                price_locked_by_user=0,
                price_setteled_at=settled_price,
                buyer_id=buyer_id,
                seller_id=seller_id
            ))

            if best_resting.number_of_shares <= 0:
                heapq.heappop(target_side)
                self.active_uuids.pop(resting_id_str, None)

        return executed_trades

    def add_order(self, order: Order):    
        order_id_str = str(order.order_id)
            
        if order.side == Side.SELL:
            sorted_tuple = (order.price, order.date_time, order_id_str, order)
            heapq.heappush(self.ask, sorted_tuple)
            self.active_uuids[order_id_str] = order
                
        if order.side == Side.BUY:
            sorted_tuple = (-1 * order.price, order.date_time, order_id_str, order)
            heapq.heappush(self.bid, sorted_tuple)
            self.active_uuids[order_id_str] = order
    
    def execute(self):
        trades_executed = []
        while self.bid and self.ask:
            best_bid = self.bid[0][3]
            best_ask = self.ask[0][3]
            
            if str(best_bid.order_id) in self.canceled_uuids:
                heapq.heappop(self.bid)
                self.canceled_uuids.remove(str(best_bid.order_id))
                continue
                
            if str(best_ask.order_id) in self.canceled_uuids:
                heapq.heappop(self.ask) 
                self.canceled_uuids.remove(str(best_ask.order_id))
                continue
                
            if best_bid.price < best_ask.price:
                break
                
            if best_bid.price >= best_ask.price:
                transactioning_shares = min(best_bid.number_of_shares, best_ask.number_of_shares)
                best_ask.number_of_shares -= transactioning_shares 
                best_bid.number_of_shares -= transactioning_shares

                if best_bid.date_time < best_ask.date_time:
                    settled_price = best_bid.price
                else:
                    settled_price = best_ask.price
                    
                trades_executed.append(Trade(
                    ticker=self.ticker,
                    quantity=transactioning_shares,
                    price_locked_by_user=best_bid.price if best_bid.price else 0,
                    price_setteled_at=settled_price,
                    buyer_id=best_bid.order_owner_id,
                    seller_id=best_ask.order_owner_id
                ))
                
            if best_ask.number_of_shares <= 0:
                heapq.heappop(self.ask)
                self.active_uuids.pop(str(best_ask.order_id), None)
                
            if best_bid.number_of_shares <= 0:
                heapq.heappop(self.bid)
                self.active_uuids.pop(str(best_bid.order_id), None)
                
        return trades_executed

    def tombstone_delete(self, order_uuid : UUID):
        with self.lock:
            order_id_str = str(order_uuid)
            order_delete = self.active_uuids.pop(order_id_str, None)
            
            if order_delete:
                order_delete.is_canceled = True
                self.canceled_uuids.add(order_id_str)
                return order_delete
            else:
                return False

    def get_specific_order_by_id(self, order_uuid):
        with self.lock:
            return self.active_uuids.get(str(order_uuid), None)

    def get_current_bbo(self) -> dict:
        with self.lock:
            best_ask = None
            best_bid = None
            
            while self.ask:
                top_ask = self.ask[0][3]
                if str(top_ask.order_id) not in self.canceled_uuids:
                    best_ask = top_ask.price
                    break
                else:
                    heapq.heappop(self.ask)
                    self.canceled_uuids.remove(str(top_ask.order_id))

            while self.bid:
                top_bid = self.bid[0][3]
                if str(top_bid.order_id) not in self.canceled_uuids:
                    best_bid = top_bid.price
                    break
                else:
                    heapq.heappop(self.bid)
                    self.canceled_uuids.remove(str(top_bid.order_id))

            return {
                "best_ask_price" : best_ask if best_ask else int(0),
                "best_bid_price" : best_bid if best_bid else int(0)
            }

    def reset_engine(self):
        self.bid = []
        self.ask = []
        self.active_uuids = {}
        self.canceled_uuids = set()

        gc.collect()
        #  we call gc collect here explictly so that it does not run in between our benchmarking phase and corrupt the benchmarking data