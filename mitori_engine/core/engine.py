import heapq
from .models import Order, Trade, Side

class OrderBook():
    ticker:str
    
    def __init__(self,ticker:str):
        self.bid =[]
        self.ask=[]
        self.ticker = ticker

    def add_order(self, order:Order):
        if(order.side == Side.SELL):
            sorted_tuple = (order.price, order.date_time,order.order_id, order)
            heapq.heappush(self.ask, sorted_tuple)
            # self.bids.append[self]
        if(order.side == Side.BUY):
            sorted_tuple = (-1*(order.price), order.date_time,order.order_id, order)
            heapq.heappush( self.bid,sorted_tuple)

    def execute(self):
        trades_executed = []
        while self.bid and self.ask :
            best_bid = self.bid[0][3]
            best_ask = self.ask[0][3]
            if(best_bid.price < best_ask.price):
                break
            if(best_bid.price >= best_ask.price):
                transactioning_shares = min(best_bid.number_of_shares, best_ask.number_of_shares)
                best_ask.number_of_shares = best_ask.number_of_shares-transactioning_shares 
                best_bid.number_of_shares = best_bid.number_of_shares-transactioning_shares
                trades_executed.append(Trade(self.ticker,transactioning_shares,best_ask.price ,best_bid.order_owner_id,best_ask.order_owner_id))

            if best_ask.is_filled:
                heapq.heappop(self.ask)
            if best_bid.is_filled:
                heapq.heappop(self.bid)
        return trades_executed