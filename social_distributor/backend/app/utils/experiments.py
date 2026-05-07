"""A/B variant experiments — comparison + winner picking.

The "engine" we A/B test is the variant-rewriter strategy that produced a
post's caption: ``claude``, ``template``, or ``none`` (raw original). We
already record this on every dispatched target via
``PostTarget.overrides['variant_engine']`` (set by ``api/posts.py::distribute``
when ``generate_variants=true`` is requested).

This module rolls those engines up against the engagement metrics that
``ingest_insights`` collects, scores them by a normalised
``engagement_per_reach`` rate, and picks a winner per group.

Why per-group? Different personas behave differently — a tech reviewer
group might prefer terse captions (template wins) while a lifestyle group
prefers narrative ones (claude wins). One winner per group lets each
persona get its own tuning without contaminating others.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import and_

from ..extensions import db
from ..models import (
    AccountGroup,
    JobStatus,
    PostMetric,
    PostTarget,
    SocialAccount,
    account_group_members,
)


# Minimum samples per engine before we trust a winner. With <5 each, the
# noise-to-signal ratio is too high — random caption variations swamp the
# real engine signal. Tweakable via ``MIN_SAMPLES_PER_ENGINE`` env in
# the future; hardcoded for now since we need to ship.
MIN_SAMPLES_PER_ENGINE = 5


@dataclass
class EngineStats:
    engine: str
    samples: int
    total_reach: int
    total_engagement: int
    rate: float  # engagement / reach (0 if reach is 0)


@dataclass
class GroupComparison:
    group_id: int
    group_name: str
    since: datetime
    by_engine: list[EngineStats]
    winner: str | None  # None when not enough data
    confidence_note: str


def compare_variants(
    group_id: int,
    *,
    since: datetime | None = None,
) -> GroupComparison | None:
    """Aggregate engagement-per-reach for each variant engine in a group.

    Returns ``None`` if the group does not exist. Returns a comparison with
    ``winner=None`` when no engine reached ``MIN_SAMPLES_PER_ENGINE``.

    Implementation note: we group at the ``PostTarget`` level rather than
    pulling raw rows — each target represents one published post, so each
    target counts as one sample per engine.
    """
    group = db.session.get(AccountGroup, group_id)
    if group is None:
        return None
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=7)

    account_ids = [a.id for a in group.accounts]
    if not account_ids:
        return GroupComparison(
            group_id=group.id, group_name=group.name, since=since,
            by_engine=[], winner=None,
            confidence_note="group has no accounts",
        )

    targets = (
        db.session.query(PostTarget)
        .filter(
            PostTarget.account_id.in_(account_ids),
            PostTarget.status == JobStatus.SUCCEEDED,
            PostTarget.published_at.isnot(None),
            PostTarget.published_at >= since,
        )
        .all()
    )

    # Map target_id -> latest metric snapshot (we want the freshest measurement
    # per target, not the sum of all snapshots, which would double-count).
    target_ids = [t.id for t in targets]
    latest_metrics = _latest_metric_per_target(target_ids)

    buckets: dict[str, dict] = defaultdict(
        lambda: {"samples": 0, "reach": 0, "engagement": 0}
    )
    for t in targets:
        engine = (t.overrides or {}).get("variant_engine") or "none"
        m = latest_metrics.get(t.id)
        if m is None:
            continue  # no metrics ingested yet — skip rather than count as zero
        reach = m.reach or m.impressions or m.plays or 0
        engagement = (m.likes or 0) + (m.comments or 0) + (m.shares or 0) + (m.saves or 0)
        b = buckets[engine]
        b["samples"] += 1
        b["reach"] += reach
        b["engagement"] += engagement

    stats = [
        EngineStats(
            engine=eng,
            samples=v["samples"],
            total_reach=v["reach"],
            total_engagement=v["engagement"],
            rate=(v["engagement"] / v["reach"]) if v["reach"] else 0.0,
        )
        for eng, v in sorted(buckets.items())
    ]

    qualifying = [s for s in stats if s.samples >= MIN_SAMPLES_PER_ENGINE]
    if len(qualifying) < 2:
        return GroupComparison(
            group_id=group.id, group_name=group.name, since=since,
            by_engine=stats, winner=None,
            confidence_note=(
                f"need at least 2 engines with ≥{MIN_SAMPLES_PER_ENGINE} "
                f"samples each (have {[(s.engine, s.samples) for s in stats]})"
            ),
        )

    winner = max(qualifying, key=lambda s: s.rate)
    runner_up = max((s for s in qualifying if s.engine != winner.engine),
                    key=lambda s: s.rate)
    margin = (winner.rate - runner_up.rate) / runner_up.rate if runner_up.rate else 0
    note = (
        f"{winner.engine} wins by {margin*100:.1f}% over {runner_up.engine}"
        if margin > 0 else
        f"{winner.engine} ties {runner_up.engine}; not declaring winner"
    )
    return GroupComparison(
        group_id=group.id, group_name=group.name, since=since,
        by_engine=stats,
        winner=winner.engine if margin > 0 else None,
        confidence_note=note,
    )


def backtest_and_persist_winners() -> list[dict]:
    """Run ``compare_variants`` for every group, persist winners.

    Called by the weekly ``ab-variant-backtest`` Celery beat. Only writes
    ``preferred_variant_engine`` when the comparison declares a winner —
    otherwise leaves the existing value untouched (don't unlearn on a quiet
    week).
    """
    out = []
    for group in db.session.query(AccountGroup).filter_by(is_active=True).all():
        comparison = compare_variants(group.id)
        if comparison is None:
            continue
        record = {
            "group_id": group.id,
            "group_name": group.name,
            "winner": comparison.winner,
            "by_engine": [
                {"engine": s.engine, "samples": s.samples,
                 "rate": round(s.rate, 4)}
                for s in comparison.by_engine
            ],
            "previous_preferred": group.preferred_variant_engine,
            "note": comparison.confidence_note,
        }
        if comparison.winner is not None:
            group.preferred_variant_engine = comparison.winner
            record["updated"] = True
        else:
            record["updated"] = False
        out.append(record)
    db.session.commit()
    return out


def _latest_metric_per_target(target_ids: Iterable[int]) -> dict[int, PostMetric]:
    """Return target_id -> most recent PostMetric row.

    We do this in Python rather than a window function so it works on SQLite
    in tests without dialect-specific SQL.
    """
    if not target_ids:
        return {}
    rows = (
        db.session.query(PostMetric)
        .filter(PostMetric.target_id.in_(list(target_ids)))
        .order_by(PostMetric.target_id, PostMetric.fetched_at.desc())
        .all()
    )
    out: dict[int, PostMetric] = {}
    for row in rows:
        if row.target_id not in out:
            out[row.target_id] = row
    return out
