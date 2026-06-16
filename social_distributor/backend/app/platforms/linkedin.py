"""LinkedIn UGC Posts publisher (text + image + video).

Reference:
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/ugc-post-api
- https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow

Scopes needed: openid, profile, w_member_social
(r_basicprofile / r_liteprofile for older apps)

Posts are created via /v2/ugcPosts (UGC Posts API).
Images use the Assets API (registerUpload → upload bytes → embed URN).
"""
from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
ME_URL = "https://api.linkedin.com/v2/me"
UGC_URL = "https://api.linkedin.com/v2/ugcPosts"

DEFAULT_SCOPES = ["openid", "profile", "w_member_social"]

CAPTION_LIMIT = 3000


class LinkedInOAuth(OAuthProvider):
    name = "linkedin"

    def authorization_url(self, state: str) -> str:
        creds = config.platform("linkedin")
        if not creds.configured:
            raise PlatformError("linkedin app credentials not configured", retryable=False)
        params = {
            "response_type": "code",
            "client_id": creds.client_id,
            "redirect_uri": creds.redirect_uri,
            "state": state,
            "scope": " ".join(DEFAULT_SCOPES),
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenBundle:
        creds = config.platform("linkedin")
        payload = request_json(
            "POST",
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": creds.redirect_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
            },
        )
        return self._bundle(payload)

    def refresh(self, refresh_token: str) -> TokenBundle:
        creds = config.platform("linkedin")
        payload = request_json(
            "POST",
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
            },
        )
        return self._bundle(payload)

    @staticmethod
    def _bundle(payload: dict) -> TokenBundle:
        expires_at = None
        if ttl := payload.get("expires_in"):
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(ttl))
        return TokenBundle(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at,
            scopes=payload.get("scope", "").split(" "),
            extra={},
        )


class LinkedInPublisher(Publisher):
    name = "linkedin"

    def validate(self, request: PublishRequest) -> list[str]:
        issues = []
        if len(request.caption) > CAPTION_LIMIT:
            issues.append(f"LinkedIn caption exceeds {CAPTION_LIMIT} chars.")
        return issues

    def publish(
        self,
        token: TokenBundle,
        external_account_id: str,
        request: PublishRequest,
    ) -> PublishResult:
        author = f"urn:li:person:{external_account_id}"
        headers = {
            "Authorization": f"Bearer {token.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        # Build share content
        share_content: dict = {
            "shareCommentary": {"text": request.caption[:CAPTION_LIMIT]},
            "shareMediaCategory": "NONE",
        }

        if request.media_url:
            if request.media_kind == "image":
                # Register image upload → get asset URN
                reg_body = {
                    "registerUploadRequest": {
                        "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                        "owner": author,
                        "serviceRelationships": [
                            {
                                "relationshipType": "OWNER",
                                "identifier": "urn:li:userGeneratedContent",
                            }
                        ],
                    }
                }
                try:
                    reg = request_json(
                        "POST",
                        "https://api.linkedin.com/v2/assets?action=registerUpload",
                        json=reg_body,
                        headers=headers,
                    )
                    upload_url = reg["value"]["uploadMechanism"][
                        "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
                    ]["uploadUrl"]
                    asset_urn = reg["value"]["asset"]
                    # Download image and upload to LinkedIn
                    import requests as _req
                    img_data = _req.get(request.media_url, timeout=30).content
                    _req.put(
                        upload_url,
                        data=img_data,
                        headers={"Authorization": f"Bearer {token.access_token}"},
                        timeout=60,
                    )
                    share_content["shareMediaCategory"] = "IMAGE"
                    share_content["media"] = [
                        {
                            "status": "READY",
                            "description": {"text": request.caption[:200]},
                            "media": asset_urn,
                            "title": {"text": request.caption[:100]},
                        }
                    ]
                except Exception as exc:
                    logger.warning("linkedin image upload failed, posting text-only: %s", exc)

            elif request.media_kind == "video":
                # Video via URL as article link (LinkedIn video upload is complex;
                # link share is the practical path for PULL_FROM_URL)
                share_content["shareMediaCategory"] = "ARTICLE"
                share_content["media"] = [
                    {
                        "status": "READY",
                        "originalUrl": request.media_url,
                        "title": {"text": request.caption[:100]},
                    }
                ]

        body = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": share_content,
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": request.overrides.get(
                    "visibility", "PUBLIC"
                ),
            },
        }

        data = request_json("POST", UGC_URL, json=body, headers=headers)
        post_id = data.get("id", "")
        if not post_id:
            raise PlatformError(f"linkedin ugcPost missing id: {data}", retryable=True)
        return PublishResult(
            external_post_id=post_id,
            permalink=f"https://www.linkedin.com/feed/update/{post_id}/",
            raw=data,
        )

    def fetch_insights(self, token, external_account_id, external_post_id):
        """LinkedIn organic post stats via Share Statistics API."""
        try:
            data = request_json(
                "GET",
                "https://api.linkedin.com/v2/organizationalEntityShareStatistics",
                params={
                    "q": "organizationalEntity",
                    "organizationalEntity": f"urn:li:person:{external_account_id}",
                    "shares[0]": external_post_id,
                },
                headers={
                    "Authorization": f"Bearer {token.access_token}",
                    "X-Restli-Protocol-Version": "2.0.0",
                },
            )
        except PlatformError:
            return None
        elements = data.get("elements", [])
        if not elements:
            return None
        s = elements[0].get("totalShareStatistics", {})
        return InsightsSnapshot(
            plays=s.get("videoViews"),
            likes=s.get("likeCount"),
            comments=s.get("commentCount"),
            shares=s.get("shareCount"),
            raw=s,
        )
