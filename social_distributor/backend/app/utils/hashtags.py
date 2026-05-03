"""Hashtag suggestions per platform.

Uses the same Claude pattern as :mod:`app.utils.variants` (style profile
cached, platform conventions short prompt). Returns a deduped list of
hashtags ordered by relevance.

Without ``ANTHROPIC_API_KEY`` we fall back to the persona's ``hashtag_pool``
deterministically pruned by length — no Claude, no invented tags. A pool
shorter than ``count`` is fine, we return what we have.

This is intentionally separate from variants: variants can rewrite text in
voice; hashtag suggestion narrows in on tag selection only, so the prompt
is tighter and the cost per call is lower.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
from dataclasses import dataclass

from ..compliance.rules import PLATFORM_RULES
from ..models import Platform

log = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("ANTHROPIC_VARIANT_MODEL", "claude-haiku-4-5-20251001")


@dataclass
class HashtagRequest:
    caption: str
    platform: str
    style_profile: dict
    count: int = 5


@dataclass
class HashtagResult:
    hashtags: list[str]
    used_engine: str  # "claude" | "pool"


def suggest_hashtags(req: HashtagRequest) -> HashtagResult:
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _claude(req)
        except Exception as exc:
            log.warning("Claude hashtag failed (%s); falling back to pool", exc)
    return _pool_fallback(req)


_BANNED_BY_PLATFORM: dict[str, tuple[str, ...]] = {
    plat.value: rules.banned_hashtags
    for plat, rules in PLATFORM_RULES.items()
}


def _filter_disallowed(tags: list[str], platform: str) -> list[str]:
    banned = {b.lower() for b in _BANNED_BY_PLATFORM.get(platform, ())}
    return [t for t in tags if t.lower() not in banned]


def _normalise(tag: str) -> str:
    tag = tag.strip()
    if not tag:
        return ""
    if not tag.startswith("#"):
        tag = "#" + tag
    # Strip whitespace inside the tag.
    return re.sub(r"\s+", "", tag)


def _dedupe(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def _claude(req: HashtagRequest) -> HashtagResult:
    from anthropic import Anthropic

    client = Anthropic()
    style_block = json.dumps(req.style_profile, ensure_ascii=False, indent=2)

    system = [
        {
            "type": "text",
            "text": (
                "You suggest social-media hashtags for a single piece of "
                "content. Return ONLY a JSON array of strings, e.g. "
                '["#tag1","#tag2"]. No prose, no markdown fences. '
                "Tags must start with '#' and contain no whitespace. "
                "Prefer specific tags over broad ones (#台北拉麵 over #食物). "
                "Never invent claims (e.g. don't add #verified)."
            ),
        },
        {
            "type": "text",
            "text": f"Persona style profile:\n{style_block}",
            "cache_control": {"type": "ephemeral"},
        },
    ]
    user_text = (
        f"Platform: {req.platform}\n"
        f"Suggest {req.count} hashtags for this caption:\n\n{req.caption}"
    )
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=400,
        system=system,
        messages=[{"role": "user", "content": user_text}],
    )
    raw = "".join(
        block.text for block in response.content
        if getattr(block, "type", None) == "text"
    ).strip()
    if raw.startswith("```"):
        raw = "\n".join(line for line in raw.splitlines() if not line.startswith("```")).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Claude returned non-JSON for hashtags; falling back")
        return _pool_fallback(req)
    if not isinstance(parsed, list):
        return _pool_fallback(req)

    tags = [_normalise(str(t)) for t in parsed]
    tags = [t for t in tags if t]
    tags = _filter_disallowed(_dedupe(tags), req.platform)[: req.count]
    return HashtagResult(hashtags=tags, used_engine="claude")


def _pool_fallback(req: HashtagRequest) -> HashtagResult:
    pool = list(req.style_profile.get("hashtag_pool", []))
    pool = [_normalise(t) for t in pool if t]
    pool = _filter_disallowed(_dedupe(pool), req.platform)
    seed = hashlib.sha256(
        f"{req.caption}|{req.platform}".encode()
    ).hexdigest()
    rng = random.Random(int(seed, 16) % (2 ** 32))
    rng.shuffle(pool)
    return HashtagResult(hashtags=pool[: req.count], used_engine="pool")
