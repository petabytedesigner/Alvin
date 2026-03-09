from __future__ import annotations


def combine_reasons(*reason_groups: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for group in reason_groups:
        for reason in group:
            if reason not in seen:
                seen.add(reason)
                ordered.append(reason)
    return ordered
