"""Schedule jitter for matrix distribution.

When fanning out to N accounts at the same nominal time, posting all of them
within seconds of each other looks like coordinated automation and can hurt
reach. ``spread`` deterministically scatters the start times across a window
so behaviour is reproducible (so re-runs of the same distribute call don't
double-post on different times).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta


def spread(base: datetime, window_minutes: int, seed: str, count: int) -> list[datetime]:
    if count <= 0:
        return []
    if window_minutes <= 0:
        return [base for _ in range(count)]

    seconds = window_minutes * 60
    digest = hashlib.sha256(seed.encode()).digest()
    offsets: list[int] = []
    for i in range(count):
        # Stretch the digest by mixing in the index so we don't repeat offsets.
        chunk = hashlib.sha256(digest + i.to_bytes(4, "big")).digest()
        offsets.append(int.from_bytes(chunk[:4], "big") % seconds)
    offsets.sort()
    return [base + timedelta(seconds=offset) for offset in offsets]
