from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

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
    def transition_to_submit_started(
        self,
        *,
        intent: OrderIntent,
        reason: str = "submit_started",
    ) -> IntentStateTransition:
        previous_state = intent.state
        requested_next_state = "submit_started"
        reasons = [reason]
        details: Dict[str, Any] = {
            "intent_id": intent.intent_id,
            "requested_next_state": requested_next_state,
            "current_state": previous_state,
        }

        allowed = intent.can_transition(requested_next_state)
        if not allowed:
            reasons.append("intent_state_transition_not_allowed_by_contract")
            return IntentStateTransition(
                previous_state=previous_state,
                next_state=previous_state,
                allowed=False,
                reasons=_dedupe(reasons),
                details=details,
            )

        details["next_state"] = requested_next_state
        reasons.append("intent_submit_started")
        return IntentStateTransition(
            previous_state=previous_state,
            next_state=requested_next_state,
            allowed=True,
            reasons=_dedupe(reasons),
            details=details,
        )

    def apply_transition(
        self,
        *,
        intent: OrderIntent,
        transition: IntentStateTransition,
        reason: Optional[str] = None,
    ) -> IntentStateTransition:
        if not transition.allowed:
            return transition

        if transition.next_state != intent.state:
            transition_reason = reason or (transition.reasons[-1] if transition.reasons else None)
            intent.transition(transition.next_state, reason=transition_reason)
        return transition

    def transition_from_execution(
        self,
        *,
        intent: OrderIntent,
        handled_result: HandledExecutionResult,
    ) -> IntentStateTransition:
        previous_state = intent.state
        next_state = self._map_handled_state(handled_result.state)
        reasons: list[str] = list(handled_result.reasons)
        details: Dict[str, Any] = {
            "intent_id": intent.intent_id,
            "handled_category": handled_result.category,
            "handled_state": handled_result.state,
            "execution_details": dict(handled_result.details),
        }

        allowed = intent.can_transition(next_state)
        if not allowed:
            reasons.append("intent_state_transition_not_allowed_by_contract")
            details["contract_state"] = intent.state
            details["requested_next_state"] = next_state
            return IntentStateTransition(
                previous_state=previous_state,
                next_state=previous_state,
                allowed=False,
                reasons=_dedupe(reasons),
                details=details,
            )

        if handled_result.accepted:
            reasons.append("intent_submitted_to_broker")
        elif next_state == "retryable_failure":
            reasons.append("intent_marked_retryable_failure")
        elif next_state == "terminal_failure":
            reasons.append("intent_marked_terminal_failure")
        elif next_state == "unknown_failure":
            reasons.append("intent_marked_unknown_failure")
        else:
            reasons.append("intent_transitioned")

        details["next_state"] = next_state

        return IntentStateTransition(
            previous_state=previous_state,
            next_state=next_state,
            allowed=True,
            reasons=_dedupe(reasons),
            details=details,
        )

    def _map_handled_state(self, handled_state: str) -> str:
        mapping = {
            "submitted_to_broker": "submitted_to_broker",
            "retryable_failure": "retryable_failure",
            "terminal_failure": "terminal_failure",
            "unknown_failure": "unknown_failure",
        }
        return mapping.get(handled_state, "unknown_failure")


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
