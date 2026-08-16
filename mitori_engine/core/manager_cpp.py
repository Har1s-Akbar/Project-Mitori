from mitori_engine.core.gateway_cpp import MitoriGateway
from core.config import ALLOWED_TICKERS

class EngineManager:
    def __init__(self, allowed_tickers: set[str]):
        self._gateways: dict[str, MitoriGateway] = {
            ticker: MitoriGateway(ticker=ticker) for ticker in allowed_tickers
        }
        self._allowed_tickers : set[str] = {ticker.upper() for ticker in allowed_tickers}

    def get_gateway(self, ticker: str) -> MitoriGateway:
        normalized_ticker = ticker.upper()
        if normalized_ticker not in self._allowed_tickers:
            raise KeyError(f"Unsupported ticker : {ticker}")
        if normalized_ticker not in self._gateways:
            self._gateways[ticker] = MitoriGateway(ticker=normalized_ticker)

        return self._gateways[ticker]

    def reset_all(self):
        for gateway in self._gateways.values():
            gateway.reset_engine()

engine_registry = EngineManager(allowed_tickers=ALLOWED_TICKERS)