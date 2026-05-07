"""Direct-to-storage upload endpoints.

The browser asks ``/api/uploads/presign`` for a one-shot PUT URL, uploads the
file directly to S3/R2, then registers the resulting object as a
:class:`MediaAsset` via ``/api/uploads/complete``. Completing a video upload
also queues an ffmpeg transcode for the standard aspect ratios.

Deduplication: clients should compute the file's sha256 in the browser
(SubtleCrypto) and:

1. Call ``GET /api/uploads/check?sha256=...&user_id=...`` first. If we
   already have a MediaAsset with that hash, the browser skips the upload
   entirely and reuses ``existing.media_id``.
2. Otherwise call presign + PUT + complete. On ``complete`` we accept
   ``sha256`` and re-check (race-safe): if a MediaAsset with that hash
   already exists, return the existing id and tag the just-uploaded S3
   object as orphaned (caller can delete or leave it for lifecycle policy).
"""
from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import MediaAsset
from ..scheduler.tasks import transcode_media
from ..utils.audit import record as audit
from ..utils.auth import current_user_id
from ..utils.storage import presign_upload

bp = Blueprint("uploads", __name__, url_prefix="/api/uploads")

_EXT = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@bp.get("")
@bp.get("/")
def list_uploads():
    """C4: list this user's media library.

    Query params:
      - ``user_id`` (required, int)
      - ``kind`` (optional: ``image`` or ``video``)
      - ``transcode_status`` (optional: ``done`` / ``pending`` / ``failed`` / ``skipped``)
      - ``since`` / ``until`` (optional ISO 8601)
      - ``limit`` (default 50, max 200), ``offset`` (default 0)
    """
    from datetime import datetime
    user_id = current_user_id()
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    q = db.session.query(MediaAsset).filter(MediaAsset.user_id == user_id)
    if (kind := request.args.get("kind")):
        if kind not in ("image", "video"):
            return jsonify({"error": "kind must be image|video"}), 400
        q = q.filter(MediaAsset.kind == kind)
    if (ts := request.args.get("transcode_status")):
        q = q.filter(MediaAsset.transcode_status == ts)
    for arg, op in (("since", "ge"), ("until", "le")):
        if (val := request.args.get(arg)):
            try:
                dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                return jsonify({"error": f"{arg} must be ISO 8601"}), 400
            q = q.filter(getattr(MediaAsset.created_at, f"__{op}__")(dt))
    limit = min(max(int(request.args.get("limit", 50)), 1), 200)
    offset = max(int(request.args.get("offset", 0)), 0)
    total = q.count()
    items = q.order_by(MediaAsset.created_at.desc()).limit(limit).offset(offset).all()
    return jsonify({
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_serialize_asset(m) for m in items],
    })


def _serialize_asset(m: MediaAsset) -> dict:
    return {
        "id": m.id,
        "kind": m.kind,
        "storage_url": m.storage_url,
        "mime_type": m.mime_type,
        "width": m.width,
        "height": m.height,
        "duration_seconds": m.duration_seconds,
        "sha256": m.sha256,
        "transcode_status": m.transcode_status,
        "derivatives": m.derivatives or {},
        "compliance_status": m.compliance_status,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@bp.get("/check")
def check_dedup():
    """Look up an existing MediaAsset by sha256 to skip re-upload."""
    sha = request.args.get("sha256")
    user_id = current_user_id()
    if not (sha and user_id):
        return jsonify({"error": "sha256 and user_id required"}), 400
    existing = (
        db.session.query(MediaAsset)
        .filter_by(user_id=user_id, sha256=sha)
        .order_by(MediaAsset.created_at.desc())
        .first()
    )
    if existing:
        return jsonify({
            "found": True,
            "media_id": existing.id,
            "kind": existing.kind,
            "transcode_status": existing.transcode_status,
            "storage_url": existing.storage_url,
        })
    return jsonify({"found": False})


@bp.post("/presign")
def presign():
    body = request.get_json(silent=True) or {}
    user_id = current_user_id()
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    kind = body.get("kind")
    content_type = body.get("content_type", "application/octet-stream")
    if kind not in ("video", "image"):
        return jsonify({"error": "kind must be video or image"}), 400

    info = presign_upload(
        user_id,
        kind,
        content_type,
        extension=_EXT.get(content_type, ""),
    )
    return jsonify(
        {
            "bucket": info.bucket,
            "key": info.key,
            "put_url": info.put_url,
            "public_get_url": info.public_get_url,
            "headers": {"Content-Type": content_type},
        }
    )


@bp.post("/complete")
def complete():
    """Browser calls this after a successful PUT to register the asset.

    If ``sha256`` is provided and an existing MediaAsset matches, the upload
    is treated as a duplicate and we return the existing media_id with
    ``deduped: true``. The newly-uploaded S3 object is reported back so the
    caller can decide whether to delete it (we don't, because orphan cleanup
    via S3 lifecycle policies is more reliable than per-request deletes).
    """
    body = request.get_json(silent=True) or {}
    user_id = current_user_id()
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    if not body.get("kind") or not body.get("bucket") or not body.get("key") or not body.get("public_get_url"):
        return jsonify({"error": "kind, bucket, key, public_get_url required"}), 400
    sha = body.get("sha256") or None

    if sha:
        existing = (
            db.session.query(MediaAsset)
            .filter_by(user_id=user_id, sha256=sha)
            .order_by(MediaAsset.created_at.desc())
            .first()
        )
        if existing:
            audit("media.deduped", "media_asset", existing.id,
                  actor_user_id=user_id,
                  detail={"sha256": sha,
                          "orphan_bucket": body.get("bucket"),
                          "orphan_key": body.get("key")})
            db.session.commit()
            return jsonify({
                "id": existing.id,
                "deduped": True,
                "orphan_bucket": body.get("bucket"),
                "orphan_key": body.get("key"),
                "transcode_status": existing.transcode_status,
            }), 200

    media = MediaAsset(
        user_id=user_id,
        kind=body["kind"],
        storage_url=body["public_get_url"],
        mime_type=body.get("content_type", "application/octet-stream"),
        sha256=sha,
        compliance_report={"s3_bucket": body["bucket"], "s3_key": body["key"]},
        transcode_status="pending" if body["kind"] == "video" else "skipped",
    )
    db.session.add(media)
    db.session.commit()
    audit("media.uploaded", "media_asset", media.id,
          actor_user_id=media.user_id,
          detail={"bucket": body["bucket"], "key": body["key"], "sha256": sha})

    if media.kind == "video" and os.environ.get("ENABLE_TRANSCODE", "1") != "0":
        transcode_media.delay(media.id)
    return jsonify({"id": media.id, "deduped": False,
                    "transcode_status": media.transcode_status}), 201
