from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from execution.execution_result_handler import HandledExecutionResult
from execution.intent_state_manager import IntentStateTransition


@dataclass(slots=True)
class RetryDecision:
    should_retry: bool
    retry_after_seconds: int
    max_attempts: int
    reason: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "should_retry": self.should_retry,
            "retry_after_seconds": self.retry_after_seconds,
            "max_attempts": self.max_attempts,
            "reason": self.reason,
            "details": dict(self.details),
        }


class RetryPolicy:
    DEFAULT_RETRY_AFTER = {
        "transport_error": 15,
        "rate_limited": 60,
        "broker_error": 30,
        "configuration_error": 0,
        "authorization_error": 0,
        "rejected": 0,
        "not_found": 0,
        "unknown_failure": 45,
        "submitted": 0,
    }

    DEFAULT_MAX_ATTEMPTS = {
        "transport_error": 3,
        "rate_limited": 5,
        "broker_error": 3,
        "configuration_error": 0,
        "authorization_error": 0,
        "rejected": 0,
        "not_found": 0,
        "unknown_failure": 2,
        "submitted": 0,
    }

    def decide(
        self,
        *,
        handled_result: HandledExecutionResult,
        transition: IntentStateTransition,
        attempt_number: int,
    ) -> RetryDecision:
        category = handled_result.category
        next_state = transition.next_state

        retry_after = self.DEFAULT_RETRY_AFTER.get(category, 0)
        max_attempts = self.DEFAULT_MAX_ATTEMPTS.get(category, 0)

        details: Dict[str, Any] = {
            "category": category,
            "next_state": next_state,
            "attempt_number": attempt_number,
            "handled_state": handled_result.state,
            "transition_allowed": transition.allowed,
        }

        if not transition.allowed:
            return RetryDecision(
                should_retry=False,
                retry_after_seconds=0,
                max_attempts=0,
                reason="transition_not_allowed",
                details=details,
            )

        if next_state != "retryable_failure":
            return RetryDecision(
                should_retry=False,
                retry_after_seconds=0,
                max_attempts=0,
                reason="state_not_retryable",
                details=details,
            )

        if max_attempts <= 0:
            return RetryDecision(
                should_retry=False,
                retry_after_seconds=0,
                max_attempts=max_attempts,
                reason="retry_not_permitted_for_category",
                details=details,
            )

        if attempt_number >= max_attempts:
            return RetryDecision(
                should_retry=False,
                retry_after_seconds=0,
                max_attempts=max_attempts,
                reason="retry_budget_exhausted",
                details=details,
            )

        return RetryDecision(
            should_retry=True,
            retry_after_seconds=retry_after,
            max_attempts=max_attempts,
            reason="retry_scheduled",
            details=details,
        )
