from typing import Dict
from core.config import ALLOWED_TICKERS
from core.gateway_python import PythonMitoriGateway

class PythonEngineRegistry:
    def __init__(self, allowed_ticker:set[str]):
        self._engines: Dict[str, PythonMitoriGateway] = {
            ticker: PythonMitoriGateway(ticker=ticker) for ticker in allowed_ticker
        }
    def get_engine(self, ticker: str) -> PythonMitoriGateway:
        if ticker not in ALLOWED_TICKERS:
            raise KeyError(f"Not supported ticker: {ticker}")
        if ticker not in self._engines:
            self._engines[ticker] = PythonMitoriGateway(ticker)
            
        return self._engines[ticker]

engine_registry = PythonEngineRegistry(allowed_ticker=ALLOWED_TICKERS)