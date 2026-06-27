"""Post composition, versioning, compliance preview, and rollback."""
from __future__ import annotations

from datetime import datetime, timezone

import pytz
from flask import Blueprint, jsonify, request

from ..compliance import ComplianceEngine
from ..extensions import db
from ..models import (
    AccountGroup,
    JobStatus,
    MediaAsset,
    Post,
    PostTarget,
    SocialAccount,
)
from ..scheduler import dispatch_target
from ..utils.audit import record as audit
from ..utils.auth import current_user_id
from ..utils.best_times import next_best_time_for_group
from ..utils.jitter import spread
from ..utils.variants import VariantRequest, generate_variant

bp = Blueprint("posts", __name__, url_prefix="/api/posts")


def _load_owned_post(post_id: int):
    """Return (post, None) if the post belongs to the logged-in user.

    Returns (None, response) otherwise: 404 if the post doesn't exist, 403 if
    it belongs to another user. Prevents cross-tenant IDOR on every post route.
    """
    post = db.session.get(Post, post_id)
    if not post:
        return None, (jsonify({"error": "not found"}), 404)
    if post.user_id != current_user_id():
        return None, (jsonify({"error": "forbidden"}), 403)
    return post, None


def _serialize_post(post: Post) -> dict:
    return {
        "id": post.id,
        "user_id": post.user_id,
        "title": post.title,
        "caption": post.caption,
        "link_url": post.link_url,
        "media_id": post.media_id,
        "version": post.version,
        "parent_post_id": post.parent_post_id,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "targets": [
            {
                "id": t.id,
                "account_id": t.account_id,
                "platform": t.account.platform.value,
                "status": t.status.value,
                "scheduled_for": t.scheduled_for.isoformat() if t.scheduled_for else None,
                "cron_expr": t.cron_expr,
                "timezone": t.timezone,
                "external_post_id": t.external_post_id,
                "last_error": t.last_error,
                "overrides": t.overrides,
            }
            for t in post.targets
        ],
    }


@bp.post("")
def create_post():
    """Create a draft post. Targets are added separately via /schedules."""
    body = request.get_json(force=True)
    user_id = current_user_id()
    media_id = body.get("media_id")
    if media_id:
        media = db.session.get(MediaAsset, media_id)
        if not media:
            return jsonify({"error": "unknown media_id"}), 400
        if media.user_id != user_id:
            return jsonify({"error": "forbidden"}), 403

    post = Post(
        user_id=user_id,
        title=body.get("title", ""),
        caption=body.get("caption", ""),
        link_url=body.get("link_url"),
        media_id=media_id,
    )
    db.session.add(post)
    db.session.flush()
    audit("post.created", "post", post.id, actor_user_id=user_id)
    db.session.commit()
    return jsonify(_serialize_post(post)), 201


@bp.get("/<int:post_id>")
def get_post(post_id: int):
    post, err = _load_owned_post(post_id)
    if err:
        return err
    return jsonify(_serialize_post(post))


@bp.put("/<int:post_id>")
def update_post(post_id: int):
    """Mutating a post creates a new version pointing at the previous one.

    This gives the rollback endpoint something to revert to.
    """
    post, err = _load_owned_post(post_id)
    if err:
        return err
    body = request.get_json(force=True)

    revision = Post(
        user_id=post.user_id,
        title=body.get("title", post.title),
        caption=body.get("caption", post.caption),
        link_url=body.get("link_url", post.link_url),
        media_id=body.get("media_id", post.media_id),
        version=post.version + 1,
        parent_post_id=post.id,
    )
    db.session.add(revision)
    db.session.flush()
    audit(
        "post.revised",
        "post",
        revision.id,
        actor_user_id=post.user_id,
        detail={"from_version": post.version, "to_version": revision.version},
    )
    db.session.commit()
    return jsonify(_serialize_post(revision))


@bp.post("/<int:post_id>/rollback")
def rollback(post_id: int):
    """Roll back to the previous version of the post."""
    post, err = _load_owned_post(post_id)
    if err:
        return err
    if not post.parent_post_id:
        return jsonify({"error": "no parent version"}), 400
    parent = db.session.get(Post, post.parent_post_id)
    revision = Post(
        user_id=parent.user_id,
        title=parent.title,
        caption=parent.caption,
        link_url=parent.link_url,
        media_id=parent.media_id,
        version=post.version + 1,
        parent_post_id=post.id,
    )
    db.session.add(revision)
    db.session.flush()
    audit(
        "post.rolled_back",
        "post",
        revision.id,
        actor_user_id=parent.user_id,
        detail={"reverted_to_version": parent.version},
    )
    db.session.commit()
    return jsonify(_serialize_post(revision))


@bp.get("/<int:post_id>/diff/<int:other_id>")
def diff_post(post_id: int, other_id: int):
    """Multi-platform / cross-version diff helper."""
    a, err = _load_owned_post(post_id)
    if err:
        return err
    b, err = _load_owned_post(other_id)
    if err:
        return err
    diff = {
        field: {"a": getattr(a, field), "b": getattr(b, field)}
        for field in ("title", "caption", "link_url", "media_id")
        if getattr(a, field) != getattr(b, field)
    }
    return jsonify({"a": a.id, "b": b.id, "diff": diff})


@bp.post("/<int:post_id>/preview-compliance")
def preview_compliance(post_id: int):
    """Run the compliance engine without scheduling the publish."""
    post, err = _load_owned_post(post_id)
    if err:
        return err

    body = request.get_json(silent=True) or {}
    account_ids: list[int] = body.get("account_ids", [])
    # IDOR guard: only the caller's own accounts may be referenced.
    accounts = (
        db.session.query(SocialAccount)
        .filter(
            SocialAccount.id.in_(account_ids),
            SocialAccount.user_id == current_user_id(),
        )
        .all()
        if account_ids
        else []
    )
    if account_ids and len(accounts) != len(set(account_ids)):
        return jsonify({"error": "one or more account_ids not found"}), 404
    targets = [
        PostTarget(
            post=post,
            account=a,
            overrides=body.get("overrides", {}),
        )
        for a in accounts
    ]
    # A3 + A4: shared engine instance, no DB writes for preview.
    engine = ComplianceEngine()
    findings = engine.evaluate(post, targets, persist=False)
    db.session.rollback()  # transient targets are still on the session

    return jsonify(
        {
            "blocked": engine.has_blockers(findings),
            "findings": [
                {
                    "checker": f.checker,
                    "passed": f.passed,
                    "severity": f.severity,
                    "detail": f.detail,
                }
                for f in findings
            ],
        }
    )


@bp.post("/<int:post_id>/distribute")
def distribute(post_id: int):
    """Fan a post out to one or more account groups.

    Body::

        {
          "group_ids": [1, 2, 3],
          "scheduled_for": "2026-05-04T09:00:00",  // optional ISO 8601
          "timezone": "Asia/Taipei",
          "jitter_minutes": 30,                     // spread starts across window
          "generate_variants": true,                // per-group/per-platform rewriting
          "dry_run": false
        }
    """
    post, err = _load_owned_post(post_id)
    if err:
        return err
    body = request.get_json(force=True) or {}

    group_ids: list[int] = body.get("group_ids", [])
    if not group_ids:
        return jsonify({"error": "group_ids is required"}), 400

    # IDOR guard: only fan out to the caller's own account groups.
    groups = (
        db.session.query(AccountGroup)
        .filter(
            AccountGroup.id.in_(group_ids),
            AccountGroup.user_id == current_user_id(),
        )
        .all()
    )
    if len(groups) != len(set(group_ids)):
        return jsonify({"error": "one or more group_ids not found"}), 400

    tz_name = body.get("timezone", "UTC")
    use_best_time = bool(body.get("use_best_time", False))
    best_time_used: dict[int, str] = {}

    # Best time is per-group, so we compute per group below. ``base`` is
    # only used as the fallback when a group has no data yet.
    base = _parse_when(body.get("scheduled_for"), tz_name) or datetime.now(timezone.utc)

    jitter = max(0, int(body.get("jitter_minutes", 0)))
    do_variants = bool(body.get("generate_variants", False))
    referral_code: str | None = body.get("referral_code") or None
    dry_run = bool(body.get("dry_run", False))

    # B7: validate caller-provided overrides against the platform whitelist.
    # We validate against every member platform in the selected groups, since
    # the same overrides apply uniformly. (Per-platform overrides can be
    # added later via a nested dict.)
    body_overrides = body.get("overrides", {})
    if body_overrides:
        from ..utils.overrides import validate_overrides
        platforms_in_groups = {
            a.platform.value for g in groups for a in g.accounts
        }
        for plat in platforms_in_groups:
            errors = validate_overrides(plat, body_overrides)
            if errors:
                return jsonify({
                    "error": "invalid overrides",
                    "platform": plat,
                    "details": errors,
                }), 400

    plan: list[dict] = []
    created_ids: list[int] = []

    for group in groups:
        active_accounts = [a for a in group.accounts if a.revoked_at is None]
        if not active_accounts:
            continue

        group_base = base
        if use_best_time:
            suggested = next_best_time_for_group(group.id)
            if suggested is not None:
                group_base = suggested
                best_time_used[group.id] = "learned"
            else:
                best_time_used[group.id] = "fallback_no_data"

        seed = f"distribute:{post.id}:group:{group.id}:{group_base.isoformat()}"
        starts = spread(group_base, jitter, seed, len(active_accounts))

        for account, when in zip(active_accounts, starts):
            overrides: dict = {}
            engine_used = "none"
            if do_variants:
                req = VariantRequest(
                    source_caption=post.caption,
                    source_title=post.title,
                    platform=account.platform.value,
                    style_profile=group.style_profile or {},
                    seed=f"{seed}:{account.id}",
                    referral_code=referral_code,
                )
                result = generate_variant(req)
                overrides["caption"] = result.caption
                overrides["title"] = result.title
                engine_used = result.used_engine

            entry = {
                "group_id": group.id,
                "group_name": group.name,
                "account_id": account.id,
                "platform": account.platform.value,
                "handle": account.handle,
                "scheduled_for": when.isoformat(),
                "variant_engine": engine_used,
                "preview_caption": overrides.get("caption", post.caption)[:200],
            }
            plan.append(entry)

            if not dry_run:
                target = PostTarget(
                    post_id=post.id,
                    account_id=account.id,
                    group_id=group.id,
                    overrides=overrides,
                    timezone=tz_name,
                    scheduled_for=when,
                    status=JobStatus.PENDING,
                )
                db.session.add(target)
                db.session.flush()
                created_ids.append(target.id)

    if not dry_run:
        audit(
            "post.distributed",
            "post",
            post.id,
            actor_user_id=post.user_id,
            detail={
                "group_ids": group_ids,
                "target_count": len(created_ids),
                "jitter_minutes": jitter,
                "variants": do_variants,
            },
        )
        db.session.commit()
        # Immediately queue any targets whose dispatch time has already passed.
        now = datetime.now(timezone.utc)
        for tid in created_ids:
            t = db.session.get(PostTarget, tid)
            if not t:
                continue
            scheduled = t.scheduled_for
            if scheduled is not None and scheduled.tzinfo is None:
                scheduled = scheduled.replace(tzinfo=timezone.utc)
            if scheduled is not None and scheduled <= now:
                t.status = JobStatus.QUEUED
                db.session.commit()
                dispatch_target.delay(tid)

    return jsonify(
        {
            "dry_run": dry_run,
            "created_target_ids": created_ids,
            "plan": plan,
            "best_time_used": best_time_used,
        }
    ), (200 if dry_run else 201)


def _parse_when(raw: str | None, tz_name: str):
    if not raw:
        return None
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = pytz.timezone(tz_name).localize(dt)
    return dt.astimezone(timezone.utc)


@bp.post("/media")
def create_media():
    body = request.get_json(force=True)
    media = MediaAsset(
        user_id=current_user_id(),
        kind=body["kind"],
        storage_url=body["storage_url"],
        mime_type=body.get("mime_type", "application/octet-stream"),
        width=body.get("width"),
        height=body.get("height"),
        duration_seconds=body.get("duration_seconds"),
        sha256=body.get("sha256"),
        compliance_report={
            "s3_bucket": body.get("s3_bucket"),
            "s3_key": body.get("s3_key"),
        },
    )
    db.session.add(media)
    db.session.commit()
    return jsonify({"id": media.id}), 201
