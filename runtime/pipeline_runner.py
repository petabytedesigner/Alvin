from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from execution.order_intent_builder import OrderIntentBuildResult, OrderIntentBuilder
from strategy.setup_builder import SetupBuildResult, StrategySetupBuilder
from strategy.setup_evaluator import SetupEvaluationResult, SetupEvaluator


@dataclass(slots=True)
class PipelineRunResult:
    stage: str
    allowed: bool
    setup_result: Optional[SetupBuildResult]
    evaluation_result: Optional[SetupEvaluationResult]
    intent_result: Optional[OrderIntentBuildResult]
    execution_payload_result: Any = None
    execution_result: Any = None
    handled_result: Any = None
    transition_result: Any = None
    audit_record: Any = None
    retry_decision: Any = None
    details: Dict[str, Any] = field(default_factory=dict)


class PipelineRunner:
    def __init__(
        self,
        *,
        config: Dict[str, Any],
        setup_builder: StrategySetupBuilder,
        setup_evaluator: SetupEvaluator,
        order_intent_builder: OrderIntentBuilder,
        execution_payload_builder: Any = None,
        order_executor: Any = None,
        execution_result_handler: Any = None,
        intent_state_manager: Any = None,
        execution_audit_builder: Any = None,
        retry_policy: Any = None,
    ) -> None:
        self.config = config
        self.setup_builder = setup_builder
        self.setup_evaluator = setup_evaluator
        self.order_intent_builder = order_intent_builder
        self.execution_payload_builder = execution_payload_builder
        self.order_executor = order_executor
        self.execution_result_handler = execution_result_handler
        self.intent_state_manager = intent_state_manager
        self.execution_audit_builder = execution_audit_builder
        self.retry_policy = retry_policy

    def readiness_report(self) -> Dict[str, Any]:
        setup_to_intent_ready = all(
            [
                self.setup_builder is not None,
                self.setup_evaluator is not None,
                self.order_intent_builder is not None,
            ]
        )
        full_execution_wired = all(
            [
                self.execution_payload_builder is not None,
                self.order_executor is not None,
                self.execution_result_handler is not None,
                self.intent_state_manager is not None,
                self.execution_audit_builder is not None,
                self.retry_policy is not None,
            ]
        )
        return {
            "pipeline_runner_ready": True,
            "setup_to_intent_ready": setup_to_intent_ready,
            "full_execution_wired": full_execution_wired,
            "component_summary": {
                "setup_builder": type(self.setup_builder).__name__ if self.setup_builder is not None else None,
                "setup_evaluator": type(self.setup_evaluator).__name__ if self.setup_evaluator is not None else None,
                "order_intent_builder": type(self.order_intent_builder).__name__ if self.order_intent_builder is not None else None,
                "execution_payload_builder": type(self.execution_payload_builder).__name__ if self.execution_payload_builder is not None else None,
                "order_executor": type(self.order_executor).__name__ if self.order_executor is not None else None,
                "execution_result_handler": type(self.execution_result_handler).__name__ if self.execution_result_handler is not None else None,
                "intent_state_manager": type(self.intent_state_manager).__name__ if self.intent_state_manager is not None else None,
                "execution_audit_builder": type(self.execution_audit_builder).__name__ if self.execution_audit_builder is not None else None,
                "retry_policy": type(self.retry_policy).__name__ if self.retry_policy is not None else None,
            },
        }

    def run_setup_to_intent(
        self,
        *,
        instrument: str,
        timeframe: str,
        side: str,
        setup_type: str,
        level: Any,
        break_retest: Any,
        confirmation: Any,
        atr_value: float,
        score_hint: float,
        grade: str,
        evaluation_inputs: Dict[str, Any],
        session: str = "unknown",
        post_news: bool = False,
        metadata: Dict[str, Any] | None = None,
        ttl_minutes: int = 60,
        correlation_id: str | None = None,
        intent_notes: Dict[str, Any] | None = None,
    ) -> PipelineRunResult:
        setup_result = self.setup_builder.build(
            instrument=instrument,
            timeframe=timeframe,
            side=side,
            setup_type=setup_type,
            level=level,
            break_retest=break_retest,
            confirmation=confirmation,
            atr_value=atr_value,
            score_hint=score_hint,
            grade=grade,
            session=session,
            post_news=post_news,
            metadata=metadata,
        )
        if not setup_result.allowed or setup_result.candidate is None:
            return PipelineRunResult(
                stage="setup_blocked",
                allowed=False,
                setup_result=setup_result,
                evaluation_result=None,
                intent_result=None,
                details={"reasons": list(setup_result.reasons)},
            )

        candidate = setup_result.candidate
        minimum_trade_score = float(self.config.get("scoring", {}).get("minimum_trade_score", 50.0))
        risk_cfg = self.config.get("risk", {})

        evaluation_result = self.setup_evaluator.evaluate(
            setup_result=setup_result,
            score_allowed=bool(evaluation_inputs.get("score_allowed", True)),
            score_value=float(evaluation_inputs.get("score_value", candidate.score)),
            regime_assessment=evaluation_inputs["regime_assessment"],
            execution_result=evaluation_inputs["execution_result"],
            portfolio_result=evaluation_inputs["portfolio_result"],
            grade=grade,
            daily_loss_pct=float(evaluation_inputs.get("daily_loss_pct", 0.0)),
            daily_loss_limit_pct=float(
                evaluation_inputs.get("daily_loss_limit_pct", risk_cfg.get("daily_loss_limit_pct", 2.0))
            ),
            open_risk_pct=float(evaluation_inputs.get("open_risk_pct", 0.0)),
            max_open_risk_pct=float(
                evaluation_inputs.get("max_open_risk_pct", risk_cfg.get("max_open_risk_pct", 2.0))
            ),
            concurrent_trades=int(evaluation_inputs.get("concurrent_trades", 0)),
            max_concurrent_trades=int(
                evaluation_inputs.get("max_concurrent_trades", risk_cfg.get("max_concurrent_trades", 3))
            ),
            kill_switch_active=bool(evaluation_inputs.get("kill_switch_active", False)),
            cooldown_active=bool(evaluation_inputs.get("cooldown_active", False)),
            news_lock_active=bool(evaluation_inputs.get("news_lock_active", False)),
            session_allowed=bool(evaluation_inputs.get("session_allowed", True)),
        )
        if not evaluation_result.allowed:
            return PipelineRunResult(
                stage="evaluation_blocked",
                allowed=False,
                setup_result=setup_result,
                evaluation_result=evaluation_result,
                intent_result=None,
                details={"reasons": list(evaluation_result.reasons)},
            )

        intent_result = self.order_intent_builder.build(
            candidate=candidate,
            evaluation=evaluation_result,
            ttl_minutes=ttl_minutes,
            correlation_id=correlation_id,
            notes=intent_notes,
            minimum_trade_score=minimum_trade_score,
        )
        if not intent_result.allowed or intent_result.intent is None:
            return PipelineRunResult(
                stage="intent_blocked",
                allowed=False,
                setup_result=setup_result,
                evaluation_result=evaluation_result,
                intent_result=intent_result,
                details={"reasons": list(intent_result.reasons)},
            )

        return PipelineRunResult(
            stage="intent_ready",
            allowed=True,
            setup_result=setup_result,
            evaluation_result=evaluation_result,
            intent_result=intent_result,
            details={
                "candidate_id": candidate.candidate_id,
                "intent_id": intent_result.intent.intent_id,
                "minimum_trade_score": minimum_trade_score,
            },
        )

    def run_intent_to_execution(
        self,
        *,
        intent: Any,
        execution_request: Dict[str, Any],
        base_result: PipelineRunResult | None = None,
    ) -> PipelineRunResult:
        result = base_result or PipelineRunResult(
            stage="intent_ready",
            allowed=True,
            setup_result=None,
            evaluation_result=None,
            intent_result=None,
            details={},
        )

        if self.execution_payload_builder is None or self.order_executor is None:
            result.stage = "payload_blocked"
            result.allowed = False
            result.details.setdefault("reasons", []).append("execution_stack_not_wired")
            return result

        attempt_number = int(execution_request.get("attempt_number", 1))
        payload_request = {key: value for key, value in execution_request.items() if key != "attempt_number"}

        execution_payload_result = self.execution_payload_builder.build(intent=intent, **payload_request)
        result.execution_payload_result = execution_payload_result

        if not getattr(execution_payload_result, "allowed", False):
            result.stage = "payload_blocked"
            result.allowed = False
            result.details.setdefault("reasons", []).extend(list(getattr(execution_payload_result, "reasons", [])))
            return result

        if getattr(intent, "state", None) == "intent_created" and hasattr(intent, "transition"):
            intent.transition("submit_started", reason="submit_started")

        execution_payload = getattr(execution_payload_result, "execution_payload", None)
        execution_result = self.order_executor.submit(execution_payload=execution_payload)
        result.execution_result = execution_result

        handled_result = None
        if self.execution_result_handler is not None and hasattr(self.execution_result_handler, "handle"):
            handled_result = self.execution_result_handler.handle(result=execution_result)
            result.handled_result = handled_result

        transition_result = None
        if (
            handled_result is not None
            and self.intent_state_manager is not None
            and hasattr(self.intent_state_manager, "transition_from_execution")
        ):
            transition_result = self.intent_state_manager.transition_from_execution(
                intent=intent,
                handled_result=handled_result,
            )
            result.transition_result = transition_result

            if transition_result.allowed and hasattr(intent, "transition"):
                transition_reason = transition_result.reasons[-1] if transition_result.reasons else None
                intent.transition(transition_result.next_state, reason=transition_reason)

        retry_decision = None
        if (
            handled_result is not None
            and transition_result is not None
            and self.retry_policy is not None
            and hasattr(self.retry_policy, "decide")
        ):
            retry_decision = self.retry_policy.decide(
                handled_result=handled_result,
                transition=transition_result,
                attempt_number=attempt_number,
            )
            result.retry_decision = retry_decision

        audit_result = None
        if (
            handled_result is not None
            and transition_result is not None
            and self.execution_audit_builder is not None
            and hasattr(self.execution_audit_builder, "build")
        ):
            audit_result = self.execution_audit_builder.build(
                intent=intent,
                handled_result=handled_result,
                transition=transition_result,
            )
            result.audit_record = audit_result

        result.stage = "execution_complete"
        result.allowed = bool(getattr(execution_result, "submitted", False))
        result.details.update(
            {
                "execution_submitted": bool(getattr(execution_result, "submitted", False)),
                "execution_status": getattr(execution_result, "status", "unknown"),
                "handled_state": getattr(handled_result, "state", None) if handled_result is not None else None,
                "transition_next_state": getattr(transition_result, "next_state", None) if transition_result is not None else None,
                "intent_state": getattr(intent, "state", None),
                "intent_history": list(getattr(intent, "history", [])) if hasattr(intent, "history") else None,
                "retry_scheduled": bool(getattr(retry_decision, "should_retry", False)) if retry_decision is not None else False,
                "audit_allowed": bool(getattr(audit_result, "allowed", False)) if audit_result is not None else None,
            }
        )
        return result

    def run_full(
        self,
        *,
        instrument: str,
        timeframe: str,
        side: str,
        setup_type: str,
        level: Any,
        break_retest: Any,
        confirmation: Any,
        atr_value: float,
        score_hint: float,
        grade: str,
        evaluation_inputs: Dict[str, Any],
        execution_request: Dict[str, Any] | None = None,
        session: str = "unknown",
        post_news: bool = False,
        metadata: Dict[str, Any] | None = None,
        ttl_minutes: int = 60,
        correlation_id: str | None = None,
        intent_notes: Dict[str, Any] | None = None,
    ) -> PipelineRunResult:
        base_result = self.run_setup_to_intent(
            instrument=instrument,
            timeframe=timeframe,
            side=side,
            setup_type=setup_type,
            level=level,
            break_retest=break_retest,
            confirmation=confirmation,
            atr_value=atr_value,
            score_hint=score_hint,
            grade=grade,
            evaluation_inputs=evaluation_inputs,
            session=session,
            post_news=post_news,
            metadata=metadata,
            ttl_minutes=ttl_minutes,
            correlation_id=correlation_id,
            intent_notes=intent_notes,
        )
        if not base_result.allowed or base_result.intent_result is None or base_result.intent_result.intent is None:
            return base_result

        if execution_request is None:
            return base_result

        return self.run_intent_to_execution(
            intent=base_result.intent_result.intent,
            execution_request=execution_request,
            base_result=base_result,
        )
