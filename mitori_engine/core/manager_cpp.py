from core.gateway import MitoriGateway

class EngineManager:
    def __init__(self, supported_tickers: list[str]):
        # Initialize an isolated MitoriGateway per valid ticker symbol
        self._gateways: dict[str, MitoriGateway] = {
            ticker: MitoriGateway(ticker=ticker) for ticker in supported_tickers
        }

    def get_gateway(self, ticker: str) -> MitoriGateway:
        normalized_ticker = ticker.upper()
        if normalized_ticker not in self._gateways:
            raise KeyError(f"Unsupported or inactive ticker: {ticker}")
        return self._gateways[normalized_ticker]

    def reset_all(self):
        for gateway in self._gateways.values():
            gateway.reset_engine()