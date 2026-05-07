"""Video moderation via AWS Rekognition StartContentModeration.

If AWS isn't configured we no-op (returns a single finding flagged ``skipped``);
the engine treats this as a non-blocking informational result so deployments
without AWS can still publish. To use this in anger, give the IAM principal
``rekognition:StartContentModeration`` and ``rekognition:GetContentModeration``
on a bucket containing the video.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover
    boto3 = None
    BotoCoreError = ClientError = Exception

from ..config import config


@dataclass
class VideoFinding:
    passed: bool
    severity: str
    detail: dict


def analyze_video_s3(bucket: str, key: str, *, min_confidence: float = 80.0) -> VideoFinding:
    if boto3 is None:
        return VideoFinding(passed=True, severity="skipped",
                            detail={"reason": "boto3 not installed"})
    try:
        client = boto3.client("rekognition", region_name=config.aws_region)
        start = client.start_content_moderation(
            Video={"S3Object": {"Bucket": bucket, "Name": key}},
            MinConfidence=min_confidence,
        )
        job_id = start["JobId"]
        return _poll(client, job_id)
    except (BotoCoreError, ClientError) as exc:
        return VideoFinding(
            passed=True,
            severity="warn",
            detail={"reason": f"rekognition error: {exc}"},
        )


def _poll(client, job_id: str, *, deadline_seconds: int = 600) -> VideoFinding:
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        result = client.get_content_moderation(JobId=job_id, MaxResults=1000)
        status = result["JobStatus"]
        if status == "SUCCEEDED":
            labels = result.get("ModerationLabels", [])
            high = [
                label for label in labels
                if label.get("ModerationLabel", {}).get("Confidence", 0) >= 90
            ]
            return VideoFinding(
                passed=not high,
                severity="block" if high else "info",
                detail={"labels": labels[:25], "high_confidence_hits": len(high)},
            )
        if status == "FAILED":
            return VideoFinding(
                passed=True,
                severity="warn",
                detail={"reason": result.get("StatusMessage", "rekognition failed")},
            )
        time.sleep(5)
    return VideoFinding(
        passed=True,
        severity="warn",
        detail={"reason": "rekognition polling timed out"},
    )
