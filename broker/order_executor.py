from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from broker.oanda_client import OandaClient
from execution.execution_payload_builder import ExecutionPayload


@dataclass(slots=True)
class OrderExecutionResult:
    submitted: bool
    status: str
    broker_http_status: int
    broker_order_id: Optional[str]
    reasons: list[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "submitted": self.submitted,
            "status": self.status,
            "broker_http_status": self.broker_http_status,
            "broker_order_id": self.broker_order_id,
            "reasons": list(self.reasons),
            "details": dict(self.details),
        }


class OrderExecutor:
    def __init__(self, client: OandaClient) -> None:
        self.client = client

    def submit(self, execution_payload: ExecutionPayload, timeout: int = 15) -> OrderExecutionResult:
        if not self.client.is_configured():
            return OrderExecutionResult(
                submitted=False,
                status="configuration_error",
                broker_http_status=0,
                broker_order_id=None,
                reasons=["oanda_not_configured"],
                details={
                    "intent_id": execution_payload.intent_id,
                    "execution_category": "configuration_error",
                },
            )

        try:
            status_code, response_json = self.client.submit_order(
                execution_payload.payload,
                timeout=timeout,
            )
        except Exception as exc:
            return OrderExecutionResult(
                submitted=False,
                status="transport_error",
                broker_http_status=0,
                broker_order_id=None,
                reasons=["broker_submit_exception"],
                details={
                    "intent_id": execution_payload.intent_id,
                    "execution_category": "transport_error",
                    "error": str(exc),
                },
            )

        broker_order_id = self._extract_order_id(response_json)
        reasons = self._classify(status_code, response_json)
        execution_category = self._execution_category(status_code=status_code, response_json=response_json, broker_order_id=broker_order_id)

        broker_truth: Dict[str, Any] = {
            "order_id": broker_order_id,
            "create_transaction_id": self._extract_transaction_id(response_json, "orderCreateTransaction"),
            "fill_transaction_id": self._extract_transaction_id(response_json, "orderFillTransaction"),
            "cancel_transaction_id": self._extract_transaction_id(response_json, "orderCancelTransaction"),
            "reject_transaction_id": self._extract_transaction_id(response_json, "orderRejectTransaction"),
        }

        submitted = 200 <= status_code < 300 and broker_order_id is not None
        status = "submitted" if submitted else self._status_name(status_code, response_json)

        return OrderExecutionResult(
            submitted=submitted,
            status=status,
            broker_http_status=status_code,
            broker_order_id=broker_order_id,
            reasons=reasons,
            details={
                "intent_id": execution_payload.intent_id,
                "instrument": execution_payload.instrument,
                "side": execution_payload.side,
                "units": execution_payload.units,
                "execution_category": execution_category,
                "broker_truth": broker_truth,
                "response": response_json,
            },
        )

    def _extract_order_id(self, response_json: Dict[str, Any]) -> Optional[str]:
        for key in (
            "orderCreateTransaction",
            "orderFillTransaction",
            "longOrderCreateTransaction",
            "shortOrderCreateTransaction",
            "orderCancelTransaction",
        ):
            block = response_json.get(key)
            if isinstance(block, dict) and block.get("id") is not None:
                return str(block["id"])
        if isinstance(response_json.get("id"), (str, int)):
            return str(response_json["id"])
        return None

    def _extract_transaction_id(self, response_json: Dict[str, Any], key: str) -> Optional[str]:
        block = response_json.get(key)
        if isinstance(block, dict) and block.get("id") is not None:
            return str(block["id"])
        return None

    def _classify(self, status_code: int, response_json: Dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        error_code = str(response_json.get("errorCode", "")).strip()
        error_message = str(response_json.get("errorMessage", "")).strip()

        if 200 <= status_code < 300:
            reasons.append("broker_submit_ok")
        elif status_code == 400:
            reasons.append("broker_bad_request")
        elif status_code == 401:
            reasons.append("broker_auth_failed")
        elif status_code == 403:
            reasons.append("broker_forbidden")
        elif status_code == 404:
            reasons.append("broker_not_found")
        elif status_code == 405:
            reasons.append("broker_method_not_allowed")
        elif status_code == 409:
            reasons.append("broker_conflict")
        elif status_code == 429:
            reasons.append("broker_rate_limited")
        elif 500 <= status_code < 600:
            reasons.append("broker_server_error")
        else:
            reasons.append("broker_unknown_status")

        if error_code:
            reasons.append(f"broker_error_code:{error_code}")
        if error_message:
            reasons.append("broker_error_message_present")

        return reasons

    def _status_name(self, status_code: int, response_json: Dict[str, Any]) -> str:
        if status_code == 400:
            return "rejected"
        if status_code in {401, 403}:
            return "authorization_error"
        if status_code == 404:
            return "not_found"
        if status_code == 409:
            return "conflict"
        if status_code == 429:
            return "rate_limited"
        if 500 <= status_code < 600:
            return "broker_error"
        if response_json.get("errorMessage"):
            return "rejected"
        return "unknown_failure"

    def _execution_category(
        self,
        *,
        status_code: int,
        response_json: Dict[str, Any],
        broker_order_id: Optional[str],
    ) -> str:
        if 200 <= status_code < 300 and broker_order_id is not None:
            return "submitted_to_broker"
        if status_code in {400, 404, 409}:
            return "terminal_rejection"
        if status_code in {401, 403}:
            return "authorization_failure"
        if status_code == 429:
            return "retryable_rate_limit"
        if 500 <= status_code < 600:
            return "retryable_server_error"
        if response_json.get("errorMessage"):
            return "terminal_rejection"
        return "unknown_failure"
