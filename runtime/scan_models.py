from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class ScanRequest:
    instrument: str
    h1_count: int = 200
    m15_count: int = 200
    post_news: bool = False
    session: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instrument": self.instrument,
            "h1_count": self.h1_count,
            "m15_count": self.m15_count,
            "post_news": self.post_news,
            "session": self.session,
        }


@dataclass(slots=True)
class ScanResult:
    allowed: bool
    stage: str
    reasons: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "stage": self.stage,
            "reasons": self.reasons,
            "details": self.details,
        }
