"""Facebook Page publisher (Graph API v20).

Reference:
- https://developers.facebook.com/docs/pages-api/posts
- https://developers.facebook.com/docs/video-api/guides/publishing
"""
from __future__ import annotations

import os
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

GRAPH_BASE = "https://graph.facebook.com/v20.0"
GRAPH_VIDEO_BASE = "https://graph-video.facebook.com/v20.0"
DIALOG_BASE = "https://www.facebook.com/v20.0/dialog/oauth"

DEFAULT_SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "instagram_basic",
    "instagram_content_publish",
]


class MetaOAuth(OAuthProvider):
    """Shared between Facebook and Instagram (Meta consolidated app)."""

    name = "meta"

    def refresh(self, refresh_token: str) -> TokenBundle:
        """B4: Meta long-lived Page tokens don't expire, but the user
        token used to mint them does (60 days). We re-exchange the stored
        page/user token via ``fb_exchange_token`` which both extends the
        expiry window and detects revocation (returns 4xx from Graph)."""
        creds = config.platform("meta")
        if not creds.configured:
            raise PlatformError("meta app credentials not configured",
                                retryable=False)
        long_lived = request_json(
            "GET",
            f"{GRAPH_BASE}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "fb_exchange_token": refresh_token,
            },
        )
        from datetime import datetime, timedelta, timezone as _tz
        expires_at = None
        if (ttl := long_lived.get("expires_in")):
            expires_at = datetime.now(_tz.utc) + timedelta(seconds=int(ttl))
        return TokenBundle(
            access_token=long_lived["access_token"],
            expires_at=expires_at,
            scopes=DEFAULT_SCOPES,
        )

    def authorization_url(self, state: str) -> str:
        creds = config.platform("meta")
        if not creds.configured:
            raise PlatformError("meta app credentials not configured", retryable=False)
        params = {
            "client_id": creds.client_id,
            "redirect_uri": creds.redirect_uri,
            "response_type": "code",
            "state": state,
            # auth_type=reauthorize forces FB to show the consent dialog even
            # for already-connected users. Without it, FB Login for Business
            # short-circuits to a dead-end "already connected" info page that
            # never redirects back to our callback, so we can't re-pull the
            # Page list (e.g. when the user has added new Pages since the
            # original OAuth, or when paging cursor was missed in older code).
            "auth_type": "reauthorize",
        }
        # Facebook Login for Business: scopes are baked into the login config
        # so we send config_id instead of scope. Falls back to classic
        # Facebook Login flow with explicit scopes when META_LOGIN_CONFIG_ID
        # isn't set.
        config_id = os.environ.get("META_LOGIN_CONFIG_ID", "").strip()
        if config_id:
            params["config_id"] = config_id
        else:
            params["scope"] = ",".join(DEFAULT_SCOPES)
        return f"{DIALOG_BASE}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenBundle:
        creds = config.platform("meta")
        payload = request_json(
            "GET",
            f"{GRAPH_BASE}/oauth/access_token",
            params={
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "redirect_uri": creds.redirect_uri,
                "code": code,
            },
        )
        # Exchange short-lived for long-lived (60 day) token.
        long_lived = request_json(
            "GET",
            f"{GRAPH_BASE}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "fb_exchange_token": payload["access_token"],
            },
        )
        expires_at = None
        if (ttl := long_lived.get("expires_in")):
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(ttl))
        return TokenBundle(
            access_token=long_lived["access_token"],
            expires_at=expires_at,
            scopes=DEFAULT_SCOPES,
        )


class FacebookPublisher(Publisher):
    name = "facebook"

    def validate(self, request: PublishRequest) -> list[str]:
        issues: list[str] = []
        if len(request.caption) > 63206:
            issues.append("Facebook post text exceeds 63,206 characters.")
        return issues

    def publish(
        self,
        token: TokenBundle,
        external_account_id: str,
        request: PublishRequest,
    ) -> PublishResult:
        # external_account_id is the Page ID. The token must be a Page Access Token,
        # which the OAuth callback converts via /me/accounts.
        page_token = token.extra.get("page_access_token", token.access_token)

        if request.media_url and request.media_kind == "video":
            result = self._publish_video(page_token, external_account_id, request)
        elif request.media_url and request.media_kind == "image":
            result = self._publish_photo(page_token, external_account_id, request)
        else:
            result = self._publish_text(page_token, external_account_id, request)

        # Phase D: auto first comment. Seeds engagement on new accounts
        # (no comment -> 0 reach) and carries the brand site for traffic.
        self._post_first_comment(page_token, result.external_post_id, request)
        return result

    def _post_first_comment(self, token, post_id, req: PublishRequest) -> None:
        """Post a first comment on the page's own post right after publishing.

        ``req.first_comment`` is resolved upstream by
        ``compliance.engine.resolve_first_comment`` (per-post override, then
        per-account profile, then brand-line default, then the
        ``FB_FIRST_COMMENT`` environment variable). The env var is checked
        here too so a directly-constructed request still honours it.

        The text supports an optional ``{link}`` placeholder, filled with
        request.link_url. This never raises -- a failed comment must not
        fail an already-succeeded post.
        """
        template = (getattr(req, "first_comment", "")
                    or os.environ.get("FB_FIRST_COMMENT", "")).strip()
        if not template or not post_id:
            return
        try:
            message = template.replace("{link}", req.link_url or "")
            request_json(
                "POST",
                f"{GRAPH_BASE}/{post_id}/comments",
                data={"message": message, "access_token": token},
                timeout=30,
            )
        except Exception:
            # Intentionally swallowed: the main post already succeeded.
            pass

    def _publish_text(self, token, page_id, req: PublishRequest) -> PublishResult:
        body = {"message": req.caption, "access_token": token}
        if req.link_url:
            body["link"] = req.link_url
        data = request_json("POST", f"{GRAPH_BASE}/{page_id}/feed", data=body)
        return PublishResult(external_post_id=data["id"], raw=data)

    def _publish_photo(self, token, page_id, req: PublishRequest) -> PublishResult:
        data = request_json(
            "POST",
            f"{GRAPH_BASE}/{page_id}/photos",
            data={
                "url": req.media_url,
                "caption": req.caption,
                "access_token": token,
            },
        )
        return PublishResult(external_post_id=data.get("post_id", data["id"]), raw=data)

    def fetch_insights(self, token, external_account_id, external_post_id):
        page_token = token.extra.get("page_access_token", token.access_token)
        try:
            data = request_json(
                "GET",
                f"{GRAPH_BASE}/{external_post_id}/insights",
                params={
                    "access_token": page_token,
                    "metric": "post_impressions,post_impressions_unique,"
                              "post_reactions_by_type_total,post_clicks",
                },
            )
        except PlatformError:
            return None
        metrics = {item["name"]: item["values"][0]["value"]
                   for item in data.get("data", []) if item.get("values")}
        reactions = metrics.get("post_reactions_by_type_total") or {}
        likes = sum(reactions.values()) if isinstance(reactions, dict) else None
        return InsightsSnapshot(
            reach=metrics.get("post_impressions_unique"),
            impressions=metrics.get("post_impressions"),
            likes=likes,
            raw=metrics,
        )

    def _publish_video(self, token, page_id, req: PublishRequest) -> PublishResult:
        # B6: video uploads can take 60-120s; use long timeout instead of
        # the 60s default so a slow Meta CDN doesn't fail us spuriously.
        data = request_json(
            "POST",
            f"{GRAPH_VIDEO_BASE}/{page_id}/videos",
            data={
                "file_url": req.media_url,
                "description": req.caption,
                "title": req.title or None,
                "access_token": token,
            },
            timeout=180,
        )
        return PublishResult(external_post_id=str(data.get("id")), raw=data)
