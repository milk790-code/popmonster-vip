"""Scheduling endpoints: attach platforms to a post and queue dispatch."""
from __future__ import annotations

from datetime import datetime, timezone

import pytz
from croniter import croniter
from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import JobStatus, Post, PostTarget, SocialAccount
from ..scheduler import dispatch_target
from ..utils.audit import record as audit
from ..utils.auth import current_user_id

bp = Blueprint("schedules", __name__, url_prefix="/api/schedules")


def _parse_when(when: str | None, tz_name: str) -> datetime | None:
    if not when:
        return None
    dt = datetime.fromisoformat(when)
    if dt.tzinfo is None:
        dt = pytz.timezone(tz_name).localize(dt)
    return dt.astimezone(timezone.utc)


@bp.post("")
def create_schedule():
    """Body: {post_id, items: [{account_id, scheduled_for?, cron?, timezone?, overrides?}]}"""
    body = request.get_json(force=True)
    post = db.session.get(Post, body["post_id"])
    if not post:
        return jsonify({"error": "post not found"}), 404
    if post.user_id != current_user_id():
        return jsonify({"error": "forbidden"}), 403

    from ..utils.overrides import validate_overrides

    created: list[int] = []
    for item in body.get("items", []):
        account = db.session.get(SocialAccount, item["account_id"])
        if not account or account.revoked_at is not None:
            return jsonify({"error": f"account {item['account_id']} not connected"}), 400
        # IDOR guard: only schedule onto the caller's own accounts.
        if account.user_id != current_user_id():
            return jsonify({"error": "forbidden"}), 403

        # B7: per-target overrides validated against the account's platform.
        item_overrides = item.get("overrides", {})
        if item_overrides:
            errors = validate_overrides(account.platform.value, item_overrides)
            if errors:
                return jsonify({
                    "error": "invalid overrides",
                    "account_id": account.id,
                    "platform": account.platform.value,
                    "details": errors,
                }), 400

        tz_name = item.get("timezone", "UTC")
        cron_expr = item.get("cron")
        if cron_expr and not croniter.is_valid(cron_expr):
            return jsonify({"error": f"invalid cron expression: {cron_expr}"}), 400

        scheduled_for = _parse_when(item.get("scheduled_for"), tz_name)
        if cron_expr and scheduled_for is None:
            tz = pytz.timezone(tz_name)
            scheduled_for = (
                croniter(cron_expr, datetime.now(tz)).get_next(datetime).astimezone(timezone.utc)
            )

        target = PostTarget(
            post_id=post.id,
            account_id=account.id,
            overrides=item_overrides,
            cron_expr=cron_expr,
            timezone=tz_name,
            scheduled_for=scheduled_for,
            status=JobStatus.PENDING,
        )
        db.session.add(target)
        db.session.flush()
        created.append(target.id)

        if scheduled_for is None:
            target.status = JobStatus.QUEUED
            db.session.flush()
            dispatch_target.delay(target.id)
        audit(
            "schedule.created",
            "post_target",
            target.id,
            actor_user_id=post.user_id,
            detail={
                "platform": account.platform.value,
                "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
                "cron": cron_expr,
            },
        )
    db.session.commit()
    return jsonify({"created_target_ids": created}), 201


@bp.get("")
def list_schedules():
    # Always scope to the logged-in user's accounts.
    query = (
        db.session.query(PostTarget)
        .join(SocialAccount)
        .filter(SocialAccount.user_id == current_user_id())
    )
    rows = query.order_by(PostTarget.scheduled_for.is_(None), PostTarget.scheduled_for).all()
    return jsonify(
        [
            {
                "id": t.id,
                "post_id": t.post_id,
                "platform": t.account.platform.value,
                "handle": t.account.handle,
                "status": t.status.value,
                "scheduled_for": t.scheduled_for.isoformat() if t.scheduled_for else None,
                "cron": t.cron_expr,
                "timezone": t.timezone,
                "attempt_count": t.attempt_count,
                "last_error": t.last_error,
                "external_post_id": t.external_post_id,
                "published_at": t.published_at.isoformat() if t.published_at else None,
            }
            for t in rows
        ]
    )


@bp.post("/<int:target_id>/cancel")
def cancel_target(target_id: int):
    target = db.session.get(PostTarget, target_id)
    if not target:
        return jsonify({"error": "not found"}), 404
    if target.post.user_id != current_user_id():
        return jsonify({"error": "forbidden"}), 403
    if target.status in (JobStatus.SUCCEEDED, JobStatus.RUNNING):
        return jsonify({"error": f"cannot cancel from {target.status.value}"}), 409
    target.status = JobStatus.CANCELLED
    audit("schedule.cancelled", "post_target", target.id,
          actor_user_id=target.post.user_id)
    db.session.commit()
    return jsonify({"cancelled": target_id})


@bp.post("/<int:target_id>/retry")
def retry_target(target_id: int):
    target = db.session.get(PostTarget, target_id)
    if not target:
        return jsonify({"error": "not found"}), 404
    if target.post.user_id != current_user_id():
        return jsonify({"error": "forbidden"}), 403
    if target.status != JobStatus.FAILED:
        return jsonify({"error": "only failed targets can be retried"}), 409
    target.status = JobStatus.QUEUED
    target.last_error = None
    db.session.commit()
    dispatch_target.delay(target.id)
    audit("schedule.retried", "post_target", target.id,
          actor_user_id=target.post.user_id)
    return jsonify({"requeued": target_id})
