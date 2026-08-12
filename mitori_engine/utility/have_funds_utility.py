from decimal import Decimal

async def redis_get_buyer_portfolio( ticker:str ,pipeline, portfolio_id:str)-> dict:
    available_cash = await pipeline.hget(portfolio_id,'available_cash')
    locked_cash = await pipeline.hget(portfolio_id,'locked_balance')
    safe_available_cash = Decimal(str(available_cash or 0))
    safe_locked_cash = Decimal(str(locked_cash or 0))
    get_sell_price = await pipeline.hget(f'ticker:{ticker}:bbo', 'best_ask_price')
    
    return{
        'safe_available_cash': safe_available_cash,
        'safe_locked_cash': safe_locked_cash,
        'BBO_ask_price':get_sell_price  if get_sell_price else None
    }

async def redis_get_seller_positions(ticker:str, positions_id:str, pipeline)->dict:
    available_shares = await pipeline.hget(positions_id, ticker)
    locked_shares = await pipeline.hget(positions_id, f'locked_{ticker}')
    
    safe_available_shares = Decimal(str(available_shares or 0))
    safe_locked_shares = Decimal(str(locked_shares or 0))
    get_bid_price = await pipeline.hget(f'ticker:{ticker}:bbo', 'best_bid_price')

    return  {
        f'{ticker}':safe_available_shares,
        f'locked_{ticker}':safe_locked_shares,
        'BBO_bid_price':get_bid_price if get_bid_price else None
    }