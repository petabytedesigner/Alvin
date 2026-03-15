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

    def mismatch_count(self) -> int:
        return len(self.mismatches)

    def repair_count(self) -> int:
        return len(self.repairs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts_utc": self.ts_utc,
            "status": self.status,
            "mismatches": list(self.mismatches),
            "repairs": list(self.repairs),
            "mismatch_count": self.mismatch_count(),
            "repair_count": self.repair_count(),
            "has_mismatches": self.has_mismatches(),
        }


@dataclass(slots=True)
class ReconciliationMismatch:
    category: str
    severity: str
    intent_id: str | None
    expected: Dict[str, Any]
    actual: Dict[str, Any]
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "intent_id": self.intent_id,
            "expected": dict(self.expected),
            "actual": dict(self.actual),
            "reasons": list(self.reasons),
        }


@dataclass(slots=True)
class ReconciliationRepair:
    action: str
    status: str
    intent_id: str | None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "status": self.status,
            "intent_id": self.intent_id,
            "details": dict(self.details),
        }
