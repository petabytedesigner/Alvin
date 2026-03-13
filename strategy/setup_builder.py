from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from strategy.signal_candidate import SignalCandidate, SignalCandidateBuilder
from strategy.level_detection import Level
from strategy.break_retest_validator import BreakRetestResult
from strategy.m15_confirmation import ConfirmationResult


@dataclass(slots=True)
class SetupBuildResult:
    candidate: Optional[SignalCandidate]
    allowed: bool
    reasons: list[str]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if self.candidate is not None:
            payload["candidate"] = self.candidate.to_dict()
        return payload


class StrategySetupBuilder:
    def __init__(self) -> None:
        self._candidate_builder = SignalCandidateBuilder()

    def build(
        self,
        *,
        instrument: str,
        timeframe: str,
        side: str,
        setup_type: str,
        level: Level,
        break_retest: BreakRetestResult,
        confirmation: ConfirmationResult,
        atr_value: float,
        score_hint: float,
        grade: str = "B",
        session: str = "unknown",
        post_news: bool = False,
        regime: str = "unknown",
        metadata: Dict[str, Any] | None = None,
    ) -> SetupBuildResult:
        reasons: list[str] = []
        bounded_score_hint = round(max(0.0, min(100.0, float(score_hint))), 2)
        normalized_regime = str(regime or "unknown").strip() or "unknown"
        details: Dict[str, Any] = {
            "instrument": instrument,
            "timeframe": timeframe,
            "side": side,
            "setup_type": setup_type,
            "atr_value": atr_value,
            "score_hint": bounded_score_hint,
            "score_hint_normalized": round(bounded_score_hint / 100.0, 4),
            "regime": normalized_regime,
            "level_id": level.level_id,
            "level_kind": level.kind,
            "level_price": level.price,
            "level_touches": level.touches,
            "break_retest": {
                "valid": break_retest.valid,
                "direction": break_retest.direction,
                "reason": break_retest.reason,
                "break_valid": break_retest.break_assessment.valid,
                "retest_valid": break_retest.retest_assessment.valid if break_retest.retest_assessment else False,
            },
            "confirmation": {
                "confirmed": confirmation.confirmed,
                "type": confirmation.confirmation_type,
                "confidence": confirmation.confidence,
                "reasons": confirmation.reasons,
            },
        }

        if not break_retest.valid:
            reasons.append("break_retest_not_valid")
        if not confirmation.confirmed:
            reasons.append("m15_confirmation_not_valid")
        if atr_value <= 0:
            reasons.append("atr_invalid")
        if bounded_score_hint <= 0:
            reasons.append("score_hint_invalid")
        if side not in {"long", "short"}:
            reasons.append("side_invalid")
        if break_retest.direction not in {"long", "short"}:
            reasons.append("break_direction_invalid")
        elif break_retest.direction != side:
            reasons.append("side_direction_mismatch")

        allowed = not reasons
        if not allowed:
            return SetupBuildResult(candidate=None, allowed=False, reasons=reasons, details=details)

        trigger_ref = f"{level.kind}:{round(level.price, 5)}:{break_retest.break_assessment.close_price}"
        candidate = self._candidate_builder.build(
            instrument=instrument,
            timeframe=timeframe,
            side=side,
            score=bounded_score_hint,
            grade=grade,
            regime=normalized_regime,
            trigger_reference=trigger_ref,
            level_reference=level.level_id,
            setup_type=setup_type,
            session=session,
            post_news=post_news,
            notes={
                "break_reason": break_retest.reason,
                "confirmation_type": confirmation.confirmation_type,
            },
            metadata={
                **(metadata or {}),
                **details,
            },
        )

        reasons.append("setup_candidate_built")
        return SetupBuildResult(candidate=candidate, allowed=True, reasons=reasons, details=details)
