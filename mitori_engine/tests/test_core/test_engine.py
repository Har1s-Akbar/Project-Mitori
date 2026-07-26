from core.engine import OrderBook
from core.models import Side, Order, Trade
from decimal import Decimal
from uuid import uuid4

def create_order(side, shares, price, ticker):
    return Order(
        ticker=ticker,
        price = Decimal(price),
        number_of_shares=shares,
        side=side,
        order_owner_id=uuid4(),
        is_canceled=False,
    )

def test_match_order_same_price():
    book =  OrderBook('APP')

    buySide= create_order(Side.BUY, 200, "10", 'APP')
    sellSide = create_order(Side.SELL, 200,"10",'APP')

    book.add_order(buySide)
    book.add_order(sellSide)

    trade = book.execute()

    assert len(trade) == 1
    assert trade[0].quantity == 200
    assert trade[0].buyer_id != trade[0].seller_id
    assert trade[0].price_locked_by_user == trade[0].price_setteled_at 
    assert trade[0].ticker == 'APP'

def test_order_partial_fill():
    book = OrderBook('APP')
    buySide = create_order(Side.BUY, 40, "10",'APP')
    sellSide = create_order(Side.SELL,20,"10",'APP')

    book.add_order(buySide)
    book.add_order(sellSide)
    trade = book.execute()


    assert len(trade) == 1
    assert trade[0].quantity ==20.0000
    assert trade[0].buyer_id != trade[0].seller_id
    assert trade[0].price_locked_by_user == trade[0].price_setteled_at
    assert trade[0].ticker == 'APP'

def test_order_no_match():
    book = OrderBook('APP')
    buySide = create_order(Side.BUY, 40, "5",'APP')
    sellSide = create_order(Side.SELL,20,"20",'APP')

    book.add_order(buySide)
    book.add_order(sellSide)
    trade = book.execute()

    assert len(trade) ==0

def test_best_bid_match():
    book = OrderBook('APP')
    buySide = create_order(Side.BUY, 20, "15",'APP')
    sellSide = create_order(Side.SELL,20,"8",'APP')

    book.add_order(buySide)
    book.add_order(sellSide)
    trade = book.execute()

    assert len(trade) == 1
    assert trade[0].price_setteled_at == 8.000
    assert trade[0].quantity == 20
    assert trade[0].price_setteled_at != trade[0].price_locked_by_user
    assert trade[0].buyer_id != trade[0].seller_id
    assert trade[0].ticker == 'APP'

def test_best_bid_partial_fill():
    book = OrderBook('APP')
    buySide = create_order(Side.BUY, 40, "15",'APP')
    sellSide = create_order(Side.SELL,20.5,"8",'APP')

    book.add_order(buySide)
    book.add_order(sellSide)
    trade = book.execute()

    assert len(trade) ==1
    assert trade[0].quantity == 20.50000
    assert trade[0].price_locked_by_user != trade[0].price_setteled_at
    assert trade[0].seller_id != trade[0].buyer_id
    assert trade[0].ticker == 'APP'
    assert trade[0].price_setteled_at == 8

def test_ticker_mismatch():
    book = OrderBook('APP')
    buySide = create_order(Side.BUY, 20, "15",'TSLA')
    sellSide = create_order(Side.SELL,20,"15",'APP')

    book.add_order(buySide)
    book.add_order(sellSide)

    trade = book.execute()

    assert len(trade) == 1

    #This test  is telling that order book's only job is to match orders and not to check for ticker match , which i have correctly
    # implemented in the route when /order comes we check and route the order to the correct order book

def test_tombstone_cancel():
    book = OrderBook('APP')

    buySide = create_order(Side.BUY, 20, "15",'APP')
    sellSide = create_order(Side.SELL,20,"15",'APP')

    book.add_order(buySide)
    book.add_order(sellSide)

    book.tombstone_delete(buySide.order_id)

    trade = book.execute()

    assert len(trade) == 0