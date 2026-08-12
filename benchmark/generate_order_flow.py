import numpy as np
import os
from decimal import Decimal , ROUND_HALF_UP
import uuid
from enum import Enum
import orjson


class Type(str, Enum):
    MARKET="market"
    LIMIT = "limit"

class Side(str , Enum):
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
        prices[t] = prices[t-1] + theta*(center_value - prices[t-1])+sigma*shock_value[t]


    return prices

def format_as_decimal_string(value:float)->str:
    dec_as_str = Decimal(str(value)).quantize(Decimal('0.00000001'),rounding=ROUND_HALF_UP)
    return str(dec_as_str)


def generate_resting_book():
    prices = ornstein_Uhlenbeck_price(50000)
    sides = np.random.choice([Side.SELL.value,  Side.BUY.value],size=50000)
    quantities = np.random.randint(1,101,size=50000)
    user_uuids = np.array([uuid.uuid4() for _ in range(50000)], dtype=object)
    master_resting = []


    for i in range(50000):
        absolute_difference = abs(prices[i] - center_value)

        if sides[i] == Side.BUY.value:
            safe_price = prices[i] - absolute_difference - 0.01
        if sides[i] == Side.SELL.value:
            safe_price = prices[i] + absolute_difference +0.01
        master_resting.append({
            'ticker':'APP',
            'type': Type.LIMIT.value,
            'side':sides[i],
            'price': format_as_decimal_string(safe_price),
            'number_of_shares':str(quantities[i]),
            'is_canceled':False,
            'order_owner_id':user_uuids[i],
            'is_canceled':False
        })

    print("Slicing and saving tier files...")
    with open("benchmark/data/seed_1k.json", "wb") as f:
        f.write(orjson.dumps(master_resting[:1000]))
    with open("benchmark/data/seed_25k.json", "wb") as f:
        f.write(orjson.dumps(master_resting[:25_000]))
    with open("benchmark/data/seed_50k.json", "wb") as f:
        f.write(orjson.dumps(master_resting))

def generate_active_stream():
    prices = ornstein_Uhlenbeck_price(200000)

    types = np.random.choice([Type.MARKET.value, Type.LIMIT.value], size=200_000, p=[0.3,0.7])

    sides = np.random.choice([Side.BUY.value, Side.SELL.value], size=200_000)

    quantities = np.random.randint(1,101,size=200_000)
    user_uuids = np.array([uuid.uuid4() for _ in range(200000)], dtype=object)

    active_stream = []
    for i in range(200_000):
        price_val = format_as_decimal_string(prices[i]) if types[i] == Type.LIMIT else None
        
        active_stream.append({
            'ticker':'APP',
            "type": types[i],
            "side": sides[i],
            "price": price_val,
            "number_of_shares": str(quantities[i]),
            'order_owner_id': user_uuids[i],
            'is_canceled':False
        })
        
    with open("benchmark/data/active_stream.json", "wb") as f:
        f.write(orjson.dumps(active_stream))

if __name__ == "__main__":
    np.random.seed(seed)
    steup()
    generate_resting_book()
    generate_active_stream()
    print("Synthetic data pipeline execution complete.")