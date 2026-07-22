import  redis
from core_ledger.models import Portfolio, Position

redis_client = redis.Redis(host='localhost',port=6379,db=0,decode_responses=True)

def redis_positions_portfolio_service(id:str):
    try:
        user_portfolio = Portfolio.objects.get(user_id=id)

        user_position = Position.objects.filter(portfolio_id=user_portfolio.id, quantity__gt=0)

        portfolio_key = f"cache:portfolio:{id}"

        positions_key = f"cache:positions:{id}"
        with redis_client.pipeline() as pipeline:
            pipeline.delete(portfolio_key)
            portfolio_redis_dict ={
                'available_cash':str(user_portfolio.cash_balance),
                'locked_balance':0
            }
            pipeline.hset(portfolio_key, mapping=portfolio_redis_dict)

            pipeline.delete(positions_key)

            if user_position.exists():
                position_dict = {}
                for pos in user_position:
                    position_dict[pos.asset_symbol] = str(pos.quantity)
                    position_dict[f'locked_{pos.asset_symbol}'] = 0
                
                pipeline.hset(positions_key, mapping=position_dict)

            pipeline.execute()
    except Exception as e:
        print(e)

def settle_cache(transaction_data, redis_server):
    ticker = transaction_data['ticker']
    seller_id = transaction_data['seller_id']
    seller_cache = f"cache:positions:{seller_id}"
    seller_cash_cache = f"cache:portfolio:{seller_id}"

    buyer_id = transaction_data['buyer_id']
    buyer_cache = f"cache:portfolio:{buyer_id}"
    buyer_position_cache = f"cache:positions:{buyer_id}"

    quantity = int(transaction_data['quantity'])
    price_locked = float(transaction_data['price_locked_by_user'])
    price_settled = float(transaction_data['price_setteled_at'])

    total_locked = price_locked * quantity
    total_settled = price_settled * quantity
    funds_remaining = total_locked - total_settled

    redis_server.hincrbyfloat(seller_cache, f"locked_{ticker}", -quantity)
    redis_server.hincrbyfloat(seller_cash_cache, 'available_cash', total_settled)

    redis_server.hincrbyfloat(buyer_cache, 'locked_balance', -total_locked)
    redis_server.hincrbyfloat(buyer_position_cache, ticker, quantity)

    if funds_remaining > 0:
        redis_server.hincrbyfloat(buyer_cache, 'available_cash', funds_remaining)

    print('finished running')