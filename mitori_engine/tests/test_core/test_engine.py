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
    assert trade[0].quantity ==20
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
    sellSide = create_order(Side.SELL,20,"8",'APP')

    book.add_order(buySide)
    book.add_order(sellSide)
    trade = book.execute()

    assert len(trade) ==1
    assert trade[0].quantity == 20
    assert trade[0].price_locked_by_user != trade[0].price_setteled_at
    assert trade[0].seller_id != trade[0].buyer_id
    assert trade[0].ticker == 'APP'
    assert trade[0].price_setteled_at == 8
    # checking if the partial filled order is in the book and checking if the completely filled order is flushed from the book
    assert len(book.bid) == 1 
    assert len(book.ask) == 0
    #checking for the remaining order shares quantity is 19.5 and checking the price of the order did it mutate after being matched with the order or not
    assert book.bid[0][3].number_of_shares == 20
    assert book.bid[0][3].price ==  15
    #checking when it is in the heap it is properly being appended with - in front of the price for creation of min heap
    assert book.bid[0][0] == -15

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

def test_price_time_priority():
    book = OrderBook('APP')

    sellSide1 = create_order(Side.SELL, 30, "7.00", 'APP')
    sellSide2 = create_order(Side.SELL, 30, "7.00", 'APP')
    sellSide3 = create_order(Side.SELL, 30, "7.00", 'APP')
    sellSide4 = create_order(Side.SELL, 30, "7.00", 'APP')

    buySide1 = create_order(Side.BUY, 30 , "7", 'APP')
    buySide2 = create_order(Side.BUY, 30 , "7", 'APP')

    book.add_order(sellSide1)
    book.add_order(sellSide2)
    book.add_order(sellSide3)
    book.add_order(sellSide4)
    # Checking if the time priority is holding up or not in heap
    assert (book.ask[0][1] < book.ask[1][1]) and (book.ask[1][1]<book.ask[2][1]) and (book.ask[2][1]<book.ask[3][1])

    book.add_order(buySide1)
    book.add_order(buySide2)
    assert book.bid[0][1]<book.bid[1][1]

    trades = book.execute()

    assert len(trades) == 2
    assert trades[0].price_setteled_at == trades[1].price_setteled_at
    assert trades[0].order_id != trades[1].order_id
    assert trades[0].date_time < trades[1].date_time

    #checking if both orders are matched and only the ask is populated and bid is empty

    assert len(book.ask) == 2
    assert len(book.bid) == 0

    # checking if the remaining orders are the one that were created later or we can say the later remaining orders have same order_id as sellside3 and sellside4

    assert book.ask[0][3].order_id == sellSide3.order_id
    assert book.ask[1][3].order_id == sellSide4.order_id

def test_one_request_at_a_time():
    book = OrderBook('APP')

    sellSide1 = create_order(Side.SELL, 30, "7.00", 'APP')
    book.add_order(sellSide1)
    trade = book.execute()
    assert len(trade) == 0

    buySide1 = create_order(Side.BUY, 30 , "7", 'APP')
    book.add_order(buySide1)
    trade1  = book.execute()
    assert len(trade1) == 1

    sellSide2 = create_order(Side.SELL, 30, "7.00", 'APP')
    book.add_order(sellSide2)
    trade3  = book.execute()
    assert len(trade3) == 0


    sellSide3 = create_order(Side.SELL, 30, "7.00", 'APP')
    book.add_order(sellSide3)
    trade4 = book.execute()
    assert len(trade4) == 0

    sellSide4 = create_order(Side.SELL, 30, "7.00", 'APP')
    book.add_order(sellSide4)
    trade5 = book.execute()
    assert len(trade5) == 0

    buySide2 = create_order(Side.BUY, 30 , "7", 'APP')
    book.add_order(buySide2)
    trade6 = book.execute()
    assert len(trade6) == 1