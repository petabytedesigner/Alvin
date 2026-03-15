from __future__ import annotations

from typing import Any, Dict

from core.events import build_event, utc_now_iso
from storage.database import Database


class Journal:
    def __init__(self, db: Database) -> None:
        self.db = db

    def info(self, message: str, context: Dict[str, Any] | None = None) -> None:
        self.db.insert_journal_entry(utc_now_iso(), "INFO", message, context)

    def warning(self, message: str, context: Dict[str, Any] | None = None) -> None:
        self.db.insert_journal_entry(utc_now_iso(), "WARNING", message, context)

    def error(self, message: str, context: Dict[str, Any] | None = None) -> None:
        self.db.insert_journal_entry(utc_now_iso(), "ERROR", message, context)

    def broker_health(self, result: Dict[str, Any]) -> None:
        level = "INFO" if bool(result.get("ok")) else "WARNING"
        self.db.insert_journal_entry(
            utc_now_iso(),
            level,
            "Broker health check",
            result,
        )

    def execution(self, message: str, context: Dict[str, Any] | None = None) -> None:
        self.db.insert_journal_entry(
            utc_now_iso(),
            "INFO",
            f"Execution: {message}",
            context,
        )

    def emit_event(
        self,
        *,
        event_type: str,
        module: str,
        payload: Dict[str, Any] | None = None,
        instrument: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        event = build_event(
            event_type=event_type,
            module=module,
            payload=payload,
            instrument=instrument,
            correlation_id=correlation_id,
        )
        self.db.insert_event(event.to_record())
