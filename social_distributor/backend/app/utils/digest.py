"""Weekly insights digest — fact-grounded summary email.

The digest:

1. Aggregates the user's last 7 days of SUCCEEDED ``PostTarget`` rows + their
   freshest ``PostMetric`` snapshot.
2. Computes only the metrics we have honest data for: total reach, total
   engagement, engagement rate distribution, best vs worst post by rate,
   emoji-vs-no-emoji engagement-rate diff (when sample sizes meet the
   minimum), and (when present) the latest A/B winner per group.
3. Asks Claude to write 200 words of *advice grounded in those numbers*
   under a strict system prompt that forbids inventing any new data.
4. Sends via SendGrid using ``notify.send_failure_email`` (we reuse the
   existing transport — no new credentials).

If a user has no metrics in the window, we send a short "no data this
week — keep posting" note instead of pretending to have insight.

If the Anthropic API isn't configured, the digest still goes out but with
a deterministic non-LLM summary (the underlying numbers are the same; the
narrative is just a template). This means "set ANTHROPIC_API_KEY" is a
quality upgrade, not a hard dependency.
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..extensions import db
from ..models import (
    AccountGroup,
    JobStatus,
    Platform,
    PostMetric,
    PostTarget,
    SocialAccount,
    User,
)
from .experiments import compare_variants
from .notify import send_failure_email

log = logging.getLogger(__name__)

EMOJI_RANGES = (
    (0x1F300, 0x1F5FF),   # symbols & pictographs
    (0x1F600, 0x1F64F),   # emoticons
    (0x1F680, 0x1F6FF),   # transport & maps
    (0x1F900, 0x1F9FF),   # supplemental symbols
    (0x2600, 0x26FF),     # misc symbols
    (0x2700, 0x27BF),     # dingbats
)

# Minimum samples required for emoji-vs-no comparison to be reported.
EMOJI_MIN_SAMPLES = 3


@dataclass
class TargetSnapshot:
    target_id: int
    platform: str
    handle: str
    caption: str
    reach: int
    engagement: int
    rate: float


@dataclass
class UserDigest:
    user_id: int
    user_email: str
    since: datetime
    until: datetime
    total_published: int
    total_reach: int
    total_engagement: int
    avg_rate: float
    best: TargetSnapshot | None
    worst: TargetSnapshot | None
    emoji_vs_plain: dict | None
    ab_winners: list[dict]
    narrative: str  # filled by build_user_digest

    def has_data(self) -> bool:
        return self.total_published > 0


def build_user_digest(user_id: int, *, days: int = 7) -> UserDigest | None:
    """Compute the digest for one user over a rolling window. Returns
    ``None`` if the user doesn't exist."""
    user = db.session.get(User, user_id)
    if user is None:
        return None
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=days)

    targets = (
        db.session.query(PostTarget)
        .join(SocialAccount, SocialAccount.id == PostTarget.account_id)
        .filter(SocialAccount.user_id == user_id)
        .filter(PostTarget.status == JobStatus.SUCCEEDED)
        .filter(PostTarget.published_at.isnot(None))
        .filter(PostTarget.published_at >= since)
        .all()
    )

    snapshots = _build_snapshots(targets)
    digest = UserDigest(
        user_id=user.id,
        user_email=user.email,
        since=since,
        until=until,
        total_published=len(snapshots),
        total_reach=sum(s.reach for s in snapshots),
        total_engagement=sum(s.engagement for s in snapshots),
        avg_rate=(sum(s.rate for s in snapshots) / len(snapshots)) if snapshots else 0.0,
        best=max(snapshots, key=lambda s: s.rate, default=None),
        worst=min((s for s in snapshots if s.reach > 0), key=lambda s: s.rate, default=None),
        emoji_vs_plain=_emoji_comparison(snapshots),
        ab_winners=_ab_winners_for_user(user_id),
        narrative="",
    )
    digest.narrative = _narrative_for(digest)
    return digest


def send_weekly_digests() -> dict:
    """Iterate every user with at least one published target this week and
    send their digest email. Returns counts for the celery task summary."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    user_ids = [
        row[0]
        for row in db.session.query(SocialAccount.user_id)
        .join(PostTarget, PostTarget.account_id == SocialAccount.id)
        .filter(PostTarget.status == JobStatus.SUCCEEDED)
        .filter(PostTarget.published_at >= cutoff)
        .distinct()
        .all()
    ]
    sent = 0
    skipped_empty = 0
    for uid in user_ids:
        digest = build_user_digest(uid)
        if digest is None or not digest.has_data():
            skipped_empty += 1
            continue
        send_failure_email(
            to=[digest.user_email],
            subject=f"📈 Weekly insights — {digest.total_published} posts, "
                    f"{digest.total_engagement:,} engagement",
            body=_format_email_body(digest),
        )
        sent += 1
    return {"sent": sent, "users_evaluated": len(user_ids),
            "skipped_empty": skipped_empty}


# -------------------------------------------------------------------- helpers


def _build_snapshots(targets: list[PostTarget]) -> list[TargetSnapshot]:
    if not targets:
        return []
    target_ids = [t.id for t in targets]
    metrics = (
        db.session.query(PostMetric)
        .filter(PostMetric.target_id.in_(target_ids))
        .order_by(PostMetric.target_id, PostMetric.fetched_at.desc())
        .all()
    )
    latest: dict[int, PostMetric] = {}
    for m in metrics:
        if m.target_id not in latest:
            latest[m.target_id] = m

    snapshots: list[TargetSnapshot] = []
    for t in targets:
        m = latest.get(t.id)
        if m is None:
            continue
        reach = m.reach or m.impressions or m.plays or 0
        engagement = (m.likes or 0) + (m.comments or 0) + (m.shares or 0) + (m.saves or 0)
        rate = (engagement / reach) if reach else 0.0
        caption = (t.overrides or {}).get("caption") or (t.post.caption if t.post else "")
        snapshots.append(TargetSnapshot(
            target_id=t.id,
            platform=t.account.platform.value,
            handle=t.account.handle,
            caption=caption,
            reach=reach,
            engagement=engagement,
            rate=rate,
        ))
    return snapshots


def _has_emoji(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        for lo, hi in EMOJI_RANGES:
            if lo <= cp <= hi:
                return True
    return False


def _emoji_comparison(snapshots: list[TargetSnapshot]) -> dict | None:
    with_emoji = [s for s in snapshots if _has_emoji(s.caption)]
    without = [s for s in snapshots if not _has_emoji(s.caption)]
    if len(with_emoji) < EMOJI_MIN_SAMPLES or len(without) < EMOJI_MIN_SAMPLES:
        return None
    avg_with = sum(s.rate for s in with_emoji) / len(with_emoji)
    avg_without = sum(s.rate for s in without) / len(without)
    return {
        "with_emoji_samples": len(with_emoji),
        "without_emoji_samples": len(without),
        "with_emoji_rate": round(avg_with, 4),
        "without_emoji_rate": round(avg_without, 4),
        "delta_pct": round(((avg_with - avg_without) / avg_without * 100)
                            if avg_without else 0, 1),
    }


def _ab_winners_for_user(user_id: int) -> list[dict]:
    out = []
    groups = (
        db.session.query(AccountGroup)
        .filter_by(user_id=user_id, is_active=True)
        .all()
    )
    for g in groups:
        cmp = compare_variants(g.id)
        if cmp is None or cmp.winner is None:
            continue
        out.append({
            "group_id": g.id,
            "group_name": g.name,
            "winner": cmp.winner,
            "note": cmp.confidence_note,
        })
    return out


def _narrative_for(digest: UserDigest) -> str:
    """Try Claude with strict no-fabrication prompt; fall back to template."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _template_narrative(digest)
    try:
        return _claude_narrative(digest)
    except Exception as exc:  # noqa: BLE001 - any LLM failure → template
        log.warning("digest narrative via Claude failed (%s); falling back", exc)
        return _template_narrative(digest)


def _claude_narrative(digest: UserDigest) -> str:
    from anthropic import Anthropic

    client = Anthropic()
    payload = {
        "total_published": digest.total_published,
        "total_reach": digest.total_reach,
        "total_engagement": digest.total_engagement,
        "avg_rate": round(digest.avg_rate, 4),
        "best_post": _ts_dict(digest.best),
        "worst_post": _ts_dict(digest.worst),
        "emoji_comparison": digest.emoji_vs_plain,
        "ab_winners": digest.ab_winners,
    }
    import json as _json
    system = (
        "You write a SHORT (under 200 words) actionable weekly insights "
        "summary for a social media creator. STRICT RULES:\n"
        "- Use ONLY numbers from the JSON payload below. Never invent.\n"
        "- Never claim percentages or comparisons that aren't in the payload.\n"
        "- If a field is null or missing, do not mention it.\n"
        "- Output plain text, no markdown headers, no emoji, no bullet "
        "  ornaments. Two short paragraphs maximum.\n"
        "- End with one concrete action the creator can try this week, "
        "  drawn from the data (e.g. \"Lean into emoji captions — they "
        "  beat plain by N%\")."
    )
    response = client.messages.create(
        model=os.environ.get("ANTHROPIC_DIGEST_MODEL", "claude-haiku-4-5-20251001"),
        max_tokens=400,
        system=system,
        messages=[{"role": "user", "content": _json.dumps(payload)}],
    )
    text = "".join(
        b.text for b in response.content if getattr(b, "type", None) == "text"
    ).strip()
    return text or _template_narrative(digest)


def _ts_dict(t: TargetSnapshot | None) -> dict | None:
    if t is None:
        return None
    return {
        "platform": t.platform, "handle": t.handle,
        "reach": t.reach, "engagement": t.engagement,
        "rate": round(t.rate, 4),
        "caption_preview": t.caption[:80],
    }


def _template_narrative(digest: UserDigest) -> str:
    if not digest.has_data():
        return "No published posts in the last 7 days. Keep going!"
    parts = [
        f"You published {digest.total_published} posts this week, "
        f"reaching {digest.total_reach:,} people with "
        f"{digest.total_engagement:,} total engagements "
        f"(avg engagement rate {digest.avg_rate*100:.2f}%)."
    ]
    if digest.best:
        parts.append(
            f"Top performer: {digest.best.platform} @{digest.best.handle} "
            f"at {digest.best.rate*100:.2f}% engagement rate."
        )
    if digest.emoji_vs_plain:
        e = digest.emoji_vs_plain
        sign = "higher" if e["delta_pct"] > 0 else "lower"
        parts.append(
            f"Posts with emoji had {abs(e['delta_pct']):.1f}% {sign} "
            f"engagement than plain ones "
            f"(samples: {e['with_emoji_samples']} vs {e['without_emoji_samples']})."
        )
    if digest.ab_winners:
        parts.append(
            "A/B winners this week: "
            + "; ".join(f"{w['group_name']} → {w['winner']}"
                        for w in digest.ab_winners)
            + "."
        )
    return " ".join(parts)


def _format_email_body(digest: UserDigest) -> str:
    return (
        f"Weekly insights — {digest.since.date()} to {digest.until.date()}\n\n"
        f"{digest.narrative}\n\n"
        f"--\n"
        f"Total published: {digest.total_published}\n"
        f"Total reach: {digest.total_reach:,}\n"
        f"Total engagement: {digest.total_engagement:,}\n"
        f"Average engagement rate: {digest.avg_rate*100:.2f}%\n"
    )
