"""Abstract interfaces for OAuth providers and content publishers.

Adapters wrap the official platform APIs. They are intentionally thin so
behaviour stays close to platform documentation, which keeps the implementation
robust against API drift. Adapters MUST raise :class:`PlatformError` (or a
subclass) on failure so the retry/audit machinery can react uniformly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TokenBundle:
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scopes: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublishRequest:
    caption: str
    title: str = ""
    link_url: str | None = None
    media_url: str | None = None
    media_kind: str | None = None  # "video" | "image" | None
    # Text posted as a comment on our own post immediately after publishing.
    # Empty means "don't comment". Supports a ``{link}`` placeholder.
    first_comment: str = ""
    overrides: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublishResult:
    external_post_id: str
    permalink: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    # The auto first comment (the one carrying the funnel link) is posted as
    # part of publishing, and its failure must never fail the post. That is
    # why it went unnoticed for months: swallowed silently, a comment that
    # had never once worked looked exactly like one working fine. Reporting
    # the outcome here lets the caller record it without the platform layer
    # reaching into the database.
    first_comment_id: str = ""
    first_comment_error: str = ""
    # Set when a funnel link was already on the post (another engine
    # beat us to it). Not an error and not a success -- a third state,
    # because collapsing it into either one hides a real duplicate.
    first_comment_skipped: str = ""
    # Which surface the video actually landed on ("reel" or "video"), and why
    # it fell back if it did. A Reel is the only surface Facebook still shows
    # to non-followers for free, so on a Page with no followers this is the
    # difference between some plays and none. Without recording it, a fleet
    # that had quietly stopped qualifying for Reels would look identical to
    # one that never stopped -- the same blind spot as the first comment.
    surface: str = ""
    surface_fallback_error: str = ""


@dataclass
class InsightsSnapshot:
    """Normalised engagement metrics. ``None`` for fields a platform omits."""
    reach: int | None = None
    impressions: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    plays: int | None = None
    watch_time_seconds: float | None = None
    avg_view_pct: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class PlatformError(Exception):
    """Raised on platform API failures.

    ``retryable`` distinguishes transient errors (5xx, rate-limit) from
    permanent ones (validation, auth) so the scheduler does not waste retries.
    """

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
        platform_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.platform_code = platform_code


class OAuthProvider(ABC):
    name: str

    @abstractmethod
    def authorization_url(self, state: str) -> str: ...

    @abstractmethod
    def exchange_code(self, code: str) -> TokenBundle: ...

    def refresh(self, refresh_token: str) -> TokenBundle:
        raise NotImplementedError


class Publisher(ABC):
    name: str

    @abstractmethod
    def publish(
        self,
        token: TokenBundle,
        external_account_id: str,
        request: PublishRequest,
    ) -> PublishResult: ...

    def validate(self, request: PublishRequest) -> list[str]:
        """Pre-publish validation hooks. Returns a list of human-readable issues."""
        return []

    def fetch_insights(
        self,
        token: TokenBundle,
        external_account_id: str,
        external_post_id: str,
    ) -> InsightsSnapshot | None:
        """Pull engagement metrics. Return ``None`` when not supported."""
        return None
