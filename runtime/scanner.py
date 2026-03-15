from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, Sequence

from analytics.atr import ATRCalculator
from analytics.candle_mapping import CandleMapper
from data.candle_cache import CandleCache
from intelligence.execution_quality import ExecutionQualityAssessor
from intelligence.regime_classifier import RegimeClassifier
from market_data.contracts import MarketDataCandle, Timeframe
from market_data.oanda_market_data import OandaMarketData
from runtime.scan_models import ScanRequest, ScanResult
from strategy.break_retest_validator import BreakRetestResult, BreakRetestValidator
from strategy.level_detection import Candle, Level, LevelDetector
from strategy.m15_confirmation import ConfirmationResult, M15ConfirmationValidator
from strategy.setup_builder import StrategySetupBuilder
from strategy.setup_evaluator import SetupEvaluationResult, SetupEvaluator


class Scanner:
    """
    Scanner upgraded from market-context mode to setup/evaluation mode.

    Current scope:
    - fetch H1 / M15 data
    - compute ATR
    - detect levels
    - classify regime
    - locate a recent break/retest candidate on H1
    - validate M15 confirmation
    - build setup candidate
    - evaluate setup
    - build order intent when evaluation is approved
    """

    def __init__(
        self,
        *,
        market_data: OandaMarketData,
        atr_calculator: ATRCalculator,
        candle_mapper: CandleMapper,
        candle_cache: CandleCache,
        level_detector: LevelDetector,
        break_retest_validator: BreakRetestValidator,
        regime_classifier: RegimeClassifier,
        execution_quality_assessor: ExecutionQualityAssessor,
        setup_builder: StrategySetupBuilder,
        setup_evaluator: SetupEvaluator,
        order_intent_builder: Any | None = None,
        minimum_trade_score: float = 50.0,
    ) -> None:
        self.market_data = market_data
        self.atr_calculator = atr_calculator
        self.candle_mapper = candle_mapper
        self.candle_cache = candle_cache
        self.level_detector = level_detector
        self.break_retest_validator = break_retest_validator
        self.regime_classifier = regime_classifier
        self.execution_quality_assessor = execution_quality_assessor
        self.setup_builder = setup_builder
        self.setup_evaluator = setup_evaluator
        self.order_intent_builder = order_intent_builder
        self.minimum_trade_score = float(minimum_trade_score)
        self.confirmation_validator = M15ConfirmationValidator()

    def scan_once(self, request: ScanRequest) -> ScanResult:
        instrument = request.instrument.strip().upper()
        if not instrument:
            return ScanResult(allowed=False, stage="scan_blocked", reasons=["instrument_missing"])

        h1_batch = self.market_data.fetch_h1(instrument=instrument, count=request.h1_count)
        m15_batch = self.market_data.fetch_m15(instrument=instrument, count=request.m15_count)

        self.candle_cache.put(h1_batch)
        self.candle_cache.put(m15_batch)

        if len(h1_batch.candles) < max(20, self.atr_calculator.period + 1):
            return ScanResult(
                allowed=False,
                stage="scan_blocked",
                reasons=["insufficient_h1_data"],
                details={"h1_count": len(h1_batch.candles)},
            )

        if len(m15_batch.candles) < 3:
            return ScanResult(
                allowed=False,
                stage="scan_blocked",
                reasons=["insufficient_m15_data"],
                details={"m15_count": len(m15_batch.candles)},
            )

        atr = self.atr_calculator.calculate(h1_batch.candles)
        h1_level_candles = self.candle_mapper.to_level_detection_candles(h1_batch.candles)
        m15_confirmation_candles = self.candle_mapper.to_m15_confirmation_candles(m15_batch.candles)

        levels = self.level_detector.detect_levels(h1_level_candles, atr_value=atr.value)
        regime = self._classify_regime(
            h1_candles=h1_batch.candles,
            atr_value=atr.value,
            post_news=request.post_news,
        )

        selected_level = self._select_primary_level(
            levels=levels,
            current_price=h1_batch.candles[-1].close,
        )
        if selected_level is None:
            return ScanResult(
                allowed=False,
                stage="setup_blocked",
                reasons=["no_candidate_level"],
                details=self._base_details(
                    instrument=instrument,
                    request=request,
                    atr=atr.to_dict(),
                    levels=levels,
                    regime=regime,
                    h1_count=len(h1_batch.candles),
                    m15_count=len(m15_batch.candles),
                ),
            )

        break_scan = self._find_recent_break_retest(
            level=selected_level,
            candles=h1_level_candles,
            atr_value=atr.value,
        )
        break_retest = break_scan["result"]
        if not break_retest.valid:
            return ScanResult(
                allowed=False,
                stage="setup_blocked",
                reasons=["break_retest_not_valid", break_retest.reason],
                details={
                    **self._base_details(
                        instrument=instrument,
                        request=request,
                        atr=atr.to_dict(),
                        levels=levels,
                        regime=regime,
                        h1_count=len(h1_batch.candles),
                        m15_count=len(m15_batch.candles),
                    ),
                    "selected_level": selected_level.to_dict(),
                    "break_retest": self._serialize_break_retest(break_retest),
                    "break_indices": {
                        "break_index": break_scan.get("break_index"),
                        "retest_index": break_scan.get("retest_index"),
                    },
                },
            )

        side = break_retest.direction
        confirmation = self.confirmation_validator.validate(m15_confirmation_candles, side)
        if not confirmation.confirmed:
            return ScanResult(
                allowed=False,
                stage="setup_blocked",
                reasons=["m15_confirmation_not_valid", *confirmation.reasons],
                details={
                    **self._base_details(
                        instrument=instrument,
                        request=request,
                        atr=atr.to_dict(),
                        levels=levels,
                        regime=regime,
                        h1_count=len(h1_batch.candles),
                        m15_count=len(m15_batch.candles),
                    ),
                    "selected_level": selected_level.to_dict(),
                    "break_retest": self._serialize_break_retest(break_retest),
                    "confirmation": self._serialize_confirmation(confirmation),
                },
            )

        score_hint = self._score_hint(
            level=selected_level,
            break_retest=break_retest,
            confirmation=confirmation,
            regime_name=regime.regime,
            regime_confidence=regime.confidence,
        )

        setup_result = self.setup_builder.build(
            instrument=instrument,
            timeframe=Timeframe.H1,
            side=side,
            setup_type="break_retest",
            level=selected_level,
            break_retest=break_retest,
            confirmation=confirmation,
            atr_value=atr.value,
            score_hint=score_hint,
            grade=self._grade_from_score(score_hint),
            session=request.session,
            post_news=request.post_news,
            regime=regime.regime,
            metadata={
                "scanner_stage": "setup_build",
                "regime_confidence": regime.confidence,
                "break_index": break_scan.get("break_index"),
                "retest_index": break_scan.get("retest_index"),
            },
        )

        if not setup_result.allowed or setup_result.candidate is None:
            return ScanResult(
                allowed=False,
                stage="setup_blocked",
                reasons=list(setup_result.reasons),
                details={
                    **self._base_details(
                        instrument=instrument,
                        request=request,
                        atr=atr.to_dict(),
                        levels=levels,
                        regime=regime,
                        h1_count=len(h1_batch.candles),
                        m15_count=len(m15_batch.candles),
                    ),
                    "selected_level": selected_level.to_dict(),
                    "break_retest": self._serialize_break_retest(break_retest),
                    "confirmation": self._serialize_confirmation(confirmation),
                    "setup": setup_result.to_dict(),
                },
            )

        execution_quality = self._assess_execution_quality(
            instrument=instrument,
            confirmation=confirmation,
        )
        portfolio_result = SimpleNamespace(
            allowed=True,
            pressure_score=0.10,
            reasons=["portfolio_ok"],
        )

        evaluation_result = self.setup_evaluator.evaluate(
            setup_result=setup_result,
            score_allowed=True,
            score_value=score_hint,
            regime_assessment=regime,
            execution_result=execution_quality,
            portfolio_result=portfolio_result,
            grade=self._grade_from_score(score_hint),
            daily_loss_pct=0.0,
            daily_loss_limit_pct=2.0,
            open_risk_pct=0.0,
            max_open_risk_pct=2.0,
            concurrent_trades=0,
            max_concurrent_trades=3,
            kill_switch_active=False,
            cooldown_active=False,
            news_lock_active=False,
            session_allowed=True,
        )

        base_details = {
            **self._base_details(
                instrument=instrument,
                request=request,
                atr=atr.to_dict(),
                levels=levels,
                regime=regime,
                h1_count=len(h1_batch.candles),
                m15_count=len(m15_batch.candles),
            ),
            "selected_level": selected_level.to_dict(),
            "break_retest": self._serialize_break_retest(break_retest),
            "confirmation": self._serialize_confirmation(confirmation),
            "execution_quality": self._serialize_execution_quality(execution_quality),
            "setup": setup_result.to_dict(),
            "evaluation": self._serialize_evaluation(evaluation_result),
            "cache_keys": [
                f"{instrument}::{Timeframe.H1}",
                f"{instrument}::{Timeframe.M15}",
            ],
        }

        if not evaluation_result.allowed:
            return ScanResult(
                allowed=False,
                stage="evaluation_blocked",
                reasons=list(evaluation_result.reasons),
                details=base_details,
            )

        intent_result = self._build_intent(
            candidate=setup_result.candidate,
            evaluation_result=evaluation_result,
            instrument=instrument,
            request=request,
            selected_level=selected_level,
        )
        base_details["intent"] = intent_result

        if not intent_result["allowed"]:
            return ScanResult(
                allowed=False,
                stage="intent_blocked",
                reasons=list(intent_result["reasons"]),
                details=base_details,
            )

        return ScanResult(
            allowed=True,
            stage="intent_ready",
            reasons=list(intent_result["reasons"]),
            details=base_details,
        )

    def _build_intent(
        self,
        *,
        candidate: Any,
        evaluation_result: SetupEvaluationResult,
        instrument: str,
        request: ScanRequest,
        selected_level: Level,
    ) -> Dict[str, Any]:
        if self.order_intent_builder is None:
            return {
                "allowed": False,
                "reasons": ["order_intent_builder_missing"],
                "details": {"instrument": instrument},
                "intent": None,
            }

        build_result = self.order_intent_builder.build(
            candidate=candidate,
            evaluation=evaluation_result,
            ttl_minutes=60,
            correlation_id=f"scan-{instrument.lower()}-{selected_level.level_id}",
            notes={
                "source": "scan_once",
                "session": request.session,
                "post_news": request.post_news,
                "selected_level_id": selected_level.level_id,
            },
            minimum_trade_score=self.minimum_trade_score,
        )

        return {
            "allowed": bool(build_result.allowed),
            "reasons": list(build_result.reasons),
            "details": dict(build_result.details),
            "intent": build_result.intent.to_dict() if build_result.intent is not None else None,
        }

    def _base_details(
        self,
        *,
        instrument: str,
        request: ScanRequest,
        atr: Dict[str, Any],
        levels: Dict[str, list[Any]],
        regime: Any,
        h1_count: int,
        m15_count: int,
    ) -> Dict[str, Any]:
        return {
            "instrument": instrument,
            "session": request.session,
            "post_news": request.post_news,
            "h1_count": h1_count,
            "m15_count": m15_count,
            "atr": atr,
            "levels": {
                "swing_count": len(levels.get("swing_levels", [])),
                "range_count": len(levels.get("range_levels", [])),
            },
            "regime": {
                "name": regime.regime,
                "confidence": regime.confidence,
                "details": regime.details,
            },
        }

    def _select_primary_level(self, *, levels: Dict[str, list[Any]], current_price: float) -> Level | None:
        all_levels = list(levels.get("swing_levels", [])) + list(levels.get("range_levels", []))
        if not all_levels:
            return None

        ranked = sorted(
            all_levels,
            key=lambda level: (
                abs(float(level.price) - float(current_price)),
                -float(level.confidence),
                -int(level.touches),
            ),
        )
        return ranked[0]

    def _find_recent_break_retest(
        self,
        *,
        level: Level,
        candles: Sequence[Candle],
        atr_value: float,
    ) -> Dict[str, Any]:
        if len(candles) < 3:
            invalid = self.break_retest_validator.validate(
                level=level,
                break_candle=candles[-1],
                retest_candle=None,
                atr_value=atr_value,
            )
            return {"result": invalid, "break_index": None, "retest_index": None}

        lookback_start = max(1, len(candles) - 16)
        fallback_result: BreakRetestResult | None = None
        fallback_break_index: int | None = None

        for break_index in range(len(candles) - 2, lookback_start - 1, -1):
            break_candle = candles[break_index]
            break_assessment = self.break_retest_validator.assess_break(
                level=level,
                candle=break_candle,
                atr_value=atr_value,
                spread_buffer=0.0,
            )
            if not break_assessment.valid:
                if fallback_result is None:
                    fallback_result = BreakRetestResult(
                        valid=False,
                        direction=break_assessment.direction,
                        reason=break_assessment.reason,
                        break_assessment=break_assessment,
                        retest_assessment=None,
                    )
                    fallback_break_index = break_index
                continue

            for retest_index in range(break_index + 1, len(candles)):
                retest_candle = candles[retest_index]
                result = self.break_retest_validator.validate(
                    level=level,
                    break_candle=break_candle,
                    retest_candle=retest_candle,
                    atr_value=atr_value,
                    spread_buffer=0.0,
                    bars_since_break=retest_index - break_index,
                )
                if result.valid:
                    return {
                        "result": result,
                        "break_index": break_index,
                        "retest_index": retest_index,
                    }

                if fallback_result is None or fallback_result.reason == "close_not_beyond_level":
                    fallback_result = result
                    fallback_break_index = break_index

        if fallback_result is None:
            fallback_result = self.break_retest_validator.validate(
                level=level,
                break_candle=candles[-2],
                retest_candle=candles[-1],
                atr_value=atr_value,
                spread_buffer=0.0,
                bars_since_break=1,
            )
            fallback_break_index = len(candles) - 2

        return {
            "result": fallback_result,
            "break_index": fallback_break_index,
            "retest_index": None,
        }

    def _classify_regime(self, *, h1_candles: list[MarketDataCandle], atr_value: float, post_news: bool) -> Any:
        recent = h1_candles[-20:] if len(h1_candles) >= 20 else h1_candles
        if not recent:
            return self.regime_classifier.classify(
                atr_ratio=0.0,
                trend_strength=0.0,
                range_tightness=0.0,
                post_news=post_news,
            )

        price_range = max(c.high for c in recent) - min(c.low for c in recent)
        latest_range = recent[-1].high - recent[-1].low
        price_move = abs(recent[-1].close - recent[0].close)

        atr_ratio = 0.0 if atr_value <= 0 else round(latest_range / atr_value, 4)
        trend_strength = 0.0 if atr_value <= 0 else round(min(1.0, price_move / max(atr_value * 4, 1e-9)), 4)
        range_tightness = 0.0 if price_range <= 0 else round(max(0.0, min(1.0, 1.0 - (price_range / max(atr_value * 8, 1e-9)))), 4)

        return self.regime_classifier.classify(
            atr_ratio=atr_ratio,
            trend_strength=trend_strength,
            range_tightness=range_tightness,
            post_news=post_news,
        )

    def _score_hint(
        self,
        *,
        level: Level,
        break_retest: BreakRetestResult,
        confirmation: ConfirmationResult,
        regime_name: str,
        regime_confidence: float,
    ) -> float:
        score = 52.0
        score += min(18.0, float(level.confidence) * 18.0)
        score += min(12.0, float(confirmation.confidence) * 12.0)
        score += min(8.0, float(regime_confidence) * 8.0)

        if break_retest.valid:
            score += 6.0
        if confirmation.confirmed:
            score += 4.0
        if regime_name in {"trend", "expansion_trend"}:
            score += 4.0
        if regime_name in {"mixed", "compression", "post_news_disorder"}:
            score -= 8.0

        return round(max(0.0, min(100.0, score)), 2)

    def _grade_from_score(self, score: float) -> str:
        if score >= 90:
            return "A++"
        if score >= 80:
            return "A+"
        if score >= 70:
            return "A"
        if score >= 60:
            return "B"
        return "C"

    def _assess_execution_quality(
        self,
        *,
        instrument: str,
        confirmation: ConfirmationResult,
    ) -> Any:
        adverse_risk = 0.20 if confirmation.confirmed else 0.55
        if instrument.endswith("_USD") and instrument.startswith("XAU"):
            spread_ratio = 0.95
            slippage_estimate = 0.08
        elif instrument.endswith("_USD") and instrument.startswith("NAS"):
            spread_ratio = 1.05
            slippage_estimate = 0.12
        else:
            spread_ratio = 0.70
            slippage_estimate = 0.03

        return self.execution_quality_assessor.assess(
            spread_ratio=spread_ratio,
            slippage_estimate=slippage_estimate,
            timing_delay_seconds=0.5,
            adverse_selection_risk=adverse_risk,
        )

    def _serialize_break_retest(self, result: BreakRetestResult) -> Dict[str, Any]:
        return {
            "valid": result.valid,
            "direction": result.direction,
            "reason": result.reason,
            "break_assessment": {
                "valid": result.break_assessment.valid,
                "direction": result.break_assessment.direction,
                "reason": result.break_assessment.reason,
                "close_price": result.break_assessment.close_price,
                "body_size": result.break_assessment.body_size,
                "atr": result.break_assessment.atr,
                "body_atr_ratio": result.break_assessment.body_atr_ratio,
                "counter_wick_ratio": result.break_assessment.counter_wick_ratio,
                "details": result.break_assessment.details,
            },
            "retest_assessment": None
            if result.retest_assessment is None
            else {
                "valid": result.retest_assessment.valid,
                "touched_zone": result.retest_assessment.touched_zone,
                "held_zone": result.retest_assessment.held_zone,
                "reason": result.retest_assessment.reason,
                "zone_low": result.retest_assessment.zone_low,
                "zone_high": result.retest_assessment.zone_high,
                "retest_price": result.retest_assessment.retest_price,
                "bars_since_break": result.retest_assessment.bars_since_break,
                "details": result.retest_assessment.details,
            },
            "details": result.details,
        }

    def _serialize_confirmation(self, result: ConfirmationResult) -> Dict[str, Any]:
        return {
            "confirmed": result.confirmed,
            "confirmation_type": result.confirmation_type,
            "confidence": result.confidence,
            "reasons": list(result.reasons),
            "details": dict(result.details),
        }

    def _serialize_execution_quality(self, result: Any) -> Dict[str, Any]:
        return {
            "quality": result.quality,
            "score": result.score,
            "allowed": result.allowed,
            "reasons": list(result.reasons),
            "details": dict(result.details),
        }

    def _serialize_evaluation(self, result: SetupEvaluationResult) -> Dict[str, Any]:
        return result.to_dict()
