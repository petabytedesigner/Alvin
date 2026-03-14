from __future__ import annotations

from typing import Any, Dict

from analytics.atr import ATRCalculator
from analytics.candle_mapping import CandleMapper
from data.candle_cache import CandleCache
from market_data.contracts import Timeframe
from runtime.scan_models import ScanRequest, ScanResult
from strategy.break_retest_validator import BreakRetestValidator
from strategy.level_detection import LevelDetector
from intelligence.regime_classifier import RegimeClassifier
from market_data.oanda_market_data import OandaMarketData


class Scanner:
    """
    Foundational scanner for Alvin.

    Current scope:
    - fetch H1 / M15 market data
    - compute H1 ATR
    - map candles into strategy formats
    - detect H1 levels
    - classify a market regime snapshot

    This is a market-context scanner foundation, not yet the final
    end-to-end trade decision engine.
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
    ) -> None:
        self.market_data = market_data
        self.atr_calculator = atr_calculator
        self.candle_mapper = candle_mapper
        self.candle_cache = candle_cache
        self.level_detector = level_detector
        self.break_retest_validator = break_retest_validator
        self.regime_classifier = regime_classifier

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

        levels = self.level_detector.detect_levels(h1_level_candles, atr_value=atr.value)
        regime = self._classify_regime(
            h1_batch_count=len(h1_batch.candles),
            h1_candles=h1_batch.candles,
            atr_value=atr.value,
            post_news=request.post_news,
        )

        primary_level = self._select_primary_level(levels)

        return ScanResult(
            allowed=True,
            stage="market_context_ready",
            reasons=["scan_context_built"],
            details={
                "instrument": instrument,
                "session": request.session,
                "h1_count": len(h1_batch.candles),
                "m15_count": len(m15_batch.candles),
                "atr": atr.to_dict(),
                "levels": {
                    "swing_count": len(levels.get("swing_levels", [])),
                    "range_count": len(levels.get("range_levels", [])),
                    "primary_level": primary_level,
                },
                "regime": {
                    "name": regime.regime,
                    "confidence": regime.confidence,
                    "details": regime.details,
                },
                "cache_keys": [
                    f"{instrument}::{Timeframe.H1}",
                    f"{instrument}::{Timeframe.M15}",
                ],
            },
        )

    def _select_primary_level(self, levels: Dict[str, list[Any]]) -> Dict[str, Any] | None:
        swing_levels = levels.get("swing_levels", [])
        range_levels = levels.get("range_levels", [])

        candidate = None
        if swing_levels:
            candidate = swing_levels[0]
        elif range_levels:
            candidate = range_levels[0]

        if candidate is None:
            return None

        if hasattr(candidate, "to_dict"):
            return candidate.to_dict()
        return {
            "level_id": getattr(candidate, "level_id", None),
            "kind": getattr(candidate, "kind", None),
            "price": getattr(candidate, "price", None),
            "confidence": getattr(candidate, "confidence", None),
        }

    def _classify_regime(self, *, h1_batch_count: int, h1_candles: list[Any], atr_value: float, post_news: bool) -> Any:
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
