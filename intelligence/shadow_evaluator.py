from dataclasses import dataclass, asdict

@dataclass(slots=True)
class ShadowEvaluation:
    instrument: str
    candidate_id: str
    decision: str
    hypothetical_outcome: str
    notes: dict

    def to_dict(self) -> dict:
        return asdict(self)

class ShadowEvaluator:
    def build(self, *, instrument: str, candidate_id: str, decision: str, hypothetical_outcome: str = "pending", notes: dict | None = None) -> ShadowEvaluation:
        return ShadowEvaluation(instrument, candidate_id, decision, hypothetical_outcome, notes or {})
