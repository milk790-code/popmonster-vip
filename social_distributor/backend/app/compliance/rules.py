"""Per-platform community-rule snippets used as a guard rail.

The lists are deliberately narrow — they catch obvious problems before content
reaches the platform API, where rejections are slow and noisy. Each platform
publishes its own canonical guidelines; consult those for the authoritative
rules.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..models import Platform


@dataclass(frozen=True)
class PlatformRules:
    caption_max: int
    title_max: int | None
    requires_media: bool
    allowed_media: tuple[str, ...]
    banned_hashtags: tuple[str, ...] = ()
    notes: str = ""


PLATFORM_RULES: dict[Platform, PlatformRules] = {
    Platform.FACEBOOK: PlatformRules(
        caption_max=63206,
        title_max=None,
        requires_media=False,
        allowed_media=("image", "video"),
        notes="Pages must comply with Meta Community Standards.",
    ),
    Platform.INSTAGRAM: PlatformRules(
        caption_max=2200,
        title_max=None,
        requires_media=True,
        allowed_media=("image", "video"),
        notes="Captions allow up to 30 hashtags; over-use can demote posts.",
    ),
    Platform.TIKTOK: PlatformRules(
        caption_max=2200,
        title_max=None,
        requires_media=True,
        allowed_media=("video",),
        banned_hashtags=("#fyp", "#foryou"),
        notes=(
            "Tags like #fyp do not guarantee placement and can look spammy; "
            "TikTok Community Guidelines forbid integrity-and-authenticity "
            "violations such as engagement manipulation."
        ),
    ),
    Platform.YOUTUBE: PlatformRules(
        caption_max=5000,
        title_max=100,
        requires_media=True,
        allowed_media=("video",),
        notes="Avoid misleading metadata; misleading thumbnails violate policy.",
    ),
}
