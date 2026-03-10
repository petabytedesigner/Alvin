from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from strategy.level_detection import Candle, Level


@dataclass(slots=True)
class BreakAssessment:
    valid: bool
    direction: str
    reason: str
    close_price: float
    body_size: float
    atr: float
    body_atr_ratio: float
    counter_wick_ratio: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RetestAssessment:
    valid: bool
    touched_zone: bool
    held_zone: bool
    reason: str
    zone_low: float
    zone_high: float
    retest_price: float
    bars_since_break: int
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BreakRetestResult:
    valid: bool
    direction: str
    reason: str
    break_assessment: BreakAssessment
    retest_assessment: Optional[RetestAssessment]
    details: Dict[str, Any] = field(default_factory=dict)


class BreakRetestValidator:
    def __init__(
        self,
        *,
        min_body_atr_ratio: float = 0.60,
        max_counter_wick_ratio: float = 0.40,
        base_retest_zone_atr_ratio: float = 0.20,
        min_retest_bars: int = 1,
        max_retest_bars: int = 10,
        config: Mapping[str, Any] | None = None,
    ) -> None:
        cfg = self._resolve_config(config)
        self.min_body_atr_ratio = float(cfg.get("min_body_atr_ratio", min_body_atr_ratio))
        self.max_counter_wick_ratio = float(cfg.get("max_counter_wick_ratio", max_counter_wick_ratio))
        self.base_retest_zone_atr_ratio = float(cfg.get("base_retest_zone_atr_ratio", base_retest_zone_atr_ratio))
        self.min_retest_bars = int(cfg.get("min_retest_bars", min_retest_bars))
        self.max_retest_bars = int(cfg.get("max_retest_bars", max_retest_bars))

    @classmethod
    def from_config(cls, strategy_config: Mapping[str, Any]) -> "BreakRetestValidator":
        return cls(config=strategy_config.get("break_retest", {}))

    def _resolve_config(self, config: Mapping[str, Any] | None) -> Mapping[str, Any]:
        if config is None:
            return {}
        if not isinstance(config, Mapping):
            raise ValueError("break_retest config must be a mapping")
        return config

    def assess_break(
        self,
        *,
        level: Level,
        candle: Candle,
        atr_value: float,
        spread_buffer: float = 0.0,
    ) -> BreakAssessment:
        if atr_value <= 0:
            return BreakAssessment(
                valid=False,
                direction="none",
                reason="invalid_atr",
                close_price=candle.close,
                body_size=0.0,
                atr=atr_value,
                body_atr_ratio=0.0,
                counter_wick_ratio=1.0,
            )

        bullish_break = candle.close > level.price + spread_buffer
        bearish_break = candle.close < level.price - spread_buffer

        if not bullish_break and not bearish_break:
            return BreakAssessment(
                valid=False,
                direction="none",
                reason="close_not_beyond_level",
                close_price=candle.close,
                body_size=abs(candle.close - candle.open),
                atr=atr_value,
                body_atr_ratio=abs(candle.close - candle.open) / atr_value,
                counter_wick_ratio=1.0,
                details={"level_price": level.price, "spread_buffer": spread_buffer},
            )

        direction = "long" if bullish_break else "short"
        body_size = abs(candle.close - candle.open)
        body_atr_ratio = body_size / atr_value

        if direction == "long":
            counter_wick = max(0.0, min(candle.open, candle.close) - candle.low)
        else:
            counter_wick = max(0.0, candle.high - max(candle.open, candle.close))

        counter_wick_ratio = 0.0 if body_size == 0 else counter_wick / body_size

        if body_atr_ratio < self.min_body_atr_ratio:
            return BreakAssessment(
                valid=False,
                direction=direction,
                reason="body_too_small_vs_atr",
                close_price=candle.close,
                body_size=body_size,
                atr=atr_value,
                body_atr_ratio=body_atr_ratio,
                counter_wick_ratio=counter_wick_ratio,
                details={"required_min_ratio": self.min_body_atr_ratio},
            )

        if counter_wick_ratio > self.max_counter_wick_ratio:
            return BreakAssessment(
                valid=False,
                direction=direction,
                reason="counter_wick_too_large",
                close_price=candle.close,
                body_size=body_size,
                atr=atr_value,
                body_atr_ratio=body_atr_ratio,
                counter_wick_ratio=counter_wick_ratio,
                details={"allowed_max_ratio": self.max_counter_wick_ratio},
            )

        return BreakAssessment(
            valid=True,
            direction=direction,
            reason="valid_break",
            close_price=candle.close,
            body_size=body_size,
            atr=atr_value,
            body_atr_ratio=round(body_atr_ratio, 6),
            counter_wick_ratio=round(counter_wick_ratio, 6),
            details={"level_price": level.price, "spread_buffer": spread_buffer},
        )

    def assess_retest(
        self,
        *,
        level: Level,
        direction: str,
        retest_candle: Candle,
        atr_value: float,
        spread_buffer: float = 0.0,
        bars_since_break: int = 1,
    ) -> RetestAssessment:
        zone_padding = (atr_value * self.base_retest_zone_atr_ratio) + spread_buffer
        zone_low = level.price - zone_padding
        zone_high = level.price + zone_padding

        touched_zone = retest_candle.low <= zone_high and retest_candle.high >= zone_low
        if not touched_zone:
            return RetestAssessment(
                valid=False,
                touched_zone=False,
                held_zone=False,
                reason="retest_missed_zone",
                zone_low=zone_low,
                zone_high=zone_high,
                retest_price=retest_candle.close,
                bars_since_break=bars_since_break,
            )

        if bars_since_break < self.min_retest_bars:
            return RetestAssessment(
                valid=False,
                touched_zone=True,
                held_zone=False,
                reason="retest_too_early",
                zone_low=zone_low,
                zone_high=zone_high,
                retest_price=retest_candle.close,
                bars_since_break=bars_since_break,
                details={"min_retest_bars": self.min_retest_bars},
            )

        if bars_since_break > self.max_retest_bars:
            return RetestAssessment(
                valid=False,
                touched_zone=True,
                held_zone=False,
                reason="retest_too_late",
                zone_low=zone_low,
                zone_high=zone_high,
                retest_price=retest_candle.close,
                bars_since_break=bars_since_break,
                details={"max_retest_bars": self.max_retest_bars},
            )

        if direction == "long":
            held_zone = retest_candle.close >= zone_low
        else:
            held_zone = retest_candle.close <= zone_high

        if not held_zone:
            return RetestAssessment(
                valid=False,
                touched_zone=True,
                held_zone=False,
                reason="retest_failed_to_hold_zone",
                zone_low=zone_low,
                zone_high=zone_high,
                retest_price=retest_candle.close,
                bars_since_break=bars_since_break,
            )

        return RetestAssessment(
            valid=True,
            touched_zone=True,
            held_zone=True,
            reason="valid_retest",
            zone_low=round(zone_low, 6),
            zone_high=round(zone_high, 6),
            retest_price=retest_candle.close,
            bars_since_break=bars_since_break,
            details={"level_price": level.price, "spread_buffer": spread_buffer},
        )

    def validate(
        self,
        *,
        level: Level,
        break_candle: Candle,
        retest_candle: Optional[Candle],
        atr_value: float,
        spread_buffer: float = 0.0,
        bars_since_break: int = 1,
    ) -> BreakRetestResult:
        break_assessment = self.assess_break(
            level=level,
            candle=break_candle,
            atr_value=atr_value,
            spread_buffer=spread_buffer,
        )
        if not break_assessment.valid:
            return BreakRetestResult(
                valid=False,
                direction=break_assessment.direction,
                reason=break_assessment.reason,
                break_assessment=break_assessment,
                retest_assessment=None,
            )

        if retest_candle is None:
            return BreakRetestResult(
                valid=False,
                direction=break_assessment.direction,
                reason="missing_retest_candle",
                break_assessment=break_assessment,
                retest_assessment=None,
            )

        retest_assessment = self.assess_retest(
            level=level,
            direction=break_assessment.direction,
            retest_candle=retest_candle,
            atr_value=atr_value,
            spread_buffer=spread_buffer,
            bars_since_break=bars_since_break,
        )
        if not retest_assessment.valid:
            return BreakRetestResult(
                valid=False,
                direction=break_assessment.direction,
                reason=retest_assessment.reason,
                break_assessment=break_assessment,
                retest_assessment=retest_assessment,
            )

        return BreakRetestResult(
            valid=True,
            direction=break_assessment.direction,
            reason="valid_break_retest",
            break_assessment=break_assessment,
            retest_assessment=retest_assessment,
            details={
                "level_kind": level.kind,
                "level_price": level.price,
                "atr_value": atr_value,
                "bars_since_break": bars_since_break,
            },
        )
