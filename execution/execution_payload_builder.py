from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from contracts.order_lifecycle import OrderIntent


@dataclass(slots=True)
class ExecutionPayload:
    intent_id: str
    correlation_id: str
    instrument: str
    side: str
    units: int
    order_type: str
    time_in_force: str
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "correlation_id": self.correlation_id,
            "instrument": self.instrument,
            "side": self.side,
            "units": self.units,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "payload": self.payload,
        }


@dataclass(slots=True)
class ExecutionPayloadBuildResult:
    allowed: bool
    execution_payload: ExecutionPayload | None
    reasons: list[str]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "execution_payload": self.execution_payload.to_dict() if self.execution_payload is not None else None,
            "reasons": list(self.reasons),
            "details": dict(self.details),
        }


class ExecutionPayloadBuilder:
    VALID_ORDER_TYPES = {"market"}
    VALID_TIME_IN_FORCE = {"FOK", "IOC"}
    SUBMITTABLE_STATES = {"intent_created", "submit_started", "retryable_failure"}

    def build(
        self,
        *,
        intent: OrderIntent,
        units: int,
        order_type: str = "market",
        time_in_force: str = "FOK",
        price_bound: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> ExecutionPayloadBuildResult:
        reasons: list[str] = []
        details: Dict[str, Any] = {
            "intent_id": intent.intent_id,
            "instrument": intent.instrument,
            "side": intent.side,
            "grade": intent.grade,
            "score": intent.score,
            "dedupe_key": intent.dedupe_key,
            "intent_state": intent.state,
        }

        order_type_normalized = order_type.strip().lower()
        tif_normalized = time_in_force.strip().upper()

        if units <= 0:
            reasons.append("units_invalid")
        if intent.side not in {"long", "short"}:
            reasons.append("side_invalid")
        if order_type_normalized not in self.VALID_ORDER_TYPES:
            reasons.append("order_type_invalid")
        if tif_normalized not in self.VALID_TIME_IN_FORCE:
            reasons.append("time_in_force_invalid")
        if intent.state not in self.SUBMITTABLE_STATES:
            reasons.append("intent_state_not_submittable")

        signed_units = units if intent.side == "long" else -units

        broker_payload: Dict[str, Any] = {
            "order": {
                "type": "MARKET",
                "instrument": intent.instrument,
                "units": str(signed_units),
                "timeInForce": tif_normalized,
                "positionFill": "DEFAULT",
                "clientExtensions": {
                    "id": intent.intent_id,
                    "tag": "alvin",
                    "comment": intent.correlation_id,
                },
            }
        }

        if price_bound is not None:
            broker_payload["order"]["priceBound"] = f"{price_bound:.6f}"
        if stop_loss is not None:
            broker_payload["order"]["stopLossOnFill"] = {"price": f"{stop_loss:.6f}"}
        if take_profit is not None:
            broker_payload["order"]["takeProfitOnFill"] = {"price": f"{take_profit:.6f}"}

        if metadata:
            broker_payload["order"]["metadata"] = metadata

        if reasons:
            return ExecutionPayloadBuildResult(
                allowed=False,
                execution_payload=None,
                reasons=reasons,
                details=details,
            )

        execution_payload = ExecutionPayload(
            intent_id=intent.intent_id,
            correlation_id=intent.correlation_id,
            instrument=intent.instrument,
            side=intent.side,
            units=signed_units,
            order_type=order_type_normalized,
            time_in_force=tif_normalized,
            payload=broker_payload,
        )

        reasons.append("execution_payload_created")
        details.update(
            {
                "units": signed_units,
                "order_type": order_type_normalized,
                "time_in_force": tif_normalized,
                "has_price_bound": price_bound is not None,
                "has_stop_loss": stop_loss is not None,
                "has_take_profit": take_profit is not None,
                "resubmission": intent.state in {"submit_started", "retryable_failure"},
            }
        )

        return ExecutionPayloadBuildResult(
            allowed=True,
            execution_payload=execution_payload,
            reasons=reasons,
            details=details,
        )
