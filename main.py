from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from broker.oanda_client import OandaClient
from broker.order_executor import OrderExecutionResult
from core.events import Event, utc_now_iso
from intelligence.execution_quality import ExecutionQualityResult
from intelligence.regime_classifier import RegimeAssessment
from monitoring.journal import Journal
from runtime.component_factory import build_alvin_components
from runtime.scan_models import ScanRequest
from storage.database import Database
from strategy.break_retest_validator import BreakAssessment, BreakRetestResult, RetestAssessment
from strategy.level_detection import Level
from strategy.m15_confirmation import ConfirmationResult
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


def _scan_cli_summary(request: ScanRequest, result) -> dict:
    result_summary = result.summary()
    return {
        "instrument": request.instrument,
        "session": request.session,
        "post_news": request.post_news,
        "status": result_summary.get("status"),
        "stage": result_summary.get("stage"),
        "stage_group": result_summary.get("stage_group"),
        "primary_reason": result_summary.get("primary_reason"),
        "regime_name": result_summary.get("regime_name"),
        "selected_level_kind": result_summary.get("selected_level_kind"),
        "selected_level_price": result_summary.get("selected_level_price"),
        "break_retest_direction": result_summary.get("break_retest_direction"),
        "confirmation_type": result_summary.get("confirmation_type"),
        "candidate_id": result_summary.get("candidate_id"),
        "candidate_side": result_summary.get("candidate_side"),
        "candidate_grade": result_summary.get("candidate_grade"),
        "score_value": result_summary.get("score_value"),
        "evaluation_state": result_summary.get("evaluation_state"),
        "risk_pct": result_summary.get("risk_pct"),
        "execution_quality": result_summary.get("execution_quality"),
    }


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
    broker_env_configured = broker.is_configured() if should_check_broker else None

    checks = {
        "config_loaded": True,
        "db_ready": True,
        "runtime_components_ready": True,
        "pipeline_runner_ready": True,
        "scanner_ready": getattr(components, "scanner", None) is not None,
        "broker_connectivity_required": broker_connectivity_required,
        "broker_check_skipped": not should_check_broker,
        "broker_env_configured": broker_env_configured,
        "doctor_scope": "config_env_wiring",
        "doctor_semantics": {
            "broker_check_kind": "env_presence_only" if should_check_broker else "skipped",
            "broker_live_connectivity_checked": False,
            "broker_auth_verified": False,
            "market_data_path_checked": False,
            "execution_submission_checked": False,
        },
        "config_driven_components": {
            "level_detector": type(components.level_detector).__name__,
            "break_retest_validator": type(components.break_retest_validator).__name__,
            "regime_classifier": type(components.regime_classifier).__name__,
            "execution_quality_assessor": type(components.execution_quality_assessor).__name__,
            "risk_gate": type(components.risk_gate).__name__,
            "scanner": type(components.scanner).__name__ if getattr(components, "scanner", None) is not None else None,
            "pipeline_runner": type(components.pipeline_runner).__name__,
        },
    }

    if journal is not None:
        journal.info("Doctor check completed", checks)

    print(json.dumps(checks, indent=2))
    db.close()


def cmd_pipeline_smoke() -> None:
    config = load_all_configs()
    db = build_db(config)
    journal = _journal_if_enabled(config, db)
    components = build_alvin_components(config)
    broker = getattr(components, "oanda_client", OandaClient())
    runner = components.pipeline_runner

    report = {
        "config_loaded": True,
        "db_ready": True,
        **runner.readiness_report(),
        "scanner_ready": getattr(components, "scanner", None) is not None,
        "oanda_env_configured": broker.is_configured(),
        "smoke_scope": "pipeline_wiring",
        "smoke_semantics": {
            "market_data_checked": False,
            "scanner_checked": False,
            "broker_submission_checked": False,
            "live_trading_ready_proof": False,
        },
    }

    if journal is not None:
        journal.info("Pipeline smoke completed", report)

    print(json.dumps(report, indent=2))
    db.close()


def cmd_scan_once(instrument: str | None = None, session: str | None = None, post_news: bool = False) -> None:
    config = load_all_configs()
    db = build_db(config)
    journal = _journal_if_enabled(config, db)

    if not _feature_enabled(config, "scan_once_enabled", True):
        raise RuntimeError("scan-once is disabled by config.features.scan_once_enabled")

    components = build_alvin_components(config)
    scanner_cfg = config["scanner"]
    market_data_cfg = config["market_data"]

    resolved_instrument = (instrument or scanner_cfg.get("default_instrument") or "").strip().upper()
    if not resolved_instrument:
        raise RuntimeError("scan-once requires an instrument or scanner.default_instrument")

    resolved_session = (session or scanner_cfg.get("default_session") or "unknown").strip().lower()

    if post_news and not bool(scanner_cfg.get("allow_post_news_scan", True)):
        raise RuntimeError("post-news scan requested but scanner.allow_post_news_scan is false")

    request = ScanRequest(
        instrument=resolved_instrument,
        h1_count=int(market_data_cfg.get("default_h1_count", 200)),
        m15_count=int(market_data_cfg.get("default_m15_count", 200)),
        post_news=post_news,
        session=resolved_session,
    )
    result = components.scanner.scan_once(request)

    payload = {
        "config_loaded": True,
        "db_ready": True,
        "scanner_ready": getattr(components, "scanner", None) is not None,
        "scan_scope": "scanner_cli",
        "scan_semantics": {
            "market_data_fetch_attempted": True,
            "setup_flow_attempted": True,
            "evaluation_flow_attempted": True,
            "intent_flow_attempted": False,
            "execution_submission_attempted": False,
        },
        "request": request.to_dict(),
        "summary": _scan_cli_summary(request, result),
        "result": result.to_dict(),
    }

    if journal is not None:
        journal.info("Scan once completed", payload)

    print(json.dumps(payload, indent=2))
    db.close()


def cmd_pipeline_selftest() -> None:
    config = load_all_configs()
    db = build_db(config)
    journal = _journal_if_enabled(config, db)
    components = build_alvin_components(config)
    runner = components.pipeline_runner

    level = Level(
        level_id="selftest-level-1",
        kind="swing_high",
        price=1.1000,
        touches=3,
        first_index=10,
        last_index=40,
        confidence=0.82,
        metadata={"source": "selftest"},
    )

    break_assessment = BreakAssessment(
        valid=True,
        direction="long",
        reason="valid_break",
        close_price=1.1012,
        body_size=0.0012,
        atr=0.0015,
        body_atr_ratio=0.8,
        counter_wick_ratio=0.2,
        details={"source": "selftest"},
    )

    retest_assessment = RetestAssessment(
        valid=True,
        touched_zone=True,
        held_zone=True,
        reason="valid_retest",
        zone_low=1.0997,
        zone_high=1.1003,
        retest_price=1.1004,
        bars_since_break=2,
        details={"source": "selftest"},
    )

    break_retest = BreakRetestResult(
        valid=True,
        direction="long",
        reason="valid_break_retest",
        break_assessment=break_assessment,
        retest_assessment=retest_assessment,
        details={"source": "selftest"},
    )

    confirmation = ConfirmationResult(
        confirmed=True,
        confirmation_type="mss_plus_rejection",
        confidence=0.75,
        reasons=["market_structure_shift", "rejection_candle"],
        details={"source": "selftest"},
    )

    regime_assessment = RegimeAssessment(
        regime="trend",
        confidence=0.78,
        details={"source": "selftest"},
    )

    execution_quality = ExecutionQualityResult(
        quality="clean",
        score=0.91,
        allowed=True,
        reasons=["execution_clean"],
        details={"source": "selftest"},
    )

    portfolio_result = SimpleNamespace(
        allowed=True,
        pressure_score=0.10,
        reasons=["portfolio_ok"],
    )

    evaluation_inputs = {
        "score_allowed": True,
        "score_value": 78.0,
        "regime_assessment": regime_assessment,
        "execution_result": execution_quality,
        "portfolio_result": portfolio_result,
        "daily_loss_pct": 0.25,
        "daily_loss_limit_pct": config["risk"]["daily_loss_limit_pct"],
        "open_risk_pct": 0.25,
        "max_open_risk_pct": config["risk"]["max_open_risk_pct"],
        "concurrent_trades": 0,
        "max_concurrent_trades": config["risk"]["max_concurrent_trades"],
        "kill_switch_active": False,
        "cooldown_active": False,
        "news_lock_active": False,
        "session_allowed": True,
    }

    setup_to_intent = runner.run_setup_to_intent(
        instrument="EUR_USD",
        timeframe="H1",
        side="long",
        setup_type="break_retest",
        level=level,
        break_retest=break_retest,
        confirmation=confirmation,
        atr_value=0.0015,
        score_hint=78.0,
        grade="A+",
        evaluation_inputs=evaluation_inputs,
        session="london",
        post_news=False,
        metadata={"source": "pipeline_selftest"},
        ttl_minutes=60,
        correlation_id="selftest-correlation",
        intent_notes={"mode": "selftest"},
    )

    setup_stage = setup_to_intent.stage
    setup_allowed = setup_to_intent.allowed
    candidate_regime = None

    if setup_to_intent.setup_result is not None and setup_to_intent.setup_result.candidate is not None:
        candidate_regime = getattr(setup_to_intent.setup_result.candidate, "regime", None)

    payload_result = None
    handled_result = None
    transition_result = None
    retry_decision = None
    audit_result = None
    execution_run = None
    intent = None

    persisted = {
        "order_intent_saved": False,
        "order_intent_updated": False,
        "execution_result_saved": False,
        "transition_saved": False,
        "audit_saved": False,
        "retry_saved": False,
    }

    if setup_to_intent.allowed and setup_to_intent.intent_result and setup_to_intent.intent_result.intent is not None:
        intent = setup_to_intent.intent_result.intent
        db.insert_order_intent(intent)
        persisted["order_intent_saved"] = True

        synthetic_execution = OrderExecutionResult(
            submitted=False,
            status="transport_error",
            broker_http_status=0,
            broker_order_id=None,
            reasons=["broker_submit_exception"],
            details={"source": "pipeline_selftest"},
        )

        original_submit = components.order_executor.submit

        def _synthetic_submit(execution_payload, timeout=15):
            return synthetic_execution

        components.order_executor.submit = _synthetic_submit
        try:
            execution_run = runner.run_intent_to_execution(
                intent=intent,
                execution_request={
                    "units": 1000,
                    "order_type": "market",
                    "time_in_force": "FOK",
                    "attempt_number": 1,
                },
                base_result=setup_to_intent,
            )
        finally:
            components.order_executor.submit = original_submit

        payload_result = execution_run.execution_payload_result
        handled_result = execution_run.handled_result
        transition_result = execution_run.transition_result
        retry_decision = execution_run.retry_decision
        audit_result = execution_run.audit_record

        db.insert_order_intent(intent)
        persisted["order_intent_updated"] = True

        ts_utc = utc_now_iso()

        if execution_run.execution_result is not None:
            db.insert_execution_result(
                intent_id=intent.intent_id,
                result=execution_run.execution_result,
                ts_utc=ts_utc,
            )
            persisted["execution_result_saved"] = True

        if transition_result is not None:
            db.insert_intent_state_transition(
                intent_id=intent.intent_id,
                transition=transition_result,
                ts_utc=ts_utc,
            )
            persisted["transition_saved"] = True

        if audit_result is not None and getattr(audit_result, "allowed", False) and getattr(audit_result, "record", None) is not None:
            db.insert_execution_audit(
                record=audit_result.record,
                ts_utc=ts_utc,
            )
            persisted["audit_saved"] = True

        if retry_decision is not None:
            db.insert_retry_decision(
                intent_id=intent.intent_id,
                decision=retry_decision,
                ts_utc=ts_utc,
            )
            persisted["retry_saved"] = True

    report = {
        "config_loaded": True,
        "db_ready": True,
        **runner.readiness_report(),
        "selftest": {
            "setup_stage": setup_stage,
            "setup_allowed": setup_allowed,
            "candidate_regime": candidate_regime,
            "intent_created": bool(
                setup_to_intent.intent_result is not None
                and setup_to_intent.intent_result.intent is not None
            ),
            "payload_allowed": bool(getattr(payload_result, "allowed", False)) if payload_result is not None else None,
            "execution_stage": getattr(execution_run, "stage", None) if execution_run is not None else None,
            "execution_allowed": bool(getattr(execution_run, "allowed", False)) if execution_run is not None else None,
            "handled_state": getattr(handled_result, "state", None) if handled_result is not None else None,
            "transition_allowed": bool(getattr(transition_result, "allowed", False)) if transition_result is not None else None,
            "transition_next_state": getattr(transition_result, "next_state", None) if transition_result is not None else None,
            "intent_state": getattr(intent, "state", None) if intent is not None else None,
            "intent_history": list(getattr(intent, "history", [])) if intent is not None and hasattr(intent, "history") else None,
            "retry_should_retry": bool(getattr(retry_decision, "should_retry", False)) if retry_decision is not None else None,
            "retry_reason": getattr(retry_decision, "reason", None) if retry_decision is not None else None,
            "audit_allowed": bool(getattr(audit_result, "allowed", False)) if audit_result is not None else None,
            "persistence": persisted,
        },
    }

    if journal is not None:
        journal.info("Pipeline selftest completed", report)

    print(json.dumps(report, indent=2))
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
    sub.add_parser("pipeline-smoke")
    sub.add_parser("pipeline-selftest")

    scan_once_parser = sub.add_parser("scan-once")
    scan_once_parser.add_argument("--instrument", required=False)
    scan_once_parser.add_argument("--session", required=False)
    scan_once_parser.add_argument("--post-news", action="store_true")

    args = parser.parse_args()

    Path("runtime").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)

    if args.command == "bootstrap":
        cmd_bootstrap()
    elif args.command == "doctor":
        cmd_doctor()
    elif args.command == "show-config":
        cmd_show_config()
    elif args.command == "pipeline-smoke":
        cmd_pipeline_smoke()
    elif args.command == "pipeline-selftest":
        cmd_pipeline_selftest()
    elif args.command == "scan-once":
        cmd_scan_once(
            instrument=getattr(args, "instrument", None),
            session=getattr(args, "session", None),
            post_news=bool(getattr(args, "post_news", False)),
        )


if __name__ == "__main__":
    main()
