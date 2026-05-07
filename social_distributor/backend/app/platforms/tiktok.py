"""TikTok Content Posting API publisher.

Reference:
- https://developers.tiktok.com/doc/content-posting-api-get-started
- https://developers.tiktok.com/doc/oauth-user-access-token-management

Only the "PULL_FROM_URL" upload mode is implemented here; resumable file
uploads from local disk are intentionally left out to keep the integration
focused. Posts are submitted in DIRECT_POST mode so the caller can control
visibility, captions and challenge tags up front.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
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

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
POST_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"

DEFAULT_SCOPES = ["user.info.basic", "video.publish", "video.upload"]


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
        """
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
