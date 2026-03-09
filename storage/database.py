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

    def close(self) -> None:
        self.connection.close()
