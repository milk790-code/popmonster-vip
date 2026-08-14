"""Celery tasks that drive the publish queue."""
from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytz
from croniter import croniter

from ..compliance import ComplianceEngine
from ..compliance.engine import publisher_request_from, target_media_asset
from ..extensions import db
from ..models import (
    AuditLog, JobStatus, MediaAsset, Platform, PostMetric, PostTarget,
    SocialAccount, TokenExpiryAlert, User,
)
from ..platforms import get_oauth_provider, get_publisher
from ..platforms._http import clear_proxy, set_proxy
from ..platforms.base import PlatformError, TokenBundle
from ..utils import boost as boost_rules
from ..utils.account_profile import read_profile
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

    The whole body is wrapped in a final ``try/except`` (A2): an unexpected
    crash (decrypt failure, AttributeError on a malformed model row, etc.)
    used to leave the row stuck in ``RUNNING`` forever — Celery's own retry
    semantics never fire for non-Celery exceptions raised before the publish
    step. We now always flip to FAILED and audit ``dispatch.uncaught`` so the
    Status board surfaces the row instead of silently hanging.
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

    try:
        _dispatch_body(self, target)
    except Exception as exc:  # noqa: BLE001 - last-resort guard for A2
        if isinstance(exc, self.retry.__self__.MaxRetriesExceededError if hasattr(self.retry, "__self__") else type(None)):
            raise
        # Celery's self.retry() raises Retry() to schedule the next attempt;
        # don't swallow that — let it propagate so Celery does its thing.
        from celery.exceptions import Retry
        if isinstance(exc, Retry):
            raise
        log.exception("dispatch_target uncaught exception target_id=%s", target.id)
        target.status = JobStatus.FAILED
        target.last_error = f"uncaught: {type(exc).__name__}: {str(exc)[:300]}"
        audit(
            "dispatch.uncaught",
            "post_target",
            target.id,
            actor_user_id=target.post.user_id,
            detail={"error_type": type(exc).__name__, "error": str(exc)[:500]},
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
                "error": target.last_error,
            },
        )


def _dispatch_body(self, target: PostTarget) -> None:
    """Body of dispatch_target, factored out so A2's outer try/except is clean."""
    engine = ComplianceEngine()
    findings = engine.evaluate(target.post, [target])
    if engine.has_blockers(findings):
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
    _swap_in_preferred_derivative(
        request, target_media_asset(target.post, target), target.account.platform.value
    )

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
    set_proxy((target.account.extra or {}).get("proxy_url"))
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
    finally:
        clear_proxy()

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
    # The first comment is where the funnel link lives, so "did it post?"
    # has to be answerable without reading worker logs. Only recorded when
    # a comment was actually attempted.
    if result.first_comment_id or result.first_comment_error:
        audit(
            "post.first_comment" if result.first_comment_id
            else "post.first_comment_failed",
            "post_target",
            target.id,
            actor_user_id=target.post.user_id,
            detail={
                "comment_id": result.first_comment_id,
                "error": result.first_comment_error,
            },
        )
    # Which surface a video landed on decides whether anyone outside the
    # Page's followers can ever see it, so it has to be answerable per post
    # rather than inferred from play counts weeks later.
    if result.surface:
        audit(
            "post.surface_downgraded" if result.surface_fallback_error
            else "post.surface",
            "post_target",
            target.id,
            actor_user_id=target.post.user_id,
            detail={
                "surface": result.surface,
                "error": result.surface_fallback_error,
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
    _queue_boost(target)


# ---------------------------------------------------------------------------
# Cross-account boost: our other Pages like AND comment on this post.
# ---------------------------------------------------------------------------


def _queue_boost(target: PostTarget) -> None:
    """Hand a freshly published Facebook post to the boost planner.

    Never raises: the post already succeeded, and a boost that cannot be
    scheduled must not turn a published post into a failed one.
    """
    try:
        if not boost_rules.enabled():
            return
        if target.account.platform != Platform.FACEBOOK:
            return
        if not target.external_post_id:
            return
        schedule_boost.delay(target.id)
    except Exception:  # noqa: BLE001 - boost is strictly best-effort
        log.warning("could not queue boost for target_id=%s", target.id, exc_info=True)


# Counted toward a Page's allowance. ``reserved`` is written the moment we
# schedule, ``performed`` when it actually happens.
#
# Counting only ``performed`` was a hole with teeth: a boost fires 25-180
# minutes after publishing, so two posts on the same morning both planned
# against a count of zero and recruited the same Page twice -- breaking the
# one guardrail that matters most (frequency). At ~3 posts a day that broke
# on day one. A reservation closes the window between deciding and acting.
BOOST_SPEND_ACTIONS = ("boost.performed", "boost.reserved")

# A rolling window rather than "since midnight": UTC midnight is 08:00 in
# Taipei, so a calendar-day cap quietly reset in the middle of the morning.
BOOST_WINDOW_HOURS = 24


def _boost_spend_recent(account_ids: list[int],
                        actions: tuple[str, ...] | None = None) -> dict[int, int]:
    """How many boosts each Page has committed to in the last 24 hours.

    Counted from the audit log rather than a counter column so the number
    can always be reconciled against what actually happened.
    """
    if not account_ids:
        return {}
    # Resolved at call time, not bound as a default: a default argument is
    # evaluated once at import, so tuning or patching the module constant
    # would silently have no effect.
    actions = actions or BOOST_SPEND_ACTIONS
    since = datetime.now(timezone.utc) - timedelta(hours=BOOST_WINDOW_HOURS)
    rows = (
        db.session.query(AuditLog.resource_id)
        .filter(
            AuditLog.action.in_(actions),
            AuditLog.resource_type == "social_account",
            AuditLog.created_at >= since,
            AuditLog.resource_id.in_([str(i) for i in account_ids]),
        )
        .all()
    )
    spent: dict[int, int] = {}
    for (resource_id,) in rows:
        try:
            key = int(resource_id)
        except (TypeError, ValueError):
            continue
        spent[key] = spent.get(key, 0) + 1
    return spent


def build_boost_plan(target: PostTarget) -> boost_rules.BoostPlan:
    """Resolve which of the owner's other Pages will support ``target``.

    Split out from the task so the dashboard can show the same plan the
    worker would run, without running it.
    """
    candidates = (
        db.session.query(SocialAccount)
        .filter(
            SocialAccount.user_id == target.post.user_id,
            SocialAccount.platform == Platform.FACEBOOK,
            SocialAccount.id != target.account_id,
        )
        .all()
    )
    # Stay inside the brand line. A meatball Page commenting under a
    # car-polish post is not a supportive neighbour, it is the shape of a
    # network -- unrelated assets moving together is precisely what gets
    # read as coordinated. Pages share a line when they share a group.
    if not boost_rules.cross_line_allowed():
        leader_groups = {g.id for g in (target.account.groups or [])}
        # Fail closed. A Page in no group has no line, and "no line" must
        # not read as "every line" -- that would let an ungrouped Page pull
        # the whole fleet into its post.
        candidates = [
            a for a in candidates
            if leader_groups & {g.id for g in (a.groups or [])}
        ]
    ids = [a.id for a in candidates]
    return boost_rules.plan_boost(
        post_key=f"target:{target.id}",
        leader_account_id=target.account_id,
        supporters=candidates,
        spent_today=_boost_spend_recent(ids),
        recent_by_account=_boost_recent_lines(ids),
    )


def _boost_recent_lines(account_ids: list[int], depth: int = 6) -> dict[int, list[str]]:
    """The pool lines each Page used most recently, newest first.

    A Page holds three sentences, so without this it repeats itself every
    third boost. Instagram bans repetitive comments outright and Facebook
    reads them as spam, and there is no reason to hand over that signal
    when rotating is free.
    """
    if not account_ids:
        return {}
    rows = (
        db.session.query(AuditLog.resource_id, AuditLog.detail)
        .filter(
            AuditLog.action.in_(BOOST_SPEND_ACTIONS),
            AuditLog.resource_type == "social_account",
            AuditLog.resource_id.in_([str(i) for i in account_ids]),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(len(account_ids) * depth)
        .all()
    )
    recent: dict[int, list[str]] = {}
    for resource_id, detail in rows:
        line = (detail or {}).get("line")
        if not line:
            continue
        try:
            key = int(resource_id)
        except (TypeError, ValueError):
            continue
        seen = recent.setdefault(key, [])
        if line not in seen and len(seen) < depth:
            seen.append(line)
    return recent


@celery_app.task
def schedule_boost(target_id: int) -> dict:
    """Plan the boost for one published post and queue each Page's turn."""
    target = db.session.get(PostTarget, target_id)
    if target is None or not target.external_post_id:
        return {"scheduled": 0, "reason": "target missing or never published"}
    if not boost_rules.enabled():
        return {"scheduled": 0, "reason": "boost disabled"}

    plan = build_boost_plan(target)
    for action in plan.actions:
        # Reserve before queueing, and commit before the task can run: the
        # next post published this morning must see this Page as spoken for
        # even though nothing has happened on Facebook yet.
        audit(
            "boost.reserved",
            "social_account",
            action.account_id,
            actor_user_id=target.post.user_id,
            detail={"target_id": target.id,
                    "delay_seconds": action.delay_seconds,
                    "line": action.source_line},
        )
    db.session.commit()
    for action in plan.actions:
        perform_boost.apply_async(
            args=[target.id, action.account_id, action.message],
            kwargs={"source_line": action.source_line},
            countdown=action.delay_seconds,
        )
    audit(
        "boost.scheduled",
        "post_target",
        target.id,
        actor_user_id=target.post.user_id,
        detail={
            "external_post_id": target.external_post_id,
            "supporters": [a.handle for a in plan.actions],
            "skipped": plan.skipped,
        },
    )
    db.session.commit()
    log.info(
        "boost scheduled target_id=%s supporters=%s skipped=%s",
        target.id, len(plan.actions), len(plan.skipped),
    )
    return {"scheduled": len(plan.actions), "skipped": len(plan.skipped)}


@celery_app.task(bind=True, max_retries=3)
def perform_boost(self, target_id: int, account_id: int, message: str,
                  source_line: str = "") -> dict:
    """One supporting Page likes the post, then leaves its comment.

    The like comes first because it is the cheaper call: if the token or
    permission is broken we find out before writing a comment, and a like
    on its own is a harmless partial state.
    """
    target = db.session.get(PostTarget, target_id)
    account = db.session.get(SocialAccount, account_id)
    if target is None or account is None or not target.external_post_id:
        return {"ok": False, "reason": "target or account gone"}
    if account.revoked_at:
        return {"ok": False, "reason": "account revoked"}
    if not boost_rules.enabled():
        # The switch can be turned off between scheduling and firing; the
        # later check is the one that counts.
        return {"ok": False, "reason": "boost disabled"}

    # Second gate, against what actually happened rather than what was
    # planned. The reservation closes the scheduling window; this closes the
    # replay window (a redelivered task, a resumed queue after an outage).
    allowance = int(
        (read_profile(account).get("interaction") or {}).get("max_per_day") or 0
    )
    done = _boost_spend_recent([account.id], actions=("boost.performed",)).get(
        account.id, 0
    )
    if done >= allowance:
        log.info(
            "boost skipped account=%s: already did %s in the last %sh (cap %s)",
            account.handle, done, BOOST_WINDOW_HOURS, allowance,
        )
        return {"ok": False, "reason": "daily cap already reached"}

    publisher = get_publisher(account.platform)
    set_proxy((account.extra or {}).get("proxy_url"))
    liked = False
    comment_id = ""
    try:
        token = _decrypt_token(account)
        publisher.like_as_page(token, target.external_post_id)
        liked = True
        comment_id = publisher.comment_as_page(
            token, target.external_post_id, message
        )
    except PlatformError as exc:
        audit(
            "boost.failed",
            "social_account",
            account.id,
            actor_user_id=target.post.user_id,
            detail={
                "target_id": target.id,
                "liked": liked,
                "error": str(exc)[:500],
            },
        )
        db.session.commit()
        if exc.retryable and self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=backoff_seconds(self.request.retries))
        log.warning(
            "boost failed account=%s target=%s liked=%s err=%s "
            "(liking/commenting as a Page needs pages_manage_engagement)",
            account.handle, target.id, liked, exc,
        )
        return {"ok": False, "liked": liked, "reason": str(exc)[:200]}
    finally:
        clear_proxy()

    audit(
        "boost.performed",
        "social_account",
        account.id,
        actor_user_id=target.post.user_id,
        detail={
            "target_id": target.id,
            "external_post_id": target.external_post_id,
            "comment_id": comment_id,
            "message": message,
            "line": source_line,
        },
    )
    db.session.commit()
    return {"ok": True, "liked": True, "comment_id": comment_id}


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
    # B1: skip_locked + with_for_update so two beat ticks running on
    # different workers don't both queue the same row. SQLite ignores the
    # lock hint silently, which is fine for dev where there's only one
    # beat process anyway.
    query = (
        db.session.query(PostTarget)
        .filter(PostTarget.status == JobStatus.PENDING)
        .filter(PostTarget.scheduled_for.isnot(None))
        .filter(PostTarget.scheduled_for <= now)
    )
    try:
        rows = query.with_for_update(skip_locked=True).all()
    except Exception:
        # Fallback for backends that don't support skip_locked.
        rows = query.all()
    for target in rows:
        target.status = JobStatus.QUEUED
        db.session.add(target)
    db.session.commit()
    for target in rows:
        dispatch_target.delay(target.id)


def _swap_in_preferred_derivative(request, media: MediaAsset | None, platform: str) -> None:
    """If the media has a transcoded variant for this platform, use it.

    Re-signs rather than replaying the stored URL — derivatives are presigned
    the same way the original is, so a schedule more than 7 days out would
    otherwise swap a working link for an expired one.
    """
    from ..utils.storage import fresh_media_url

    if not media or media.kind != "video" or not media.derivatives:
        return
    aspect = _preferred_aspect(platform)
    if aspect and (url := fresh_media_url(media, aspect)):
        request.media_url = url


def _preferred_aspect(platform: str) -> str | None:
    """Which derivative to send, given the surface we are aiming for.

    Facebook is the one platform where this is not a matter of taste. Reels
    reject anything wider than 9:16 outright, so handing the 16:9 derivative
    to the Reels path does not merely look wrong -- it guarantees a refusal on
    every single video, which would quietly turn the whole Reels change into a
    no-op. A portrait clip posted as a plain video (the fallback) is merely
    tall, so preferring 9:16 costs nothing there.
    """
    if platform == "facebook":
        from ..platforms.facebook import reels_enabled
        return "9:16" if reels_enabled() else "16:9"
    return _PREFERRED_ASPECT.get(platform)


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
                derived_key = storage.derivative_key(key, aspect)
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
        except PlatformError as exc:
            # B2: 401 = the user revoked our app or the refresh token is dead;
            # there is no point retrying. Mark the account revoked so the
            # publisher stops trying to use it. 5xx / network errors fall
            # through to the generic warning + retry-on-next-tick.
            if exc.status_code == 401:
                account.revoked_at = datetime.now(timezone.utc)
                audit(
                    "account.revoked_by_provider", "social_account", account.id,
                    actor_user_id=account.user_id,
                    detail={"reason": "refresh returned 401",
                            "platform": account.platform.value},
                )
                db.session.commit()
                continue
            log.warning("token refresh transient failure account %s: %s",
                        account.id, exc)
            audit(
                "account.refresh_failed", "social_account", account.id,
                actor_user_id=account.user_id,
                detail={"error": str(exc)[:300],
                        "status_code": exc.status_code},
            )
            db.session.commit()
            continue
        except Exception as exc:  # noqa: BLE001 - non-PlatformError fallback
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
def permission_health_sweep() -> dict:
    """Daily reconciliation of recorded grants vs. platform truth."""
    from ..permissions.health import run_health_sweep
    return run_health_sweep()


@celery_app.task
def expire_overdue_transfers() -> int:
    """Move past-deadline manual transfers to ``expired`` and notify."""
    from ..transfers.manual_transfer import transition_expired_if_overdue
    return transition_expired_if_overdue()


@celery_app.task
def ab_variant_backtest() -> list[dict]:
    """C2: weekly A/B winner pick — see utils.experiments."""
    from ..utils.experiments import backtest_and_persist_winners
    return backtest_and_persist_winners()


@celery_app.task
def weekly_insights_digest() -> dict:
    """C5: weekly actionable digest email per user."""
    from ..utils.digest import send_weekly_digests
    return send_weekly_digests()


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


@celery_app.task
def sweep_expiring_tokens() -> dict:
    """Daily scan: alert on tokens expiring within 7 days + probe FB liveness.

    Writes TokenExpiryAlert rows (upsert by account+kind so re-runs are safe).
    Returns a JSON-serialisable report for auditing.
    """
    now = datetime.now(timezone.utc)
    threshold_7d = now + timedelta(days=7)

    # --- Tokens with known expiry within 7 days ---
    expiring = (
        db.session.query(SocialAccount)
        .filter(SocialAccount.revoked_at.is_(None))
        .filter(SocialAccount.token_expires_at.isnot(None))
        .filter(SocialAccount.token_expires_at > now)
        .filter(SocialAccount.token_expires_at <= threshold_7d)
        .all()
    )

    # --- FB page tokens have no expiry — probe liveness via /me?fields=id ---
    fb_accounts = (
        db.session.query(SocialAccount)
        .filter(SocialAccount.revoked_at.is_(None))
        .filter(SocialAccount.platform == Platform.FACEBOOK)
        .filter(SocialAccount.token_expires_at.is_(None))
        .all()
    )

    report: dict = {"expiring_soon": [], "needs_reauth": []}

    for acct in expiring:
        _upsert_token_alert(
            acct, "expiring_soon",
            expires_at=acct.token_expires_at,
            detail={"days_left": (acct.token_expires_at - now).days},
        )
        report["expiring_soon"].append({
            "account_id": acct.id,
            "handle": acct.handle,
            "platform": acct.platform.value,
            "expires_at": acct.token_expires_at.isoformat(),
        })
        log.warning(
            "token expiring soon: account_id=%s handle=%s platform=%s expires=%s",
            acct.id, acct.handle, acct.platform.value,
            acct.token_expires_at.isoformat(),
        )

    for acct in fb_accounts:
        alive = _probe_fb_liveness(acct)
        if not alive:
            _upsert_token_alert(acct, "needs_reauth", expires_at=None,
                                detail={"reason": "/me probe failed"})
            report["needs_reauth"].append({
                "account_id": acct.id,
                "handle": acct.handle,
                "platform": "facebook",
            })
            log.warning(
                "FB page token liveness failed: account_id=%s handle=%s",
                acct.id, acct.handle,
            )

    db.session.commit()
    log.info(
        "sweep_expiring_tokens: %d expiring, %d needs_reauth",
        len(report["expiring_soon"]), len(report["needs_reauth"]),
    )
    return report


def _upsert_token_alert(
    account: SocialAccount,
    kind: str,
    *,
    expires_at,
    detail: dict,
) -> None:
    existing = (
        db.session.query(TokenExpiryAlert)
        .filter_by(account_id=account.id, kind=kind)
        .filter(TokenExpiryAlert.resolved_at.is_(None))
        .one_or_none()
    )
    if existing:
        existing.expires_at = expires_at
        existing.detail = detail
    else:
        db.session.add(TokenExpiryAlert(
            account_id=account.id,
            kind=kind,
            expires_at=expires_at,
            detail=detail,
        ))


def _probe_fb_liveness(account: SocialAccount) -> bool:
    """Return True if the FB token can authenticate /me, False otherwise."""
    try:
        import requests as _requests
        c = cipher()
        token = c.decrypt(account.access_token_enc)
        r = _requests.get(
            "https://graph.facebook.com/me",
            params={"fields": "id", "access_token": token},
            timeout=10,
        )
        return r.ok and "id" in r.json()
    except Exception as exc:
        log.debug("FB liveness probe failed for account %s: %s", account.id, exc)
        return False
