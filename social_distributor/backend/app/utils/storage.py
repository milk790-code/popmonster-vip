"""S3-compatible object storage (works with AWS S3, Cloudflare R2, MinIO).

Presigned URLs let the browser PUT directly without proxying through the API
server, and let downstream platforms (FB/IG/YouTube) GET media without us
exposing a public bucket. Defaults to AWS but accepts an ``S3_ENDPOINT_URL``
override for R2 etc.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import boto3
from botocore.config import Config as BotoConfig

_DEFAULT_GET_TTL = 7 * 24 * 3600  # 7 days = S3 max for SigV4 presigned URLs
_DEFAULT_PUT_TTL = 60 * 30


@dataclass
class PresignedUpload:
    bucket: str
    key: str
    put_url: str
    public_get_url: str


def _client():
    endpoint = os.environ.get("S3_ENDPOINT_URL") or None
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        config=BotoConfig(signature_version="s3v4"),
    )


def media_bucket() -> str:
    bucket = os.environ.get("MEDIA_BUCKET")
    if not bucket:
        raise RuntimeError("MEDIA_BUCKET env var is required for uploads")
    return bucket


def presign_upload(
    user_id: int,
    kind: str,
    content_type: str,
    *,
    extension: str = "",
    put_ttl: int = _DEFAULT_PUT_TTL,
    get_ttl: int = _DEFAULT_GET_TTL,
) -> PresignedUpload:
    bucket = media_bucket()
    key = f"users/{user_id}/{kind}/{uuid.uuid4().hex}{extension}"
    s3 = _client()
    put_url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=put_ttl,
    )
    get_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=get_ttl,
    )
    return PresignedUpload(bucket=bucket, key=key, put_url=put_url, public_get_url=get_url)


def presign_get(bucket: str, key: str, ttl: int = _DEFAULT_GET_TTL) -> str:
    return _client().generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=ttl
    )


def download_to_file(bucket: str, key: str, path: str) -> None:
    _client().download_file(bucket, key, path)


def upload_file(path: str, bucket: str, key: str, content_type: str) -> None:
    _client().upload_file(
        path, bucket, key, ExtraArgs={"ContentType": content_type}
    )


def derivative_key(base_key: str, aspect: str) -> str:
    """Deterministic object key for a transcoded variant.

    Shared so the transcoder and the dispatcher cannot drift: the dispatcher
    has to rebuild this key to re-sign a derivative at send time, and a
    mismatch would silently fall back to the expired URL.
    """
    return f"{base_key.rsplit('.', 1)[0]}__{aspect.replace(':', 'x')}.mp4"


def fresh_media_url(media, aspect: str | None = None) -> str | None:
    """A presigned URL valid *now* for this asset, or None if we can't sign one.

    ``MediaAsset.storage_url`` and every entry in ``MediaAsset.derivatives``
    hold presigned URLs, which SigV4 caps at 7 days. Storing them and reusing
    them later is the bug this exists to fix: any post scheduled more than a
    week out fetches a dead URL and fails with a 403 that looks like a
    permissions problem. The durable reference (bucket + key) is already kept
    in ``compliance_report``, so we re-sign instead of replaying.

    Falls back to the stored URL when there is no bucket/key — media can also
    arrive as an external URL (rebroadcast candidates), and those are not ours
    to sign.
    """
    if media is None:
        return None
    report = media.compliance_report or {}
    bucket, key = report.get("s3_bucket"), report.get("s3_key")
    stored = (media.derivatives or {}).get(aspect) if aspect else media.storage_url
    if not (bucket and key):
        return stored
    if aspect:
        # Only re-sign a derivative we know was actually produced.
        if not (media.derivatives or {}).get(aspect):
            return None
        key = derivative_key(key, aspect)
    try:
        return presign_get(bucket, key)
    except Exception:  # noqa: BLE001 - signing must never break a dispatch
        return stored
