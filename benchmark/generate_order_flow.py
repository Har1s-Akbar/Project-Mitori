import numpy as np
import json
import os
from decimal import Decimal , ROUND_HALF_UP

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