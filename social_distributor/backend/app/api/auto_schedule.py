"""Auto-schedule endpoint: one-click fill today's distribution slots."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..utils.audit import record as audit
from ..utils.auth import current_user_id
from ..utils.auto_schedule_orchestrator import (
    AutoScheduleParams,
    build_today_schedule,
)

bp = Blueprint("auto_schedule", __name__, url_prefix="/api/auto-schedule")


@bp.post("/today")
def auto_schedule_today():
    body = request.get_json(silent=True) or {}
    user_id = current_user_id()
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    try:
        params = AutoScheduleParams(
            user_id=user_id,
            videos_per_account=int(body.get("videos_per_account", 2)),
            posts_per_account=int(body.get("posts_per_account", 2)),
            link=(body.get("link") or "").strip() or None,
            window_start_hour=int(body.get("window_start_hour", 10)),
            window_end_hour=int(body.get("window_end_hour", 22)),
            spacing_minutes_min=int(body.get("spacing_minutes_min", 5)),
            spacing_minutes_max=int(body.get("spacing_minutes_max", 15)),
            platforms=tuple(body.get("platforms") or ("facebook",)),
            timezone=str(body.get("timezone") or "Asia/Taipei"),
            dry_run=bool(body.get("dry_run", False)),
        )
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"invalid params: {e}"}), 400

    if not (0 <= params.window_start_hour < params.window_end_hour <= 24):
        return jsonify({"error": "window_start_hour must be < window_end_hour, both in [0, 24]"}), 400
    if params.videos_per_account < 0 or params.posts_per_account < 0:
        return jsonify({"error": "per-account counts must be non-negative"}), 400
    if (params.videos_per_account + params.posts_per_account) > 20:
        return jsonify({"error": "videos_per_account + posts_per_account must be <= 20"}), 400

    result = build_today_schedule(params)
    if not params.dry_run:
        audit(
            "auto_schedule.created",
            "user",
            user_id,
            actor_user_id=user_id,
            detail={
                "accounts": result["summary"]["accounts"],
                "posts_created": result["summary"]["posts_created"],
                "videos_per_account": params.videos_per_account,
                "posts_per_account": params.posts_per_account,
                "window": [params.window_start_hour, params.window_end_hour],
            },
        )
    return jsonify(result)
