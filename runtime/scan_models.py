from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class ScanRequest:
    instrument: str
    h1_count: int = 200
    m15_count: int = 200
    post_news: bool = False
    session: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instrument": self.instrument,
            "h1_count": self.h1_count,
            "m15_count": self.m15_count,
            "post_news": self.post_news,
            "session": self.session,
        }


@dataclass(slots=True)
class ScanResult:
    allowed: bool
    stage: str
    reasons: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def stage_group(self) -> str:
        stage = str(self.stage or "")
        if stage.startswith("scan_"):
            return "scan"
        if stage.startswith("setup_"):
            return "setup"
        if stage.startswith("evaluation_"):
            return "evaluation"
        if stage.startswith("intent_"):
            return "intent"
        if stage.startswith("payload_"):
            return "payload"
        return "unknown"

    def summary(self) -> Dict[str, Any]:
        selected_level = self.details.get("selected_level") or {}
        regime = self.details.get("regime") or {}
        confirmation = self.details.get("confirmation") or {}
        setup = self.details.get("setup") or {}
        evaluation = self.details.get("evaluation") or {}
        candidate = setup.get("candidate") or {}
        evaluation_details = evaluation.get("details") or {}
        execution_quality = self.details.get("execution_quality") or {}
        break_retest = self.details.get("break_retest") or {}
        intent = self.details.get("intent") or {}
        intent_details = intent.get("details") or {}
        intent_obj = intent.get("intent") or {}
        sizing = self.details.get("sizing") or {}
        payload_preview = self.details.get("payload_preview") or {}
        payload_details = payload_preview.get("details") or {}

        return {
            "status": "allowed" if self.allowed else "blocked",
            "stage": self.stage,
            "stage_group": self.stage_group(),
            "primary_reason": self.reasons[0] if self.reasons else None,
            "instrument": self.details.get("instrument"),
            "session": self.details.get("session"),
            "regime_name": regime.get("name"),
            "regime_confidence": regime.get("confidence"),
            "selected_level_id": selected_level.get("level_id"),
            "selected_level_kind": selected_level.get("kind"),
            "selected_level_price": selected_level.get("price"),
            "break_retest_valid": break_retest.get("valid"),
            "break_retest_direction": break_retest.get("direction"),
            "confirmation_type": confirmation.get("confirmation_type"),
            "confirmation_confidence": confirmation.get("confidence"),
            "candidate_id": candidate.get("candidate_id"),
            "candidate_side": candidate.get("side"),
            "candidate_grade": candidate.get("grade"),
            "score_value": evaluation_details.get("score_value"),
            "evaluation_state": evaluation.get("state"),
            "risk_pct": evaluation_details.get("risk_pct"),
            "execution_quality": execution_quality.get("quality"),
            "intent_allowed": intent.get("allowed"),
            "intent_id": intent_obj.get("intent_id") or intent_details.get("intent_id"),
            "intent_state": intent_obj.get("state"),
            "sizing_allowed": sizing.get("allowed"),
            "sized_units": sizing.get("units"),
            "stop_distance": sizing.get("stop_distance"),
            "payload_allowed": payload_preview.get("allowed"),
            "payload_units": payload_details.get("units"),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "stage": self.stage,
            "stage_group": self.stage_group(),
            "reasons": self.reasons,
            "summary": self.summary(),
            "details": self.details,
        }
