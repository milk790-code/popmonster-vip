"""Suggest best publishing times from historical engagement.

Engagement rate per snapshot = ``(likes + comments + shares) / max(reach, 1)``.
We bucket each successful target by its **published_at hour-of-week** (Mon
00:00 = bucket 0, Sun 23:00 = bucket 167) and average the rate. Top buckets
are returned with the corresponding day-of-week and hour-of-day labels.

The signal stays meaningful with as few as ~10 samples per account. Below
that we just expose the raw counts so the dashboard can hint "still
collecting data" rather than fabricate a recommendation.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import JobStatus, PostMetric, PostTarget

_DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class TimeSlot:
    day: str
    hour: int
    sample_count: int
    avg_engagement_rate: float


def _bucket_of(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.weekday() * 24 + dt.hour


def _label_of(bucket: int) -> tuple[str, int]:
    return _DOW_LABELS[bucket // 24], bucket % 24


def next_best_time_for_group(
    group_id: int,
    *,
    after: datetime | None = None,
    min_samples: int = 3,
) -> datetime | None:
    """Return the next future occurrence of the group's top engagement slot.

    Uses the bucket's day-of-week + hour-of-day to find the closest future
    moment in UTC. Returns ``None`` when there isn't enough data to make a
    confident recommendation — caller should fall back to "now" or prompt
    the user.
    """
    slots = best_times_for_group(group_id, top_n=1, min_samples=min_samples)
    if not slots:
        return None
    return _next_future_occurrence(slots[0], after=after)


def _next_future_occurrence(slot: TimeSlot,
                             after: datetime | None = None) -> datetime:
    now = (after or datetime.now(timezone.utc)).astimezone(timezone.utc)
    target_dow = _DOW_LABELS.index(slot.day)
    days_ahead = (target_dow - now.weekday()) % 7
    candidate = now.replace(
        hour=slot.hour, minute=0, second=0, microsecond=0
    ) + timedelta(days=days_ahead)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def best_times_for_account(account_id: int, *, top_n: int = 5,
                            min_samples: int = 3) -> list[TimeSlot]:
    targets = (
        db.session.query(PostTarget)
        .options(joinedload(PostTarget.account))
        .filter(PostTarget.account_id == account_id)
        .filter(PostTarget.status == JobStatus.SUCCEEDED)
        .filter(PostTarget.published_at.isnot(None))
        .all()
    )
    return _aggregate(targets, top_n=top_n, min_samples=min_samples)


def best_times_for_group(group_id: int, *, top_n: int = 5,
                          min_samples: int = 3) -> list[TimeSlot]:
    from ..models import AccountGroup
    group = db.session.get(AccountGroup, group_id)
    if not group:
        return []
    account_ids = [a.id for a in group.accounts]
    if not account_ids:
        return []
    targets = (
        db.session.query(PostTarget)
        .filter(PostTarget.account_id.in_(account_ids))
        .filter(PostTarget.status == JobStatus.SUCCEEDED)
        .filter(PostTarget.published_at.isnot(None))
        .all()
    )
    return _aggregate(targets, top_n=top_n, min_samples=min_samples)


def _aggregate(targets, *, top_n: int, min_samples: int) -> list[TimeSlot]:
    rates: dict[int, list[float]] = defaultdict(list)
    for target in targets:
        rate = _engagement_rate_for(target.id)
        if rate is None:
            continue
        rates[_bucket_of(target.published_at)].append(rate)

    slots: list[TimeSlot] = []
    for bucket, samples in rates.items():
        if len(samples) < min_samples:
            continue
        day, hour = _label_of(bucket)
        slots.append(
            TimeSlot(
                day=day,
                hour=hour,
                sample_count=len(samples),
                avg_engagement_rate=sum(samples) / len(samples),
            )
        )
    slots.sort(key=lambda s: s.avg_engagement_rate, reverse=True)
    return slots[:top_n]


def _engagement_rate_for(target_id: int) -> float | None:
    metric = (
        db.session.query(PostMetric)
        .filter_by(target_id=target_id)
        .order_by(PostMetric.fetched_at.desc())
        .first()
    )
    if metric is None:
        return None
    base = metric.reach or metric.impressions or metric.plays
    if not base:
        return None
    interactions = (metric.likes or 0) + (metric.comments or 0) + (metric.shares or 0)
    return interactions / base
