from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4


class RuntimeSchemaCompatibilityError(RuntimeError):
    pass


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

    def apply_schema(self, schema_path: str) -> None:
        schema = Path(schema_path).read_text(encoding="utf-8")
        self.connection.executescript(schema)
        self.connection.commit()
        self._verify_runtime_schema()

    def insert_event(self, *args: Any, **kwargs: Any) -> None:
        if len(args) == 1 and isinstance(args[0], dict):
            record = args[0]
            self.connection.execute(
                """
                INSERT INTO events (event_id, event_type, module, instrument, correlation_id, ts_utc, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["event_id"],
                    record["event_type"],
                    record["module"],
                    record.get("instrument"),
                    record.get("correlation_id"),
                    record["ts_utc"],
                    json.dumps(record.get("payload", {}), ensure_ascii=False, sort_keys=True),
                ),
            )
        elif len(args) == 3:
            ts_utc, event_type, payload = args
            self.connection.execute(
                """
                INSERT INTO events (event_id, event_type, module, instrument, correlation_id, ts_utc, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    kwargs.get("event_id") or f"legacy-{hashlib.sha256(f'{ts_utc}:{event_type}'.encode()).hexdigest()[:16]}",
                    event_type,
                    kwargs.get("module", "legacy"),
                    kwargs.get("instrument"),
                    kwargs.get("correlation_id"),
                    ts_utc,
                    json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
                ),
            )
        else:
            raise TypeError("insert_event expects either a record dict or (ts_utc, event_type, payload)")
        self.connection.commit()

    def insert_error(self, ts_utc: str, module: str, message: str, payload: Dict[str, Any] | None = None) -> None:
        self.connection.execute(
            "INSERT INTO errors (ts_utc, module, message, payload_json) VALUES (?, ?, ?, ?)",
            (ts_utc, module, message, json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)),
        )
        self.connection.commit()

    def insert_journal_entry(self, ts_utc: str, level: str, message: str, context: Dict[str, Any] | None = None) -> None:
        self.connection.execute(
            "INSERT INTO journal_entries (ts_utc, level, message, context_json) VALUES (?, ?, ?, ?)",
            (ts_utc, level, message, json.dumps(context or {}, ensure_ascii=False, sort_keys=True)),
        )
        self.connection.commit()

    def snapshot_config(self, ts_utc: str, config: Dict[str, Any]) -> str:
        config_json = json.dumps(config, ensure_ascii=False, sort_keys=True)
        sha256 = hashlib.sha256(config_json.encode("utf-8")).hexdigest()
        self.connection.execute(
            "INSERT INTO config_snapshots (ts_utc, sha256, config_json) VALUES (?, ?, ?)",
            (ts_utc, sha256, config_json),
        )
        self.connection.commit()
        return sha256

    def insert_shadow_evaluation(
        self,
        *,
        candidate_id: str,
        instrument: str,
        decision: str,
        hypothetical_outcome: str,
        notes: Dict[str, Any],
        ts_utc: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO shadow_evaluations (candidate_id, instrument, decision, hypothetical_outcome, notes_json, ts_utc)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (candidate_id, instrument, decision, hypothetical_outcome, json.dumps(notes, ensure_ascii=False, sort_keys=True), ts_utc),
        )
        self.connection.commit()

    def insert_order_intent(self, intent: Any) -> None:
        snapshot = self._serialize_order_intent(intent)
        self.connection.execute(
            """
            INSERT OR REPLACE INTO order_intents (intent_id, dedupe_key, instrument, state, side, payload_json, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                intent.intent_id,
                intent.dedupe_key,
                intent.instrument,
                intent.state,
                intent.side,
                json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                snapshot.get("created_at_utc", ""),
            ),
        )
        self.connection.commit()

    def update_order_intent_state(
        self,
        *,
        intent_id: str,
        state: str,
        payload: Dict[str, Any] | None = None,
    ) -> None:
        current_payload_json = self.connection.execute(
            "SELECT payload_json FROM order_intents WHERE intent_id = ?",
            (intent_id,),
        ).fetchone()

        current_payload: Dict[str, Any] = {}
        if current_payload_json and current_payload_json["payload_json"]:
            try:
                current_payload = json.loads(current_payload_json["payload_json"])
            except Exception:
                current_payload = {}

        merged_payload = dict(current_payload)
        merged_payload["state"] = state
        if payload:
            merged_payload["payload"] = payload

        self.connection.execute(
            "UPDATE order_intents SET state = ?, payload_json = ? WHERE intent_id = ?",
            (state, json.dumps(merged_payload, ensure_ascii=False, sort_keys=True), intent_id),
        )
        self.connection.commit()

    def insert_execution_result(self, *, intent_id: str, result: Any, ts_utc: str) -> None:
        self.connection.execute(
            """
            INSERT INTO execution_results
            (intent_id, status, submitted, broker_http_status, broker_order_id, reasons_json, details_json, ts_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                intent_id,
                result.status,
                1 if bool(result.submitted) else 0,
                int(result.broker_http_status),
                result.broker_order_id,
                json.dumps(list(getattr(result, "reasons", [])), ensure_ascii=False, sort_keys=True),
                json.dumps(dict(getattr(result, "details", {})), ensure_ascii=False, sort_keys=True),
                ts_utc,
            ),
        )
        self.connection.commit()

    def insert_intent_state_transition(self, *, intent_id: str, transition: Any, ts_utc: str) -> None:
        self.connection.execute(
            """
            INSERT INTO intent_state_transitions
            (intent_id, previous_state, next_state, allowed, reasons_json, details_json, ts_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                intent_id,
                transition.previous_state,
                transition.next_state,
                1 if bool(transition.allowed) else 0,
                json.dumps(list(getattr(transition, "reasons", [])), ensure_ascii=False, sort_keys=True),
                json.dumps(dict(getattr(transition, "details", {})), ensure_ascii=False, sort_keys=True),
                ts_utc,
            ),
        )
        self.connection.commit()

    def insert_execution_audit(self, *, record: Any, ts_utc: str) -> None:
        self.connection.execute(
            """
            INSERT INTO execution_audits
            (intent_id, correlation_id, instrument, side, previous_state, next_state, execution_category, accepted, payload_json, ts_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.intent_id,
                record.correlation_id,
                record.instrument,
                record.side,
                record.previous_state,
                record.next_state,
                record.execution_category,
                1 if bool(record.accepted) else 0,
                json.dumps(dict(getattr(record, "payload", {})), ensure_ascii=False, sort_keys=True),
                ts_utc,
            ),
        )
        self.connection.commit()

    def insert_retry_decision(self, *, intent_id: str, decision: Any, ts_utc: str) -> None:
        self.connection.execute(
            """
            INSERT INTO retry_decisions
            (intent_id, should_retry, retry_after_seconds, max_attempts, reason, details_json, ts_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                intent_id,
                1 if bool(decision.should_retry) else 0,
                int(decision.retry_after_seconds),
                int(decision.max_attempts),
                decision.reason,
                json.dumps(dict(getattr(decision, "details", {})), ensure_ascii=False, sort_keys=True),
                ts_utc,
            ),
        )
        self.connection.commit()

    def insert_scan_run(
        self,
        *,
        instrument: str,
        session: str,
        stage: str,
        allowed: bool,
        stage_group: str,
        request: Dict[str, Any],
        summary: Dict[str, Any],
        result: Dict[str, Any],
        ts_utc: str,
        primary_reason: str | None = None,
        correlation_id: str | None = None,
        scan_id: str | None = None,
    ) -> str:
        resolved_scan_id = scan_id or str(uuid4())
        self.connection.execute(
            """
            INSERT INTO scan_runs
            (scan_id, instrument, session, stage, allowed, stage_group, primary_reason, correlation_id, ts_utc, request_json, summary_json, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_scan_id,
                instrument,
                session,
                stage,
                1 if bool(allowed) else 0,
                stage_group,
                primary_reason,
                correlation_id,
                ts_utc,
                json.dumps(request or {}, ensure_ascii=False, sort_keys=True),
                json.dumps(summary or {}, ensure_ascii=False, sort_keys=True),
                json.dumps(result or {}, ensure_ascii=False, sort_keys=True),
            ),
        )
        self.connection.commit()
        return resolved_scan_id

    def insert_payload_preview(
        self,
        *,
        scan_id: str,
        instrument: str,
        payload_preview: Dict[str, Any],
        sizing: Dict[str, Any] | None,
        ts_utc: str,
        intent_id: str | None = None,
        preview_id: str | None = None,
    ) -> str:
        resolved_preview_id = preview_id or str(uuid4())
        execution_payload = (payload_preview or {}).get("execution_payload") or {}
        details = (payload_preview or {}).get("details") or {}
        sizing_details = sizing or {}
        self.connection.execute(
            """
            INSERT INTO payload_previews
            (preview_id, scan_id, intent_id, instrument, allowed, units, order_type, stop_distance, risk_amount, payload_json, ts_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_preview_id,
                scan_id,
                intent_id,
                instrument,
                1 if bool((payload_preview or {}).get("allowed")) else 0,
                execution_payload.get("units") or details.get("units"),
                execution_payload.get("order_type"),
                sizing_details.get("stop_distance"),
                sizing_details.get("risk_amount"),
                json.dumps(
                    {
                        "payload_preview": payload_preview or {},
                        "sizing": sizing_details,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                ts_utc,
            ),
        )
        self.connection.commit()
        return resolved_preview_id

    def insert_scan_decision_snapshot(
        self,
        *,
        scan_id: str,
        instrument: str,
        stage: str,
        payload: Dict[str, Any],
        ts_utc: str,
        candidate_id: str | None = None,
        intent_id: str | None = None,
        payload_preview_id: str | None = None,
        snapshot_id: str | None = None,
    ) -> str:
        resolved_snapshot_id = snapshot_id or str(uuid4())
        self.connection.execute(
            """
            INSERT INTO scan_decision_snapshots
            (snapshot_id, scan_id, instrument, stage, candidate_id, intent_id, payload_preview_id, ts_utc, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_snapshot_id,
                scan_id,
                instrument,
                stage,
                candidate_id,
                intent_id,
                payload_preview_id,
                ts_utc,
                json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
            ),
        )
        self.connection.commit()
        return resolved_snapshot_id

    def _serialize_order_intent(self, intent: Any) -> Dict[str, Any]:
        if hasattr(intent, "to_dict") and callable(intent.to_dict):
            snapshot = intent.to_dict()
            if isinstance(snapshot, dict):
                return snapshot
        return {
            "intent_id": getattr(intent, "intent_id", ""),
            "dedupe_key": getattr(intent, "dedupe_key", ""),
            "instrument": getattr(intent, "instrument", ""),
            "state": getattr(intent, "state", ""),
            "side": getattr(intent, "side", ""),
            "timeframe": getattr(intent, "timeframe", ""),
            "setup_type": getattr(intent, "setup_type", ""),
            "trigger_reference": getattr(intent, "trigger_reference", ""),
            "score": getattr(intent, "score", 0.0),
            "grade": getattr(intent, "grade", ""),
            "correlation_id": getattr(intent, "correlation_id", ""),
            "ttl_minutes": getattr(intent, "ttl_minutes", 0),
            "payload": dict(getattr(intent, "payload", {}) or {}),
            "created_at_utc": getattr(intent, "created_at_utc", ""),
            "history": list(getattr(intent, "history", []) or []),
            "reason": getattr(intent, "reason", None),
            "broker_request_id": getattr(intent, "broker_request_id", None),
        }

    def _verify_runtime_schema(self) -> None:
        required_columns = {
            "order_intents": {
                "intent_id",
                "dedupe_key",
                "instrument",
                "state",
                "side",
                "payload_json",
                "created_at_utc",
            },
            "execution_results": {
                "intent_id",
                "status",
                "submitted",
                "broker_http_status",
                "broker_order_id",
                "reasons_json",
                "details_json",
                "ts_utc",
            },
            "intent_state_transitions": {
                "intent_id",
                "previous_state",
                "next_state",
                "allowed",
                "reasons_json",
                "details_json",
                "ts_utc",
            },
            "execution_audits": {
                "intent_id",
                "correlation_id",
                "instrument",
                "side",
                "previous_state",
                "next_state",
                "execution_category",
                "accepted",
                "payload_json",
                "ts_utc",
            },
            "retry_decisions": {
                "intent_id",
                "should_retry",
                "retry_after_seconds",
                "max_attempts",
                "reason",
                "details_json",
                "ts_utc",
            },
            "scan_runs": {
                "scan_id",
                "instrument",
                "session",
                "stage",
                "allowed",
                "stage_group",
                "primary_reason",
                "correlation_id",
                "ts_utc",
                "request_json",
                "summary_json",
                "result_json",
            },
            "payload_previews": {
                "preview_id",
                "scan_id",
                "intent_id",
                "instrument",
                "allowed",
                "units",
                "order_type",
                "stop_distance",
                "risk_amount",
                "payload_json",
                "ts_utc",
            },
            "scan_decision_snapshots": {
                "snapshot_id",
                "scan_id",
                "instrument",
                "stage",
                "candidate_id",
                "intent_id",
                "payload_preview_id",
                "ts_utc",
                "payload_json",
            },
        }

        for table_name, expected_columns in required_columns.items():
            actual_columns = self._table_columns(table_name)
            missing_columns = sorted(expected_columns - actual_columns)
            if missing_columns:
                missing_render = ", ".join(missing_columns)
                raise RuntimeSchemaCompatibilityError(
                    f"Database schema at '{self.db_path}' is out of date for table '{table_name}'. "
                    f"Missing columns: {missing_render}. Back up or remove the local SQLite database and run bootstrap again."
                )

    def _table_columns(self, table_name: str) -> set[str]:
        rows = self.connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}

    def close(self) -> None:
        self.connection.close()
