"""Threads publisher and OAuth provider (Meta Threads API v1.0).

Reference:
- https://developers.facebook.com/docs/threads
- https://developers.facebook.com/docs/threads/posts
- https://developers.facebook.com/docs/threads/videos

Publishing flow (2-step container model):
1. POST /{user_id}/threads  → creation_id  (media container)
2. Poll /{creation_id}?fields=status,error_message until FINISHED
3. POST /{user_id}/threads_publish → id  (live post)
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

from ..config import config
from ._http import request_json
from .base import (
    InsightsSnapshot,
    OAuthProvider,
    PlatformError,
    PublishRequest,
    PublishResult,
    Publisher,
    TokenBundle,
)

THREADS_BASE = "https://graph.threads.net/v1.0"
THREADS_AUTH_BASE = "https://www.threads.net/oauth/authorize"
THREADS_TOKEN_URL = "https://graph.threads.net/oauth/access_token"
THREADS_LONG_LIVED_URL = "https://graph.threads.net/access_token"

DEFAULT_SCOPES = [
    "threads_basic",
    "threads_content_publish",
    "threads_read_replies",
    "threads_manage_replies",
    "threads_manage_insights",
]

# How long to poll the container status before giving up (seconds)
CONTAINER_POLL_TIMEOUT = 120
CONTAINER_POLL_INTERVAL = 5


class ThreadsOAuth(OAuthProvider):
    name = "threads"

    def authorization_url(self, state: str) -> str:
        creds = config.platform("threads")
        if not creds.configured:
            raise PlatformError("threads app credentials not configured", retryable=False)
        params = {
            "client_id": creds.client_id,
            "redirect_uri": creds.redirect_uri,
            "scope": ",".join(DEFAULT_SCOPES),
            "response_type": "code",
            "state": state,
        }
        return f"{THREADS_AUTH_BASE}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenBundle:
        creds = config.platform("threads")
        if not creds.configured:
            raise PlatformError("threads app credentials not configured", retryable=False)

        # Step 1: short-lived token
        data = request_json(
            "POST",
            THREADS_TOKEN_URL,
            data={
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "grant_type": "authorization_code",
                "redirect_uri": creds.redirect_uri,
                "code": code,
            },
        )
        short_token = data["access_token"]
        user_id = str(data.get("user_id", ""))

        # Step 2: long-lived token (60 days)
        long_data = request_json(
            "GET",
            THREADS_LONG_LIVED_URL,
            params={
                "grant_type": "th_exchange_token",
                "client_secret": creds.client_secret,
                "access_token": short_token,
            },
        )
        long_token = long_data["access_token"]
        expires_in = long_data.get("expires_in", 5183944)  # ~60 days default
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        return TokenBundle(
            access_token=long_token,
            refresh_token=long_token,  # Threads uses the same token for refresh
            expires_at=expires_at,
            scopes=DEFAULT_SCOPES,
            extra={"threads_user_id": user_id},
        )

    def refresh(self, refresh_token: str) -> TokenBundle:
        """Refresh a long-lived Threads token (extends another 60 days)."""
        data = request_json(
            "GET",
            THREADS_LONG_LIVED_URL,
            params={
                "grant_type": "th_refresh_token",
                "access_token": refresh_token,
            },
        )
        expires_in = data.get("expires_in", 5183944)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        return TokenBundle(
            access_token=data["access_token"],
            refresh_token=data["access_token"],
            expires_at=expires_at,
            scopes=DEFAULT_SCOPES,
        )


class ThreadsPublisher(Publisher):
    """Publish text + video posts to Threads."""

    def _get_threads_user_id(self, token: str) -> str:
        """Resolve the Threads user ID from /me."""
        me = request_json(
            "GET",
            f"{THREADS_BASE}/me",
            params={"fields": "id,username", "access_token": token},
        )
        return me["id"]

    def _create_container(
        self,
        threads_user_id: str,
        token: str,
        req: PublishRequest,
    ) -> str:
        """Step 1: Create media container, return creation_id."""
        params: dict[str, Any] = {
            "access_token": token,
            "text": req.caption,
        }

        if req.media_url and req.media_kind == "video":
            params["media_type"] = "VIDEO"
            params["video_url"] = req.media_url
        elif req.media_url and req.media_kind == "image":
            params["media_type"] = "IMAGE"
            params["image_url"] = req.media_url
        else:
            params["media_type"] = "TEXT"

        data = request_json(
            "POST",
            f"{THREADS_BASE}/{threads_user_id}/threads",
            params=params,
        )
        creation_id = data.get("id")
        if not creation_id:
            raise PlatformError(
                f"threads container creation returned no id: {data}",
                retryable=False,
            )
        return creation_id

    def _poll_container(self, creation_id: str, token: str) -> None:
        """Step 2: Poll until container status = FINISHED (or timeout)."""
        deadline = time.monotonic() + CONTAINER_POLL_TIMEOUT
        while time.monotonic() < deadline:
            data = request_json(
                "GET",
                f"{THREADS_BASE}/{creation_id}",
                params={
                    "fields": "status,error_message",
                    "access_token": token,
                },
            )
            status = data.get("status", "")
            if status == "FINISHED":
                return
            if status == "ERROR":
                error_msg = data.get("error_message", "unknown")
                raise PlatformError(
                    f"threads container error: {error_msg}",
                    retryable=False,
                )
            time.sleep(CONTAINER_POLL_INTERVAL)

        raise PlatformError(
            f"threads container {creation_id} timed out after {CONTAINER_POLL_TIMEOUT}s",
            retryable=True,
        )

    def _publish_container(
        self, threads_user_id: str, creation_id: str, token: str
    ) -> str:
        """Step 3: Publish the container, return the live post ID."""
        data = request_json(
            "POST",
            f"{THREADS_BASE}/{threads_user_id}/threads_publish",
            params={
                "creation_id": creation_id,
                "access_token": token,
            },
        )
        post_id = data.get("id")
        if not post_id:
            raise PlatformError(
                f"threads publish returned no post id: {data}",
                retryable=False,
            )
        return post_id

    def publish(self, req: PublishRequest, account_token: str) -> PublishResult:
        threads_user_id = self._get_threads_user_id(account_token)

        creation_id = self._create_container(threads_user_id, account_token, req)

        if req.media_kind == "video":
            # Video containers need time to process
            self._poll_container(creation_id, account_token)

        post_id = self._publish_container(threads_user_id, creation_id, account_token)
        permalink = f"https://www.threads.net/post/{post_id}"

        return PublishResult(
            external_post_id=post_id,
            permalink=permalink,
            raw={"creation_id": creation_id, "threads_user_id": threads_user_id},
        )

    def fetch_insights(
        self, external_post_id: str, account_token: str
    ) -> InsightsSnapshot:
        """Fetch basic engagement metrics for a published post."""
        data = request_json(
            "GET",
            f"{THREADS_BASE}/{external_post_id}/insights",
            params={
                "metric": "views,likes,replies,reposts,quotes",
                "access_token": account_token,
            },
        )
        metrics: dict[str, int] = {}
        for item in data.get("data", []):
            metrics[item["name"]] = item.get("values", [{}])[0].get("value", 0)

        return InsightsSnapshot(
            impressions=metrics.get("views"),
            likes=metrics.get("likes"),
            comments=metrics.get("replies"),
            shares=metrics.get("reposts"),
            raw=data,
        )
