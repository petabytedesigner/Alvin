from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from broker.oanda_client import OandaClient
from broker.order_executor import OrderExecutor
from execution.execution_audit_builder import ExecutionAuditBuilder
from execution.execution_payload_builder import ExecutionPayloadBuilder
from execution.execution_result_handler import ExecutionResultHandler
from execution.intent_state_manager import IntentStateManager
from execution.order_intent_builder import OrderIntentBuilder
from execution.retry_policy import RetryPolicy
from intelligence.acceptance_pipeline import AcceptancePipeline
from intelligence.execution_quality import ExecutionQualityAssessor
from intelligence.regime_classifier import RegimeClassifier
from risk.risk_gate import RiskGate
from runtime.pipeline_runner import PipelineRunner
from strategy.break_retest_validator import BreakRetestValidator
from strategy.level_detection import LevelDetector
from strategy.setup_builder import StrategySetupBuilder
from strategy.setup_evaluator import SetupEvaluator
from utils.config_loader import load_all_configs


@dataclass(slots=True)
class AlvinComponents:
    config: Dict[str, Any]
    oanda_client: OandaClient
    level_detector: LevelDetector
    break_retest_validator: BreakRetestValidator
    regime_classifier: RegimeClassifier
    execution_quality_assessor: ExecutionQualityAssessor
    acceptance_pipeline: AcceptancePipeline
    risk_gate: RiskGate
    setup_builder: StrategySetupBuilder
    setup_evaluator: SetupEvaluator
    order_intent_builder: OrderIntentBuilder
    execution_payload_builder: ExecutionPayloadBuilder
    order_executor: OrderExecutor
    execution_result_handler: ExecutionResultHandler
    intent_state_manager: IntentStateManager
    execution_audit_builder: ExecutionAuditBuilder
    retry_policy: RetryPolicy
    pipeline_runner: PipelineRunner


def build_alvin_components(config: Dict[str, Any] | None = None) -> AlvinComponents:
    resolved_config = config or load_all_configs()

    oanda_client = OandaClient()
    level_detector = LevelDetector.from_config(resolved_config["strategy"])
    break_retest_validator = BreakRetestValidator.from_config(resolved_config["strategy"])
    regime_classifier = RegimeClassifier.from_config(resolved_config["regime"])
    execution_quality_assessor = ExecutionQualityAssessor.from_config(resolved_config["execution"])
    acceptance_pipeline = AcceptancePipeline()
    risk_gate = RiskGate.from_config(resolved_config["risk"])
    setup_builder = StrategySetupBuilder()
    setup_evaluator = SetupEvaluator(acceptance_pipeline=acceptance_pipeline, risk_gate=risk_gate)
    order_intent_builder = OrderIntentBuilder()
    execution_payload_builder = ExecutionPayloadBuilder()
    order_executor = OrderExecutor(client=oanda_client)
    execution_result_handler = ExecutionResultHandler()
    intent_state_manager = IntentStateManager()
    execution_audit_builder = ExecutionAuditBuilder()
    retry_policy = RetryPolicy()

    pipeline_runner = PipelineRunner(
        config=resolved_config,
        setup_builder=setup_builder,
        setup_evaluator=setup_evaluator,
        order_intent_builder=order_intent_builder,
        execution_payload_builder=execution_payload_builder,
        order_executor=order_executor,
        execution_result_handler=execution_result_handler,
        intent_state_manager=intent_state_manager,
        execution_audit_builder=execution_audit_builder,
        retry_policy=retry_policy,
    )

    return AlvinComponents(
        config=resolved_config,
        oanda_client=oanda_client,
        level_detector=level_detector,
        break_retest_validator=break_retest_validator,
        regime_classifier=regime_classifier,
        execution_quality_assessor=execution_quality_assessor,
        acceptance_pipeline=acceptance_pipeline,
        risk_gate=risk_gate,
        setup_builder=setup_builder,
        setup_evaluator=setup_evaluator,
        order_intent_builder=order_intent_builder,
        execution_payload_builder=execution_payload_builder,
        order_executor=order_executor,
        execution_result_handler=execution_result_handler,
        intent_state_manager=intent_state_manager,
        execution_audit_builder=execution_audit_builder,
        retry_policy=retry_policy,
        pipeline_runner=pipeline_runner,
    )
