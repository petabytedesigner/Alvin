from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


CONFIG_FILES = [
    "global.json",
    "features.json",
    "risk.json",
    "scoring.json",
    "instruments.json",
    "strategy.json",
    "regime.json",
    "execution.json",
    "market_data.json",
    "scanner.json",
]


class ConfigValidationError(ValueError):
    pass


def load_all_configs(config_dir: str = "config") -> Dict[str, Any]:
    base = Path(config_dir)
    if not base.exists():
        raise FileNotFoundError(f"Missing config directory: {config_dir}")

    loaded: Dict[str, Any] = {}
    for name in CONFIG_FILES:
        path = base / name
        if not path.exists():
            raise FileNotFoundError(f"Missing config file: {path}")
        loaded[path.stem] = json.loads(path.read_text(encoding="utf-8"))

    _validate_configs(loaded)
    return loaded


def _validate_configs(config: Dict[str, Any]) -> None:
    for section in (
        "global",
        "features",
        "risk",
        "scoring",
        "instruments",
        "strategy",
        "regime",
        "execution",
        "market_data",
        "scanner",
    ):
        if section not in config:
            raise ConfigValidationError(f"Missing config section: {section}")
        if not isinstance(config[section], dict):
            raise ConfigValidationError(f"Config section must be an object: {section}")

    _validate_global(config["global"])
    _validate_features(config["features"])
    _validate_risk(config["risk"])
    _validate_scoring(config["scoring"])
    _validate_instruments(config["instruments"])
    _validate_strategy(config["strategy"])
    _validate_regime(config["regime"])
    _validate_execution(config["execution"])
    _validate_market_data(config["market_data"])
    _validate_scanner(config["scanner"])


def _require_keys(section_name: str, data: Dict[str, Any], keys: list[str]) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise ConfigValidationError(f"Missing keys in {section_name}: {', '.join(missing)}")


def _validate_global(data: Dict[str, Any]) -> None:
    _require_keys(
        "global",
        data,
        ["project_name", "environment", "timezone", "trading_day_anchor", "log_level", "db_path"],
    )
    if not isinstance(data["project_name"], str) or not data["project_name"].strip():
        raise ConfigValidationError("global.project_name must be a non-empty string")
    if data["environment"] not in {"practice", "live", "dev", "test"}:
        raise ConfigValidationError("global.environment must be one of: practice, live, dev, test")
    if not isinstance(data["timezone"], str) or not data["timezone"].strip():
        raise ConfigValidationError("global.timezone must be a non-empty string")
    if not isinstance(data["trading_day_anchor"], str) or " " not in data["trading_day_anchor"]:
        raise ConfigValidationError("global.trading_day_anchor must look like 'HH:MM Zone'")
    if not isinstance(data["log_level"], str) or not data["log_level"].strip():
        raise ConfigValidationError("global.log_level must be a non-empty string")
    if not isinstance(data["db_path"], str) or not data["db_path"].strip():
        raise ConfigValidationError("global.db_path must be a non-empty string")


def _validate_features(data: Dict[str, Any]) -> None:
    _require_keys(
        "features",
        data,
        [
            "broker_connectivity_required",
            "journal_enabled",
            "bootstrap_writes_snapshot",
            "doctor_checks_broker",
            "scan_once_enabled",
            "market_data_cache_enabled",
        ],
    )
    for key, value in data.items():
        if not isinstance(value, bool):
            raise ConfigValidationError(f"features.{key} must be boolean")


def _validate_risk(data: Dict[str, Any]) -> None:
    _require_keys(
        "risk",
        data,
        [
            "daily_loss_limit_pct",
            "max_open_risk_pct",
            "max_concurrent_trades",
            "kill_switch_drawdown_pct",
            "loss_streak_reduction_pct",
            "loss_streak_pause_after",
            "grade_risk_pct",
        ],
    )

    float_keys = [
        "daily_loss_limit_pct",
        "max_open_risk_pct",
        "kill_switch_drawdown_pct",
        "loss_streak_reduction_pct",
    ]
    for key in float_keys:
        value = data[key]
        if not isinstance(value, (int, float)) or value < 0:
            raise ConfigValidationError(f"risk.{key} must be a non-negative number")

    int_keys = ["max_concurrent_trades", "loss_streak_pause_after"]
    for key in int_keys:
        value = data[key]
        if not isinstance(value, int) or value < 0:
            raise ConfigValidationError(f"risk.{key} must be a non-negative integer")

    if data["max_concurrent_trades"] == 0:
        raise ConfigValidationError("risk.max_concurrent_trades must be > 0")

    grade_risk = data["grade_risk_pct"]
    if not isinstance(grade_risk, dict) or not grade_risk:
        raise ConfigValidationError("risk.grade_risk_pct must be a non-empty object")

    required_grades = {"A++", "A+", "A", "B", "C"}
    missing = sorted(required_grades - set(grade_risk.keys()))
    if missing:
        raise ConfigValidationError(f"risk.grade_risk_pct missing required grades: {', '.join(missing)}")

    for grade, value in grade_risk.items():
        if not isinstance(value, (int, float)) or value < 0:
            raise ConfigValidationError(f"risk.grade_risk_pct.{grade} must be a non-negative number")

    ordered = [grade_risk["A++"], grade_risk["A+"], grade_risk["A"], grade_risk["B"], grade_risk["C"]]
    if ordered != sorted(ordered, reverse=True):
        raise ConfigValidationError("risk grade risk bands must descend from A++ to C")


def _validate_scoring(data: Dict[str, Any]) -> None:
    _require_keys("scoring", data, ["score_scale_max", "minimum_trade_score", "grades", "no_trade_grade", "weights"])

    if not isinstance(data["score_scale_max"], (int, float)) or data["score_scale_max"] <= 0:
        raise ConfigValidationError("scoring.score_scale_max must be > 0")
    if not isinstance(data["minimum_trade_score"], (int, float)) or data["minimum_trade_score"] < 0:
        raise ConfigValidationError("scoring.minimum_trade_score must be >= 0")

    grades = data["grades"]
    if not isinstance(grades, dict) or not grades:
        raise ConfigValidationError("scoring.grades must be a non-empty object")

    required_grades = {"A++", "A+", "A", "B", "C"}
    missing = sorted(required_grades - set(grades.keys()))
    if missing:
        raise ConfigValidationError(f"scoring.grades missing required grades: {', '.join(missing)}")

    for grade, value in grades.items():
        if not isinstance(value, (int, float)) or value < 0:
            raise ConfigValidationError(f"scoring.grades.{grade} must be a non-negative number")

    ordered = [grades["A++"], grades["A+"], grades["A"], grades["B"], grades["C"]]
    if ordered != sorted(ordered, reverse=True):
        raise ConfigValidationError("scoring grade thresholds must descend from A++ to C")

    no_trade_grade = data["no_trade_grade"]
    if no_trade_grade not in grades:
        raise ConfigValidationError("scoring.no_trade_grade must exist in scoring.grades")

    weights = data["weights"]
    if not isinstance(weights, dict) or not weights:
        raise ConfigValidationError("scoring.weights must be a non-empty object")
    total_weight = 0.0
    for key, value in weights.items():
        if not isinstance(value, (int, float)) or value < 0:
            raise ConfigValidationError(f"scoring.weights.{key} must be a non-negative number")
        total_weight += float(value)
    if round(total_weight, 6) != round(float(data["score_scale_max"]), 6):
        raise ConfigValidationError("sum of scoring.weights must equal scoring.score_scale_max")


def _validate_instruments(data: Dict[str, Any]) -> None:
    _require_keys("instruments", data, ["fx_majors", "metals", "crypto", "indices"])

    all_symbols: list[str] = []
    for key in ("fx_majors", "metals", "crypto", "indices"):
        value = data[key]
        if not isinstance(value, list):
            raise ConfigValidationError(f"instruments.{key} must be a list")
        for symbol in value:
            if not isinstance(symbol, str) or not symbol.strip():
                raise ConfigValidationError(f"instruments.{key} contains an invalid symbol")
            all_symbols.append(symbol.strip())

    if len(set(all_symbols)) != len(all_symbols):
        raise ConfigValidationError("instruments contains duplicate symbols across groups")

    if "scan_default_instrument" in data:
        value = data["scan_default_instrument"]
        if not isinstance(value, str) or not value.strip():
            raise ConfigValidationError("instruments.scan_default_instrument must be a non-empty string")

    if "scan_timeframes" in data:
        value = data["scan_timeframes"]
        if not isinstance(value, list) or not value:
            raise ConfigValidationError("instruments.scan_timeframes must be a non-empty list")


def _validate_strategy(data: Dict[str, Any]) -> None:
    _require_keys("strategy", data, ["level_detection", "break_retest"])
    level_detection = data["level_detection"]
    break_retest = data["break_retest"]

    if not isinstance(level_detection, dict):
        raise ConfigValidationError("strategy.level_detection must be an object")
    if not isinstance(break_retest, dict):
        raise ConfigValidationError("strategy.break_retest must be an object")

    _require_keys(
        "strategy.level_detection",
        level_detection,
        [
            "fractal_window",
            "min_swing_touches",
            "min_swing_spacing",
            "min_range_candles",
            "range_width_atr_multiple",
            "touch_tolerance_atr_multiple",
        ],
    )
    _require_keys(
        "strategy.break_retest",
        break_retest,
        [
            "min_body_atr_ratio",
            "max_counter_wick_ratio",
            "base_retest_zone_atr_ratio",
            "min_retest_bars",
            "max_retest_bars",
        ],
    )

    for key in ("fractal_window", "min_swing_touches", "min_swing_spacing", "min_range_candles"):
        value = level_detection[key]
        if not isinstance(value, int) or value < 1:
            raise ConfigValidationError(f"strategy.level_detection.{key} must be an integer >= 1")

    for key in ("range_width_atr_multiple", "touch_tolerance_atr_multiple"):
        value = level_detection[key]
        if not isinstance(value, (int, float)) or value <= 0:
            raise ConfigValidationError(f"strategy.level_detection.{key} must be > 0")

    for key in ("min_body_atr_ratio", "max_counter_wick_ratio", "base_retest_zone_atr_ratio"):
        value = break_retest[key]
        if not isinstance(value, (int, float)) or value < 0:
            raise ConfigValidationError(f"strategy.break_retest.{key} must be >= 0")

    for key in ("min_retest_bars", "max_retest_bars"):
        value = break_retest[key]
        if not isinstance(value, int) or value < 1:
            raise ConfigValidationError(f"strategy.break_retest.{key} must be an integer >= 1")

    if break_retest["max_retest_bars"] < break_retest["min_retest_bars"]:
        raise ConfigValidationError("strategy.break_retest.max_retest_bars must be >= min_retest_bars")

    if "atr_period" in data:
        value = data["atr_period"]
        if not isinstance(value, int) or value < 2:
            raise ConfigValidationError("strategy.atr_period must be an integer >= 2")


def _validate_regime(data: Dict[str, Any]) -> None:
    _require_keys("regime", data, ["thresholds", "labels"])
    thresholds = data["thresholds"]
    labels = data["labels"]

    if not isinstance(thresholds, dict):
        raise ConfigValidationError("regime.thresholds must be an object")
    if not isinstance(labels, dict):
        raise ConfigValidationError("regime.labels must be an object")

    _require_keys(
        "regime.thresholds",
        thresholds,
        [
            "expansion_atr_ratio",
            "trend_strength_min",
            "compression_range_tightness",
            "compression_atr_ratio_max",
            "range_tightness_min",
        ],
    )

    for key, value in thresholds.items():
        if not isinstance(value, (int, float)) or value < 0:
            raise ConfigValidationError(f"regime.thresholds.{key} must be a non-negative number")

    required_labels = {
        "post_news_disorder",
        "expansion_trend",
        "compression",
        "trend",
        "range",
        "mixed",
    }
    missing = sorted(required_labels - set(labels.keys()))
    if missing:
        raise ConfigValidationError(f"regime.labels missing required labels: {', '.join(missing)}")

    for key, value in labels.items():
        if not isinstance(value, str) or not value.strip():
            raise ConfigValidationError(f"regime.labels.{key} must be a non-empty string")


def _validate_execution(data: Dict[str, Any]) -> None:
    _require_keys(
        "execution",
        data,
        [
            "spread_ratio_warn",
            "slippage_warn",
            "timing_delay_warn_seconds",
            "adverse_selection_warn",
            "score_floor",
            "quality_bands",
        ],
    )

    for key in ("spread_ratio_warn", "slippage_warn", "timing_delay_warn_seconds", "adverse_selection_warn", "score_floor"):
        value = data[key]
        if not isinstance(value, (int, float)) or value < 0:
            raise ConfigValidationError(f"execution.{key} must be a non-negative number")

    bands = data["quality_bands"]
    if not isinstance(bands, dict):
        raise ConfigValidationError("execution.quality_bands must be an object")

    _require_keys("execution.quality_bands", bands, ["clean", "acceptable", "fragile"])
    for key in ("clean", "acceptable", "fragile"):
        value = bands[key]
        if not isinstance(value, (int, float)) or value < 0 or value > 1:
            raise ConfigValidationError(f"execution.quality_bands.{key} must be between 0 and 1")

    if not (bands["clean"] >= bands["acceptable"] >= bands["fragile"] >= data["score_floor"]):
        raise ConfigValidationError("execution quality bands must descend clean >= acceptable >= fragile >= score_floor")


def _validate_market_data(data: Dict[str, Any]) -> None:
    _require_keys(
        "market_data",
        data,
        ["default_h1_count", "default_m15_count", "request_timeout_seconds", "price_component"],
    )
    for key in ("default_h1_count", "default_m15_count", "request_timeout_seconds"):
        value = data[key]
        if not isinstance(value, int) or value < 1:
            raise ConfigValidationError(f"market_data.{key} must be an integer >= 1")
    if not isinstance(data["price_component"], str) or not data["price_component"].strip():
        raise ConfigValidationError("market_data.price_component must be a non-empty string")


def _validate_scanner(data: Dict[str, Any]) -> None:
    _require_keys(
        "scanner",
        data,
        ["default_instrument", "default_session", "allow_post_news_scan", "scan_once_timeout_seconds"],
    )
    if not isinstance(data["default_instrument"], str) or not data["default_instrument"].strip():
        raise ConfigValidationError("scanner.default_instrument must be a non-empty string")
    if not isinstance(data["default_session"], str) or not data["default_session"].strip():
        raise ConfigValidationError("scanner.default_session must be a non-empty string")
    if not isinstance(data["allow_post_news_scan"], bool):
        raise ConfigValidationError("scanner.allow_post_news_scan must be boolean")
    if not isinstance(data["scan_once_timeout_seconds"], int) or data["scan_once_timeout_seconds"] < 1:
        raise ConfigValidationError("scanner.scan_once_timeout_seconds must be an integer >= 1")
