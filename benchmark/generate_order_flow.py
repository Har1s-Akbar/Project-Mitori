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
    os.makedirs('benchmark/data/data_for_test', exist_ok=True)
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
    sides = np.random.choice([Side.SELL.value, Side.BUY.value], size=50000)
    quantities = np.random.randint(1, 101, size=50000)
    user_uuids = np.array([uuid.uuid4() for _ in range(50000)], dtype=object)
    master_resting = []
    for i in range(50000):
        absolute_difference = abs(prices[i] - center_value)
        if sides[i] == Side.BUY.value:
            safe_price = center_value - absolute_difference - 0.01
        else:
            safe_price = center_value + absolute_difference + 0.01
        master_resting.append({
            'ticker': 'APP',
            'type': Type.LIMIT.value,
            'side': sides[i],
            'price': format_as_decimal_string(safe_price),
            'number_of_shares': str(quantities[i]),
            'is_canceled': False,
            'order_owner_id': user_uuids[i]
        })
    print("Slicing and saving tier files...")
    with open("benchmark/data/data_for_test/seed_1k.json", "wb") as f:
        f.write(orjson.dumps(master_resting[:1000]))
    with open("benchmark/data/data_for_test/seed_25k.json", "wb") as f:
        f.write(orjson.dumps(master_resting[:25_000]))
    with open("benchmark/data/data_for_test/seed_50k.json", "wb") as f:
        f.write(orjson.dumps(master_resting))

def generate_active_stream():
    streams =[
        {"name":"active_stream", "order_numbers":200_000},
        {"name":"active_stream_for_q1", "order_numbers":350_000}
    ]
    for stream in streams:
        prices = ornstein_Uhlenbeck_price(stream['order_numbers'])
        types = np.random.choice([Type.MARKET.value, Type.LIMIT.value], size=stream['order_numbers'], p=[0.5, 0.5])
        sides = np.random.choice([Side.BUY.value, Side.SELL.value], size=stream['order_numbers'])
        quantities = np.random.randint(1, 101, size=stream['order_numbers'])
        user_uuids = np.array([uuid.uuid4() for _ in range(stream['order_numbers'])], dtype=object)
        active_stream = []
        for i in range(stream['order_numbers']):
            if types[i] == Type.LIMIT.value:
                absolute_difference = abs(prices[i] - center_value)
                if sides[i] == Side.BUY.value:
                    safe_price = center_value - absolute_difference - 0.01
                else:
                    safe_price = center_value + absolute_difference + 0.01
                price_val = format_as_decimal_string(safe_price)
            else:
                price_val = None
            active_stream.append({
                'ticker': 'APP',
                'type': types[i],
                'side': sides[i],
                'price': price_val,
                'number_of_shares': str(quantities[i]),
                'order_owner_id': user_uuids[i],
                'is_canceled': False
            })
        with open(f"benchmark/data/data_for_test/{stream['name']}.json", "wb") as f:
            f.write(orjson.dumps(active_stream))

if __name__ == "__main__":
    np.random.seed(seed)
    steup()
    generate_resting_book()
    generate_active_stream()
    print("Synthetic data pipeline execution complete.")