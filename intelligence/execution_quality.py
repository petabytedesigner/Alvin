from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(slots=True)
class ExecutionQualityResult:
    quality: str
    score: float
    allowed: bool
    reasons: list[str]
    details: dict


class ExecutionQualityAssessor:
    def __init__(
        self,
        *,
        spread_ratio_warn: float = 1.0,
        slippage_warn: float = 0.20,
        timing_delay_warn_seconds: float = 3.0,
        adverse_selection_warn: float = 0.55,
        score_floor: float = 0.50,
        quality_bands: Mapping[str, float] | None = None,
    ) -> None:
        self.spread_ratio_warn = float(spread_ratio_warn)
        self.slippage_warn = float(slippage_warn)
        self.timing_delay_warn_seconds = float(timing_delay_warn_seconds)
        self.adverse_selection_warn = float(adverse_selection_warn)
        self.score_floor = float(score_floor)
        self.quality_bands = {
            "clean": 0.85,
            "acceptable": 0.65,
            "fragile": 0.50,
            **dict(quality_bands or {}),
        }

    @classmethod
    def from_config(cls, execution_config: Mapping[str, Any]) -> "ExecutionQualityAssessor":
        return cls(
            spread_ratio_warn=execution_config.get("spread_ratio_warn", 1.0),
            slippage_warn=execution_config.get("slippage_warn", 0.20),
            timing_delay_warn_seconds=execution_config.get("timing_delay_warn_seconds", 3.0),
            adverse_selection_warn=execution_config.get("adverse_selection_warn", 0.55),
            score_floor=execution_config.get("score_floor", 0.50),
            quality_bands=execution_config.get("quality_bands", {}),
        )

    def assess(self, *, spread_ratio: float, slippage_estimate: float, timing_delay_seconds: float, adverse_selection_risk: float) -> ExecutionQualityResult:
        reasons = []
        score = 1.0
        if spread_ratio > self.spread_ratio_warn:
            reasons.append("spread_above_threshold")
            score -= min(0.35, spread_ratio - self.spread_ratio_warn)
        if slippage_estimate > self.slippage_warn:
            reasons.append("slippage_elevated")
            score -= min(0.25, slippage_estimate)
        if timing_delay_seconds > self.timing_delay_warn_seconds:
            reasons.append("timing_delay_high")
            score -= min(0.15, timing_delay_seconds / 20)
        if adverse_selection_risk > self.adverse_selection_warn:
            reasons.append("adverse_selection_risk")
            score -= min(0.30, adverse_selection_risk / 2)

        score = max(0.0, round(score, 4))
        allowed = score >= self.score_floor

        if score >= self.quality_bands["clean"]:
            quality = "clean"
        elif score >= self.quality_bands["acceptable"]:
            quality = "acceptable"
        elif score >= self.quality_bands["fragile"]:
            quality = "fragile"
        else:
            quality = "blocked"

        if not reasons:
            reasons.append("execution_clean")

        return ExecutionQualityResult(
            quality=quality,
            score=score,
            allowed=allowed,
            reasons=reasons,
            details={
                "spread_ratio": spread_ratio,
                "slippage_estimate": slippage_estimate,
                "timing_delay_seconds": timing_delay_seconds,
                "adverse_selection_risk": adverse_selection_risk,
                "config": {
                    "spread_ratio_warn": self.spread_ratio_warn,
                    "slippage_warn": self.slippage_warn,
                    "timing_delay_warn_seconds": self.timing_delay_warn_seconds,
                    "adverse_selection_warn": self.adverse_selection_warn,
                    "score_floor": self.score_floor,
                    "quality_bands": dict(self.quality_bands),
                },
            },
        )
