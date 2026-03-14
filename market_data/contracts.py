from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


class Timeframe:
    H1 = "H1"
    M15 = "M15"


@dataclass(slots=True)
class MarketDataCandle:
    ts_utc: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    complete: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CandleBatch:
    instrument: str
    timeframe: str
    candles: List[MarketDataCandle] = field(default_factory=list)
    source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "candles": [candle.to_dict() for candle in self.candles],
            "source": self.source,
            "count": len(self.candles),
        }
