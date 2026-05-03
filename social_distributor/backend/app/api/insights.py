"""Engagement insights + best-time recommendations."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import AccountGroup, PostMetric, PostTarget
from ..utils.best_times import best_times_for_account, best_times_for_group

bp = Blueprint("insights", __name__, url_prefix="/api/insights")


def _serialize_metric(m: PostMetric) -> dict:
    return {
        "fetched_at": m.fetched_at.isoformat() if m.fetched_at else None,
        "reach": m.reach,
        "impressions": m.impressions,
        "likes": m.likes,
        "comments": m.comments,
        "shares": m.shares,
        "saves": m.saves,
        "plays": m.plays,
        "watch_time_seconds": m.watch_time_seconds,
        "avg_view_pct": m.avg_view_pct,
    }


@bp.get("")
def list_insights():
    """Latest snapshot per target, optionally filtered by post_id or group_id."""
    post_id = request.args.get("post_id", type=int)
    group_id = request.args.get("group_id", type=int)

    query = db.session.query(PostTarget).options(joinedload(PostTarget.account))
    if post_id:
        query = query.filter_by(post_id=post_id)
    if group_id:
        group = db.session.get(AccountGroup, group_id)
        if not group:
            return jsonify({"error": "group not found"}), 404
        query = query.filter(PostTarget.account_id.in_([a.id for a in group.accounts]))

    out = []
    for target in query.all():
        latest = (
            db.session.query(PostMetric)
            .filter_by(target_id=target.id)
            .order_by(PostMetric.fetched_at.desc())
            .first()
        )
        if latest is None:
            continue
        out.append({
            "target_id": target.id,
            "post_id": target.post_id,
            "platform": target.account.platform.value,
            "handle": target.account.handle,
            "external_post_id": target.external_post_id,
            "metric": _serialize_metric(latest),
        })
    return jsonify(out)


@bp.get("/best-times")
def best_times():
    account_id = request.args.get("account_id", type=int)
    group_id = request.args.get("group_id", type=int)
    top_n = min(request.args.get("top_n", default=5, type=int), 20)
    min_samples = max(request.args.get("min_samples", default=3, type=int), 1)

    if account_id:
        slots = best_times_for_account(account_id, top_n=top_n, min_samples=min_samples)
    elif group_id:
        slots = best_times_for_group(group_id, top_n=top_n, min_samples=min_samples)
    else:
        return jsonify({"error": "account_id or group_id is required"}), 400

    return jsonify(
        [
            {
                "day": s.day,
                "hour": s.hour,
                "sample_count": s.sample_count,
                "avg_engagement_rate": round(s.avg_engagement_rate, 4),
            }
            for s in slots
        ]
    )
