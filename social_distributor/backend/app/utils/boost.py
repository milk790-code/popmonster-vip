"""Cross-account boost: our other Pages like AND comment on our own post.

Why this exists
---------------
The fleet already stores a per-account ``interaction`` block (role,
max_per_day, comment_pool) but nothing ever acted on it, so "mutual
support" was a setting with no engine behind it. A like alone carries no
traffic; the point of a supporting Page is to leave a *readable* comment
that also carries that Page's own permanent funnel link, so the visit can
be attributed back to the Page that earned it.

What keeps this on the legal side of Meta's rules
-------------------------------------------------
Meta does not ban one entity running many real Pages, and "interact as a
Page on another Page's post" is a shipped feature. What Meta's Spam policy
bans is *very high frequency* interaction (explicitly "manually or
automatically" -- so "a human clicked it" is no defence) and *identical*
content replicated across many assets. Every guardrail below maps to one
of those two sentences:

* ``role`` defaults to ``off``  -- nothing participates until turned on.
* ``max_per_day`` caps at 5     -- frequency ceiling per Page.
* ``MAX_SUPPORTERS_PER_POST``   -- a post never gets a wall of our own Pages.
* text is drawn from that Page's own pool and de-duplicated per post
                                -- no two of our Pages say the same thing.
* actions are spread over hours, never seconds
                                -- the shape of the traffic is not a burst.
* an empty comment pool is a *skip*, never an invented sentence.

The planner is pure: it takes rows in, returns actions out, touches no
network and no clock it wasn't handed. That is what makes the guardrails
testable rather than aspirational.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field

from .account_profile import read_profile

# The permanent funnel. Everything we publish points here unless a specific
# landing page was named for that piece.
GO_URL = "https://popmonster.vip/go"

# ``src`` is a closed allow-list on both the frontend and the go-events
# worker: an unknown value is silently re-labelled ``direct`` by the former
# and dropped entirely by the latter. So a bad code doesn't break the link,
# it breaks the *reporting* -- silently. Per-Page codes are ``fb-`` + 6 hex.
PAGE_SRC_RE = re.compile(r"^fb-[0-9a-f]{6}$")
# Used when a Page has no code of its own yet. It is on the allow-list, so
# the visit still lands in reporting -- just bucketed as generic social
# rather than attributed to that Page.
FALLBACK_SRC = "social"

# A comment shorter than this reads as "推 / +1" filler, which is exactly
# the "coordinated inauthentic comment" shape Meta called out in 2025-04.
MIN_COMMENT_CHARS = 8

LINK_PLACEHOLDER = "{link}"


def _env_int(name: str, default: int, *, lo: int, hi: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(lo, min(hi, value))


def enabled() -> bool:
    """Master switch. Off unless explicitly turned on.

    Turning this on starts writing to Facebook on our behalf, so it is a
    deliberate, human decision -- not something a deploy can flip by
    accident.
    """
    return (os.environ.get("BOOST_ENABLED") or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def max_supporters_per_post() -> int:
    return _env_int("BOOST_MAX_SUPPORTERS_PER_POST", 3, lo=0, hi=8)


def window_minutes() -> int:
    return _env_int("BOOST_WINDOW_MINUTES", 180, lo=10, hi=1440)


def min_delay_minutes() -> int:
    return _env_int("BOOST_MIN_DELAY_MINUTES", 25, lo=1, hi=720)


def cross_line_allowed() -> bool:
    """Whether Pages from a different brand line may support a post.

    Off by default. Unrelated assets moving in step is the network shape;
    a Page should only chime in where its audience would plausibly care.
    """
    return (os.environ.get("BOOST_CROSS_LINE") or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def funnel_link(link_src: str) -> str:
    """Build this Page's tracked funnel URL.

    Always fully qualified: a bare ``popmonster.vip/go`` is not
    auto-linkified by Facebook, which is how a comment ends up looking
    like spam with no preview card.
    """
    src = (link_src or "").strip()
    if not PAGE_SRC_RE.match(src):
        src = FALLBACK_SRC
    return f"{GO_URL}?src={src}"


def compose_comment(template: str, link_src: str) -> str:
    """Merge a pool line with this Page's funnel link.

    ``{link}`` lets a line place the URL mid-sentence; without it the link
    goes on its own line so the sentence still reads on its own.
    """
    text = (template or "").strip()
    if not text:
        return ""
    link = funnel_link(link_src)
    if LINK_PLACEHOLDER in text:
        return text.replace(LINK_PLACEHOLDER, link).strip()
    return f"{text}\n{link}"


def _pool_index(pool_size: int, seed: str) -> int:
    """Pick a pool line deterministically.

    Deterministic so a retry of the same post picks the same sentence
    instead of stacking a second, different comment underneath the first.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % pool_size


@dataclass(frozen=True)
class BoostAction:
    """One supporting Page's contribution to one post."""

    account_id: int
    external_account_id: str
    handle: str
    message: str
    delay_seconds: int
    link_src: str
    # The raw pool line, before the link was merged in. Recorded alongside
    # the action so "what has this Page said recently" is a lookup rather
    # than string-surgery on the composed comment.
    source_line: str = ""

    def as_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "handle": self.handle,
            "message": self.message,
            "delay_seconds": self.delay_seconds,
            "delay_minutes": round(self.delay_seconds / 60),
            "link": funnel_link(self.link_src),
            "source_line": self.source_line,
        }


@dataclass
class BoostPlan:
    actions: list[BoostAction] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "actions": [a.as_dict() for a in self.actions],
            "skipped": self.skipped,
            "enabled": enabled(),
        }


def _skip(handle: str, account_id: int, reason: str) -> dict:
    return {"account_id": account_id, "handle": handle, "reason": reason}


def plan_boost(
    *,
    post_key: str,
    leader_account_id: int,
    supporters: list,
    spent_today: dict[int, int],
    recent_by_account: dict[int, list[str]] | None = None,
    limit: int | None = None,
    window: int | None = None,
    min_delay: int | None = None,
) -> BoostPlan:
    """Decide which of our Pages support this post, and with what text.

    ``supporters`` are candidate ``SocialAccount`` rows (already filtered to
    the same owner and to Facebook). ``spent_today`` maps account id to how
    many posts that Page has already boosted in the window.
    ``recent_by_account`` maps account id to the lines that Page has used
    most recently, newest first, so it does not repeat itself -- a pool of
    three sentences otherwise cycles every third boost, and "repetitive
    comments" is banned outright on Instagram and reads as spam on Facebook.

    Nothing here talks to the network, so every rule is unit-testable.
    """
    limit = max_supporters_per_post() if limit is None else limit
    window = window_minutes() if window is None else window
    min_delay = min_delay_minutes() if min_delay is None else min_delay

    plan = BoostPlan()
    eligible: list[tuple[object, dict, str]] = []

    for account in supporters:
        handle = getattr(account, "handle", "") or ""
        aid = getattr(account, "id", 0)
        if aid == leader_account_id:
            continue  # a Page does not support its own post
        if getattr(account, "revoked_at", None):
            plan.skipped.append(_skip(handle, aid, "帳號授權已撤銷"))
            continue
        profile = read_profile(account)
        interaction = profile.get("interaction") or {}
        if interaction.get("role") != "supporter":
            continue  # role off / leader -- silent, this is the default state
        allowance = int(interaction.get("max_per_day") or 0)
        if allowance <= 0:
            plan.skipped.append(_skip(handle, aid, "每日上限設成 0"))
            continue
        if spent_today.get(aid, 0) >= allowance:
            plan.skipped.append(
                _skip(handle, aid, f"今天已經互動 {spent_today.get(aid, 0)} 次，達到上限")
            )
            continue
        pool = [t for t in (interaction.get("comment_pool") or [])
                if len(t.strip()) >= MIN_COMMENT_CHARS]
        if not pool:
            # Deliberately not falling back to a shared sentence: identical
            # text across Pages is the exact pattern that gets a network
            # flagged. No pool means this Page stays quiet.
            plan.skipped.append(_skip(handle, aid, "留言素材池是空的，沒有東西可以講"))
            continue
        eligible.append((account, profile, handle))

    # Stable ordering: same post always picks the same Pages, so a retry
    # doesn't recruit a second wave on top of the first.
    eligible.sort(key=lambda item: hashlib.sha256(
        f"{post_key}:{getattr(item[0], 'id', 0)}".encode("utf-8")
    ).hexdigest())

    if limit <= 0:
        for account, _profile, handle in eligible:
            plan.skipped.append(
                _skip(handle, getattr(account, "id", 0), "每則貼文的互助上限設成 0")
            )
        return plan

    chosen = eligible[:limit]
    for account, _profile, handle in eligible[limit:]:
        plan.skipped.append(
            _skip(handle, getattr(account, "id", 0),
                  f"這則貼文已經排了 {limit} 個粉專，其餘不再加")
        )

    used_messages: set[str] = set()
    slots = _delay_slots(post_key, len(chosen), window, min_delay)

    for index, (account, profile, handle) in enumerate(chosen):
        interaction = profile.get("interaction") or {}
        pool = [t.strip() for t in (interaction.get("comment_pool") or [])
                if len(t.strip()) >= MIN_COMMENT_CHARS]
        link_src = profile.get("link_src") or ""
        account_id = getattr(account, "id", 0)
        start = _pool_index(len(pool), f"{post_key}:{account_id}")
        recent = (recent_by_account or {}).get(account_id) or []
        # Rotate through this Page's own pool, starting at a deterministic
        # offset, and take the first line no other Page has claimed on this
        # post. Among those, prefer one this Page has not said recently --
        # if the whole pool is recent we still speak, using whatever it said
        # longest ago, rather than going silent over a style preference.
        free = [pool[(start + offset) % len(pool)] for offset in range(len(pool))]
        free = [line for line in free if line not in used_messages]

        def staleness(line: str) -> int:
            # Never said -> most stale. Otherwise, further back in `recent`
            # (newest first) is staler.
            return len(recent) if line not in recent else recent.index(line)

        message = ""
        pick = ""
        if free:
            pick = max(free, key=staleness)
            message = compose_comment(pick, link_src)
            used_messages.add(pick)
        if not message:
            plan.skipped.append(
                _skip(handle, getattr(account, "id", 0),
                      "素材池裡每一句都已經有別的粉專在這則貼文用了")
            )
            continue
        plan.actions.append(
            BoostAction(
                account_id=getattr(account, "id", 0),
                external_account_id=getattr(account, "external_account_id", ""),
                handle=handle,
                message=message,
                delay_seconds=slots[index],
                link_src=link_src if PAGE_SRC_RE.match(link_src or "") else FALLBACK_SRC,
                source_line=pick,
            )
        )

    plan.actions.sort(key=lambda a: a.delay_seconds)
    return plan


def _delay_slots(post_key: str, count: int, window: int, min_delay: int) -> list[int]:
    """Spread N supporters across the window, never two in the same minute.

    Determinism matters here for the same reason as the pool pick: a task
    replay must land on the same schedule rather than inventing a second
    burst.
    """
    if count <= 0:
        return []
    span = max(window - min_delay, count)  # minutes available after the floor
    digest = hashlib.sha256(post_key.encode("utf-8")).digest()
    offsets: list[int] = []
    for i in range(count):
        chunk = hashlib.sha256(digest + i.to_bytes(4, "big")).digest()
        offsets.append(int.from_bytes(chunk[:4], "big") % span)
    offsets.sort()
    # Push apart any two that landed in the same minute.
    for i in range(1, len(offsets)):
        if offsets[i] <= offsets[i - 1]:
            offsets[i] = offsets[i - 1] + 1
    return [(min_delay + o) * 60 for o in offsets]
