from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from market_data.contracts import CandleBatch


@dataclass(slots=True)
class CandleCache:
    _store: Dict[str, CandleBatch] = field(default_factory=dict)

    def _key(self, instrument: str, timeframe: str) -> str:
        return f"{instrument.strip().upper()}::{timeframe.strip().upper()}"

    def put(self, batch: CandleBatch) -> None:
        self._store[self._key(batch.instrument, batch.timeframe)] = batch

    def get(self, *, instrument: str, timeframe: str) -> Optional[CandleBatch]:
        return self._store.get(self._key(instrument, timeframe))

    def has(self, *, instrument: str, timeframe: str) -> bool:
        return self._key(instrument, timeframe) in self._store

    def clear(self) -> None:
        self._store.clear()
