import  redis
from core_ledger.models import Portfolio, Position
import os
from dotenv import load_dotenv
from decimal import Decimal
from django.conf import settings

load_dotenv()

redis_client = redis.Redis(host=os.getenv('REDIS'),port=os.getenv('REDIS_PORT'),db=0,decode_responses=True)

def redis_positions_portfolio_service(id:str):
    try:
        user_portfolio = Portfolio.objects.get(user_id=id)

        user_position = Position.objects.filter(portfolio_id=user_portfolio.id, quantity__gt=0)

        portfolio_key = f"cache:portfolio:{id}"
        positions_key = f"cache:positions:{id}"

        multiplier = Decimal(settings.SYSTEM_PRECISION_MULTIPLIER)

        scaled_cash_balance = int(user_portfolio.cash_balance * multiplier)
        
        with redis_client.pipeline() as pipeline:
            pipeline.delete(portfolio_key)

            portfolio_redis_dict ={
                'available_cash':scaled_cash_balance,
                'locked_balance':0
            }
            pipeline.hset(portfolio_key, mapping=portfolio_redis_dict)

            pipeline.delete(positions_key)

            if user_position.exists():
                position_dict = {}
                for pos in user_position:
                    position_dict[pos.asset_symbol] = int(pos.quantity * multiplier)
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

    multiplier = Decimal(settings.SYSTEM_PRECISION_MULTIPLIER)

    quantity = Decimal(str(transaction_data['quantity']))/multiplier
    price_locked = Decimal(str(transaction_data['price_locked_by_user']))/multiplier 
    price_settled = Decimal(str(transaction_data['price_setteled_at'])) /multiplier


    total_locked = price_locked * quantity
    total_settled = price_settled * quantity
    funds_remaining = total_locked - total_settled

    scaled_quantity = int(quantity * multiplier)
    scaled_total_locked = int(total_locked * multiplier)
    scaled_total_settled = int(total_settled * multiplier)
    scaled_funds_remaining = int(funds_remaining * multiplier)

    redis_server.hincrby(seller_cache, f"locked_{ticker}", -scaled_quantity)
    redis_server.hincrby(seller_cash_cache, 'available_cash', scaled_total_settled)

    redis_server.hincrby(buyer_cache, 'locked_balance', -scaled_total_locked)
    redis_server.hincrby(buyer_position_cache, ticker, scaled_quantity)

    if funds_remaining > 0:
        redis_server.hincrby(buyer_cache, 'available_cash', scaled_funds_remaining)

    print('finished running')