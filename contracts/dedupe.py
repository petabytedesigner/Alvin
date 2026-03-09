from __future__ import annotations

import hashlib


def build_dedupe_key(
    *,
    instrument: str,
    timeframe: str,
    setup_type: str,
    side: str,
    trigger_ref: str,
    timestamp_bucket: str,
) -> str:
    raw = "|".join([instrument, timeframe, setup_type, side, trigger_ref, timestamp_bucket])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
