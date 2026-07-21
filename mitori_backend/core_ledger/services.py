import  redis
from core_ledger.models import Portfolio, Position

redis_client = redis.Redis(host='localhost',port=6379,db=0,decode_responses=True)

def redis_positions_portfolio_service(id:str):
    user_portfolio = Portfolio.objects.get(user_id=id)

    user_position = Position.objects.get(user_portfolio.id)

    with redis_client.pipeline() as pipeline:
        pipeline.set('cache:portfolio:{id}:', user_portfolio.cash_balance)

        pipeline.delete('cache:position:{id}')