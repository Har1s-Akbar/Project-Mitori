import heapq
from .models import Order, Trade, Side

class OrderBook():
    bids = []
    ask = []
    
    def __init__(self,ticker):
        self.bids =[]
        self.ask=[]


    def add_order(self):
        if(Order.side == Side.SELL):
            self.bids.append[self]
        if(Order.side == Side.BUY):
            self.bids.append[self]
        