"""Per-platform caption variant engine.

Given a source caption and a group's ``style_profile``, produce one variant
caption per (platform, account). The goal is **content richness** — same idea
in each persona's voice — not deception. Identical text mass-posted across
many accounts is what platforms' integrity heuristics flag as spam, so a
matrix workflow needs natural variation.

If ``ANTHROPIC_API_KEY`` is set we use Claude with:
  - Prompt caching on the style profile
  - Few-shot examples from the group's top-performing posts (by engagement_rate)
  - Brand-safety net: mandatory compliance check before returning the variant
Otherwise we fall back to a deterministic template.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("ANTHROPIC_VARIANT_MODEL", "claude-opus-4-6")

REFERRAL_URL_BASE = os.environ.get("REFERRAL_URL_BASE", "https://popmonster.vip/?ref=")

_REFERRAL_CTA_BY_PLATFORM: dict[str, str] = {
    "facebook":  "🎁 用我的連結進站：{url}",
    "instagram": "🎁 用我的連結進站：{url}",
    "tiktok":    "🎁 進站連結：{url}",
    "threads":   "🎁 {url}",
    "youtube":   "🎁 用我的連結進站，送你專屬優惠：{url}",
}


def build_referral_cta(platform: str, code: str) -> str:
    url = REFERRAL_URL_BASE + code
    template = _REFERRAL_CTA_BY_PLATFORM.get(platform, "🎁 進站連結：{url}")
    return template.format(url=url)


# Spam/safety terms are rejected even if Claude copies them from the source.
ALWAYS_BLOCKLIST: list[str] = [
    r"follow\s*back",
    r"buy followers?",
    r"crypto\s+giveaway",
]

# Product-claim terms are rejected only when Claude introduces them. The source
# caption is already an operator-reviewed campaign asset, and some approved POP
# MONSTER calendars intentionally include search/category tags such as #鍍膜.
SOURCE_BOUND_BLOCKLIST: list[str] = [
    r"鍍膜",          # product should not be newly positioned as a coating
    r"保護一個月",     # unverifiable duration claim
    r"保護1個月",
    r"日本原裝",      # false provenance unless product actually is
    r"100%",          # absolute claims are unverifiable unless product spec confirms
]

# Do not block legitimate consultation CTAs such as "免費諮詢" or "免費 10 題 AI
# 診斷"; block free-goods style claims when they are newly introduced.
FREE_GOODS_BLOCKLIST: list[str] = [
    r"免費\s*(?:送|領|拿|試用|產品|商品|樣品|贈品|索取|兌換|抽)",
]

# Backward-compatible aggregate for tests/admin introspection.
BRAND_BLOCKLIST: list[str] = (
    ALWAYS_BLOCKLIST + SOURCE_BOUND_BLOCKLIST + FREE_GOODS_BLOCKLIST
)

# Numeric-fact check: caption should not introduce numbers the source didn't have.
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|倍|公里|km|ml|g)\b")


@dataclass
class VariantRequest:
    source_caption: str
    source_title: str
    platform: str          # facebook | instagram | tiktok | youtube | threads
    style_profile: dict
    seed: str              # stable identifier — same seed → same output
    few_shot_examples: list[dict] = field(default_factory=list)
    # Each example: {"caption": str, "engagement_rate": float}
    referral_code: str | None = None  # 若設定，caption 結尾附上裂變 CTA


@dataclass
class VariantResult:
    caption: str
    title: str
    used_engine: str       # "claude" | "template"


# ---------------------------------------------------------------------------
# Brand safety net — applied to every generated variant regardless of engine.
# ---------------------------------------------------------------------------

def _brand_safety_check(caption: str, source_caption: str) -> list[str]:
    """Return list of violation descriptions; empty list means clean."""
    issues: list[str] = []

    for pattern in ALWAYS_BLOCKLIST:
        if re.search(pattern, caption, re.IGNORECASE):
            issues.append(f"blocklist hit: {pattern}")

    for pattern in SOURCE_BOUND_BLOCKLIST + FREE_GOODS_BLOCKLIST:
        if re.search(pattern, caption, re.IGNORECASE) and not re.search(
            pattern, source_caption, re.IGNORECASE
        ):
            issues.append(f"new blocked claim: {pattern}")

    # Numbers in variant that weren't in source are suspicious claims.
    source_nums = set(_NUMBER_RE.findall(source_caption))
    variant_nums = set(_NUMBER_RE.findall(caption))
    new_nums = variant_nums - source_nums
    if new_nums:
        issues.append(f"新增未驗證數字: {', '.join(new_nums)}")

    return issues


def generate_variant(req: VariantRequest) -> VariantResult:
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            result = _claude_variant(req)
            violations = _brand_safety_check(result.caption, req.source_caption)
            if violations:
                log.warning(
                    "Claude variant failed brand safety (%s); falling back to template",
                    violations,
                )
            else:
                if req.referral_code:
                    result.caption = (
                        f"{result.caption}\n\n{build_referral_cta(req.platform, req.referral_code)}"
                    )
                return result
        except Exception as exc:
            log.warning("Claude variant failed (%s); falling back to template", exc)
    result = _template_variant(req)
    if req.referral_code:
        result.caption = (
            f"{result.caption}\n\n{build_referral_cta(req.platform, req.referral_code)}"
        )
    return result


# ---------------------------------------------------------------------------
# Claude implementation with prompt caching + few-shot examples.
# ---------------------------------------------------------------------------

_PLATFORM_HINTS = {
    "facebook": "Long-form is OK. Conversational. Up to 3 hashtags.",
    "instagram": "Engaging hook in first line. Up to 30 hashtags but quality > quantity. 2,200 char hard limit.",
    "tiktok": "Punchy first line. 2,200 char limit. Hashtags should be specific, not #fyp.",
    "youtube": "Title under 100 chars (return separately). Description can include timestamps and links.",
    "threads": "Concise. 500 char hard limit. Conversational tone. Minimal hashtags.",
}


def _build_few_shot_block(examples: list[dict]) -> str:
    if not examples:
        return ""
    lines = ["以下是這個人設過去互動率最高的貼文範例（供你學習文風，勿複製內容）："]
    for i, ex in enumerate(examples[:3], 1):
        rate = ex.get("engagement_rate", 0)
        caption = ex.get("caption", "")[:300]
        lines.append(f"\n範例{i}（互動率 {rate:.2%}）:\n{caption}")
    return "\n".join(lines)


def _claude_variant(req: VariantRequest) -> VariantResult:
    from anthropic import Anthropic

    client = Anthropic()
    style_block = json.dumps(req.style_profile, ensure_ascii=False, indent=2)
    few_shot_text = _build_few_shot_block(req.few_shot_examples)

    do_not_say = req.style_profile.get("do_not_say", [])
    blocklist_note = (
        f"\n\n絕對禁止出現的詞彙（do_not_say）: {', '.join(do_not_say)}"
        if do_not_say
        else ""
    )

    system = [
        {
            "type": "text",
            "text": (
                "You rewrite social media captions so each persona speaks in "
                "its own voice while preserving the source content's meaning. "
                "HARD RULE — output language: the rewritten title and caption "
                "MUST be in the same language as the source caption (Traditional "
                "Chinese source → Traditional Chinese output). The persona style "
                "profile may be written in English; it describes tone only and "
                "must NOT switch your output language. "
                "You never invent facts, never add fake stats, never claim "
                "endorsements, never introduce numbers that weren't in the source. "
                "You return strict JSON: "
                '{"title": "...", "caption": "..."} with no surrounding prose.'
                + blocklist_note
            ),
        },
        {
            "type": "text",
            "text": f"Persona style profile:\n{style_block}\n\n{few_shot_text}",
            # Cache the style profile + few-shot block across calls for the same group.
            "cache_control": {"type": "ephemeral"},
        },
    ]

    user_text = (
        f"Platform: {req.platform}\n"
        f"Platform conventions: {_PLATFORM_HINTS.get(req.platform, '')}\n\n"
        f"Source title: {req.source_title}\n"
        f"Source caption:\n{req.source_caption}\n\n"
        f"Rewrite for this platform in the persona's voice, in the SAME "
        f"language as the source caption above. "
        f"Keep emoji_density={req.style_profile.get('emoji_density', 'low')}. "
        f'Return JSON: {{"title": "...", "caption": "..."}}'
    )

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": user_text}],
    )

    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()
    payload = _parse_json_lenient(text)
    return VariantResult(
        caption=payload.get("caption", req.source_caption),
        title=payload.get("title", req.source_title),
        used_engine="claude",
    )


def _parse_json_lenient(text: str) -> dict:
    """Strip code fences if Claude wrapped the JSON in a fenced block."""
    text = text.strip()
    if text.startswith("```"):
        lines = [ln for ln in text.splitlines() if not ln.startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning("variant JSON parse failed; returning raw text as caption")
        return {"caption": text, "title": ""}


# ---------------------------------------------------------------------------
# Deterministic template fallback (no external API needed).
# ---------------------------------------------------------------------------

def _template_variant(req: VariantRequest) -> VariantResult:
    rng = random.Random(int(hashlib.sha256(req.seed.encode()).hexdigest(), 16) % (2**32))

    pool = list(req.style_profile.get("hashtag_pool", []))
    tone = req.style_profile.get("tone", "neutral")
    emoji_density = req.style_profile.get("emoji_density", "low")
    emojis_by_density = {
        "high": ["✨", "🔥", "💫", "🌟", "💖"],
        "medium": ["✨", "🔥"],
        "low": [],
    }
    emojis = emojis_by_density.get(emoji_density, [])

    base = req.source_caption.strip()
    if tone == "casual" and not base.startswith(("嘿", "Hey", "Yo")):
        base = f"嘿，{base}" if any("一" <= ch <= "鿿" for ch in base) else f"Hey — {base}"
    if tone == "formal":
        base = base.replace("!", ".").replace("！", "。")

    if emojis:
        base = f"{rng.choice(emojis)} {base}"

    rng.shuffle(pool)
    chosen_tags = pool[:5] if req.platform in ("instagram", "tiktok") else pool[:2]
    if chosen_tags:
        base = f"{base}\n\n{' '.join(chosen_tags)}"

    return VariantResult(
        caption=base,
        title=req.source_title,
        used_engine="template",
    )


# ---------------------------------------------------------------------------
# Helper: fetch top-performing posts for a group (call from Flask context).
# ---------------------------------------------------------------------------

def fetch_few_shot_examples(group_id: int, limit: int = 3) -> list[dict]:
    """Query the DB for the top-engagement posts from this persona group.

    Must be called within a Flask app context. Returns [] if no data yet.
    """
    try:
        from ..extensions import db
        from ..models import AccountGroup, PostMetric, PostTarget, Post

        rows = (
            db.session.query(
                Post.caption,
                db.func.avg(PostMetric.likes + PostMetric.comments + PostMetric.shares)
                .label("eng"),
            )
            .join(PostTarget, PostTarget.post_id == Post.id)
            .join(PostMetric, PostMetric.target_id == PostTarget.id)
            .filter(PostTarget.group_id == group_id)
            .filter(PostMetric.likes.isnot(None))
            .group_by(Post.id)
            .order_by(db.text("eng DESC"))
            .limit(limit)
            .all()
        )
        return [{"caption": r[0], "engagement_rate": float(r[1] or 0) / 1000} for r in rows]
    except Exception as exc:
        log.debug("fetch_few_shot_examples failed: %s", exc)
        return []
