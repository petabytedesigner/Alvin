from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from contracts.order_lifecycle import OrderIntent
from execution.execution_payload_builder import (
    ExecutionPayload,
    ExecutionPayloadBuildResult,
    ExecutionPayloadBuilder,
)
from risk.position_sizer import PositionSizeResult, PositionSizer


@dataclass(slots=True)
class SizedExecutionPayloadResult:
    allowed: bool
    size_result: PositionSizeResult
    payload_result: ExecutionPayloadBuildResult
    reasons: list[str]
    details: Dict[str, Any]

    @property
    def execution_payload(self) -> ExecutionPayload | None:
        return self.payload_result.execution_payload

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "size_result": self.size_result.to_dict(),
            "payload_result": {
                "allowed": self.payload_result.allowed,
                "execution_payload": self.payload_result.execution_payload.to_dict()
                if self.payload_result.execution_payload is not None
                else None,
                "reasons": list(self.payload_result.reasons),
                "details": dict(self.payload_result.details),
            },
            "reasons": list(self.reasons),
            "details": dict(self.details),
        }


class SizedExecutionPayloadBuilder:
    def __init__(
        self,
        position_sizer: PositionSizer | None = None,
        payload_builder: ExecutionPayloadBuilder | None = None,
    ) -> None:
        self.position_sizer = position_sizer or PositionSizer()
        self.payload_builder = payload_builder or ExecutionPayloadBuilder()

    def build(
        self,
        *,
        intent: OrderIntent,
        equity: float,
        risk_pct: float,
        entry_price: float,
        stop_price: float,
        price_per_unit_multiplier: float = 1.0,
        min_units: int = 1,
        max_units: Optional[int] = None,
        order_type: str = "market",
        time_in_force: str = "FOK",
        price_bound: float | None = None,
        take_profit: float | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> SizedExecutionPayloadResult:
        size_result = self.position_sizer.size(
            equity=equity,
            risk_pct=risk_pct,
            entry_price=entry_price,
            stop_price=stop_price,
            instrument=intent.instrument,
            side=intent.side,
            price_per_unit_multiplier=price_per_unit_multiplier,
            min_units=min_units,
            max_units=max_units,
        )

        if not size_result.allowed:
            payload_result = ExecutionPayloadBuildResult(
                allowed=False,
                execution_payload=None,
                reasons=["position_sizing_failed"],
                details={
                    "intent_id": intent.intent_id,
                    "instrument": intent.instrument,
                },
            )
            reasons = _dedupe([*size_result.reasons, *payload_result.reasons])
            return SizedExecutionPayloadResult(
                allowed=False,
                size_result=size_result,
                payload_result=payload_result,
                reasons=reasons,
                details={
                    "intent_id": intent.intent_id,
                    "instrument": intent.instrument,
                    "stage": "position_sizing",
                },
            )

        payload_result = self.payload_builder.build(
            intent=intent,
            units=size_result.units,
            order_type=order_type,
            time_in_force=time_in_force,
            price_bound=price_bound,
            stop_loss=stop_price,
            take_profit=take_profit,
            metadata={
                **(metadata or {}),
                "sizing": size_result.to_dict(),
            },
        )

        reasons = _dedupe([*size_result.reasons, *payload_result.reasons])
        return SizedExecutionPayloadResult(
            allowed=size_result.allowed and payload_result.allowed,
            size_result=size_result,
            payload_result=payload_result,
            reasons=reasons,
            details={
                "intent_id": intent.intent_id,
                "instrument": intent.instrument,
                "units": size_result.units,
                "risk_amount": size_result.risk_amount,
                "stop_distance": size_result.stop_distance,
                "payload_allowed": payload_result.allowed,
            },
        )

    def build_from_intent_payload(
        self,
        *,
        intent: OrderIntent,
        equity: float,
        entry_price: float,
        stop_price: float | None = None,
        atr_value: float | None = None,
        explicit_risk_pct: float | None = None,
        atr_multiple: float | None = None,
        price_per_unit_multiplier: float = 1.0,
        min_units: int = 1,
        max_units: Optional[int] = None,
        order_type: str = "market",
        time_in_force: str = "FOK",
        price_bound: float | None = None,
        take_profit: float | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> SizedExecutionPayloadResult:
        payload = dict(intent.payload or {})
        candidate = payload.get("candidate") or {}
        risk = payload.get("risk") or {}
        notes = payload.get("notes") or {}

        resolved_grade = str(candidate.get("grade") or intent.grade or "C").strip().upper()
        resolved_risk_pct = self.position_sizer.resolve_risk_pct(
            grade=resolved_grade,
            explicit_risk_pct=explicit_risk_pct if explicit_risk_pct is not None else risk.get("risk_pct"),
        )

        if stop_price is None:
            if atr_value is None:
                invalid_size = PositionSizeResult(
                    allowed=False,
                    units=0,
                    risk_amount=0.0,
                    per_unit_risk=0.0,
                    stop_distance=0.0,
                    reasons=["stop_price_or_atr_required"],
                    details={
                        "intent_id": intent.intent_id,
                        "instrument": intent.instrument,
                        "grade": resolved_grade,
                    },
                )
                invalid_payload = ExecutionPayloadBuildResult(
                    allowed=False,
                    execution_payload=None,
                    reasons=["position_sizing_failed"],
                    details={"intent_id": intent.intent_id, "instrument": intent.instrument},
                )
                return SizedExecutionPayloadResult(
                    allowed=False,
                    size_result=invalid_size,
                    payload_result=invalid_payload,
                    reasons=["stop_price_or_atr_required", "position_sizing_failed"],
                    details={"intent_id": intent.intent_id, "instrument": intent.instrument, "stage": "position_sizing"},
                )

            sized_result = self.position_sizer.size_from_grade_and_atr(
                equity=equity,
                instrument=intent.instrument,
                side=intent.side,
                entry_price=entry_price,
                atr_value=float(atr_value),
                grade=resolved_grade,
                explicit_risk_pct=resolved_risk_pct,
                atr_multiple=atr_multiple,
                price_per_unit_multiplier=price_per_unit_multiplier,
                min_units=min_units,
                max_units=max_units,
            )
            derived_stop_price = float(sized_result.details.get("derived_stop_price", 0.0))
            if not sized_result.allowed:
                invalid_payload = ExecutionPayloadBuildResult(
                    allowed=False,
                    execution_payload=None,
                    reasons=["position_sizing_failed"],
                    details={"intent_id": intent.intent_id, "instrument": intent.instrument},
                )
                return SizedExecutionPayloadResult(
                    allowed=False,
                    size_result=sized_result,
                    payload_result=invalid_payload,
                    reasons=_dedupe([*sized_result.reasons, "position_sizing_failed"]),
                    details={"intent_id": intent.intent_id, "instrument": intent.instrument, "stage": "position_sizing"},
                )

            payload_result = self.payload_builder.build(
                intent=intent,
                units=sized_result.units,
                order_type=order_type,
                time_in_force=time_in_force,
                price_bound=price_bound,
                stop_loss=derived_stop_price,
                take_profit=take_profit,
                metadata={
                    **(metadata or {}),
                    "sizing": sized_result.to_dict(),
                    "sizing_source": "intent_payload_and_atr",
                    "intent_notes": notes,
                },
            )
            reasons = _dedupe([*sized_result.reasons, *payload_result.reasons])
            return SizedExecutionPayloadResult(
                allowed=sized_result.allowed and payload_result.allowed,
                size_result=sized_result,
                payload_result=payload_result,
                reasons=reasons,
                details={
                    "intent_id": intent.intent_id,
                    "instrument": intent.instrument,
                    "units": sized_result.units,
                    "risk_amount": sized_result.risk_amount,
                    "stop_distance": sized_result.stop_distance,
                    "payload_allowed": payload_result.allowed,
                    "resolved_grade": resolved_grade,
                    "resolved_risk_pct": resolved_risk_pct,
                    "sizing_source": "intent_payload_and_atr",
                },
            )

        return self.build(
            intent=intent,
            equity=equity,
            risk_pct=resolved_risk_pct,
            entry_price=entry_price,
            stop_price=float(stop_price),
            price_per_unit_multiplier=price_per_unit_multiplier,
            min_units=min_units,
            max_units=max_units,
            order_type=order_type,
            time_in_force=time_in_force,
            price_bound=price_bound,
            take_profit=take_profit,
            metadata={
                **(metadata or {}),
                "sizing_source": "intent_payload_and_stop",
                "intent_notes": notes,
            },
        )


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
