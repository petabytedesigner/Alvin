from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(slots=True)
class PositionSizeResult:
    allowed: bool
    units: int
    risk_amount: float
    per_unit_risk: float
    stop_distance: float
    reasons: list[str]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "units": self.units,
            "risk_amount": self.risk_amount,
            "per_unit_risk": self.per_unit_risk,
            "stop_distance": self.stop_distance,
            "reasons": list(self.reasons),
            "details": dict(self.details),
        }


class PositionSizer:
    def size(
        self,
        *,
        equity: float,
        risk_pct: float,
        entry_price: float,
        stop_price: float,
        instrument: str,
        side: str,
        price_per_unit_multiplier: float = 1.0,
        min_units: int = 1,
        max_units: Optional[int] = None,
    ) -> PositionSizeResult:
        reasons: list[str] = []
        details: Dict[str, Any] = {
            "instrument": instrument,
            "side": side,
            "equity": equity,
            "risk_pct": risk_pct,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "price_per_unit_multiplier": price_per_unit_multiplier,
            "min_units": min_units,
            "max_units": max_units,
        }

        if equity <= 0:
            reasons.append("equity_invalid")
        if risk_pct <= 0:
            reasons.append("risk_pct_invalid")
        if entry_price <= 0 or stop_price <= 0:
            reasons.append("price_invalid")
        if price_per_unit_multiplier <= 0:
            reasons.append("price_per_unit_multiplier_invalid")
        if side not in {"long", "short"}:
            reasons.append("side_invalid")

        stop_distance = abs(entry_price - stop_price)
        if stop_distance <= 0:
            reasons.append("stop_distance_invalid")

        if reasons:
            return PositionSizeResult(
                allowed=False,
                units=0,
                risk_amount=0.0,
                per_unit_risk=0.0,
                stop_distance=round(stop_distance, 8),
                reasons=_dedupe(reasons),
                details=details,
            )

        risk_amount = equity * (risk_pct / 100.0)
        per_unit_risk = stop_distance * price_per_unit_multiplier

        if per_unit_risk <= 0:
            reasons.append("per_unit_risk_invalid")
            return PositionSizeResult(
                allowed=False,
                units=0,
                risk_amount=round(risk_amount, 8),
                per_unit_risk=round(per_unit_risk, 8),
                stop_distance=round(stop_distance, 8),
                reasons=_dedupe(reasons),
                details=details,
            )

        raw_units = int(risk_amount // per_unit_risk)
        units = max(min_units, raw_units)

        if max_units is not None:
            units = min(units, max_units)

        if units < min_units:
            reasons.append("units_below_minimum")
            return PositionSizeResult(
                allowed=False,
                units=0,
                risk_amount=round(risk_amount, 8),
                per_unit_risk=round(per_unit_risk, 8),
                stop_distance=round(stop_distance, 8),
                reasons=_dedupe(reasons),
                details=details,
            )

        actual_risk = units * per_unit_risk
        if actual_risk > risk_amount * 1.05:
            reasons.append("actual_risk_above_budget")
            return PositionSizeResult(
                allowed=False,
                units=0,
                risk_amount=round(risk_amount, 8),
                per_unit_risk=round(per_unit_risk, 8),
                stop_distance=round(stop_distance, 8),
                reasons=_dedupe(reasons),
                details={**details, "raw_units": raw_units, "actual_risk": round(actual_risk, 8)},
            )

        reasons.append("position_sized")
        return PositionSizeResult(
            allowed=True,
            units=units,
            risk_amount=round(risk_amount, 8),
            per_unit_risk=round(per_unit_risk, 8),
            stop_distance=round(stop_distance, 8),
            reasons=reasons,
            details={**details, "raw_units": raw_units, "actual_risk": round(actual_risk, 8)},
        )


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
