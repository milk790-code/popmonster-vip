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
