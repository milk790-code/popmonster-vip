"""Lookup tables for platform adapters."""
from __future__ import annotations

from ..models import Platform
from .base import OAuthProvider, Publisher
from .facebook import FacebookPublisher, MetaOAuth
from .instagram import InstagramPublisher
from .tiktok import TikTokOAuth, TikTokPublisher
from .youtube import YouTubeOAuth, YouTubePublisher

_PUBLISHERS: dict[Platform, Publisher] = {
    Platform.FACEBOOK: FacebookPublisher(),
    Platform.INSTAGRAM: InstagramPublisher(),
    Platform.TIKTOK: TikTokPublisher(),
    Platform.YOUTUBE: YouTubePublisher(),
}

_OAUTH: dict[str, OAuthProvider] = {
    "meta": MetaOAuth(),
    "tiktok": TikTokOAuth(),
    "youtube": YouTubeOAuth(),
}


def get_publisher(platform: Platform) -> Publisher:
    if platform not in _PUBLISHERS:
        raise KeyError(f"no publisher registered for platform {platform}")
    return _PUBLISHERS[platform]


def get_oauth_provider(name: str) -> OAuthProvider:
    if name not in _OAUTH:
        raise KeyError(f"no oauth provider named {name}")
    return _OAUTH[name]


def all_platforms() -> list[Platform]:
    return list(_PUBLISHERS.keys())
