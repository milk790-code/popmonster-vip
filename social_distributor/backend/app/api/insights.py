"""Engagement insights + best-time recommendations."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import AccountGroup, PostMetric, PostTarget, SocialAccount
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


def _latest_metric_by_target(target_ids: list[int]) -> dict[int, PostMetric]:
    """每個 target 的最新一筆 metric,一條查詢(Postgres DISTINCT ON)。取代 N+1。"""
    if not target_ids:
        return {}
    rows = (
        db.session.query(PostMetric)
        .filter(PostMetric.target_id.in_(target_ids))
        .order_by(PostMetric.target_id, PostMetric.fetched_at.desc())
        .distinct(PostMetric.target_id)  # DISTINCT ON (target_id) → 每 target 一列(最新)
        .all()
    )
    return {m.target_id: m for m in rows}


@bp.get("")
def list_insights():
    """Latest snapshot per target. 篩選優先序:post_id > group_id > user_id(預設 1)。

    根治 30s timeout:① 一律按 user 邊界,不裸掃全表 ② LIMIT 上界
    ③ 用 DISTINCT ON 一條查詢補最新 metric,殺掉原本的 N+1。
    """
    post_id = request.args.get("post_id", type=int)
    group_id = request.args.get("group_id", type=int)
    user_id = request.args.get("user_id", type=int)

    query = db.session.query(PostTarget).options(joinedload(PostTarget.account))
    if post_id:
        query = query.filter_by(post_id=post_id)
    elif group_id:
        group = db.session.get(AccountGroup, group_id)
        if not group:
            return jsonify({"error": "group not found"}), 404
        query = query.filter(
            PostTarget.account_id.in_([a.id for a in group.accounts])
        )
    else:
        # ★ 根治關鍵:一律按 user 邊界,絕不裸掃全表。
        uid = user_id or 1  # 現役單 user;多 user 時改:uid = current_user.id
        query = query.join(
            SocialAccount, PostTarget.account_id == SocialAccount.id
        ).filter(SocialAccount.user_id == uid)

    targets = query.order_by(PostTarget.id.desc()).limit(200).all()
    latest_by_target = _latest_metric_by_target([t.id for t in targets])

    out = []
    for target in targets:
        latest = latest_by_target.get(target.id)
        if latest is None:
            continue
        out.append(
            {
                "target_id": target.id,
                "post_id": target.post_id,
                "platform": target.account.platform.value,
                "handle": target.account.handle,
                "external_post_id": target.external_post_id,
                "metric": _serialize_metric(latest),
            }
        )
    return jsonify(out)


@bp.get("/digest/preview")
def digest_preview():
    """C5: render the weekly digest for a user as JSON, no email sent."""
    from ..utils.digest import build_user_digest, _ts_dict

    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    digest = build_user_digest(user_id, days=int(request.args.get("days", 7)))
    if digest is None:
        return jsonify({"error": "user not found"}), 404
    return jsonify(
        {
            "user_id": digest.user_id,
            "since": digest.since.isoformat(),
            "until": digest.until.isoformat(),
            "total_published": digest.total_published,
            "total_reach": digest.total_reach,
            "total_engagement": digest.total_engagement,
            "avg_rate": round(digest.avg_rate, 4),
            "best": _ts_dict(digest.best),
            "worst": _ts_dict(digest.worst),
            "emoji_vs_plain": digest.emoji_vs_plain,
            "ab_winners": digest.ab_winners,
            "narrative": digest.narrative,
        }
    )


@bp.post("/digest/send")
def digest_send():
    """Send the digest immediately to one user."""
    from ..utils.digest import build_user_digest, _format_email_body
    from ..utils.notify import send_failure_email
    from ..config import config

    body_in = request.get_json(silent=True) or {}
    user_id = body_in.get("user_id") or request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    digest = build_user_digest(int(user_id))
    if digest is None:
        return jsonify({"error": "user not found"}), 404
    if not digest.has_data():
        return jsonify({"sent": False, "reason": "no published posts in window"})
    will_actually_send = bool(config.sendgrid_api_key and config.notify_email_from)
    send_failure_email(
        to=[digest.user_email],
        subject=f"📈 Weekly insights — {digest.total_published} posts, "
        f"{digest.total_engagement:,} engagement",
        body=_format_email_body(digest),
    )
    return jsonify(
        {
            "sent": will_actually_send,
            "to": digest.user_email,
            "narrative_preview": digest.narrative[:200],
        }
    )


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
