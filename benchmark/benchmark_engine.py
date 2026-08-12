import time
import gc
import orjson
import numpy as np
import os

from mitori_engine.core.engine import OrderBook

def load_orjson(path:str)->list:
    with open(path,"rb") as f:
        return orjson.loads(f.read())

