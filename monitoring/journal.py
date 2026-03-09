from __future__ import annotations

from typing import Any, Dict

from core.events import utc_now_iso
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
