from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict


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

    def insert_event(self, record: Dict[str, Any]) -> None:
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

    def insert_order_intent(self, ts_utc: str, intent: Dict[str, Any]) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO order_intents
            (intent_id, dedupe_key, instrument, side, state, reason, correlation_id, broker_request_id, history_json, ts_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                intent["intent_id"],
                intent["dedupe_key"],
                intent["instrument"],
                intent["side"],
                intent["state"],
                intent.get("reason"),
                intent.get("correlation_id"),
                intent.get("broker_request_id"),
                json.dumps(intent.get("history", []), ensure_ascii=False, sort_keys=True),
                ts_utc,
            ),
        )
        self.connection.commit()

    def insert_decision_snapshot(
        self,
        *,
        ts_utc: str,
        instrument: str,
        module: str,
        decision_type: str,
        status: str,
        reasons: list[str],
        context: Dict[str, Any],
    ) -> str:
        context_json = json.dumps(context, ensure_ascii=False, sort_keys=True)
        reasons_json = json.dumps(reasons, ensure_ascii=False, sort_keys=True)
        sha256 = hashlib.sha256(
            f"{ts_utc}|{instrument}|{module}|{decision_type}|{status}|{reasons_json}|{context_json}".encode("utf-8")
        ).hexdigest()
        self.connection.execute(
            """
            INSERT OR REPLACE INTO decision_snapshots
            (ts_utc, instrument, module, decision_type, status, reasons_json, context_json, sha256)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ts_utc, instrument, module, decision_type, status, reasons_json, context_json, sha256),
        )
        self.connection.commit()
        return sha256

    def insert_reconciliation_run(self, ts_utc: str, status: str, mismatches: list[Dict[str, Any]], repairs: list[Dict[str, Any]]) -> None:
        self.connection.execute(
            """
            INSERT INTO reconciliation_runs (ts_utc, status, mismatches_json, repairs_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                ts_utc,
                status,
                json.dumps(mismatches, ensure_ascii=False, sort_keys=True),
                json.dumps(repairs, ensure_ascii=False, sort_keys=True),
            ),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()
