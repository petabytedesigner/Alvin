from dataclasses import dataclass

@dataclass(slots=True)
class ExecutionQualityResult:
    quality: str
    score: float
    allowed: bool
    reasons: list[str]
    details: dict

class ExecutionQualityAssessor:
    def assess(self, *, spread_ratio: float, slippage_estimate: float, timing_delay_seconds: float, adverse_selection_risk: float) -> ExecutionQualityResult:
        reasons = []
        score = 1.0
        if spread_ratio > 1.0:
            reasons.append("spread_above_threshold")
            score -= min(0.35, spread_ratio - 1.0)
        if slippage_estimate > 0.20:
            reasons.append("slippage_elevated")
            score -= min(0.25, slippage_estimate)
        if timing_delay_seconds > 3.0:
            reasons.append("timing_delay_high")
            score -= min(0.15, timing_delay_seconds / 20)
        if adverse_selection_risk > 0.55:
            reasons.append("adverse_selection_risk")
            score -= min(0.30, adverse_selection_risk / 2)
        score = max(0.0, round(score, 4))
        allowed = score >= 0.50
        quality = "clean" if score >= 0.85 else "acceptable" if score >= 0.65 else "fragile" if score >= 0.50 else "blocked"
        if not reasons:
            reasons.append("execution_clean")
        return ExecutionQualityResult(quality, score, allowed, reasons, {
            "spread_ratio": spread_ratio,
            "slippage_estimate": slippage_estimate,
            "timing_delay_seconds": timing_delay_seconds,
            "adverse_selection_risk": adverse_selection_risk,
        })
