"""Threads platform adapter.

OAuth uses graph.threads.net (not graph.facebook.com).
Publishing is a two-step process:
  1. Create a media container
  2. Publish the container

Docs: https://developers.facebook.com/docs/threads/getting-started
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .base import (
    OAuthProvider,
    PlatformError,
    PublishRequest,
    PublishResult,
    Publisher,
    TokenBundle,
)

_THREADS_API = "https://graph.threads.net/v1.0"
_AUTH_BASE   = "https://www.threads.net/oauth"

APP_ID     = os.getenv("THREADS_APP_ID", "")
APP_SECRET = os.getenv("THREADS_APP_SECRET", "")
REDIRECT   = os.getenv("THREADS_REDIRECT_URI", "")


def _raise(resp: requests.Response, context: str) -> None:
    try:
        err = resp.json().get("error", {})
        msg = err.get("message", resp.text)
        code = str(err.get("code", resp.status_code))
    except Exception:
        msg = resp.text or "unknown error"
        code = str(resp.status_code)
    retryable = resp.status_code >= 500
    raise PlatformError(
        f"Threads {context}: {msg}",
        retryable=retryable,
        status_code=resp.status_code,
        platform_code=code,
    )


class ThreadsOAuth(OAuthProvider):
    name = "threads"

    def authorization_url(self, state: str) -> str:
        scope = "threads_basic,threads_content_publish"
        return (
            f"{_AUTH_BASE}/authorize"
            f"?client_id={APP_ID}"
            f"&redirect_uri={REDIRECT}"
            f"&scope={scope}"
            f"&response_type=code"
            f"&state={state}"
        )

    def exchange_code(self, code: str) -> TokenBundle:
        # Step 1: short-lived token
        r = requests.post(
            f"{_AUTH_BASE}/access_token",
            data={
                "client_id": APP_ID,
                "client_secret": APP_SECRET,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT,
                "code": code,
            },
            timeout=30,
        )
        if not r.ok:
            _raise(r, "code exchange")
        short = r.json()["access_token"]

        # Step 2: long-lived token (valid 60 days)
        r2 = requests.get(
            "https://graph.threads.net/access_token",
            params={
                "grant_type": "th_exchange_token",
                "client_id": APP_ID,
                "client_secret": APP_SECRET,
                "access_token": short,
            },
            timeout=30,
        )
        if not r2.ok:
            # Fall back to short-lived if exchange fails
            expires = datetime.now(timezone.utc) + timedelta(hours=1)
            return TokenBundle(access_token=short, expires_at=expires)

        data = r2.json()
        token = data.get("access_token", short)
        expires_in = data.get("expires_in", 5_184_000)  # 60 days
        expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        return TokenBundle(access_token=token, expires_at=expires)

    def refresh(self, refresh_token: str) -> TokenBundle:
        """Threads uses token refresh via th_refresh_token."""
        r = requests.get(
            "https://graph.threads.net/refresh_access_token",
            params={
                "grant_type": "th_refresh_token",
                "access_token": refresh_token,
            },
            timeout=30,
        )
        if not r.ok:
            _raise(r, "token refresh")
        data = r.json()
        token = data["access_token"]
        expires_in = data.get("expires_in", 5_184_000)
        expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        return TokenBundle(access_token=token, expires_at=expires)


class ThreadsPublisher(Publisher):
    name = "threads"
    _POLL_MAX = 30
    _POLL_INTERVAL = 2

    def publish(
        self,
        token: TokenBundle,
        external_account_id: str,
        request: PublishRequest,
    ) -> PublishResult:
        at = token.access_token

        # Step 1: create container
        payload: dict[str, Any] = {
            "access_token": at,
            "text": request.caption,
        }
        if request.media_url and request.media_kind == "video":
            payload.update({"media_type": "VIDEO", "video_url": request.media_url})
        elif request.media_url and request.media_kind == "image":
            payload.update({"media_type": "IMAGE", "image_url": request.media_url})
        else:
            payload["media_type"] = "TEXT"

        r = requests.post(
            f"{_THREADS_API}/{external_account_id}/threads",
            data=payload,
            timeout=60,
        )
        if not r.ok:
            _raise(r, "create container")
        container_id = r.json()["id"]

        # Step 2: poll until container is ready
        for _ in range(self._POLL_MAX):
            time.sleep(self._POLL_INTERVAL)
            status_r = requests.get(
                f"{_THREADS_API}/{container_id}",
                params={"fields": "status,error_message", "access_token": at},
                timeout=15,
            )
            if status_r.ok:
                st = status_r.json().get("status", "")
                if st == "FINISHED":
                    break
                if st == "ERROR":
                    err_msg = status_r.json().get("error_message", "unknown")
                    raise PlatformError(f"Threads container error: {err_msg}", retryable=False)

        # Step 3: publish
        pub_r = requests.post(
            f"{_THREADS_API}/{external_account_id}/threads_publish",
            data={"creation_id": container_id, "access_token": at},
            timeout=30,
        )
        if not pub_r.ok:
            _raise(pub_r, "publish")
        post_id = pub_r.json()["id"]

        permalink = None
        info_r = requests.get(
            f"{_THREADS_API}/{post_id}",
            params={"fields": "permalink", "access_token": at},
            timeout=15,
        )
        if info_r.ok:
            permalink = info_r.json().get("permalink")

        return PublishResult(
            external_post_id=post_id,
            permalink=permalink,
            raw=pub_r.json(),
        )

    def validate(self, request: PublishRequest) -> list[str]:
        issues = []
        if len(request.caption) > 500:
            issues.append("Threads caption exceeds 500 characters")
        return issues
