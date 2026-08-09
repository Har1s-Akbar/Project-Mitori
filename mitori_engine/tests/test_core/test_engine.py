from core.engine import OrderBook
from core.models import Side, Type, Order, Trade
from decimal import Decimal
from uuid import uuid4
import time

def create_order(side, shares, price, ticker, order_type=Type.LIMIT, max_funds=None):
    time.sleep(0.001)
    
    return Order(
        ticker=ticker,
        type=order_type,
        price=Decimal(price) if price else None,
        number_of_shares=Decimal(shares),
        side=side,
        order_owner_id=uuid4(),
        is_canceled=False,
        max_authorized_funds=Decimal(max_funds) if max_funds else None
    )

def test_match_order_same_price():
    book = OrderBook('APP')

    buySide = create_order(Side.BUY, 200, "10", 'APP')
    sellSide = create_order(Side.SELL, 200, "10", 'APP')

    book.process_order(buySide)
    trade = book.process_order(sellSide)

    assert len(trade) == 1
    assert trade[0].quantity == 200
    assert trade[0].buyer_id != trade[0].seller_id
    assert trade[0].price_locked_by_user == trade[0].price_setteled_at 
    assert trade[0].ticker == 'APP'

def test_order_partial_fill():
    book = OrderBook('APP')
    buySide = create_order(Side.BUY, 40, "10", 'APP')
    sellSide = create_order(Side.SELL, 20, "10", 'APP')

    book.process_order(buySide)
    trade = book.process_order(sellSide)

    assert len(trade) == 1
    assert trade[0].quantity == 20
    assert trade[0].buyer_id != trade[0].seller_id
    assert trade[0].price_locked_by_user == trade[0].price_setteled_at
    assert trade[0].ticker == 'APP'

def test_order_no_match():
    book = OrderBook('APP')
    buySide = create_order(Side.BUY, 40, "5", 'APP')
    sellSide = create_order(Side.SELL, 20, "20", 'APP')

    book.process_order(buySide)
    trade = book.process_order(sellSide)

    assert len(trade) == 0

def test_best_bid_match():
    book = OrderBook('APP')
    buySide = create_order(Side.BUY, 20, "15", 'APP')   
    sellSide = create_order(Side.SELL, 20, "8", 'APP')  

    book.process_order(buySide)
    trade = book.process_order(sellSide)

    assert len(trade) == 1
    assert trade[0].price_setteled_at == Decimal('15')

def test_best_bid_partial_fill():
    book = OrderBook('APP')
    buySide = create_order(Side.BUY, 40, "15", 'APP')
    sellSide = create_order(Side.SELL, 20, "8", 'APP')

    book.process_order(buySide)
    trade = book.process_order(sellSide)

    assert len(trade) == 1
    assert trade[0].quantity == 20
    assert trade[0].price_setteled_at == Decimal('15')
    
    assert len(book.bid) == 1 
    assert len(book.ask) == 0
    
    assert book.bid[0][3].number_of_shares == 20
    assert book.bid[0][3].price == Decimal('15')
    assert book.bid[0][0] == Decimal('-15')

def test_tombstone_cancel():
    book = OrderBook('APP')

    buySide = create_order(Side.BUY, 20, "15", 'APP')
    sellSide = create_order(Side.SELL, 20, "15", 'APP')

    book.process_order(buySide)
    
    book.tombstone_delete(buySide.order_id)
    
    trade = book.process_order(sellSide)
    assert len(trade) == 0

def test_price_time_priority():
    book = OrderBook('APP')

    sellSide1 = create_order(Side.SELL, 30, "7.00", 'APP')
    sellSide2 = create_order(Side.SELL, 30, "7.00", 'APP')
    sellSide3 = create_order(Side.SELL, 30, "7.00", 'APP')
    sellSide4 = create_order(Side.SELL, 30, "7.00", 'APP')

    buySide1 = create_order(Side.BUY, 30, "7", 'APP')
    buySide2 = create_order(Side.BUY, 30, "7", 'APP')

    book.process_order(sellSide1)
    book.process_order(sellSide2)
    book.process_order(sellSide3)
    book.process_order(sellSide4)
    
    assert (book.ask[0][1] < book.ask[1][1]) and (book.ask[1][1] < book.ask[2][1]) and (book.ask[2][1] < book.ask[3][1])

    trades1 = book.process_order(buySide1)

    trades2 = book.process_order(buySide2)

    assert len(trades1) == 1
    assert len(trades2) == 1
    assert len(book.ask) == 2
    assert len(book.bid) == 0

    assert book.ask[0][3].order_id == sellSide3.order_id
    assert book.ask[1][3].order_id == sellSide4.order_id

def test_market_order_financial_ceiling():
    """
    Validates that a Market BUY order drops remaining shares if the cost 
    exceeds the max_authorized_funds locked by the Redis dependency.
    """
    book = OrderBook('APP')
    
    book.process_order(create_order(Side.SELL, 10, "10", 'APP'))
    book.process_order(create_order(Side.SELL, 10, "15", 'APP'))
    
    market_buy = create_order(
        side=Side.BUY, 
        shares=20, 
        price=None, 
        ticker='APP', 
        order_type=Type.MARKET, 
        max_funds="120.00"
    )
    
    trades = book.process_order(market_buy)
        
    assert len(trades) == 1
    assert trades[0].quantity == Decimal("10")
    assert trades[0].price_setteled_at == Decimal("10")
    
    assert len(book.ask) == 1
    assert book.ask[0][3].price == Decimal("15")

def test_get_current_bbo():
    book = OrderBook('APP')
    
    book.process_order(create_order(Side.BUY, 10, "99.50", 'APP'))
    book.process_order(create_order(Side.SELL, 10, "100.50", 'APP'))
    
    bbo = book.get_current_bbo()
    
    assert bbo["best_bid_price"] == "99.50"
    assert bbo["best_ask_price"] == "100.50"