from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional
from uuid import uuid4


@dataclass(slots=True)
class SignalCandidate:
    candidate_id: str = field(default_factory=lambda: str(uuid4()))
    instrument: str = ""
    timeframe: str = "H1"
    side: str = ""
    setup_type: str = "break_retest"
    grade: str = "C"
    score: float = 0.0
    regime: str = "unknown"
    trigger_reference: str = ""
    level_reference: str = ""
    session: str = "unknown"
    post_news: bool = False
    notes: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SignalCandidateBuilder:
    VALID_SIDES = {"long", "short"}
    VALID_GRADES = {"A++", "A+", "A", "B", "C"}

    def build(
        self,
        *,
        instrument: str,
        side: str,
        score: float,
        grade: str,
        regime: str,
        trigger_reference: str,
        level_reference: str,
        timeframe: str = "H1",
        setup_type: str = "break_retest",
        session: str = "unknown",
        post_news: bool = False,
        notes: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SignalCandidate:
        side_normalized = side.strip().lower()
        if side_normalized not in self.VALID_SIDES:
            raise ValueError(f"Invalid side: {side}")

        grade_normalized = grade.strip().upper()
        if grade_normalized not in self.VALID_GRADES:
            raise ValueError(f"Invalid grade: {grade}")

        if not instrument.strip():
            raise ValueError("instrument is required")
        if not trigger_reference.strip():
            raise ValueError("trigger_reference is required")
        if not level_reference.strip():
            raise ValueError("level_reference is required")

        bounded_score = round(max(0.0, min(1.0, score)), 4)

        return SignalCandidate(
            instrument=instrument.strip().upper(),
            timeframe=timeframe.strip().upper(),
            side=side_normalized,
            setup_type=setup_type.strip().lower(),
            grade=grade_normalized,
            score=bounded_score,
            regime=regime.strip().lower(),
            trigger_reference=trigger_reference.strip(),
            level_reference=level_reference.strip(),
            session=session.strip().lower(),
            post_news=post_news,
            notes=notes or {},
            metadata=metadata or {},
        )
