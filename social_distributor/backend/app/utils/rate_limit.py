"""Per-platform sliding-window rate limit guard.

Backed by Redis when available; falls back to a process-local in-memory
counter (only useful for tests / single-process dev). Defaults follow each
platform's documented developer limits with a safety margin.
"""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from threading import Lock

log = logging.getLogger(__name__)

# (max_calls, window_seconds) per platform. Conservative defaults.
DEFAULT_LIMITS = {
    "facebook": (200, 3600),     # Pages API ~200/hour/page is the sweet spot
    "instagram": (50, 3600),     # Content publishing API: 50 posts/24h per IG user
    "tiktok": (30, 86400),       # Content Posting API: ~30/day/account
    "youtube": (6, 86400),       # Conservative — quota is 10k units/day, upload = 1600
}


class RateLimitExceeded(Exception):
    def __init__(self, platform: str, retry_after_seconds: int) -> None:
        super().__init__(
            f"rate limit exceeded for {platform}; retry in {retry_after_seconds}s"
        )
        self.platform = platform
        self.retry_after_seconds = retry_after_seconds


class _MemoryCounter:
    def __init__(self) -> None:
        self._store: dict[str, deque[float]] = {}
        self._lock = Lock()

    def hit(self, key: str, max_calls: int, window: int) -> tuple[bool, int]:
        now = time.time()
        with self._lock:
            bucket = self._store.setdefault(key, deque())
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if len(bucket) >= max_calls:
                retry = int(window - (now - bucket[0])) + 1
                return False, retry
            bucket.append(now)
            return True, 0


_memory = _MemoryCounter()
_redis_client = None


def _redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    url = os.environ.get("REDIS_URL")
    if not url:
        return None
    try:
        import redis as redis_pkg
        _redis_client = redis_pkg.from_url(url, decode_responses=True)
        _redis_client.ping()
    except Exception as exc:
        log.warning("redis unavailable, using memory rate limiter: %s", exc)
        _redis_client = None
    return _redis_client


def check_and_consume(platform: str, account_external_id: str) -> None:
    """Raises :class:`RateLimitExceeded` if the platform/account is over quota."""
    limits = _resolve_limits(platform)
    if limits is None:
        return
    max_calls, window = limits
    key = f"ratelim:{platform}:{account_external_id}"

    client = _redis()
    if client is None:
        ok, retry = _memory.hit(key, max_calls, window)
    else:
        ok, retry = _redis_hit(client, key, max_calls, window)

    if not ok:
        raise RateLimitExceeded(platform, retry)


def _redis_hit(client, key: str, max_calls: int, window: int) -> tuple[bool, int]:
    now = time.time()
    pipeline = client.pipeline()
    pipeline.zremrangebyscore(key, 0, now - window)
    pipeline.zcard(key)
    _, count = pipeline.execute()
    if int(count) >= max_calls:
        oldest = client.zrange(key, 0, 0, withscores=True)
        if oldest:
            retry = int(window - (now - oldest[0][1])) + 1
            return False, max(1, retry)
        return False, window
    client.zadd(key, {f"{now}:{os.urandom(4).hex()}": now})
    client.expire(key, window + 60)
    return True, 0


def _resolve_limits(platform: str) -> tuple[int, int] | None:
    raw = os.environ.get(f"RATE_LIMIT_{platform.upper()}")
    if raw:
        try:
            calls_s, window_s = raw.split(":", 1)
            return int(calls_s), int(window_s)
        except ValueError:
            log.warning("ignoring malformed RATE_LIMIT_%s=%s", platform, raw)
    return DEFAULT_LIMITS.get(platform)
