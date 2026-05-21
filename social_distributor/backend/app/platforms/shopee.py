"""Shopee Open Platform publisher — 蝦皮短影音 (Shopee Short Video).

References:
- https://open.shopee.com/documents/v2/v2.shop.auth_partner
- https://open.shopee.com/documents/v2/v2.auth.token.get
- https://open.shopee.com/documents/v2/v2.media_space.upload_video_by_url
- https://open.shopee.com/documents/v2/v2.shop.short_video

All API calls are signed with HMAC-SHA256 as required by the Shopee Open
Platform v2. Shop-level OAuth 2.0 grants access to publish content under a
seller shop.
"""
from __future__ import annotations

import hashlib
import hmac
import time
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

_BASE = "https://partner.shopeemobile.com"
_AUTH_PATH = "/api/v2/shop/auth_partner"
_TOKEN_PATH = "/api/v2/auth/token/get"
_REFRESH_PATH = "/api/v2/auth/access_token/get"
_UPLOAD_VIDEO_PATH = "/api/v2/media_space/upload_video_by_url"
_PUBLISH_VIDEO_PATH = "/api/v2/shop/short_video/publish"
_VIDEO_LIST_PATH = "/api/v2/shop/short_video/get_short_video_list"

DESCRIPTION_LIMIT = 500


def _sign(partner_key: str, partner_id: str, path: str, timestamp: int,
          access_token: str = "", shop_id: str = "") -> str:
    """HMAC-SHA256 signature for Shopee Open Platform v2."""
    parts = [partner_id, path, str(timestamp)]
    if access_token:
        parts.append(access_token)
    if shop_id:
        parts.append(shop_id)
    base = "".join(parts)
    return hmac.new(partner_key.encode(), base.encode(), hashlib.sha256).hexdigest()


def _public_params(partner_key: str, partner_id: str, path: str) -> dict:
    ts = int(time.time())
    return {
        "partner_id": int(partner_id),
        "timestamp": ts,
        "sign": _sign(partner_key, partner_id, path, ts),
    }


def _auth_params(partner_key: str, partner_id: str, path: str,
                 access_token: str, shop_id: str) -> dict:
    ts = int(time.time())
    return {
        "partner_id": int(partner_id),
        "timestamp": ts,
        "access_token": access_token,
        "shop_id": int(shop_id),
        "sign": _sign(partner_key, partner_id, path, ts, access_token, shop_id),
    }


class ShopeeOAuth(OAuthProvider):
    name = "shopee"

    def authorization_url(self, state: str) -> str:
        creds = config.platform("shopee")
        if not creds.configured:
            raise PlatformError("shopee app credentials not configured", retryable=False)
        ts = int(time.time())
        partner_key = creds.client_secret
        partner_id = creds.client_id
        sign = _sign(partner_key, partner_id, _AUTH_PATH, ts)
        params = {
            "partner_id": int(partner_id),
            "timestamp": ts,
            "sign": sign,
            "redirect": creds.redirect_uri,
        }
        # Pass state through redirect URI as query param so the callback can
        # verify it (Shopee doesn't have a native state parameter).
        redirect_with_state = f"{creds.redirect_uri}?state={state}"
        params["redirect"] = redirect_with_state
        return f"{_BASE}{_AUTH_PATH}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenBundle:
        """Exchange auth code for access + refresh tokens.

        Shopee passes shop_id and code (main_account_id) in the redirect.
        The caller is responsible for extracting shop_id from the callback
        query params and encoding it into ``code`` as ``<shop_id>:<code>``.
        """
        shop_id, auth_code = code.split(":", 1)
        creds = config.platform("shopee")
        params = _public_params(creds.client_secret, creds.client_id, _TOKEN_PATH)
        payload = request_json(
            "POST",
            f"{_BASE}{_TOKEN_PATH}",
            params=params,
            json={
                "code": auth_code,
                "shop_id": int(shop_id),
                "partner_id": int(creds.client_id),
            },
        )
        return self._bundle(payload, shop_id)

    def refresh(self, refresh_token: str) -> TokenBundle:
        """Refresh using stored refresh token (encoded as ``<shop_id>:<token>``)."""
        shop_id, token = refresh_token.split(":", 1)
        creds = config.platform("shopee")
        params = _public_params(creds.client_secret, creds.client_id, _REFRESH_PATH)
        payload = request_json(
            "POST",
            f"{_BASE}{_REFRESH_PATH}",
            params=params,
            json={
                "refresh_token": token,
                "shop_id": int(shop_id),
                "partner_id": int(creds.client_id),
            },
        )
        return self._bundle(payload, shop_id)

    @staticmethod
    def _bundle(payload: dict, shop_id: str) -> TokenBundle:
        if payload.get("error"):
            raise PlatformError(
                f"Shopee token error: {payload.get('error')} — {payload.get('message')}",
                retryable=False,
            )
        expires_at = None
        if (ttl := payload.get("expire_in")):
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(ttl))
        # Encode shop_id into tokens so the publisher can retrieve it.
        raw_access = payload["access_token"]
        raw_refresh = payload.get("refresh_token", "")
        return TokenBundle(
            access_token=f"{shop_id}:{raw_access}",
            refresh_token=f"{shop_id}:{raw_refresh}" if raw_refresh else None,
            expires_at=expires_at,
            scopes=[],
            extra={"shop_id": shop_id},
        )


class ShopeePublisher(Publisher):
    name = "shopee"

    def validate(self, request: PublishRequest) -> list[str]:
        issues: list[str] = []
        if len(request.caption) > DESCRIPTION_LIMIT:
            issues.append(f"Shopee short video description exceeds {DESCRIPTION_LIMIT} characters.")
        if not request.media_url or request.media_kind != "video":
            issues.append("Shopee short video requires a video asset.")
        return issues

    def publish(
        self,
        token: TokenBundle,
        external_account_id: str,
        request: PublishRequest,
    ) -> PublishResult:
        if not request.media_url:
            raise PlatformError("shopee publish needs media_url", retryable=False)

        shop_id, access_token = token.access_token.split(":", 1)
        creds = config.platform("shopee")
        partner_id = creds.client_id
        partner_key = creds.client_secret

        # Step 1: upload video via URL to Shopee Media Space.
        upload_params = _auth_params(
            partner_key, partner_id, _UPLOAD_VIDEO_PATH, access_token, shop_id
        )
        upload_resp = request_json(
            "POST",
            f"{_BASE}{_UPLOAD_VIDEO_PATH}",
            params=upload_params,
            json={"url": request.media_url},
        )
        if upload_resp.get("error"):
            raise PlatformError(
                f"Shopee video upload failed: {upload_resp.get('error')} — "
                f"{upload_resp.get('message')}",
                retryable=True,
            )
        video_id = (upload_resp.get("response") or {}).get("video_id")
        if not video_id:
            raise PlatformError(
                f"Shopee upload response missing video_id: {upload_resp}",
                retryable=True,
            )

        # Step 2: publish as a short video post.
        publish_params = _auth_params(
            partner_key, partner_id, _PUBLISH_VIDEO_PATH, access_token, shop_id
        )
        body = {
            "video_id": video_id,
            "description": request.caption[:DESCRIPTION_LIMIT],
        }
        if request.title:
            body["title"] = request.title[:100]

        publish_resp = request_json(
            "POST",
            f"{_BASE}{_PUBLISH_VIDEO_PATH}",
            params=publish_params,
            json=body,
        )
        if publish_resp.get("error"):
            raise PlatformError(
                f"Shopee short video publish failed: {publish_resp.get('error')} — "
                f"{publish_resp.get('message')}",
                retryable=False,
            )
        short_video_id = str(
            (publish_resp.get("response") or {}).get("short_video_id", video_id)
        )
        return PublishResult(
            external_post_id=short_video_id,
            permalink=None,
            raw=publish_resp,
        )

    def fetch_insights(
        self,
        token: TokenBundle,
        external_account_id: str,
        external_post_id: str,
    ) -> InsightsSnapshot | None:
        try:
            shop_id, access_token = token.access_token.split(":", 1)
            creds = config.platform("shopee")
            params = _auth_params(
                creds.client_secret, creds.client_id,
                _VIDEO_LIST_PATH, access_token, shop_id,
            )
            params["short_video_id_list"] = [int(external_post_id)]
            resp = request_json("GET", f"{_BASE}{_VIDEO_LIST_PATH}", params=params)
            videos = (resp.get("response") or {}).get("short_video_list", [])
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
        except PlatformError:
            return None
