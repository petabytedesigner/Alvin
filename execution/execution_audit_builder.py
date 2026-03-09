from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from contracts.order_lifecycle import OrderIntent
from execution.execution_result_handler import HandledExecutionResult
from execution.intent_state_manager import IntentStateTransition


@dataclass(slots=True)
class ExecutionAuditRecord:
    intent_id: str
    correlation_id: str
    instrument: str
    side: str
    previous_state: str
    next_state: str
    execution_category: str
    accepted: bool
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "correlation_id": self.correlation_id,
            "instrument": self.instrument,
            "side": self.side,
            "previous_state": self.previous_state,
            "next_state": self.next_state,
            "execution_category": self.execution_category,
            "accepted": self.accepted,
            "payload": dict(self.payload),
        }


@dataclass(slots=True)
class ExecutionAuditBuildResult:
    allowed: bool
    record: Optional[ExecutionAuditRecord]
    reasons: list[str]
    details: Dict[str, Any]


class ExecutionAuditBuilder:
    def build(
        self,
        *,
        intent: OrderIntent,
        handled_result: HandledExecutionResult,
        transition: IntentStateTransition,
    ) -> ExecutionAuditBuildResult:
        reasons: list[str] = []
        details: Dict[str, Any] = {
            "intent_id": intent.intent_id,
            "instrument": intent.instrument,
            "side": intent.side,
            "current_intent_state": intent.state,
            "transition_allowed": transition.allowed,
        }

        if not transition.allowed:
            reasons.append("transition_not_allowed_for_audit")
            reasons.extend(list(transition.reasons))
            return ExecutionAuditBuildResult(
                allowed=False,
                record=None,
                reasons=_dedupe(reasons),
                details=details,
            )

        payload = {
            "intent": {
                "intent_id": intent.intent_id,
                "dedupe_key": intent.dedupe_key,
                "instrument": intent.instrument,
                "side": intent.side,
                "timeframe": intent.timeframe,
                "setup_type": intent.setup_type,
                "grade": intent.grade,
                "score": intent.score,
                "state": intent.state,
                "correlation_id": intent.correlation_id,
                "payload": dict(intent.payload),
            },
            "execution": handled_result.to_dict(),
            "transition": transition.to_dict(),
        }

        record = ExecutionAuditRecord(
            intent_id=intent.intent_id,
            correlation_id=intent.correlation_id,
            instrument=intent.instrument,
            side=intent.side,
            previous_state=transition.previous_state,
            next_state=transition.next_state,
            execution_category=handled_result.category,
            accepted=handled_result.accepted,
            payload=payload,
        )

        reasons.append("execution_audit_record_built")
        details.update(
            {
                "previous_state": transition.previous_state,
                "next_state": transition.next_state,
                "execution_category": handled_result.category,
                "accepted": handled_result.accepted,
            }
        )

        return ExecutionAuditBuildResult(
            allowed=True,
            record=record,
            reasons=reasons,
            details=details,
        )


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
