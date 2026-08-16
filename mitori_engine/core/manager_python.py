from typing import Dict
from core.engine import OrderBook
from core.config import ALLOWED_TICKERS

class PythonEngineRegistry:
    def __init__(self, allowed_ticker:set[str]):
        self._engines: Dict[str, OrderBook] = {
            ticker: OrderBook(ticker=ticker) for ticker in allowed_ticker
        }
    def get_engine(self, ticker: str) -> OrderBook:
        if ticker not in ALLOWED_TICKERS:
            raise KeyError(f"Not supported ticker: {ticker}")
        if ticker not in self._engines:
            self._engines[ticker] = OrderBook(ticker)
            
        return self._engines[ticker]

engine_registry = PythonEngineRegistry(allowed_ticker=ALLOWED_TICKERS)