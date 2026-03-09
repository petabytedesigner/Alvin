from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from broker.order_executor import OrderExecutionResult


@dataclass(slots=True)
class HandledExecutionResult:
    accepted: bool
    state: str
    category: str
    reasons: list[str]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted": self.accepted,
            "state": self.state,
            "category": self.category,
            "reasons": list(self.reasons),
            "details": dict(self.details),
        }


class ExecutionResultHandler:
    def handle(self, result: OrderExecutionResult) -> HandledExecutionResult:
        category = self._categorize(result)
        accepted = result.submitted and category == "submitted"
        state = self._state_for(category, accepted)
        reasons = self._build_reasons(result, category, accepted)
        details = {
            "broker_http_status": result.broker_http_status,
            "broker_order_id": result.broker_order_id,
            "executor_status": result.status,
            "submitted": result.submitted,
            "raw_details": dict(result.details),
        }
        return HandledExecutionResult(
            accepted=accepted,
            state=state,
            category=category,
            reasons=reasons,
            details=details,
        )

    def _categorize(self, result: OrderExecutionResult) -> str:
        if result.submitted and result.status == "submitted":
            return "submitted"
        if result.status == "configuration_error":
            return "configuration_error"
        if result.status == "transport_error":
            return "transport_error"
        if result.status == "authorization_error":
            return "authorization_error"
        if result.status == "rate_limited":
            return "rate_limited"
        if result.status == "broker_error":
            return "broker_error"
        if result.status == "rejected":
            return "rejected"
        if result.status == "not_found":
            return "not_found"
        return "unknown_failure"

    def _state_for(self, category: str, accepted: bool) -> str:
        if accepted:
            return "submitted_to_broker"
        if category in {"configuration_error", "transport_error", "broker_error", "rate_limited"}:
            return "retryable_failure"
        if category in {"authorization_error", "rejected", "not_found"}:
            return "terminal_failure"
        return "unknown_failure"

    def _build_reasons(self, result: OrderExecutionResult, category: str, accepted: bool) -> list[str]:
        reasons: list[str] = []
        reasons.extend(list(result.reasons))

        if accepted:
            reasons.append("execution_submitted")
        elif category == "configuration_error":
            reasons.append("execution_configuration_blocked")
        elif category == "transport_error":
            reasons.append("execution_transport_failed")
        elif category == "authorization_error":
            reasons.append("execution_authorization_failed")
        elif category == "rate_limited":
            reasons.append("execution_rate_limited")
        elif category == "broker_error":
            reasons.append("execution_broker_error")
        elif category == "rejected":
            reasons.append("execution_rejected")
        elif category == "not_found":
            reasons.append("execution_endpoint_not_found")
        else:
            reasons.append("execution_unknown_failure")

        return _dedupe(reasons)


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
