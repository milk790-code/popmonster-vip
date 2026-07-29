"""Private Celery worker heartbeat stored in the shared Redis service."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import redis
from celery import shared_task
from celery.signals import worker_ready

from ..config import config

log = logging.getLogger(__name__)
HEARTBEAT_KEY = "social_distributor:worker:heartbeat"
HEARTBEAT_TTL_SECONDS = 180


def _redis():
    return redis.from_url(config.redis_url, decode_responses=True)


def write_worker_heartbeat(*, now: datetime | None = None) -> dict:
    observed_at = now or datetime.now(timezone.utc)
    payload = {
        "component": "worker",
        "status": "ok",
        "observed_at": observed_at.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "release": os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or os.environ.get("RELEASE_VERSION")
        or "unknown",
    }
    _redis().set(
        HEARTBEAT_KEY,
        json.dumps(payload, separators=(",", ":")),
        ex=HEARTBEAT_TTL_SECONDS,
    )
    return payload


@shared_task(name="app.scheduler.worker_heartbeat.emit")
def emit_worker_heartbeat() -> dict:
    return write_worker_heartbeat()


@worker_ready.connect
def emit_worker_ready_heartbeat(**_kwargs) -> None:
    try:
        write_worker_heartbeat()
    except Exception as exc:  # noqa: BLE001
        log.error("worker heartbeat bootstrap failed: %s", exc)
