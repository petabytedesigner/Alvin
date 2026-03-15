from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional


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
    def __init__(
        self,
        *,
        grade_to_risk_pct: Mapping[str, float] | None = None,
        default_atr_stop_multiple: float = 1.5,
        grade_to_atr_stop_multiple: Mapping[str, float] | None = None,
    ) -> None:
        self.grade_to_risk_pct = {
            "A++": 1.5,
            "A+": 1.0,
            "A": 0.5,
            "B": 0.25,
            "C": 0.0,
            **dict(grade_to_risk_pct or {}),
        }
        self.default_atr_stop_multiple = float(default_atr_stop_multiple)
        self.grade_to_atr_stop_multiple = {
            "A++": 1.2,
            "A+": 1.35,
            "A": 1.5,
            "B": 1.75,
            "C": 2.0,
            **dict(grade_to_atr_stop_multiple or {}),
        }

    @classmethod
    def from_config(cls, risk_config: Mapping[str, Any]) -> "PositionSizer":
        return cls(
            grade_to_risk_pct=risk_config.get("grade_risk_pct", {}),
            default_atr_stop_multiple=float(risk_config.get("default_atr_stop_multiple", 1.5)),
            grade_to_atr_stop_multiple=risk_config.get("grade_atr_stop_multiple", {}),
        )

    def resolve_risk_pct(self, *, grade: str | None = None, explicit_risk_pct: float | None = None) -> float:
        if explicit_risk_pct is not None:
            return float(explicit_risk_pct)
        normalized_grade = str(grade or "C").strip().upper()
        return float(self.grade_to_risk_pct.get(normalized_grade, 0.0))

    def resolve_atr_stop_multiple(self, *, grade: str | None = None, explicit_multiple: float | None = None) -> float:
        if explicit_multiple is not None:
            return float(explicit_multiple)
        normalized_grade = str(grade or "C").strip().upper()
        return float(self.grade_to_atr_stop_multiple.get(normalized_grade, self.default_atr_stop_multiple))

    def derive_stop_price_from_atr(
        self,
        *,
        entry_price: float,
        atr_value: float,
        side: str,
        atr_multiple: float,
    ) -> float:
        normalized_side = side.strip().lower()
        if normalized_side == "long":
            return float(entry_price) - (float(atr_value) * float(atr_multiple))
        if normalized_side == "short":
            return float(entry_price) + (float(atr_value) * float(atr_multiple))
        raise ValueError(f"Unsupported side: {side}")

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

    def size_from_grade_and_atr(
        self,
        *,
        equity: float,
        instrument: str,
        side: str,
        entry_price: float,
        atr_value: float,
        grade: str,
        explicit_risk_pct: float | None = None,
        atr_multiple: float | None = None,
        price_per_unit_multiplier: float = 1.0,
        min_units: int = 1,
        max_units: Optional[int] = None,
    ) -> PositionSizeResult:
        normalized_grade = str(grade or "C").strip().upper()
        resolved_risk_pct = self.resolve_risk_pct(grade=normalized_grade, explicit_risk_pct=explicit_risk_pct)
        resolved_atr_multiple = self.resolve_atr_stop_multiple(grade=normalized_grade, explicit_multiple=atr_multiple)
        stop_price = self.derive_stop_price_from_atr(
            entry_price=entry_price,
            atr_value=atr_value,
            side=side,
            atr_multiple=resolved_atr_multiple,
        )
        result = self.size(
            equity=equity,
            risk_pct=resolved_risk_pct,
            entry_price=entry_price,
            stop_price=stop_price,
            instrument=instrument,
            side=side,
            price_per_unit_multiplier=price_per_unit_multiplier,
            min_units=min_units,
            max_units=max_units,
        )
        enriched_details = {
            **result.details,
            "grade": normalized_grade,
            "atr_value": float(atr_value),
            "atr_stop_multiple": resolved_atr_multiple,
            "resolved_risk_pct": resolved_risk_pct,
            "derived_stop_price": round(stop_price, 8),
        }
        return PositionSizeResult(
            allowed=result.allowed,
            units=result.units,
            risk_amount=result.risk_amount,
            per_unit_risk=result.per_unit_risk,
            stop_distance=result.stop_distance,
            reasons=list(result.reasons),
            details=enriched_details,
        )


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
