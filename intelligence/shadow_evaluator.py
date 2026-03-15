from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass(slots=True)
class ShadowEvaluation:
    instrument: str
    candidate_id: str
    decision: str
    hypothetical_outcome: str
    notes: dict

    def to_dict(self) -> dict:
        return asdict(self)


class ShadowEvaluator:
    def build(
        self,
        *,
        instrument: str,
        candidate_id: str,
        decision: str,
        hypothetical_outcome: str = "pending",
        notes: dict | None = None,
    ) -> ShadowEvaluation:
        return ShadowEvaluation(instrument, candidate_id, decision, hypothetical_outcome, notes or {})

    def build_from_scan_result(
        self,
        *,
        instrument: str,
        candidate_id: str,
        stage: str,
        allowed: bool,
        reasons: list[str],
        regime_name: str | None = None,
        score_value: float | None = None,
        intent_id: str | None = None,
        payload_allowed: bool | None = None,
    ) -> ShadowEvaluation:
        if allowed and stage == "payload_ready":
            decision = "shadow_accept"
            hypothetical_outcome = "shadow_payload_ready"
        elif allowed and stage == "intent_ready":
            decision = "shadow_accept_pending_payload"
            hypothetical_outcome = "shadow_intent_ready"
        elif stage.endswith("_blocked"):
            decision = "shadow_reject"
            hypothetical_outcome = stage
        else:
            decision = "shadow_watch"
            hypothetical_outcome = stage

        notes: Dict[str, Any] = {
            "stage": stage,
            "allowed": allowed,
            "reasons": list(reasons),
            "regime_name": regime_name,
            "score_value": score_value,
            "intent_id": intent_id,
            "payload_allowed": payload_allowed,
        }
        return ShadowEvaluation(
            instrument=instrument,
            candidate_id=candidate_id,
            decision=decision,
            hypothetical_outcome=hypothetical_outcome,
            notes=notes,
        )
