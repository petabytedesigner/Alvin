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
    for section in ("global", "features", "risk", "scoring", "instruments"):
        if section not in config:
            raise ConfigValidationError(f"Missing config section: {section}")
        if not isinstance(config[section], dict):
            raise ConfigValidationError(f"Config section must be an object: {section}")

    _validate_global(config["global"])
    _validate_features(config["features"])
    _validate_risk(config["risk"])
    _validate_scoring(config["scoring"])
    _validate_instruments(config["instruments"])


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


def _validate_scoring(data: Dict[str, Any]) -> None:
    _require_keys("scoring", data, ["grades", "no_trade_grade"])
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

    no_trade_grade = data["no_trade_grade"]
    if no_trade_grade not in grades:
        raise ConfigValidationError("scoring.no_trade_grade must exist in scoring.grades")


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
