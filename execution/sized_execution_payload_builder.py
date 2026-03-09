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


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
