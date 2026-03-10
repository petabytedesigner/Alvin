from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import uuid4

from contracts.order_lifecycle import OrderIntent
from strategy.signal_candidate import SignalCandidate
from strategy.setup_evaluator import SetupEvaluationResult


@dataclass(slots=True)
class OrderIntentBuildResult:
    allowed: bool
    intent: Optional[OrderIntent]
    reasons: list[str]
    details: Dict[str, Any]


class OrderIntentBuilder:
    def build(
        self,
        *,
        candidate: SignalCandidate,
        evaluation: SetupEvaluationResult,
        ttl_minutes: int = 60,
        correlation_id: str | None = None,
        notes: Dict[str, Any] | None = None,
        minimum_trade_score: float = 50.0,
    ) -> OrderIntentBuildResult:
        reasons: list[str] = []
        details: Dict[str, Any] = {
            "candidate_id": candidate.candidate_id,
            "instrument": candidate.instrument,
            "side": candidate.side,
            "grade": candidate.grade,
            "score": candidate.score,
            "score_normalized": candidate.normalized_score,
            "minimum_trade_score": minimum_trade_score,
            "setup_type": candidate.setup_type,
        }

        if not evaluation.allowed:
            reasons.append("setup_not_approved_for_intent")
            reasons.extend(list(evaluation.reasons))
            return OrderIntentBuildResult(
                allowed=False,
                intent=None,
                reasons=_dedupe(reasons),
                details=details,
            )

        if candidate.grade == "C" or candidate.score < float(minimum_trade_score):
            reasons.append("candidate_not_tradeable")
            return OrderIntentBuildResult(
                allowed=False,
                intent=None,
                reasons=_dedupe(reasons),
                details=details,
            )

        payload: Dict[str, Any] = {
            "candidate": candidate.to_dict(),
            "acceptance": evaluation.acceptance.to_dict(),
            "risk": {
                "allowed": evaluation.risk.allowed,
                "risk_pct": evaluation.risk.risk_pct,
                "reasons": list(evaluation.risk.reasons),
                "details": dict(evaluation.risk.details),
            },
            "evaluation": {
                "state": evaluation.state,
                "reasons": list(evaluation.reasons),
                "details": dict(evaluation.details),
            },
            "notes": notes or {},
        }

        intent = OrderIntent(
            instrument=candidate.instrument,
            side=candidate.side,
            timeframe=candidate.timeframe,
            setup_type=candidate.setup_type,
            trigger_reference=candidate.trigger_reference,
            score=candidate.score,
            grade=candidate.grade,
            correlation_id=correlation_id or str(uuid4()),
            ttl_minutes=ttl_minutes,
            payload=payload,
        )

        reasons.append("order_intent_created")
        details.update(
            {
                "intent_id": intent.intent_id,
                "dedupe_key": intent.dedupe_key,
                "expires_at_utc": intent.expires_at_utc(),
            }
        )
        return OrderIntentBuildResult(
            allowed=True,
            intent=intent,
            reasons=reasons,
            details=details,
        )


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
