from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from contracts.order_lifecycle import OrderIntent
from execution.execution_result_handler import HandledExecutionResult


@dataclass(slots=True)
class IntentStateTransition:
    previous_state: str
    next_state: str
    allowed: bool
    reasons: list[str]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "previous_state": self.previous_state,
            "next_state": self.next_state,
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "details": dict(self.details),
        }


class IntentStateManager:
    def transition_from_execution(
        self,
        *,
        intent: OrderIntent,
        handled_result: HandledExecutionResult,
    ) -> IntentStateTransition:
        previous_state = intent.state
        reasons: list[str] = list(handled_result.reasons)
        details: Dict[str, Any] = {
            "intent_id": intent.intent_id,
            "handled_category": handled_result.category,
            "handled_state": handled_result.state,
            "execution_details": dict(handled_result.details),
        }

        if previous_state != "intent_created":
            reasons.append("intent_state_transition_invalid_origin")
            return IntentStateTransition(
                previous_state=previous_state,
                next_state=previous_state,
                allowed=False,
                reasons=_dedupe(reasons),
                details=details,
            )

        mapping = {
            "submitted_to_broker": "submitted_to_broker",
            "retryable_failure": "retryable_failure",
            "terminal_failure": "terminal_failure",
            "unknown_failure": "unknown_failure",
        }

        next_state = mapping.get(handled_result.state, "unknown_failure")
        allowed = next_state != previous_state

        if handled_result.accepted:
            reasons.append("intent_submitted_to_broker")
        elif next_state == "retryable_failure":
            reasons.append("intent_marked_retryable_failure")
        elif next_state == "terminal_failure":
            reasons.append("intent_marked_terminal_failure")
        else:
            reasons.append("intent_marked_unknown_failure")

        details["next_state"] = next_state

        return IntentStateTransition(
            previous_state=previous_state,
            next_state=next_state,
            allowed=allowed,
            reasons=_dedupe(reasons),
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
