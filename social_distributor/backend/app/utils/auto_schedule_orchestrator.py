"""Auto-schedule orchestrator: build today's marketing distribution.

Picks captions from prior SUCCEEDED posts, pairs them with media from the
user's library, spreads them across the day per account. Each account gets a
random mix so all 51 pages don't post identical content (FB anti-spam).

Touches no Graph API directly — just creates ``Post`` + ``PostTarget`` rows
with ``scheduled_for`` in the future. The existing
``app.scheduler.tasks.sweep_due_targets`` Celery beat picks them up at
their scheduled time and dispatches via the normal pipeline.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence
from zoneinfo import ZoneInfo

from sqlalchemy import select

from ..extensions import db
from ..models import (
    JobStatus,
    MediaAsset,
    Platform,
    Post,
    PostTarget,
    SocialAccount,
)


@dataclass
class AutoScheduleParams:
    user_id: int
    videos_per_account: int = 2
    posts_per_account: int = 2
    link: str | None = None
    window_start_hour: int = 10
    window_end_hour: int = 22
    spacing_minutes_min: int = 5
    spacing_minutes_max: int = 15
    platforms: tuple[str, ...] = ("facebook",)
    timezone: str = "Asia/Taipei"
    dry_run: bool = False
    today: datetime | None = None  # injectable for tests; UTC


def _platform_enums(names: Sequence[str]) -> list[Platform]:
    out = []
    for n in names:
        try:
            out.append(Platform(n))
        except ValueError:
            continue
    return out


def _caption_pool(user_id: int, days_back: int = 90) -> list[str]:
    """Pull distinct captions from the user's SUCCEEDED PostTargets in the
    last ``days_back`` days. Ignores empty captions."""
    since = datetime.now(timezone.utc) - timedelta(days=days_back)
    rows = db.session.execute(
        select(Post.caption)
        .join(PostTarget, PostTarget.post_id == Post.id)
        .where(
            Post.user_id == user_id,
            PostTarget.status == JobStatus.SUCCEEDED,
            PostTarget.published_at.is_not(None),
            PostTarget.published_at >= since,
        )
        .distinct()
    ).all()
    return [r[0] for r in rows if r[0] and r[0].strip()]


def _media_pools(user_id: int) -> tuple[list[MediaAsset], list[MediaAsset]]:
    """(videos, images). Videos must have transcode_status='ready' to be
    publishable; images need no transcode."""
    media = db.session.execute(
        select(MediaAsset).where(MediaAsset.user_id == user_id)
    ).scalars().all()
    videos = [m for m in media if m.kind == "video" and m.transcode_status == "ready"]
    images = [m for m in media if m.kind == "image"]
    return videos, images


def _active_accounts(user_id: int, platforms: list[Platform]) -> list[SocialAccount]:
    return db.session.execute(
        select(SocialAccount).where(
            SocialAccount.user_id == user_id,
            SocialAccount.platform.in_(platforms),
            SocialAccount.revoked_at.is_(None),
        )
    ).scalars().all()


def _spread_today(
    n_slots: int,
    now_utc: datetime,
    start_hour: int,
    end_hour: int,
    tz_name: str,
    rng: random.Random,
) -> list[datetime]:
    """Evenly bin today's [start_hour, end_hour) window in the given timezone
    into n_slots; pick one minute inside each bin (jittered). Returns sorted
    UTC datetimes.

    Window hours are interpreted in ``tz_name``: e.g. start=10, end=22,
    tz="Asia/Taipei" means [10:00 Taipei, 22:00 Taipei) on the local
    "today" relative to ``now_utc``. If the window has already started,
    only future minutes are eligible.

    Returns [] when:
    - n_slots <= 0
    - start_hour >= end_hour
    - The window has already ended for "today" in tz_name
    """
    if start_hour >= end_hour or n_slots <= 0:
        return []
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    now_local = now_utc.astimezone(tz)
    window_start_local = now_local.replace(
        hour=start_hour, minute=0, second=0, microsecond=0
    )
    window_end_local = now_local.replace(
        hour=end_hour, minute=0, second=0, microsecond=0
    )
    earliest_local = max(window_start_local, now_local + timedelta(minutes=1))
    if earliest_local >= window_end_local:
        return []
    span_minutes = int((window_end_local - earliest_local).total_seconds() // 60)
    if span_minutes <= 0:
        return []
    bin_size = max(1, span_minutes // n_slots)
    out = []
    for i in range(n_slots):
        bin_start_min = i * bin_size
        bin_end_min = min(span_minutes, (i + 1) * bin_size)
        if bin_start_min >= bin_end_min:
            offset_min = bin_start_min
        else:
            offset_min = rng.randint(bin_start_min, bin_end_min - 1)
        out.append((earliest_local + timedelta(minutes=offset_min)).astimezone(timezone.utc))
    return out


def build_today_schedule(params: AutoScheduleParams) -> dict:
    """Main entry. Returns ``{"summary": {...}, "by_account": [...]}``.

    When ``dry_run`` is True, no DB writes happen and ``post_ids`` /
    ``target_ids`` are absent from the per-account entries.
    """
    rng = random.Random()  # deterministic seed could be wired through params later

    captions = _caption_pool(params.user_id)
    videos, images = _media_pools(params.user_id)
    platforms = _platform_enums(params.platforms)
    accounts = _active_accounts(params.user_id, platforms)

    today = params.today or datetime.now(timezone.utc)

    summary = {
        "user_id": params.user_id,
        "accounts": len(accounts),
        "captions_available": len(captions),
        "videos_available": len(videos),
        "images_available": len(images),
        "videos_per_account": params.videos_per_account,
        "posts_per_account": params.posts_per_account,
        "posts_created": 0,
        "earliest_scheduled_at": None,
        "latest_scheduled_at": None,
        "dry_run": params.dry_run,
        "warnings": [],
    }
    by_account: list[dict] = []

    if not accounts:
        summary["warnings"].append("no active accounts on selected platforms")
        return {"summary": summary, "by_account": []}
    if not captions:
        summary["warnings"].append(
            "no SUCCEEDED captions in the last 90 days; user must publish "
            "at least one post manually before auto-schedule has captions to reuse"
        )
        return {"summary": summary, "by_account": []}
    if not videos and params.videos_per_account > 0:
        summary["warnings"].append(
            "no ready videos in library; videos_per_account treated as 0"
        )

    # Heads-up if today's window is already over in the user's TZ.
    try:
        tz = ZoneInfo(params.timezone)
    except Exception:
        tz = ZoneInfo("UTC")
    now_local = (today).astimezone(tz)
    end_local = now_local.replace(
        hour=params.window_end_hour, minute=0, second=0, microsecond=0
    )
    if now_local >= end_local:
        summary["warnings"].append(
            f"window {params.window_start_hour:02d}:00–{params.window_end_hour:02d}:00 "
            f"({params.timezone}) has already passed for today; nothing scheduled"
        )

    all_scheduled: list[datetime] = []

    for account in accounts:
        per_account = params.videos_per_account + params.posts_per_account
        if per_account <= 0:
            continue

        # Mix of videos and non-videos
        n_videos = params.videos_per_account if videos else 0
        n_non_videos = per_account - n_videos

        chosen_videos = rng.choices(videos, k=n_videos) if n_videos else []
        # non-video uses image if available else None (text-only post)
        if images and n_non_videos > 0:
            chosen_non_videos: list[MediaAsset | None] = rng.choices(images, k=n_non_videos)
        else:
            chosen_non_videos = [None] * n_non_videos

        media_picks: list[MediaAsset | None] = chosen_videos + chosen_non_videos
        rng.shuffle(media_picks)

        caption_picks = rng.choices(captions, k=len(media_picks))

        scheduled_ats = _spread_today(
            n_slots=len(media_picks),
            now_utc=today,
            start_hour=params.window_start_hour,
            end_hour=params.window_end_hour,
            tz_name=params.timezone,
            rng=rng,
        )
        if len(scheduled_ats) < len(media_picks):
            # Window too narrow for the requested count; truncate.
            media_picks = media_picks[: len(scheduled_ats)]
            caption_picks = caption_picks[: len(scheduled_ats)]

        post_ids: list[int] = []
        target_ids: list[int] = []

        for media, caption, sched_at in zip(media_picks, caption_picks, scheduled_ats):
            full_caption = caption
            if params.link and params.link not in full_caption:
                full_caption = f"{caption}\n\n{params.link}"

            if not params.dry_run:
                post = Post(
                    user_id=params.user_id,
                    caption=full_caption,
                    link_url=params.link,
                    media_id=media.id if media else None,
                )
                db.session.add(post)
                db.session.flush()
                target = PostTarget(
                    post_id=post.id,
                    account_id=account.id,
                    scheduled_for=sched_at,
                    status=JobStatus.PENDING,
                )
                db.session.add(target)
                db.session.flush()
                post_ids.append(post.id)
                target_ids.append(target.id)

            all_scheduled.append(sched_at)

        by_account.append({
            "account_id": account.id,
            "platform": account.platform.value,
            "handle": account.handle,
            "post_ids": post_ids,
            "target_ids": target_ids,
            "scheduled_ats": [s.isoformat() for s in scheduled_ats[: len(media_picks)]],
        })
        summary["posts_created"] += len(media_picks)

    if not params.dry_run:
        db.session.commit()

    if all_scheduled:
        summary["earliest_scheduled_at"] = min(all_scheduled).isoformat()
        summary["latest_scheduled_at"] = max(all_scheduled).isoformat()

    return {"summary": summary, "by_account": by_account}
