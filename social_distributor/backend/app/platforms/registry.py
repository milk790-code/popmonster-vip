"""Lookup tables for platform adapters."""
from __future__ import annotations

from ..models import Platform
from .base import OAuthProvider, Publisher
from .facebook import FacebookPublisher, MetaOAuth
from .instagram import InstagramPublisher
from .shopee import ShopeeOAuth, ShopeePublisher
from .threads import ThreadsOAuth, ThreadsPublisher
from .tiktok import TikTokOAuth, TikTokPublisher
from .youtube import YouTubeOAuth, YouTubePublisher

_PUBLISHERS: dict[Platform, Publisher] = {
    Platform.FACEBOOK: FacebookPublisher(),
    Platform.INSTAGRAM: InstagramPublisher(),
    Platform.META_THREADS: ThreadsPublisher(),
    Platform.TIKTOK: TikTokPublisher(),
    Platform.YOUTUBE: YouTubePublisher(),
    Platform.SHOPEE: ShopeePublisher(),
}

_OAUTH: dict[str, OAuthProvider] = {
    "meta": MetaOAuth(),
    "threads": ThreadsOAuth(),
    "tiktok": TikTokOAuth(),
    "youtube": YouTubeOAuth(),
    "shopee": ShopeeOAuth(),
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
