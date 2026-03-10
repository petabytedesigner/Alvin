from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(slots=True)
class RiskDecision:
    allowed: bool
    risk_pct: float
    reasons: list[str]
    details: dict[str, Any]


class RiskGate:
    def __init__(self, *, grade_to_risk: Mapping[str, float] | None = None) -> None:
        self.grade_to_risk = {
            "A++": 1.5,
            "A+": 1.0,
            "A": 0.5,
            "B": 0.25,
            "C": 0.0,
            **dict(grade_to_risk or {}),
        }

    @classmethod
    def from_config(cls, risk_config: Mapping[str, Any]) -> "RiskGate":
        return cls(grade_to_risk=risk_config.get("grade_risk_pct", {}))

    def decide(
        self,
        *,
        grade: str,
        daily_loss_pct: float,
        daily_loss_limit_pct: float,
        open_risk_pct: float,
        max_open_risk_pct: float,
        concurrent_trades: int,
        max_concurrent_trades: int,
        kill_switch_active: bool,
        cooldown_active: bool,
        news_lock_active: bool,
        session_allowed: bool,
        execution_allowed: bool,
        portfolio_allowed: bool,
        score_allowed: bool = True,
    ) -> RiskDecision:
        reasons: list[str] = []
        proposed_risk = float(self.grade_to_risk.get(grade, 0.0))

        if grade not in self.grade_to_risk:
            reasons.append("unknown_grade")
        if grade == "C" or proposed_risk <= 0.0:
            reasons.append("grade_blocked")
        if daily_loss_pct >= daily_loss_limit_pct:
            reasons.append("daily_loss_limit_reached")
        if open_risk_pct >= max_open_risk_pct:
            reasons.append("max_open_risk_reached")
        elif open_risk_pct + proposed_risk > max_open_risk_pct:
            reasons.append("trade_would_exceed_open_risk")
        if concurrent_trades >= max_concurrent_trades:
            reasons.append("max_concurrent_trades_reached")
        if kill_switch_active:
            reasons.append("kill_switch_active")
        if cooldown_active:
            reasons.append("cooldown_active")
        if news_lock_active:
            reasons.append("news_lock_active")
        if not session_allowed:
            reasons.append("session_not_allowed")
        if not execution_allowed:
            reasons.append("execution_not_allowed")
        if not portfolio_allowed:
            reasons.append("portfolio_not_allowed")
        if not score_allowed:
            reasons.append("score_not_allowed")

        allowed = not reasons
        final_risk = proposed_risk if allowed else 0.0

        if allowed:
            reasons.append("risk_approved")

        return RiskDecision(
            allowed=allowed,
            risk_pct=final_risk,
            reasons=reasons,
            details={
                "grade": grade,
                "grade_to_risk": dict(self.grade_to_risk),
                "proposed_risk_pct": proposed_risk,
                "daily_loss_pct": daily_loss_pct,
                "daily_loss_limit_pct": daily_loss_limit_pct,
                "open_risk_pct": open_risk_pct,
                "max_open_risk_pct": max_open_risk_pct,
                "concurrent_trades": concurrent_trades,
                "max_concurrent_trades": max_concurrent_trades,
                "kill_switch_active": kill_switch_active,
                "cooldown_active": cooldown_active,
                "news_lock_active": news_lock_active,
                "session_allowed": session_allowed,
                "execution_allowed": execution_allowed,
                "portfolio_allowed": portfolio_allowed,
                "score_allowed": score_allowed,
            },
        )
