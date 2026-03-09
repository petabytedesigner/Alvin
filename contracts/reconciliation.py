from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ReconciliationRun:
    ts_utc: str
    status: str
    mismatches: list[Dict[str, Any]] = field(default_factory=list)
    repairs: list[Dict[str, Any]] = field(default_factory=list)

    def has_mismatches(self) -> bool:
        return len(self.mismatches) > 0
