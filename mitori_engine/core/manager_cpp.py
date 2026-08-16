from core.gateway import MitoriGateway

class EngineManager:
    def __init__(self, supported_tickers: set[str]):
        self._gateways: dict[str, MitoriGateway] = {
            ticker: MitoriGateway(ticker=ticker) for ticker in supported_tickers
        }
        self._allowed_tickers : set[str] = {ticker.upper() for ticker in supported_tickers}

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

SUPPORTED_TICKERS = {"AAPL", "TSLA", "MSFT", "GOOGL"}
engine_registry = EngineManager(allowed_tickers=SUPPORTED_TICKERS)