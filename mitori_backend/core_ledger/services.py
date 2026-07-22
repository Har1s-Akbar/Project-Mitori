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
            print("executed properly")
    except Exception as e:
        print(e)