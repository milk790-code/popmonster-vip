"""Celery tasks that drive the publish queue."""
from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytz
from croniter import croniter

from ..compliance import ComplianceEngine
from ..compliance.engine import publisher_request_from
from ..extensions import db
from ..models import JobStatus, MediaAsset, PostMetric, PostTarget, SocialAccount, User
from ..platforms import get_oauth_provider, get_publisher
from ..platforms.base import PlatformError, TokenBundle
from ..utils.events import publish_event
from ..utils.telemetry import add_breadcrumb, trace_dispatch
from ..utils.audit import record as audit
from ..utils.crypto import cipher
from ..utils.notify import notify_publish_failed
from ..utils.rate_limit import RateLimitExceeded, check_and_consume
from ..utils.retry import backoff_seconds
from .celery_app import celery_app

# Per-platform aspect ratio preference (used to pick a transcoded derivative).
_PREFERRED_ASPECT = {
    "facebook": "16:9",
    "instagram": "9:16",
    "tiktok": "9:16",
    "youtube": "16:9",
}

log = logging.getLogger(__name__)


def _decrypt_token(account: SocialAccount) -> TokenBundle:
    c = cipher()
    refresh = (
        c.decrypt(account.refresh_token_enc)
        if account.refresh_token_enc
        else None
    )
    return TokenBundle(
        access_token=c.decrypt(account.access_token_enc),
        refresh_token=refresh,
        expires_at=account.token_expires_at,
        scopes=(account.scopes or "").split(",") if account.scopes else [],
        extra=account.extra or {},
    )


@celery_app.task(bind=True, max_retries=10)
def dispatch_target(self, target_id: int) -> None:
    """Publish a single PostTarget.

    The task takes a row-level lock so two beats can't double-publish a target
    after a worker restart. On retryable errors we use our own exponential
    backoff (see ``utils.retry.backoff_seconds``); on permanent errors we
    record a terminal failure.
    """
    target: PostTarget | None = (
        db.session.query(PostTarget)
        .filter_by(id=target_id)
        .with_for_update(skip_locked=True)
        .one_or_none()
    )
    if target is None:
        return
    if target.status in (
        JobStatus.SUCCEEDED,
        JobStatus.CANCELLED,
        JobStatus.REJECTED_COMPLIANCE,
    ):
        return

    target.status = JobStatus.RUNNING
    target.attempt_count += 1
    db.session.commit()

    add_breadcrumb(
        "dispatch", f"running target #{target.id}",
        target_id=target.id, platform=target.account.platform.value,
        attempt=target.attempt_count,
    )

    findings = ComplianceEngine().evaluate(target.post, [target])
    if ComplianceEngine().has_blockers(findings):
        target.status = JobStatus.REJECTED_COMPLIANCE
        target.last_error = "compliance blocker"
        audit(
            "post.rejected_compliance",
            "post_target",
            target.id,
            actor_user_id=target.post.user_id,
            detail={"findings": [f.detail for f in findings if not f.passed]},
        )
        db.session.commit()
        return

    publisher = get_publisher(target.account.platform)
    request = publisher_request_from(target.post, target)
    _swap_in_preferred_derivative(request, target.post.media, target.account.platform.value)

    try:
        check_and_consume(
            target.account.platform.value, target.account.external_account_id
        )
    except RateLimitExceeded as exc:
        target.status = JobStatus.QUEUED
        target.last_error = str(exc)
        db.session.commit()
        raise self.retry(exc=exc, countdown=exc.retry_after_seconds)

    trace_kwargs = dict(
        target_id=target.id,
        post_id=target.post_id,
        user_id=target.post.user_id,
        platform=target.account.platform.value,
        attempt=target.attempt_count,
    )
    try:
        with trace_dispatch(**trace_kwargs) as span:
            token = _decrypt_token(target.account)
            result = publisher.publish(token, target.account.external_account_id, request)
            if span is not None and result.external_post_id:
                span.set_attribute("external_post_id", result.external_post_id)
    except PlatformError as exc:
        target.last_error = str(exc)
        if exc.retryable and target.attempt_count < self.max_retries:
            target.status = JobStatus.QUEUED
            db.session.commit()
            raise self.retry(exc=exc, countdown=backoff_seconds(target.attempt_count))
        target.status = JobStatus.FAILED
        audit(
            "post.failed",
            "post_target",
            target.id,
            actor_user_id=target.post.user_id,
            detail={"error": str(exc)},
        )
        db.session.commit()
        publish_event(
            target.post.user_id,
            "target.status_changed",
            {
                "target_id": target.id,
                "post_id": target.post_id,
                "status": target.status.value,
                "platform": target.account.platform.value,
                "error": str(exc),
            },
        )
        owner = db.session.get(User, target.post.user_id)
        notify_publish_failed(
            user_email=owner.email if owner else None,
            user_phone=None,
            platform=target.account.platform.value,
            handle=target.account.handle,
            error=str(exc),
            target_id=target.id,
        )
        return

    target.status = JobStatus.SUCCEEDED
    target.external_post_id = result.external_post_id
    target.published_at = datetime.now(timezone.utc)
    target.last_error = None
    audit(
        "post.published",
        "post_target",
        target.id,
        actor_user_id=target.post.user_id,
        detail={
            "platform": target.account.platform.value,
            "external_id": result.external_post_id,
            "permalink": result.permalink,
        },
    )
    db.session.commit()
    publish_event(
        target.post.user_id,
        "target.status_changed",
        {
            "target_id": target.id,
            "post_id": target.post_id,
            "status": target.status.value,
            "platform": target.account.platform.value,
            "external_post_id": target.external_post_id,
            "permalink": result.permalink,
        },
    )


@celery_app.task
def advance_cron_targets() -> None:
    """For cron-recurring targets, ensure we have a single PENDING successor row."""
    now = datetime.now(timezone.utc)
    cron_targets = (
        db.session.query(PostTarget)
        .filter(PostTarget.cron_expr.isnot(None))
        .filter(PostTarget.status.in_([JobStatus.SUCCEEDED, JobStatus.FAILED]))
        .all()
    )
    for parent in cron_targets:
        try:
            tz = pytz.timezone(parent.timezone or "UTC")
        except pytz.UnknownTimeZoneError:
            log.warning("unknown timezone on target %s", parent.id)
            continue
        base = (parent.published_at or now).astimezone(tz)
        next_run = croniter(parent.cron_expr, base).get_next(datetime)
        if next_run.tzinfo is None:
            next_run = tz.localize(next_run)
        next_utc = next_run.astimezone(timezone.utc)

        # Skip if a successor already exists.
        existing = (
            db.session.query(PostTarget)
            .filter_by(post_id=parent.post_id, account_id=parent.account_id,
                       cron_expr=parent.cron_expr, scheduled_for=next_utc)
            .one_or_none()
        )
        if existing:
            continue

        successor = PostTarget(
            post_id=parent.post_id,
            account_id=parent.account_id,
            overrides=parent.overrides,
            cron_expr=parent.cron_expr,
            timezone=parent.timezone,
            scheduled_for=next_utc,
            status=JobStatus.PENDING,
        )
        db.session.add(successor)
    db.session.commit()


@celery_app.task
def sweep_due_targets() -> None:
    """Queue any target whose ``scheduled_for`` has elapsed."""
    now = datetime.now(timezone.utc)
    rows = (
        db.session.query(PostTarget)
        .filter(PostTarget.status == JobStatus.PENDING)
        .filter(PostTarget.scheduled_for.isnot(None))
        .filter(PostTarget.scheduled_for <= now)
        .all()
    )
    for target in rows:
        target.status = JobStatus.QUEUED
        db.session.add(target)
    db.session.commit()
    for target in rows:
        dispatch_target.delay(target.id)


def _swap_in_preferred_derivative(request, media: MediaAsset | None, platform: str) -> None:
    """If the media has a transcoded variant for this platform, use it."""
    if not media or media.kind != "video" or not media.derivatives:
        return
    aspect = _PREFERRED_ASPECT.get(platform)
    if aspect and (url := media.derivatives.get(aspect)):
        request.media_url = url


@celery_app.task
def transcode_media(media_id: int) -> None:
    """Render 16:9 / 9:16 / 1:1 derivatives of a video and store back to S3."""
    from ..utils import ffmpeg as ffmpeg_utils
    from ..utils import storage

    media = db.session.get(MediaAsset, media_id)
    if not media or media.kind != "video":
        return
    bucket = (media.compliance_report or {}).get("s3_bucket")
    key = (media.compliance_report or {}).get("s3_key")
    if not (bucket and key):
        log.warning("media %s has no s3 location; skipping transcode", media_id)
        media.transcode_status = "skipped"
        db.session.commit()
        return

    media.transcode_status = "running"
    db.session.commit()

    derivatives: dict[str, str] = {}
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "src.mp4")
            storage.download_to_file(bucket, key, src)
            for aspect in ffmpeg_utils.ASPECT_PRESETS:
                out_path = os.path.join(tmpdir, f"out_{aspect.replace(':', 'x')}.mp4")
                ffmpeg_utils.transcode(src, out_path, aspect)
                derived_key = f"{key.rsplit('.', 1)[0]}__{aspect.replace(':', 'x')}.mp4"
                storage.upload_file(out_path, bucket, derived_key, "video/mp4")
                derivatives[aspect] = storage.presign_get(bucket, derived_key)
    except Exception as exc:
        log.exception("transcode failed for media %s", media_id)
        media.transcode_status = "failed"
        media.derivatives = {"error": str(exc)[:500]}
        db.session.commit()
        return

    media.derivatives = derivatives
    media.transcode_status = "ready"
    db.session.commit()
    audit(
        "media.transcoded",
        "media_asset",
        media.id,
        actor_user_id=media.user_id,
        detail={"aspects": list(derivatives.keys())},
    )
    db.session.commit()


@celery_app.task
def refresh_oauth_tokens() -> None:
    """Proactively refresh tokens that expire within 24 hours."""
    horizon = datetime.now(timezone.utc) + timedelta(hours=24)
    candidates = (
        db.session.query(SocialAccount)
        .filter(SocialAccount.revoked_at.is_(None))
        .filter(SocialAccount.refresh_token_enc.isnot(None))
        .filter(SocialAccount.token_expires_at.isnot(None))
        .filter(SocialAccount.token_expires_at <= horizon)
        .all()
    )
    c = cipher()
    for account in candidates:
        provider_name = _provider_name_for_platform(account.platform.value)
        if not provider_name:
            continue
        try:
            provider = get_oauth_provider(provider_name)
            refresh_token = c.decrypt(account.refresh_token_enc)
            new_bundle = provider.refresh(refresh_token)
        except NotImplementedError:
            continue
        except Exception as exc:
            log.warning("token refresh failed for account %s: %s", account.id, exc)
            audit(
                "account.refresh_failed", "social_account", account.id,
                actor_user_id=account.user_id, detail={"error": str(exc)[:300]},
            )
            db.session.commit()
            continue

        account.access_token_enc = c.encrypt(new_bundle.access_token)
        if new_bundle.refresh_token:
            account.refresh_token_enc = c.encrypt(new_bundle.refresh_token)
        account.token_expires_at = new_bundle.expires_at
        audit(
            "account.token_refreshed", "social_account", account.id,
            actor_user_id=account.user_id,
            detail={"expires_at": account.token_expires_at.isoformat()
                    if account.token_expires_at else None},
        )
    db.session.commit()


def _provider_name_for_platform(platform_value: str) -> str | None:
    return {
        "facebook": "meta",
        "instagram": "meta",
        "tiktok": "tiktok",
        "youtube": "youtube",
    }.get(platform_value)


@celery_app.task
def ingest_insights() -> None:
    """Pull engagement metrics for recently-published targets.

    Looks back 30 days. Each platform's adapter returns ``None`` for
    unsupported / unauthorised metrics; we silently skip those so a single
    flaky platform doesn't block the rest of the sweep.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    targets = (
        db.session.query(PostTarget)
        .filter(PostTarget.status == JobStatus.SUCCEEDED)
        .filter(PostTarget.external_post_id.isnot(None))
        .filter(PostTarget.published_at.isnot(None))
        .filter(PostTarget.published_at >= cutoff)
        .all()
    )
    fetched = 0
    for target in targets:
        publisher = get_publisher(target.account.platform)
        try:
            token = _decrypt_token(target.account)
            snapshot = publisher.fetch_insights(
                token, target.account.external_account_id, target.external_post_id
            )
        except Exception as exc:  # noqa: BLE001 - one bad target shouldn't kill the sweep
            log.warning("insights fetch failed for target %s: %s", target.id, exc)
            continue
        if snapshot is None:
            continue
        db.session.add(
            PostMetric(
                target_id=target.id,
                reach=snapshot.reach,
                impressions=snapshot.impressions,
                likes=snapshot.likes,
                comments=snapshot.comments,
                shares=snapshot.shares,
                saves=snapshot.saves,
                plays=snapshot.plays,
                watch_time_seconds=snapshot.watch_time_seconds,
                avg_view_pct=snapshot.avg_view_pct,
                raw=snapshot.raw,
            )
        )
        fetched += 1
    db.session.commit()
    log.info("insights ingestion: %d snapshots stored", fetched)
