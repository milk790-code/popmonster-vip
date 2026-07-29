"""Authenticated system state derived from private infrastructure."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import redis
from flask import Blueprint, jsonify

from ..config import config
from ..scheduler.worker_heartbeat import HEARTBEAT_KEY

bp = Blueprint("system", __name__, url_prefix="/api/system")
MAX_HEARTBEAT_AGE_SECONDS = 120


def _redis():
    return redis.from_url(config.redis_url, decode_responses=True)


@bp.get("/worker-heartbeat")
def worker_heartbeat():
    payload, status_code = read_worker_heartbeat()
    return jsonify(payload), status_code


def read_worker_heartbeat():
    try:
        raw = _redis().get(HEARTBEAT_KEY)
        payload = json.loads(raw) if raw else None
        observed_at = datetime.fromisoformat(
            payload["observed_at"].replace("Z", "+00:00")
        )
        age_seconds = max(
            0, int((datetime.now(timezone.utc) - observed_at).total_seconds())
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, redis.RedisError):
        return {
            "component": "worker",
            "status": "unavailable",
            "fresh": False,
        }, 503

    fresh = payload.get("status") == "ok" and age_seconds <= MAX_HEARTBEAT_AGE_SECONDS
    response = {
        "component": "worker",
        "status": "ok" if fresh else "stale",
        "fresh": fresh,
        "observed_at": payload["observed_at"],
        "age_seconds": age_seconds,
        "release": payload.get("release", "unknown"),
    }
    return response, 200 if fresh else 503
