from fastapi import HTTPException, status, Request, Depends
from api.security import is_user_Authenticated, AuthenticatedUser
from schemas.schema import OrderReq
from core.models import Type, Side
from decimal import Decimal
import redis.exceptions as exp
from schemas.schema import MARKET
from typing import AsyncGenerator
import os
from dotenv import load_dotenv
from utility.have_funds_utility import redis_get_buyer_portfolio, redis_get_seller_positions
load_dotenv()
from core.config import ALLOWED_TICKERS

async def have_funds(request: Request, user: AuthenticatedUser = Depends(is_user_Authenticated), order: OrderReq = None) -> AsyncGenerator[AuthenticatedUser, None]:
    
    if order.ticker not in ALLOWED_TICKERS:
        raise HTTPException(status_code=404, detail="Ticker does not exist")

    multiplier = Decimal(os.getenv('SYSTEM_PRECISION_MULTIPLIER', '100000000'))
    redis_connection_port = request.app.state.redis

    order_side = order.side
    order_quantity = order.number_of_shares
    order_ticker = order.ticker
    order_user_id = user.user_id
    order_type = order.type
    order_price = order.price

    retry_counter = 3
    
    locked_fiat = 0
    locked_shares = 0

    async with redis_connection_port.pipeline() as pipeline:
        while retry_counter > 0:
            try:
                if order_side == Side.BUY:
                    await pipeline.watch(f'cache:portfolio:{order_user_id}')
                    user_data = await redis_get_buyer_portfolio(ticker=order_ticker, pipeline=pipeline, portfolio_id=f'cache:portfolio:{order_user_id}')

                    if order_type == Type.MARKET:
                        if user_data['BBO_ask_price'] is None:
                            raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Market does not have enough liquidity")
                        
                        total = (Decimal(user_data['BBO_ask_price']) * order_quantity * Decimal("1.01"))
                        
                        
                    elif order_type == Type.LIMIT:
                        total = int(order_price * order_quantity * multiplier)

                    if total > user_data['safe_available_cash']:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough funds for the trade")
                    
                    updates = {
                        'available_cash': int(user_data['safe_available_cash'] - total),
                        'locked_balance': int(user_data['safe_locked_cash'] + total)
                    }
                    pipeline.multi()
                    pipeline.hset(f'cache:portfolio:{order_user_id}', mapping=updates)
                    await pipeline.execute()
                    
                    locked_fiat = total 

                    order.max_authorized_funds = Decimal(total) / multiplier 
                    break

                elif order_side == Side.SELL:
                    await pipeline.watch(f'cache:positions:{order_user_id}')
                    user_data = await redis_get_seller_positions(ticker=order_ticker, pipeline=pipeline, positions_id=f'cache:positions:{order_user_id}')

                    if order_type == Type.MARKET and user_data['BBO_bid_price'] is None:
                        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Market does not have enough liquidity")
                    
                    total_shares = int(order_quantity * multiplier)

                    if total_shares > user_data[order_ticker]:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You do not have enough shares")
                    
                    updates = {
                        order_ticker: int(user_data[order_ticker] - total_shares),
                        f'locked_{order_ticker}': int(user_data[f'locked_{order_ticker}'] + total_shares)
                    }
                    pipeline.multi()
                    pipeline.hset(f'cache:positions:{order_user_id}', mapping=updates)
                    await pipeline.execute()
                    
                    locked_shares = total_shares
                    break

            except exp.WatchError:
                retry_counter -= 1
                if retry_counter == 0:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Retry your order in few seconds")
                continue

    try:
        yield user
    except Exception as route_error:
        async with redis_connection_port.pipeline() as rollback_pipeline:
            if locked_shares > 0:
                rollback_pipeline.hincrby(f'cache:positions:{order_user_id}', order_ticker, int(locked_shares))
                rollback_pipeline.hincrby(f'cache:positions:{order_user_id}', f'locked_{order_ticker}', int(-locked_shares))
            
            if locked_fiat > 0:
                rollback_pipeline.hincrby(f'cache:portfolio:{order_user_id}', 'available_cash', int(locked_fiat))
                rollback_pipeline.hincrby(f'cache:portfolio:{order_user_id}', 'locked_balance', int(-locked_fiat))
                
            await rollback_pipeline.execute()
            
        raise route_error