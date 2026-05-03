"""Direct-to-storage upload endpoints.

The browser asks ``/api/uploads/presign`` for a one-shot PUT URL, uploads the
file directly to S3/R2, then registers the resulting object as a
:class:`MediaAsset` via ``/api/uploads/complete``. Completing a video upload
also queues an ffmpeg transcode for the standard aspect ratios.
"""
from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import MediaAsset
from ..scheduler.tasks import transcode_media
from ..utils.audit import record as audit
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


@bp.post("/presign")
def presign():
    body = request.get_json(force=True)
    user_id = int(body["user_id"])
    kind = body["kind"]
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
    """Browser calls this after a successful PUT to register the asset."""
    body = request.get_json(force=True)
    media = MediaAsset(
        user_id=int(body["user_id"]),
        kind=body["kind"],
        storage_url=body["public_get_url"],
        mime_type=body.get("content_type", "application/octet-stream"),
        compliance_report={"s3_bucket": body["bucket"], "s3_key": body["key"]},
        transcode_status="pending" if body["kind"] == "video" else "skipped",
    )
    db.session.add(media)
    db.session.commit()
    audit("media.uploaded", "media_asset", media.id,
          actor_user_id=media.user_id,
          detail={"bucket": body["bucket"], "key": body["key"]})

    if media.kind == "video" and os.environ.get("ENABLE_TRANSCODE", "1") != "0":
        transcode_media.delay(media.id)
    return jsonify({"id": media.id, "transcode_status": media.transcode_status}), 201
