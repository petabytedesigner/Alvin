from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Tuple
from uuid import uuid4


@dataclass(slots=True)
class AcceptanceDecision:
    decision_id: str
    candidate_id: str
    instrument: str
    allowed: bool
    state: str
    conviction: str
    reasons: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "candidate_id": self.candidate_id,
            "instrument": self.instrument,
            "allowed": self.allowed,
            "state": self.state,
            "conviction": self.conviction,
            "reasons": self.reasons,
            "details": self.details,
        }


class AcceptancePipeline:
    """Core acceptance combiner for Alvin."""

    def decide(
        self,
        *,
        candidate_id: str,
        instrument: str,
        score_allowed: bool,
        score_value: float,
        regime_assessment: Any,
        execution_result: Any,
        portfolio_result: Any,
        risk_result: Any,
        explainability_reasons: Iterable[str] | None = None,
    ) -> AcceptanceDecision:
        reasons: List[str] = []
        normalized_score = self._normalize_score(score_value)
        details: Dict[str, Any] = {
            "score_allowed": score_allowed,
            "score_value": round(float(score_value), 2),
            "score_normalized": normalized_score,
        }

        regime_name, regime_confidence = self._extract_regime(regime_assessment)
        execution_allowed, execution_score, execution_quality, execution_reasons = self._extract_execution(execution_result)
        portfolio_allowed, portfolio_score, portfolio_reasons = self._extract_portfolio(portfolio_result)
        risk_allowed, risk_pct, risk_reasons = self._extract_risk(risk_result)

        regime_allowed, regime_penalty, regime_reasons = self._evaluate_regime(
            regime_name=regime_name,
            regime_confidence=regime_confidence,
        )

        details["regime"] = {
            "name": regime_name,
            "confidence": regime_confidence,
            "allowed": regime_allowed,
            "penalty": regime_penalty,
        }
        details["execution"] = {
            "allowed": execution_allowed,
            "score": execution_score,
            "quality": execution_quality,
        }
        details["portfolio"] = {
            "allowed": portfolio_allowed,
            "pressure_score": portfolio_score,
        }
        details["risk"] = {
            "allowed": risk_allowed,
            "risk_pct": risk_pct,
        }

        if not score_allowed:
            reasons.append("score_blocked")

        reasons.extend(regime_reasons)
        reasons.extend(execution_reasons)
        reasons.extend(portfolio_reasons)
        reasons.extend(risk_reasons)

        if explainability_reasons:
            reasons.extend([str(x) for x in explainability_reasons if str(x).strip()])

        allowed = all([score_allowed, regime_allowed, execution_allowed, portfolio_allowed, risk_allowed])
        state = "accepted" if allowed else "rejected"
        conviction = self._compute_conviction(
            allowed=allowed,
            normalized_score=normalized_score,
            regime_confidence=regime_confidence,
            execution_score=execution_score,
            portfolio_score=portfolio_score,
            risk_pct=risk_pct,
            regime_penalty=regime_penalty,
        )

        reasons = self._dedupe_keep_order(reasons)
        if not reasons:
            reasons.append("acceptance_clean")

        return AcceptanceDecision(
            decision_id=str(uuid4()),
            candidate_id=candidate_id,
            instrument=instrument,
            allowed=allowed,
            state=state,
            conviction=conviction,
            reasons=reasons,
            details=details,
        )

    def _extract_regime(self, regime_assessment: Any) -> Tuple[str, float]:
        regime_name = str(getattr(regime_assessment, "regime", "unknown"))
        confidence = round(float(getattr(regime_assessment, "confidence", 0.0)), 4)
        return regime_name, confidence

    def _extract_execution(self, execution_result: Any) -> Tuple[bool, float, str, List[str]]:
        allowed = bool(getattr(execution_result, "allowed", False))
        score = round(float(getattr(execution_result, "score", 0.0)), 4)
        quality = str(getattr(execution_result, "quality", "unknown"))
        reasons = [str(x) for x in getattr(execution_result, "reasons", [])]
        return allowed, score, quality, reasons

    def _extract_portfolio(self, portfolio_result: Any) -> Tuple[bool, float, List[str]]:
        allowed = bool(getattr(portfolio_result, "allowed", False))
        pressure_score = round(float(getattr(portfolio_result, "pressure_score", 0.0)), 4)
        reasons = [str(x) for x in getattr(portfolio_result, "reasons", [])]
        return allowed, pressure_score, reasons

    def _extract_risk(self, risk_result: Any) -> Tuple[bool, float, List[str]]:
        allowed = bool(getattr(risk_result, "allowed", False))
        risk_pct = round(float(getattr(risk_result, "risk_pct", 0.0)), 4)
        reasons = [str(x) for x in getattr(risk_result, "reasons", [])]
        return allowed, risk_pct, reasons

    def _evaluate_regime(self, *, regime_name: str, regime_confidence: float) -> Tuple[bool, float, List[str]]:
        reasons: List[str] = []

        if regime_name == "post_news_disorder":
            reasons.append("regime_post_news_disorder")
            reasons.append("regime_blocked")
            return False, 0.35, reasons

        if regime_name == "mixed":
            reasons.append("regime_mixed")
            reasons.append("regime_blocked")
            return False, 0.25, reasons

        if regime_name == "compression":
            reasons.append("regime_compression")
            reasons.append("regime_blocked")
            return False, 0.20, reasons

        if regime_name in {"trend", "expansion_trend"}:
            reasons.append(f"regime_{regime_name}")
            return True, 0.0, reasons

        if regime_name == "range":
            reasons.append("regime_range")
            return True, 0.05, reasons

        if regime_name == "unknown":
            reasons.append("regime_unknown")
            return True, 0.10, reasons

        reasons.append(f"regime_{regime_name}")
        return True, 0.05 if regime_confidence < 0.60 else 0.0, reasons

    def _normalize_score(self, score_value: float) -> float:
        return round(max(0.0, min(1.0, float(score_value) / 100.0)), 4)

    def _compute_conviction(
        self,
        *,
        allowed: bool,
        normalized_score: float,
        regime_confidence: float,
        execution_score: float,
        portfolio_score: float,
        risk_pct: float,
        regime_penalty: float,
    ) -> str:
        if not allowed:
            return "blocked"

        composite = (
            (normalized_score * 0.35)
            + (regime_confidence * 0.20)
            + (execution_score * 0.25)
            + ((1.0 - min(1.0, portfolio_score)) * 0.10)
            + (min(1.0, risk_pct / 1.5) * 0.10)
            - regime_penalty
        )

        if composite >= 0.85:
            return "high"
        if composite >= 0.65:
            return "standard"
        return "reduced"

    def _dedupe_keep_order(self, items: Iterable[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered
