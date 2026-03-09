from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


VALID_TRANSITIONS = {
    "intent_created": {"submit_started", "rejected", "expired"},
    "submit_started": {"submitted", "rejected", "expired"},
    "submitted": {"acked", "rejected", "cancelled", "expired"},
    "acked": {"partially_filled", "filled", "cancelled"},
    "partially_filled": {"filled", "cancelled"},
    "filled": {"position_open"},
    "position_open": {"position_closed"},
    "position_closed": set(),
    "rejected": set(),
    "cancelled": set(),
    "expired": set(),
}


@dataclass
class OrderIntent:
    intent_id: str
    dedupe_key: str
    instrument: str
    side: str
    state: str = "intent_created"
    reason: Optional[str] = None
    correlation_id: Optional[str] = None
    broker_request_id: Optional[str] = None
    history: list[str] = field(default_factory=lambda: ["intent_created"])

    def transition(self, next_state: str) -> None:
        allowed = VALID_TRANSITIONS.get(self.state, set())
        if next_state not in allowed:
            raise ValueError(f"Invalid order transition: {self.state} -> {next_state}")
        self.state = next_state
        self.history.append(next_state)
