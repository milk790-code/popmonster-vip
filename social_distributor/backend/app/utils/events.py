"""Tiny Redis pub/sub event bus used to push status changes to the dashboard.

If Redis isn't reachable we silently no-op; the dashboard then falls back to
periodic polling. This keeps event publishing safe to call from anywhere
(workers, request handlers) without conditional checks at every callsite.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Iterator

log = logging.getLogger(__name__)

CHANNEL_PREFIX = "distributor:events"


def _channel(user_id: int) -> str:
    return f"{CHANNEL_PREFIX}:{user_id}"


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
        log.warning("events: redis unavailable, publish disabled: %s", exc)
        _redis_client = None
    return _redis_client


def publish_event(user_id: int, event_type: str, payload: dict) -> None:
    client = _redis()
    if client is None:
        return
    body = json.dumps(
        {"type": event_type, "ts": time.time(), "payload": payload},
        ensure_ascii=False,
    )
    try:
        client.publish(_channel(user_id), body)
    except Exception as exc:
        log.warning("events: publish failed: %s", exc)


def subscribe(user_id: int) -> Iterator[str]:
    """Yield SSE-formatted lines for a user's event stream.

    Sends a heartbeat comment every 15s so proxies and clients keep the
    connection open even when no real events flow.
    """
    client = _redis()
    if client is None:
        # No Redis → tell the caller once, then close.
        yield "event: noop\ndata: {\"reason\":\"redis unavailable; poll instead\"}\n\n"
        return

    pubsub = client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(_channel(user_id))
    try:
        last_heartbeat = time.time()
        while True:
            message = pubsub.get_message(timeout=1.0)
            if message and message["type"] == "message":
                yield f"data: {message['data']}\n\n"
            now = time.time()
            if now - last_heartbeat > 15:
                yield ": heartbeat\n\n"
                last_heartbeat = now
    finally:
        try:
            pubsub.close()
        except Exception:
            pass
