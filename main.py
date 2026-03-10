from __future__ import annotations

import argparse
import json
from pathlib import Path

from broker.oanda_client import OandaClient
from core.events import Event, utc_now_iso
from monitoring.journal import Journal
from runtime.component_factory import build_alvin_components
from storage.database import Database
from utils.config_loader import load_all_configs


def build_db(config: dict) -> Database:
    db_path = config["global"]["db_path"]
    db = Database(db_path)
    db.apply_schema("storage/schema.sql")
    return db


def _feature_enabled(config: dict, name: str, default: bool = False) -> bool:
    return bool(config.get("features", {}).get(name, default))


def _journal_if_enabled(config: dict, db: Database) -> Journal | None:
    if _feature_enabled(config, "journal_enabled", True):
        return Journal(db)
    return None


def cmd_bootstrap() -> None:
    config = load_all_configs()
    db = build_db(config)
    journal = _journal_if_enabled(config, db)

    snapshot_hash = None
    if _feature_enabled(config, "bootstrap_writes_snapshot", True):
        snapshot_hash = db.snapshot_config(utc_now_iso(), config)

    event = Event(
        event_type="BOOT",
        module="main",
        payload={"config_sha256": snapshot_hash},
    )
    db.insert_event(event.to_record())

    if journal is not None:
        journal.info(
            "Bootstrap completed",
            {
                "config_sha256": snapshot_hash,
                "snapshot_written": snapshot_hash is not None,
            },
        )

    print("bootstrap: ok")
    db.close()


def cmd_doctor() -> None:
    config = load_all_configs()
    db = build_db(config)
    journal = _journal_if_enabled(config, db)
    broker = OandaClient()
    components = build_alvin_components(config)

    broker_connectivity_required = _feature_enabled(config, "broker_connectivity_required", True)
    doctor_checks_broker = _feature_enabled(config, "doctor_checks_broker", False)
    should_check_broker = broker_connectivity_required or doctor_checks_broker

    checks = {
        "config_loaded": True,
        "db_ready": True,
        "runtime_components_ready": True,
        "pipeline_runner_ready": True,
        "broker_connectivity_required": broker_connectivity_required,
        "oanda_env_configured": broker.is_configured() if should_check_broker else None,
        "broker_check_skipped": not should_check_broker,
        "config_driven_components": {
            "level_detector": type(components.level_detector).__name__,
            "break_retest_validator": type(components.break_retest_validator).__name__,
            "regime_classifier": type(components.regime_classifier).__name__,
            "execution_quality_assessor": type(components.execution_quality_assessor).__name__,
            "risk_gate": type(components.risk_gate).__name__,
            "pipeline_runner": type(components.pipeline_runner).__name__,
        },
    }

    if journal is not None:
        journal.info("Doctor check completed", checks)

    print(json.dumps(checks, indent=2))
    db.close()


def cmd_show_config() -> None:
    config = load_all_configs()
    print(json.dumps(config, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="alvin")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("bootstrap")
    sub.add_parser("doctor")
    sub.add_parser("show-config")

    args = parser.parse_args()

    Path("runtime").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)

    if args.command == "bootstrap":
        cmd_bootstrap()
    elif args.command == "doctor":
        cmd_doctor()
    elif args.command == "show-config":
        cmd_show_config()


if __name__ == "__main__":
    main()
