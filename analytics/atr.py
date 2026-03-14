from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from market_data.contracts import MarketDataCandle


@dataclass(slots=True)
class AtrComputation:
    period: int
    value: float
    tr_values: list[float]
    source_count: int

    def to_dict(self) -> dict:
        return {
            "period": self.period,
            "value": self.value,
            "tr_values": self.tr_values,
            "source_count": self.source_count,
        }


class ATRCalculator:
    def __init__(self, period: int = 14) -> None:
        if period < 2:
            raise ValueError("ATR period must be >= 2")
        self.period = int(period)

    def calculate(self, candles: Sequence[MarketDataCandle]) -> AtrComputation:
        if len(candles) < self.period + 1:
            raise ValueError(f"Not enough candles to compute ATR({self.period})")

        tr_values: list[float] = []
        previous_close = float(candles[0].close)

        for candle in candles[1:]:
            high = float(candle.high)
            low = float(candle.low)
            close = float(candle.close)

            true_range = max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )
            tr_values.append(round(true_range, 8))
            previous_close = close

        atr_window = tr_values[-self.period :]
        atr_value = round(sum(atr_window) / len(atr_window), 8)

        return AtrComputation(
            period=self.period,
            value=atr_value,
            tr_values=atr_window,
            source_count=len(candles),
        )
