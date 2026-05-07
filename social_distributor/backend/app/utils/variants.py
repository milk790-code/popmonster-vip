"""Per-platform caption variant engine.

Given a source caption and a group's ``style_profile``, produce one variant
caption per (platform, account). The goal is **content richness** — same idea
in each persona's voice — not deception. Identical text mass-posted across
many accounts is what platforms' integrity heuristics flag as spam, so a
matrix workflow needs natural variation.

If ``ANTHROPIC_API_KEY`` is set we use Claude (with prompt caching on the
style profile, since it's reused across many calls). Otherwise we fall back
to a deterministic template that swaps hashtag pools and tone markers — not
as good but never blocks distribution.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
from dataclasses import dataclass

log = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("ANTHROPIC_VARIANT_MODEL", "claude-haiku-4-5-20251001")


@dataclass
class VariantRequest:
    source_caption: str
    source_title: str
    platform: str          # facebook | instagram | tiktok | youtube
    style_profile: dict
    seed: str              # stable identifier — same seed → same output


@dataclass
class VariantResult:
    caption: str
    title: str
    used_engine: str       # "claude" | "template"


def generate_variant(req: VariantRequest) -> VariantResult:
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _claude_variant(req)
        except Exception as exc:
            log.warning("Claude variant failed (%s); falling back to template", exc)
    return _template_variant(req)


# ---------------------------------------------------------------------------
# Claude implementation with prompt caching of the style profile.
# ---------------------------------------------------------------------------

_PLATFORM_HINTS = {
    "facebook": "Long-form is OK. Conversational. Up to 3 hashtags.",
    "instagram": "Engaging hook in first line. Up to 30 hashtags but quality > quantity. 2,200 char hard limit.",
    "tiktok": "Punchy first line. 2,200 char limit. Hashtags should be specific, not #fyp.",
    "youtube": "Title under 100 chars (return separately). Description can include timestamps and links.",
}


def _claude_variant(req: VariantRequest) -> VariantResult:
    from anthropic import Anthropic

    client = Anthropic()
    style_block = json.dumps(req.style_profile, ensure_ascii=False, indent=2)

    system = [
        {
            "type": "text",
            "text": (
                "You rewrite social media captions so each persona speaks in "
                "its own voice while preserving the source content's meaning. "
                "You never invent facts, never add fake stats, never claim "
                "endorsements. You return strict JSON: "
                '{"title": "...", "caption": "..."} with no surrounding prose.'
            ),
        },
        {
            "type": "text",
            "text": f"Persona style profile:\n{style_block}",
            # Cache the style profile across calls for the same group.
            "cache_control": {"type": "ephemeral"},
        },
    ]

    user_text = (
        f"Platform: {req.platform}\n"
        f"Platform conventions: {_PLATFORM_HINTS.get(req.platform, '')}\n\n"
        f"Source title: {req.source_title}\n"
        f"Source caption:\n{req.source_caption}\n\n"
        f"Rewrite for this platform in the persona's voice. "
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
