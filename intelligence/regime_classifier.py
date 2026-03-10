from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(slots=True)
class RegimeAssessment:
    regime: str
    confidence: float
    details: dict


class RegimeClassifier:
    def __init__(
        self,
        *,
        thresholds: Mapping[str, float] | None = None,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        self.thresholds = {
            "expansion_atr_ratio": 1.35,
            "trend_strength_min": 0.60,
            "compression_range_tightness": 0.75,
            "compression_atr_ratio_max": 0.85,
            "range_tightness_min": 0.60,
            **dict(thresholds or {}),
        }
        self.labels = {
            "post_news_disorder": "post_news_disorder",
            "expansion_trend": "expansion_trend",
            "compression": "compression",
            "trend": "trend",
            "range": "range",
            "mixed": "mixed",
            **dict(labels or {}),
        }

    @classmethod
    def from_config(cls, regime_config: Mapping[str, Any]) -> "RegimeClassifier":
        return cls(
            thresholds=regime_config.get("thresholds", {}),
            labels=regime_config.get("labels", {}),
        )

    def classify(self, *, atr_ratio: float, trend_strength: float, range_tightness: float, post_news: bool = False) -> RegimeAssessment:
        details: Dict[str, Any] = {
            "atr_ratio": atr_ratio,
            "trend_strength": trend_strength,
            "range_tightness": range_tightness,
            "post_news": post_news,
            "thresholds": dict(self.thresholds),
        }

        if post_news:
            return RegimeAssessment(self.labels["post_news_disorder"], 0.85, details)

        if atr_ratio >= self.thresholds["expansion_atr_ratio"] and trend_strength >= self.thresholds["trend_strength_min"]:
            return RegimeAssessment(self.labels["expansion_trend"], min(0.95, (atr_ratio + trend_strength) / 2), details)

        if range_tightness >= self.thresholds["compression_range_tightness"] and atr_ratio <= self.thresholds["compression_atr_ratio_max"]:
            return RegimeAssessment(self.labels["compression"], min(0.95, (range_tightness + (1 - atr_ratio)) / 2), details)

        if trend_strength >= self.thresholds["trend_strength_min"]:
            return RegimeAssessment(self.labels["trend"], min(0.9, trend_strength), details)

        if range_tightness >= self.thresholds["range_tightness_min"]:
            return RegimeAssessment(self.labels["range"], min(0.9, range_tightness), details)

        return RegimeAssessment(self.labels["mixed"], 0.5, details)
