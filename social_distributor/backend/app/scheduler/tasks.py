"""Celery tasks that drive the publish queue."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytz
from croniter import croniter

from ..compliance import ComplianceEngine
from ..compliance.engine import publisher_request_from
from ..extensions import db
from ..models import JobStatus, PostTarget, SocialAccount
from ..platforms import get_publisher
from ..platforms.base import PlatformError, TokenBundle
from ..utils.audit import record as audit
from ..utils.crypto import cipher
from ..utils.retry import backoff_seconds
from .celery_app import celery_app

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
    try:
        token = _decrypt_token(target.account)
        result = publisher.publish(token, target.account.external_account_id, request)
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
