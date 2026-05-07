"""Per-platform rate limit guard (memory backend)."""
import os

import pytest

from app.utils.rate_limit import (
    DEFAULT_LIMITS,
    RateLimitExceeded,
    _MemoryCounter,
    _memory,
    check_and_consume,
)


@pytest.fixture(autouse=True)
def clear_memory_counter(monkeypatch):
    # Force the memory backend (no Redis dependency in tests).
    monkeypatch.setattr("app.utils.rate_limit._redis", lambda: None)
    _memory._store.clear()
    yield
    _memory._store.clear()


def test_within_limit_does_not_raise(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_TIKTOK", "3:60")
    for _ in range(3):
        check_and_consume("tiktok", "acct-x")


def test_exceeding_limit_raises(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_TIKTOK", "2:60")
    check_and_consume("tiktok", "acct-y")
    check_and_consume("tiktok", "acct-y")
    with pytest.raises(RateLimitExceeded) as exc_info:
        check_and_consume("tiktok", "acct-y")
    assert exc_info.value.platform == "tiktok"
    assert exc_info.value.retry_after_seconds > 0


def test_separate_accounts_have_independent_buckets(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_TIKTOK", "1:60")
    check_and_consume("tiktok", "a")
    check_and_consume("tiktok", "b")  # different account, must succeed


def test_default_limits_are_known():
    assert "tiktok" in DEFAULT_LIMITS
    assert "youtube" in DEFAULT_LIMITS
    assert "facebook" in DEFAULT_LIMITS
    assert "instagram" in DEFAULT_LIMITS


def test_memory_counter_window_eviction():
    counter = _MemoryCounter()
    import time
    ok, _ = counter.hit("k", max_calls=1, window=1)
    assert ok
    ok2, retry = counter.hit("k", max_calls=1, window=1)
    assert not ok2
    assert retry >= 1
    time.sleep(1.1)
    ok3, _ = counter.hit("k", max_calls=1, window=1)
    assert ok3
