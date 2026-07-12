import heapq
from .models import Order, Trade, Side

class OrderBook():
    ticker:str
    
    def __init__(self,ticker):
        self.bid =[]
        self.ask=[]
        self.ticker = ticker

    def add_order(self, order:Order):
        if(order.side == Side.SELL):
            sorted_tuple = (order.price, order.date_time,order.id, order)
            heapq.heappush(self.ask, sorted_tuple)
            # self.bids.append[self]
        if(order.side == Side.BUY):
            sorted_tuple = (-1*(order.price), order.date_time,order.id, order)
            heapq.heappush( self.bid,sorted_tuple)