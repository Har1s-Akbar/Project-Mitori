import heapq
from .models import Order, Trade, Side
import uuid

class OrderBook():
    ticker: str
    
    def __init__(self, ticker: str):
        self.bid = []
        self.ask = []
        self.ticker = ticker
        self.active_uuids = {}
        self.canceled_uuids = set()

    def add_order(self, order: Order):
        order_id_str = str(order.order_id)
        
        if order.side == Side.SELL:
            sorted_tuple = (order.price, order.date_time, order.order_id, order)
            heapq.heappush(self.ask, sorted_tuple)
            self.active_uuids[order_id_str] = order
            
        if order.side == Side.BUY:
            sorted_tuple = (-1 * order.price, order.date_time, order.order_id, order)
            heapq.heappush(self.bid, sorted_tuple)
            self.active_uuids[order_id_str] = order

    def execute(self):
        trades_executed = []
        while self.bid and self.ask:
            best_bid = self.bid[0][3]
            best_ask = self.ask[0][3]
            
            if str(best_bid.order_id) in self.canceled_uuids:
                heapq.heappop(self.bid)  # Pop bid from bid heap
                self.canceled_uuids.remove(str(best_bid.order_id))
                continue
                
            if str(best_ask.order_id) in self.canceled_uuids:
                heapq.heappop(self.ask)  # Pop ask from ask heap
                self.canceled_uuids.remove(str(best_ask.order_id))
                continue
                
            if best_bid.price < best_ask.price:
                break
                
            if best_bid.price >= best_ask.price:
                transactioning_shares = min(best_bid.number_of_shares, best_ask.number_of_shares)
                best_ask.number_of_shares = best_ask.number_of_shares - transactioning_shares 
                best_bid.number_of_shares = best_bid.number_of_shares - transactioning_shares
                trades_executed.append(Trade(
                    ticker=self.ticker,
                    quantity=transactioning_shares,
                    price_locked_by_user=best_bid.price,
                    price_setteled_at=best_ask.price,
                    buyer_id=best_bid.order_owner_id,
                    seller_id=best_ask.order_owner_id
                ))

            if best_ask.is_filled:
                heapq.heappop(self.ask)
                self.active_uuids.pop(str(best_ask.order_id), None)
                
            if best_bid.is_filled:
                heapq.heappop(self.bid)
                self.active_uuids.pop(str(best_bid.order_id), None)
                
        return trades_executed

    def tombstone_delete(self, order_uuid):
        order_id_str = str(order_uuid)
        
        order_delete = self.active_uuids.pop(order_id_str, None)
        
        if order_delete:
            order_delete.is_canceled = True
            self.canceled_uuids.add(order_id_str)
            return order_delete
        else:
            return False