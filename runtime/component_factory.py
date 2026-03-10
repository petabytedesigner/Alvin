from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from execution.order_intent_builder import OrderIntentBuilder
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
    level_detector: LevelDetector
    break_retest_validator: BreakRetestValidator
    regime_classifier: RegimeClassifier
    execution_quality_assessor: ExecutionQualityAssessor
    acceptance_pipeline: AcceptancePipeline
    risk_gate: RiskGate
    setup_builder: StrategySetupBuilder
    setup_evaluator: SetupEvaluator
    order_intent_builder: OrderIntentBuilder
    pipeline_runner: PipelineRunner


def build_alvin_components(config: Dict[str, Any] | None = None) -> AlvinComponents:
    resolved_config = config or load_all_configs()

    level_detector = LevelDetector.from_config(resolved_config["strategy"])
    break_retest_validator = BreakRetestValidator.from_config(resolved_config["strategy"])
    regime_classifier = RegimeClassifier.from_config(resolved_config["regime"])
    execution_quality_assessor = ExecutionQualityAssessor.from_config(resolved_config["execution"])
    acceptance_pipeline = AcceptancePipeline()
    risk_gate = RiskGate.from_config(resolved_config["risk"])
    setup_builder = StrategySetupBuilder()
    setup_evaluator = SetupEvaluator(acceptance_pipeline=acceptance_pipeline, risk_gate=risk_gate)
    order_intent_builder = OrderIntentBuilder()
    pipeline_runner = PipelineRunner(
        config=resolved_config,
        setup_builder=setup_builder,
        setup_evaluator=setup_evaluator,
        order_intent_builder=order_intent_builder,
    )

    return AlvinComponents(
        config=resolved_config,
        level_detector=level_detector,
        break_retest_validator=break_retest_validator,
        regime_classifier=regime_classifier,
        execution_quality_assessor=execution_quality_assessor,
        acceptance_pipeline=acceptance_pipeline,
        risk_gate=risk_gate,
        setup_builder=setup_builder,
        setup_evaluator=setup_evaluator,
        order_intent_builder=order_intent_builder,
        pipeline_runner=pipeline_runner,
    )
