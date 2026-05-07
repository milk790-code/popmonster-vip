"""Retry/backoff helpers shared by Celery tasks."""
from __future__ import annotations

import random

from ..config import config


def backoff_seconds(attempt: int) -> int:
    """Exponential backoff with jitter, capped at one hour.

    ``attempt`` is the 1-indexed retry count. We add up to 25% jitter so a
    cohort of failures does not stampede the platform on resume.
    """
    base = config.retry_backoff_base_seconds
    delay = min(3600, base * (2 ** max(0, attempt - 1)))
    jitter = random.uniform(0, delay * 0.25)
    return int(delay + jitter)
