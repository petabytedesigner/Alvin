from __future__ import annotations

from typing import Sequence

from market_data.contracts import MarketDataCandle
from strategy.level_detection import Candle
from strategy.m15_confirmation import M15Candle


class CandleMapper:
    def to_level_detection_candles(self, candles: Sequence[MarketDataCandle]) -> list[Candle]:
        return [
            Candle(
                ts_utc=item.ts_utc,
                open=float(item.open),
                high=float(item.high),
                low=float(item.low),
                close=float(item.close),
            )
            for item in candles
        ]

    def to_m15_confirmation_candles(self, candles: Sequence[MarketDataCandle]) -> list[M15Candle]:
        return [
            M15Candle(
                open=float(item.open),
                high=float(item.high),
                low=float(item.low),
                close=float(item.close),
                ts_utc=item.ts_utc,
            )
            for item in candles
        ]
