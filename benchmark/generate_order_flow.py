import numpy as np
import json
import os
from decimal import Decimal , ROUND_HALF_UP
import uuid

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
    sides = np.random.choice(["BUY","SELL"],size=50000)
    quantities = np.random.randint(1,101,size=50000)
    user_uuids = np.array([uuid.uuid4() for _ in range(50000)], dtype=object)
    master_resting = []
