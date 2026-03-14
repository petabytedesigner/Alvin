from __future__ import annotations

import requests
from typing import Any, Dict, List

from broker.oanda_client import OandaClient
from market_data.contracts import CandleBatch, MarketDataCandle, Timeframe


class OandaMarketData:
    def __init__(self, client: OandaClient | None = None) -> None:
        self.client = client or OandaClient()

    def fetch_candles(
        self,
        *,
        instrument: str,
        timeframe: str,
        count: int = 200,
        price: str = "M",
        timeout: int = 15,
    ) -> CandleBatch:
        if not self.client.is_configured():
            raise RuntimeError("OANDA environment is not fully configured")

        normalized_instrument = instrument.strip().upper()
        normalized_timeframe = self._normalize_timeframe(timeframe)

        url = f"{self.client.api_url}/v3/instruments/{normalized_instrument}/candles"
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {self.client.api_token}"},
            params={
                "granularity": normalized_timeframe,
                "count": int(count),
                "price": price,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()

        raw_candles = payload.get("candles", [])
        candles = [self._to_market_data_candle(item) for item in raw_candles if bool(item.get("complete", False))]

        return CandleBatch(
            instrument=normalized_instrument,
            timeframe=normalized_timeframe,
            candles=candles,
            source="oanda",
        )

    def fetch_h1(self, instrument: str, count: int = 200, timeout: int = 15) -> CandleBatch:
        return self.fetch_candles(
            instrument=instrument,
            timeframe=Timeframe.H1,
            count=count,
            timeout=timeout,
        )

    def fetch_m15(self, instrument: str, count: int = 200, timeout: int = 15) -> CandleBatch:
        return self.fetch_candles(
            instrument=instrument,
            timeframe=Timeframe.M15,
            count=count,
            timeout=timeout,
        )

    def _to_market_data_candle(self, payload: Dict[str, Any]) -> MarketDataCandle:
        price_block = payload.get("mid") or {}
        return MarketDataCandle(
            ts_utc=str(payload.get("time", "")),
            open=float(price_block.get("o", 0.0)),
            high=float(price_block.get("h", 0.0)),
            low=float(price_block.get("l", 0.0)),
            close=float(price_block.get("c", 0.0)),
            volume=int(payload.get("volume", 0)),
            complete=bool(payload.get("complete", False)),
        )

    def _normalize_timeframe(self, timeframe: str) -> str:
        normalized = timeframe.strip().upper()
        if normalized not in {Timeframe.H1, Timeframe.M15}:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return normalized
