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
    overrides: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublishResult:
    external_post_id: str
    permalink: str | None = None
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
