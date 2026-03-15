from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from contracts.dedupe import build_dedupe_key


VALID_TRANSITIONS = {
    "intent_created": {
        "submit_started",
        "submitted_to_broker",
        "retryable_failure",
        "terminal_failure",
        "unknown_failure",
        "expired",
        "rejected",
    },
    "submit_started": {
        "submitted_to_broker",
        "retryable_failure",
        "terminal_failure",
        "unknown_failure",
        "expired",
        "rejected",
    },
    "submitted_to_broker": {
        "acked",
        "partially_filled",
        "filled",
        "cancelled",
        "expired",
        "retryable_failure",
        "terminal_failure",
        "unknown_failure",
        "rejected",
    },
    "acked": {"partially_filled", "filled", "cancelled", "position_open", "expired"},
    "partially_filled": {"filled", "cancelled", "position_open", "expired"},
    "filled": {"position_open", "position_closed"},
    "position_open": {"position_closed"},
    "retryable_failure": {"submit_started", "submitted_to_broker", "terminal_failure", "unknown_failure", "expired"},
    "terminal_failure": set(),
    "unknown_failure": {"retryable_failure", "terminal_failure", "expired"},
    "position_closed": set(),
    "rejected": set(),
    "cancelled": set(),
    "expired": set(),
}

TERMINAL_STATES = {
    "terminal_failure",
    "position_closed",
    "rejected",
    "cancelled",
    "expired",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_bucket(ts_utc: str) -> str:
    return ts_utc[:13]


@dataclass(slots=True)
class OrderIntent:
    instrument: str
    side: str
    timeframe: str = "H1"
    setup_type: str = "break_retest"
    trigger_reference: str = ""
    score: float = 0.0
    grade: str = "C"
    correlation_id: Optional[str] = None
    ttl_minutes: int = 60
    payload: Dict[str, Any] = field(default_factory=dict)

    intent_id: str = field(default_factory=lambda: str(uuid4()))
    dedupe_key: str = field(default="")
    state: str = "intent_created"
    reason: Optional[str] = None
    broker_request_id: Optional[str] = None
    created_at_utc: str = field(default_factory=utc_now_iso)
    history: list[str] = field(default_factory=lambda: ["intent_created"])

    def __post_init__(self) -> None:
        self.instrument = self.instrument.strip().upper()
        self.side = self.side.strip().lower()
        self.timeframe = self.timeframe.strip().upper()
        self.setup_type = self.setup_type.strip().lower()
        self.grade = self.grade.strip().upper()
        self.correlation_id = self.correlation_id or str(uuid4())
        if not self.created_at_utc:
            self.created_at_utc = utc_now_iso()
        if not self.history:
            self.history = [self.state]
        if not self.dedupe_key:
            self.dedupe_key = build_dedupe_key(
                instrument=self.instrument,
                timeframe=self.timeframe,
                setup_type=self.setup_type,
                side=self.side,
                trigger_ref=self.trigger_reference or self.intent_id,
                timestamp_bucket=_timestamp_bucket(self.created_at_utc),
            )

    def expires_at_utc(self) -> str:
        base_dt = datetime.fromisoformat(self.created_at_utc)
        return (base_dt + timedelta(minutes=self.ttl_minutes)).isoformat()

    def can_transition(self, next_state: str) -> bool:
        return next_state in VALID_TRANSITIONS.get(self.state, set())

    def transition(self, next_state: str, reason: Optional[str] = None) -> None:
        if not self.can_transition(next_state):
            raise ValueError(f"Invalid order transition: {self.state} -> {next_state}")
        self.state = next_state
        if reason is not None:
            self.reason = reason
        self.history.append(next_state)

    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def lifecycle_summary(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "instrument": self.instrument,
            "side": self.side,
            "timeframe": self.timeframe,
            "setup_type": self.setup_type,
            "state": self.state,
            "reason": self.reason,
            "history": list(self.history),
            "terminal": self.is_terminal(),
            "created_at_utc": self.created_at_utc,
            "expires_at_utc": self.expires_at_utc(),
            "dedupe_key": self.dedupe_key,
            "correlation_id": self.correlation_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
