"""Post composition, versioning, compliance preview, and rollback."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..compliance import ComplianceEngine
from ..extensions import db
from ..models import MediaAsset, Post, PostTarget, SocialAccount
from ..utils.audit import record as audit

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
    findings = ComplianceEngine().evaluate(post, targets)
    db.session.rollback()  # don't persist preview targets

    return jsonify(
        {
            "blocked": ComplianceEngine().has_blockers(findings),
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
