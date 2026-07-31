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
# Public alias used by the OAuth callback (routes.py) to resolve /me.
THREADS_BASE = _THREADS_API
_AUTH_BASE   = "https://www.threads.net/oauth"

# Public defaults reuse the existing "3q-threads-publisher" consumer app.
# The App ID is a public OAuth client_id (already shipped in 3q-hatchery's
# threads-auth.html and visible in every authorize URL). Only
# THREADS_APP_SECRET is a real secret and must be set in the environment.
# Env always overrides these defaults.
APP_ID     = os.getenv("THREADS_APP_ID", "") or "3114808732061005"
APP_SECRET = os.getenv("THREADS_APP_SECRET", "")
REDIRECT   = os.getenv("THREADS_REDIRECT_URI", "") or (
    "https://api-production-6de7.up.railway.app/auth/threads/callback"
)


def _raise(resp: requests.Response, context: str) -> None:
    """Raise with everything Meta told us, not just ``message``.

    Meta's top-level ``message`` is often just "Invalid parameter", which is
    useless on its own — a Threads post failed nightly for over ten days with
    exactly that string and no way to tell which parameter. The detail lives
    in ``error_subcode``, ``error_user_title``/``error_user_msg`` (the
    human-readable pair) and ``fbtrace_id`` (what Meta support asks for).
    Dropping them turns a diagnosable failure into a guess.
    """
    subcode = user_msg = trace = None
    try:
        err = resp.json().get("error", {})
        msg = err.get("message", resp.text)
        code = str(err.get("code", resp.status_code))
        subcode = err.get("error_subcode")
        user_msg = " / ".join(
            p for p in (err.get("error_user_title"), err.get("error_user_msg")) if p
        ) or None
        trace = err.get("fbtrace_id")
    except Exception:
        msg = resp.text or "unknown error"
        code = str(resp.status_code)

    parts = [f"Threads {context}: {msg}"]
    if user_msg:
        parts.append(f"（{user_msg}）")
    extras = ", ".join(
        f"{k}={v}" for k, v in (("subcode", subcode), ("fbtrace_id", trace)) if v
    )
    if extras:
        parts.append(f"[{extras}]")

    raise PlatformError(
        " ".join(parts),
        retryable=resp.status_code >= 500,
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
        # Step 1: short-lived token. The token endpoint lives on
        # graph.threads.net (NOT www.threads.net, which only hosts the
        # authorize dialog) — posting to www.threads.net/oauth/access_token
        # returns a platform error and the whole exchange fails.
        r = requests.post(
            "https://graph.threads.net/oauth/access_token",
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
