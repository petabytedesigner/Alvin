from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from intelligence.acceptance_pipeline import AcceptanceDecision, AcceptancePipeline
from risk.risk_gate import RiskDecision, RiskGate
from strategy.setup_builder import SetupBuildResult


@dataclass(slots=True)
class SetupEvaluationResult:
    allowed: bool
    state: str
    acceptance: AcceptanceDecision
    risk: RiskDecision
    reasons: List[str]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        risk_state = "approved" if self.risk.allowed else "blocked"
        return {
            "allowed": self.allowed,
            "state": self.state,
            "acceptance": self.acceptance.to_dict(),
            "risk": {
                "allowed": self.risk.allowed,
                "state": risk_state,
                "risk_pct": self.risk.risk_pct,
                "reasons": list(self.risk.reasons),
                "details": dict(self.risk.details),
            },
            "reasons": list(self.reasons),
            "details": dict(self.details),
        }


class SetupEvaluator:
    def __init__(self, acceptance_pipeline: AcceptancePipeline, risk_gate: RiskGate) -> None:
        self.acceptance_pipeline = acceptance_pipeline
        self.risk_gate = risk_gate

    def evaluate(
        self,
        *,
        setup_result: SetupBuildResult,
        score_allowed: bool,
        score_value: float,
        regime_assessment: Any,
        execution_result: Any,
        portfolio_result: Any,
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
    ) -> SetupEvaluationResult:
        bounded_score_value = round(max(0.0, min(100.0, float(score_value))), 2)

        if not setup_result.allowed or setup_result.candidate is None:
            reasons = list(setup_result.reasons) or ["setup_not_ready"]
            blocked_risk = self.risk_gate.decide(
                grade=grade,
                daily_loss_pct=daily_loss_pct,
                daily_loss_limit_pct=daily_loss_limit_pct,
                open_risk_pct=open_risk_pct,
                max_open_risk_pct=max_open_risk_pct,
                concurrent_trades=concurrent_trades,
                max_concurrent_trades=max_concurrent_trades,
                kill_switch_active=kill_switch_active,
                cooldown_active=cooldown_active,
                news_lock_active=news_lock_active,
                session_allowed=session_allowed,
                execution_allowed=False,
                portfolio_allowed=False,
                score_allowed=False,
            )
            blocked_acceptance = AcceptanceDecision(
                decision_id="setup-blocked",
                candidate_id="none",
                instrument="unknown",
                allowed=False,
                state="rejected",
                conviction="blocked",
                reasons=reasons,
                details={"stage": "setup", "score_value": bounded_score_value},
            )
            return SetupEvaluationResult(
                allowed=False,
                state="blocked",
                acceptance=blocked_acceptance,
                risk=blocked_risk,
                reasons=reasons,
                details={"candidate_id": None, "score_value": bounded_score_value},
            )

        candidate = setup_result.candidate

        provisional_risk = self.risk_gate.decide(
            grade=grade,
            daily_loss_pct=daily_loss_pct,
            daily_loss_limit_pct=daily_loss_limit_pct,
            open_risk_pct=open_risk_pct,
            max_open_risk_pct=max_open_risk_pct,
            concurrent_trades=concurrent_trades,
            max_concurrent_trades=max_concurrent_trades,
            kill_switch_active=kill_switch_active,
            cooldown_active=cooldown_active,
            news_lock_active=news_lock_active,
            session_allowed=session_allowed,
            execution_allowed=True,
            portfolio_allowed=bool(getattr(portfolio_result, "allowed", False)),
            score_allowed=score_allowed,
        )

        acceptance = self.acceptance_pipeline.decide(
            candidate_id=candidate.candidate_id,
            instrument=candidate.instrument,
            score_allowed=score_allowed,
            score_value=bounded_score_value,
            regime_assessment=regime_assessment,
            execution_result=execution_result,
            portfolio_result=portfolio_result,
            risk_result=provisional_risk,
            explainability_reasons=list(setup_result.reasons),
        )

        final_risk = self.risk_gate.decide(
            grade=grade,
            daily_loss_pct=daily_loss_pct,
            daily_loss_limit_pct=daily_loss_limit_pct,
            open_risk_pct=open_risk_pct,
            max_open_risk_pct=max_open_risk_pct,
            concurrent_trades=concurrent_trades,
            max_concurrent_trades=max_concurrent_trades,
            kill_switch_active=kill_switch_active,
            cooldown_active=cooldown_active,
            news_lock_active=news_lock_active,
            session_allowed=session_allowed,
            execution_allowed=acceptance.allowed,
            portfolio_allowed=bool(getattr(portfolio_result, "allowed", False)),
            score_allowed=score_allowed,
        )

        allowed = acceptance.allowed and final_risk.allowed
        state = "approved" if allowed else "blocked"
        reasons = _dedupe([*acceptance.reasons, *final_risk.reasons])

        return SetupEvaluationResult(
            allowed=allowed,
            state=state,
            acceptance=acceptance,
            risk=final_risk,
            reasons=reasons,
            details={
                "candidate_id": candidate.candidate_id,
                "instrument": candidate.instrument,
                "side": candidate.side,
                "grade": grade,
                "score_value": bounded_score_value,
                "score_normalized": round(bounded_score_value / 100.0, 4),
                "conviction": acceptance.conviction,
                "risk_pct": final_risk.risk_pct,
            },
        )


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
