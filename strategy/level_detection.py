from __future__ import annotations

from dataclasses import dataclass, field, asdict
from statistics import mean
from typing import Iterable, Sequence


@dataclass(slots=True)
class Candle:
    ts_utc: str
    open: float
    high: float
    low: float
    close: float

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return max(0.0, self.high - self.low)


@dataclass(slots=True)
class Level:
    level_id: str
    kind: str
    price: float
    touches: int
    first_index: int
    last_index: int
    confidence: float
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = asdict(self)
        return data


class LevelDetectionError(ValueError):
    pass


class LevelDetector:
    def __init__(
        self,
        *,
        fractal_window: int = 1,
        min_swing_touches: int = 2,
        min_swing_spacing: int = 20,
        min_range_candles: int = 15,
        range_width_atr_multiple: float = 1.5,
        touch_tolerance_atr_multiple: float = 0.15,
    ) -> None:
        if fractal_window < 1:
            raise LevelDetectionError("fractal_window must be >= 1")
        self.fractal_window = fractal_window
        self.min_swing_touches = min_swing_touches
        self.min_swing_spacing = min_swing_spacing
        self.min_range_candles = min_range_candles
        self.range_width_atr_multiple = range_width_atr_multiple
        self.touch_tolerance_atr_multiple = touch_tolerance_atr_multiple

    def detect(self, candles: Sequence[Candle], *, atr_value: float) -> dict:
        if len(candles) < max((self.fractal_window * 2) + 1, self.min_range_candles):
            raise LevelDetectionError("not enough candles for level detection")
        if atr_value <= 0:
            raise LevelDetectionError("atr_value must be > 0")

        swing_highs = self._find_fractal_highs(candles)
        swing_lows = self._find_fractal_lows(candles)
        swing_levels = self._build_swing_levels(swing_highs, swing_lows, atr_value)
        range_levels = self._detect_range_levels(candles, atr_value)

        return {
            "swing_levels": [level.to_dict() for level in swing_levels],
            "range_levels": [level.to_dict() for level in range_levels],
            "metadata": {
                "candles": len(candles),
                "atr_value": atr_value,
                "fractal_window": self.fractal_window,
                "min_swing_touches": self.min_swing_touches,
                "min_range_candles": self.min_range_candles,
            },
        }

    def _find_fractal_highs(self, candles: Sequence[Candle]) -> list[tuple[int, float]]:
        points: list[tuple[int, float]] = []
        w = self.fractal_window
        for i in range(w, len(candles) - w):
            center = candles[i]
            left = candles[i - w:i]
            right = candles[i + 1:i + 1 + w]
            if all(center.high > c.high for c in left) and all(center.high >= c.high for c in right):
                points.append((i, center.high))
        return points

    def _find_fractal_lows(self, candles: Sequence[Candle]) -> list[tuple[int, float]]:
        points: list[tuple[int, float]] = []
        w = self.fractal_window
        for i in range(w, len(candles) - w):
            center = candles[i]
            left = candles[i - w:i]
            right = candles[i + 1:i + 1 + w]
            if all(center.low < c.low for c in left) and all(center.low <= c.low for c in right):
                points.append((i, center.low))
        return points

    def _build_swing_levels(
        self,
        highs: Iterable[tuple[int, float]],
        lows: Iterable[tuple[int, float]],
        atr_value: float,
    ) -> list[Level]:
        tolerance = atr_value * self.touch_tolerance_atr_multiple
        levels: list[Level] = []
        levels.extend(self._cluster_points(highs, "swing_high", tolerance))
        levels.extend(self._cluster_points(lows, "swing_low", tolerance))
        filtered: list[Level] = []
        for level in levels:
            if level.touches < self.min_swing_touches:
                continue
            if (level.last_index - level.first_index) < self.min_swing_spacing:
                continue
            filtered.append(level)
        filtered.sort(key=lambda item: (item.kind, -item.confidence, item.price))
        return filtered

    def _cluster_points(self, points: Iterable[tuple[int, float]], kind: str, tolerance: float) -> list[Level]:
        clusters: list[dict] = []
        for idx, price in sorted(points, key=lambda item: item[0]):
            matched = None
            for cluster in clusters:
                if abs(cluster["price"] - price) <= tolerance:
                    matched = cluster
                    break
            if matched is None:
                clusters.append({"indices": [idx], "prices": [price], "price": price})
            else:
                matched["indices"].append(idx)
                matched["prices"].append(price)
                matched["price"] = mean(matched["prices"])

        results: list[Level] = []
        for pos, cluster in enumerate(clusters, start=1):
            touches = len(cluster["indices"])
            first_index = min(cluster["indices"])
            last_index = max(cluster["indices"])
            spacing = max(1, last_index - first_index)
            confidence = round(min(0.95, 0.35 + (touches * 0.12) + min(0.24, spacing / 250)), 4)
            results.append(
                Level(
                    level_id=f"{kind}:{pos}:{first_index}:{last_index}",
                    kind=kind,
                    price=round(cluster["price"], 6),
                    touches=touches,
                    first_index=first_index,
                    last_index=last_index,
                    confidence=confidence,
                    metadata={
                        "source": "fractal_cluster",
                        "cluster_size": touches,
                        "price_samples": [round(p, 6) for p in cluster["prices"]],
                    },
                )
            )
        return results

    def _detect_range_levels(self, candles: Sequence[Candle], atr_value: float) -> list[Level]:
        lookback = self.min_range_candles
        segment = candles[-lookback:]
        high = max(c.high for c in segment)
        low = min(c.low for c in segment)
        width = high - low
        if width <= 0:
            return []
        if width >= atr_value * self.range_width_atr_multiple:
            return []

        midpoint = (high + low) / 2
        confidence = round(min(0.92, 0.45 + (lookback / 100) + min(0.18, (atr_value * self.range_width_atr_multiple - width) / max(atr_value, 1e-9))), 4)
        first_index = len(candles) - lookback
        last_index = len(candles) - 1

        return [
            Level(
                level_id=f"range_high:{first_index}:{last_index}",
                kind="range_high",
                price=round(high, 6),
                touches=2,
                first_index=first_index,
                last_index=last_index,
                confidence=confidence,
                metadata={
                    "source": "range_box",
                    "range_width": round(width, 6),
                    "midpoint": round(midpoint, 6),
                    "lookback": lookback,
                },
            ),
            Level(
                level_id=f"range_low:{first_index}:{last_index}",
                kind="range_low",
                price=round(low, 6),
                touches=2,
                first_index=first_index,
                last_index=last_index,
                confidence=confidence,
                metadata={
                    "source": "range_box",
                    "range_width": round(width, 6),
                    "midpoint": round(midpoint, 6),
                    "lookback": lookback,
                },
            ),
        ]
