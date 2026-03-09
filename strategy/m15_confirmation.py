from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(slots=True)
class M15Candle:
    open: float
    high: float
    low: float
    close: float
    ts_utc: str = ""

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return max(0.0, self.high - self.low)

    @property
    def bullish(self) -> bool:
        return self.close > self.open

    @property
    def bearish(self) -> bool:
        return self.close < self.open


@dataclass(slots=True)
class ConfirmationResult:
    confirmed: bool
    confirmation_type: str
    confidence: float
    reasons: list[str]
    details: dict


class M15ConfirmationValidator:
    def detect_market_structure_shift(self, candles: Sequence[M15Candle], side: str) -> tuple[bool, dict]:
        if len(candles) < 3:
            return False, {"reason": "insufficient_candles"}

        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        if side == "long":
            shifted = c3.close > c2.high and c3.low >= c1.low
            return shifted, {
                "last_close": c3.close,
                "previous_high": c2.high,
                "anchor_low": c1.low,
            }
        if side == "short":
            shifted = c3.close < c2.low and c3.high <= c1.high
            return shifted, {
                "last_close": c3.close,
                "previous_low": c2.low,
                "anchor_high": c1.high,
            }
        raise ValueError(f"Unsupported side: {side}")

    def detect_rejection_candle(self, candle: M15Candle, side: str) -> tuple[bool, dict]:
        if candle.range <= 0:
            return False, {"reason": "zero_range"}

        upper_wick = candle.high - max(candle.open, candle.close)
        lower_wick = min(candle.open, candle.close) - candle.low
        body_ratio = candle.body / candle.range if candle.range else 0.0

        if side == "long":
            ok = lower_wick >= candle.body and candle.bullish and body_ratio >= 0.2
            return ok, {
                "lower_wick": round(lower_wick, 6),
                "upper_wick": round(upper_wick, 6),
                "body_ratio": round(body_ratio, 4),
            }
        if side == "short":
            ok = upper_wick >= candle.body and candle.bearish and body_ratio >= 0.2
            return ok, {
                "upper_wick": round(upper_wick, 6),
                "lower_wick": round(lower_wick, 6),
                "body_ratio": round(body_ratio, 4),
            }
        raise ValueError(f"Unsupported side: {side}")

    def detect_engulfing(self, previous: M15Candle, current: M15Candle, side: str) -> tuple[bool, dict]:
        if side == "long":
            ok = previous.bearish and current.bullish and current.close >= previous.open and current.open <= previous.close
            return ok, {
                "previous_bearish": previous.bearish,
                "current_bullish": current.bullish,
            }
        if side == "short":
            ok = previous.bullish and current.bearish and current.close <= previous.open and current.open >= previous.close
            return ok, {
                "previous_bullish": previous.bullish,
                "current_bearish": current.bearish,
            }
        raise ValueError(f"Unsupported side: {side}")

    def validate(self, candles: Sequence[M15Candle], side: str) -> ConfirmationResult:
        if len(candles) < 3:
            return ConfirmationResult(False, "none", 0.0, ["insufficient_confirmation_data"], {})

        reasons: list[str] = []
        details: dict = {}

        mss_ok, mss_details = self.detect_market_structure_shift(candles, side)
        details["market_structure_shift"] = mss_details
        if mss_ok:
            reasons.append("market_structure_shift")

        rejection_ok, rejection_details = self.detect_rejection_candle(candles[-1], side)
        details["rejection_candle"] = rejection_details
        if rejection_ok:
            reasons.append("rejection_candle")

        engulf_ok, engulf_details = self.detect_engulfing(candles[-2], candles[-1], side)
        details["engulfing"] = engulf_details
        if engulf_ok:
            reasons.append("engulfing_confirmation")

        confirmed = mss_ok and (rejection_ok or engulf_ok)
        confidence = 0.0
        if mss_ok:
            confidence += 0.5
        if rejection_ok:
            confidence += 0.25
        if engulf_ok:
            confidence += 0.25
        confidence = round(min(1.0, confidence), 4)

        confirmation_type = "none"
        if confirmed and rejection_ok and engulf_ok:
            confirmation_type = "mss_plus_rejection_plus_engulfing"
        elif confirmed and rejection_ok:
            confirmation_type = "mss_plus_rejection"
        elif confirmed and engulf_ok:
            confirmation_type = "mss_plus_engulfing"

        if not reasons:
            reasons.append("no_confirmation")

        return ConfirmationResult(confirmed, confirmation_type, confidence, reasons, details)
