from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
from uuid import uuid4

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
        metadata: Dict[str, Any] | None = None,
    ) -> SetupBuildResult:
        reasons: list[str] = []
        details: Dict[str, Any] = {
            "instrument": instrument,
            "timeframe": timeframe,
            "side": side,
            "setup_type": setup_type,
            "atr_value": atr_value,
            "score_hint": score_hint,
            "level_kind": level.kind,
            "level_price": level.price,
            "level_touches": getattr(level, "touches", None),
            "break_retest": {
                "allowed": break_retest.allowed,
                "break_valid": getattr(break_retest.break_assessment, "valid", False),
                "retest_valid": getattr(break_retest.retest_assessment, "valid", False),
                "confidence": getattr(break_retest, "confidence", 0.0),
            },
            "confirmation": {
                "valid": confirmation.valid,
                "kind": confirmation.kind,
                "confidence": confirmation.confidence,
            },
        }

        if not break_retest.allowed:
            reasons.append("break_retest_not_valid")
        if not confirmation.valid:
            reasons.append("m15_confirmation_not_valid")
        if atr_value <= 0:
            reasons.append("atr_invalid")
        if score_hint <= 0:
            reasons.append("score_hint_invalid")
        if side not in {"long", "short"}:
            reasons.append("side_invalid")

        allowed = not reasons
        if not allowed:
            return SetupBuildResult(None, False, reasons, details)

        trigger_ref = f"{level.kind}:{round(level.price, 5)}:{break_retest.break_assessment.break_bar_index}"
        candidate = self._candidate_builder.build(
            candidate_id=str(uuid4()),
            instrument=instrument,
            timeframe=timeframe,
            side=side,
            setup_type=setup_type,
            trigger_reference=trigger_ref,
            score_hint=score_hint,
            details={
                **(metadata or {}),
                **details,
            },
        )

        reasons.append("setup_candidate_built")
        return SetupBuildResult(candidate, True, reasons, details)
