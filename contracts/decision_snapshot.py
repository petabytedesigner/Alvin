from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any, Dict


@dataclass
class DecisionSnapshot:
    ts_utc: str
    instrument: str
    module: str
    decision_type: str
    status: str
    reasons: list[str]
    context: Dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)

    def sha256(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()
