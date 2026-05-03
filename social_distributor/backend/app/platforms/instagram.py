"""Instagram Graph API publisher.

Instagram's Content Publishing API uses a two-step "container then publish"
flow against an IG Business/Creator account linked to a Facebook Page. We
require the Meta OAuth flow to discover the IG user id when connecting the
account.

Reference: https://developers.facebook.com/docs/instagram-api/guides/content-publishing
"""
from __future__ import annotations

import time

from ._http import request_json
from .base import PlatformError, PublishRequest, PublishResult, Publisher, TokenBundle
from .facebook import GRAPH_BASE


class InstagramPublisher(Publisher):
    name = "instagram"

    CAPTION_LIMIT = 2200

    def validate(self, request: PublishRequest) -> list[str]:
        issues: list[str] = []
        if len(request.caption) > self.CAPTION_LIMIT:
            issues.append(
                f"Instagram caption exceeds {self.CAPTION_LIMIT} characters."
            )
        if not request.media_url:
            issues.append("Instagram requires media (image or video).")
        return issues

    def publish(
        self,
        token: TokenBundle,
        external_account_id: str,
        request: PublishRequest,
    ) -> PublishResult:
        if not request.media_url:
            raise PlatformError("instagram requires media", retryable=False)

        ig_user_id = external_account_id
        access_token = token.access_token

        if request.media_kind == "video":
            container = request_json(
                "POST",
                f"{GRAPH_BASE}/{ig_user_id}/media",
                data={
                    "media_type": "REELS"
                    if request.overrides.get("as_reel", True)
                    else "VIDEO",
                    "video_url": request.media_url,
                    "caption": request.caption,
                    "access_token": access_token,
                },
            )
        else:
            container = request_json(
                "POST",
                f"{GRAPH_BASE}/{ig_user_id}/media",
                data={
                    "image_url": request.media_url,
                    "caption": request.caption,
                    "access_token": access_token,
                },
            )

        container_id = container["id"]
        self._wait_for_container(container_id, access_token)

        published = request_json(
            "POST",
            f"{GRAPH_BASE}/{ig_user_id}/media_publish",
            data={"creation_id": container_id, "access_token": access_token},
        )
        return PublishResult(external_post_id=published["id"], raw=published)

    def _wait_for_container(self, container_id: str, access_token: str) -> None:
        deadline = time.monotonic() + 240  # 4 minutes
        while time.monotonic() < deadline:
            status = request_json(
                "GET",
                f"{GRAPH_BASE}/{container_id}",
                params={"fields": "status_code", "access_token": access_token},
            )
            code = status.get("status_code")
            if code == "FINISHED":
                return
            if code in ("ERROR", "EXPIRED"):
                raise PlatformError(
                    f"instagram container failed: {code}", retryable=False
                )
            time.sleep(5)
        raise PlatformError("instagram container timed out", retryable=True)
