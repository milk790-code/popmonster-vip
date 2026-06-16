"""TikTok Content Posting API publisher.

Reference:
- https://developers.tiktok.com/doc/content-posting-api-get-started
- https://developers.tiktok.com/doc/oauth-user-access-token-management

Two auth modes are supported:

  oauth (default)
    Standard OAuth2 flow. Requires TikTok developer app with
    ``video.publish`` scope approved. Posts appear immediately.

  cookie
    Bypass OAuth entirely. User supplies the ``sessionid`` cookie from
    their logged-in TikTok web session. Posts via the unofficial creator
    API (same as TikTok Studio web). No app review needed.
    ⚠ Unofficial — TikTok may change endpoints without notice. Recommended
    for personal accounts / internal tooling only.

Only the "PULL_FROM_URL" upload mode is implemented here; resumable file
uploads from local disk are intentionally left out to keep the integration
focused. Posts are submitted in DIRECT_POST mode so the caller can control
visibility, captions and challenge tags up front.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

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

logger = logging.getLogger(__name__)

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
POST_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"

# Unofficial creator API (same endpoints used by TikTok Studio web)
_COOKIE_BASE = "https://www.tiktok.com/api"
_COOKIE_USER_URL = f"{_COOKIE_BASE}/user/info/"
_COOKIE_UPLOAD_URL = "https://upload.tiktokapis.com/video/init/"
_COOKIE_PUBLISH_URL = "https://www.tiktok.com/api/post/publish/"

DEFAULT_SCOPES = ["user.info.basic", "video.publish", "video.upload"]

_COOKIE_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Cookie-mode helpers
# ---------------------------------------------------------------------------

def _cookie_headers(sessionid: str) -> dict:
    """Build request headers that look like TikTok web browser traffic."""
    return {
        "User-Agent": _COOKIE_UA,
        "Cookie": f"sessionid={sessionid}",
        "Referer": "https://www.tiktok.com/",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }


def cookie_whoami(sessionid: str) -> dict:
    """Fetch the TikTok profile bound to *sessionid*.

    Returns a dict with ``open_id`` (uid) and ``handle`` (uniqueId).
    Raises ``PlatformError`` if the session is invalid or expired.
    """
    try:
        resp = httpx.get(
            _COOKIE_USER_URL,
            params={"aid": "1988", "app_name": "tiktok_web"},
            headers=_cookie_headers(sessionid),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise PlatformError(f"tiktok cookie whoami failed: {exc}", retryable=False) from exc

    user = data.get("userInfo", {}).get("user", {})
    uid = user.get("id") or user.get("uid")
    handle = user.get("uniqueId") or user.get("nickname") or uid
    if not uid:
        raise PlatformError(
            "tiktok cookie invalid or expired — log in at tiktok.com and copy a fresh sessionid",
            retryable=False,
        )
    return {"open_id": str(uid), "handle": str(handle)}


def _cookie_publish(sessionid: str, media_url: str, caption: str,
                    privacy: str = "SELF_ONLY") -> str:
    """Post a video via the unofficial web API.  Returns the publish_id."""
    # TikTok's unofficial web upload flow:
    # 1. POST /video/init/ to get upload_url + publish_id
    # 2. PUT the raw video bytes to upload_url
    # 3. The video enters TikTok's processing queue — no explicit "publish" call needed
    # We use PULL_FROM_URL so TikTok fetches the bytes itself (no PUT needed).
    privacy_map = {
        "PUBLIC_TO_EVERYONE": 0,
        "MUTUAL_FOLLOW_FRIENDS": 1,
        "FOLLOWER_OF_CREATOR": 2,
        "SELF_ONLY": 3,
    }
    priv_int = privacy_map.get(privacy, 3)
    headers = _cookie_headers(sessionid)
    headers["Content-Type"] = "application/json"

    payload = {
        "source_info": {"source": "PULL_FROM_URL", "video_url": media_url},
        "post_info": {
            "title": caption[:2200],
            "privacy_level": priv_int,
            "disable_duet": False,
            "disable_stitch": False,
            "disable_comment": False,
        },
    }
    try:
        resp = httpx.post(
            _COOKIE_PUBLISH_URL,
            params={"aid": "1988"},
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise PlatformError(f"tiktok cookie publish failed: {exc}", retryable=True) from exc

    publish_id = (data.get("data") or {}).get("publish_id") or data.get("publish_id")
    if not publish_id:
        raise PlatformError(
            f"tiktok cookie publish: missing publish_id in response: {data}",
            retryable=True,
        )
    return str(publish_id)


# ---------------------------------------------------------------------------
# OAuth provider (unchanged)
# ---------------------------------------------------------------------------

class TikTokOAuth(OAuthProvider):
    name = "tiktok"

    def authorization_url(self, state: str) -> str:
        creds = config.platform("tiktok")
        if not creds.configured:
            raise PlatformError("tiktok app credentials not configured", retryable=False)
        params = {
            "client_key": creds.client_id,
            "scope": ",".join(DEFAULT_SCOPES),
            "response_type": "code",
            "redirect_uri": creds.redirect_uri,
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenBundle:
        creds = config.platform("tiktok")
        payload = request_json(
            "POST",
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": creds.client_id,
                "client_secret": creds.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": creds.redirect_uri,
            },
        )
        return self._bundle(payload)

    def refresh(self, refresh_token: str) -> TokenBundle:
        creds = config.platform("tiktok")
        payload = request_json(
            "POST",
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": creds.client_id,
                "client_secret": creds.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        return self._bundle(payload)

    @staticmethod
    def _bundle(payload: dict) -> TokenBundle:
        expires_at = None
        if (ttl := payload.get("expires_in")):
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(ttl))
        return TokenBundle(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at,
            scopes=payload.get("scope", "").split(","),
            extra={"open_id": payload.get("open_id")},
        )


# ---------------------------------------------------------------------------
# Publisher — handles both oauth and cookie modes
# ---------------------------------------------------------------------------

class TikTokPublisher(Publisher):
    name = "tiktok"

    CAPTION_LIMIT = 2200

    def validate(self, request: PublishRequest) -> list[str]:
        issues: list[str] = []
        if len(request.caption) > self.CAPTION_LIMIT:
            issues.append(f"TikTok caption exceeds {self.CAPTION_LIMIT} characters.")
        if not request.media_url or request.media_kind != "video":
            issues.append("TikTok requires a video asset.")
        return issues

    def publish(
        self,
        token: TokenBundle,
        external_account_id: str,
        request: PublishRequest,
    ) -> PublishResult:
        if not request.media_url:
            raise PlatformError("tiktok publish needs media_url", retryable=False)

        privacy = request.overrides.get("privacy_level", "SELF_ONLY")
        if privacy not in {
            "PUBLIC_TO_EVERYONE",
            "MUTUAL_FOLLOW_FRIENDS",
            "FOLLOWER_OF_CREATOR",
            "SELF_ONLY",
        }:
            raise PlatformError(f"invalid tiktok privacy_level: {privacy}", retryable=False)

        # Cookie mode: sessionid stored as access_token, extra.auth_type == "cookie"
        if (token.extra or {}).get("auth_type") == "cookie":
            publish_id = _cookie_publish(
                token.access_token,
                request.media_url,
                request.caption,
                privacy,
            )
            return PublishResult(external_post_id=publish_id, raw={"publish_id": publish_id, "mode": "cookie"})

        # OAuth mode (original)
        post_info = {
            "title": request.caption[: self.CAPTION_LIMIT],
            "privacy_level": privacy,
            "disable_duet": request.overrides.get("disable_duet", False),
            "disable_stitch": request.overrides.get("disable_stitch", False),
            "disable_comment": request.overrides.get("disable_comment", False),
            "video_cover_timestamp_ms": request.overrides.get("cover_ts_ms", 1000),
        }
        if (challenges := request.overrides.get("challenges")):
            post_info["brand_organic_toggle"] = False
            post_info["challenges"] = challenges

        body = {
            "post_info": post_info,
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": request.media_url,
            },
        }
        data = request_json(
            "POST",
            POST_URL,
            json=body,
            headers={
                "Authorization": f"Bearer {token.access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
        )
        publish_id = data.get("data", {}).get("publish_id")
        if not publish_id:
            raise PlatformError(f"tiktok response missing publish_id: {data}", retryable=True)
        return PublishResult(external_post_id=publish_id, raw=data)

    def fetch_insights(self, token, external_account_id, external_post_id):
        """TikTok video metrics via /v2/video/query/ (owned-user fields).

        Note: ``view_count``/``like_count`` etc. are exposed for the video
        owner without research-API approval. ``avg_view_pct`` is not available
        through this endpoint — full retention requires Research API.
        Cookie-mode accounts skip insights (unofficial API doesn't expose metrics).
        """
        if (token.extra or {}).get("auth_type") == "cookie":
            return None  # cookie mode — no official metrics API available
        try:
            data = request_json(
                "POST",
                "https://open.tiktokapis.com/v2/video/query/",
                headers={
                    "Authorization": f"Bearer {token.access_token}",
                    "Content-Type": "application/json",
                },
                params={"fields": "view_count,like_count,comment_count,share_count"},
                json={"filters": {"video_ids": [external_post_id]}},
            )
        except PlatformError:
            return None
        videos = data.get("data", {}).get("videos", [])
        if not videos:
            return None
        v = videos[0]
        return InsightsSnapshot(
            plays=v.get("view_count"),
            likes=v.get("like_count"),
            comments=v.get("comment_count"),
            shares=v.get("share_count"),
            raw=v,
        )
