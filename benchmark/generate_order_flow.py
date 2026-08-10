import numpy as np
import json
import os
from decimal import Decimal , ROUND_HALF_UP
import uuid
import  enum

class Type(enum, str):
    MARKET="market"
    LIMIT = "limit"

class Side(enum,str):
    SELL = "sell"
    BUY = "buy"

def steup():
    os.makedirs('benchmark/data', exist_ok=True)
    print("Environment verified , directory exists")

theta = 0.10
seed = 39
sigma = 0.50
center_value = 100.00

def ornstein_Uhlenbeck_price(num_of_orders: int) ->np.ndarray:
    prices = np.zeros(num_of_orders)
    prices[0] = center_value
    shock_value = np.random.normal(0,1, num_of_orders)
    for t in range(1,num_of_orders):
        prices[t] = prices[t-1] + theta(center_value - prices[t-1])+sigma*shock_value[t]
    return prices

def format_as_decimal_string(value:float)->str:
    dec_as_str = Decimal(str(value)).quantize(Decimal('0.00000001', rounding=ROUND_HALF_UP))
    return dec_as_str

def generate_resting_book():
    prices = ornstein_Uhlenbeck_price(50000)
    sides = np.random.choice([Side.SELL,  Side.BUY],size=50000)
    quantities = np.random.randint(1,101,size=50000)
    user_uuids = np.array([uuid.uuid4() for _ in range(50000)], dtype=object)
    master_resting = []


    for i in range(50000):
        master_resting.append({
            'ticker':'APP',
            type: Type.LIMIT,
            'side':sides[i],
            'price': format_as_decimal_string(prices[i]),
            'number_of_shares':quantities,
            'is_canceled':False,
            'order_owner_id':user_uuids[i]
        })

    print("Slicing and saving tier files...")
    with open("benchmarks/data/seed_1k.json", "w") as f:
        json.dump(master_resting[:1000], f)
    with open("benchmarks/data/seed_25k.json", "w") as f:
        json.dump(master_resting[:25_000], f)
    with open("benchmarks/data/seed_50k.json", "w") as f:
        json.dump(master_resting, f)

def generate_active_stream():
    prices = ornstein_Uhlenbeck_price(100000)

    types = np.random.choice([Type.MARKET, Type.LIMIT], size=100_000, p=[0.7,0.3])

    sides = np.random.choice([Side.BUY, Side.SELL], size=100_000)

    quantities = np.random.randint(1,101,size=100_000)
    user_uuids = np.array([uuid.uuid4() for _ in range(50000)], dtype=object)

    active_stream = []
    for i in range(100_000):
        price_val = format_as_decimal_string(prices[i]) if types[i] == Type.LIMIT else None
        
        active_stream.append({
            'ticker':'APP',
            "type": types[i],
            "side": sides[i],
            "price": price_val,
            "number_of_shares": str(quantities[i]),
            'order_owner_id': user_uuids[i]
        })
        
    with open("benchmarks/data/active_stream.json", "w") as f:
        json.dump(active_stream, f)

    if __name__ == "__main__":
        np.random.seed(seed)
        steup()
        generate_resting_book()
        generate_active_stream()
        print("Synthetic data pipeline execution complete.")