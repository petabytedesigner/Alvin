from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Event:
    event_type: str
    module: str
    payload: Dict[str, Any] = field(default_factory=dict)
    instrument: Optional[str] = None
    correlation_id: Optional[str] = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    ts_utc: str = field(default_factory=utc_now_iso)

    def to_record(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "module": self.module,
            "instrument": self.instrument,
            "correlation_id": self.correlation_id,
            "ts_utc": self.ts_utc,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_record(), ensure_ascii=False, sort_keys=True)


def build_event(
    *,
    event_type: str,
    module: str,
    payload: Dict[str, Any] | None = None,
    instrument: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Event:
    return Event(
        event_type=event_type,
        module=module,
        payload=payload or {},
        instrument=instrument,
        correlation_id=correlation_id,
    )
