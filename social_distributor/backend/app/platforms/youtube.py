"""YouTube Data API v3 publisher.

We use the official google-api-python-client for the resumable upload because
it correctly handles chunking, retries on 5xx, and the multipart envelope.

Reference: https://developers.google.com/youtube/v3/guides/uploading_a_video
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from ..config import config
from .base import (
    InsightsSnapshot,
    OAuthProvider,
    PlatformError,
    PublishRequest,
    PublishResult,
    Publisher,
    TokenBundle,
)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def _flow() -> Flow:
    creds = config.platform("google")
    if not creds.configured:
        raise PlatformError("google credentials not configured", retryable=False)
    client_config = {
        "web": {
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [creds.redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = creds.redirect_uri
    return flow


class YouTubeOAuth(OAuthProvider):
    name = "youtube"

    def authorization_url(self, state: str) -> str:
        flow = _flow()
        url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )
        return url

    def exchange_code(self, code: str) -> TokenBundle:
        flow = _flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials
        expires_at = credentials.expiry
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return TokenBundle(
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            expires_at=expires_at,
            scopes=list(credentials.scopes or []),
        )

    def refresh(self, refresh_token: str) -> TokenBundle:
        creds_cfg = config.platform("google")
        credentials = Credentials(
            None,
            refresh_token=refresh_token,
            client_id=creds_cfg.client_id,
            client_secret=creds_cfg.client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
        credentials.refresh(GoogleRequest())
        expires_at = credentials.expiry
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if not expires_at:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=3000)
        return TokenBundle(
            access_token=credentials.token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            scopes=SCOPES,
        )


def _credentials_from_token(token: TokenBundle) -> Credentials:
    creds_cfg = config.platform("google")
    return Credentials(
        token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=creds_cfg.client_id,
        client_secret=creds_cfg.client_secret,
        scopes=SCOPES,
    )


class YouTubePublisher(Publisher):
    name = "youtube"

    TITLE_LIMIT = 100
    DESCRIPTION_LIMIT = 5000

    def validate(self, request: PublishRequest) -> list[str]:
        issues: list[str] = []
        title = request.title or request.caption.split("\n", 1)[0]
        if len(title) > self.TITLE_LIMIT:
            issues.append(f"YouTube title exceeds {self.TITLE_LIMIT} characters.")
        if len(request.caption) > self.DESCRIPTION_LIMIT:
            issues.append(
                f"YouTube description exceeds {self.DESCRIPTION_LIMIT} characters."
            )
        if not request.media_url or request.media_kind != "video":
            issues.append("YouTube requires a video asset.")
        return issues

    def publish(
        self,
        token: TokenBundle,
        external_account_id: str,
        request: PublishRequest,
    ) -> PublishResult:
        if not request.media_url:
            raise PlatformError("youtube publish needs a video", retryable=False)

        credentials = _credentials_from_token(token)
        youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)

        title = (request.title or request.caption.split("\n", 1)[0])[: self.TITLE_LIMIT]
        body = {
            "snippet": {
                "title": title,
                "description": request.caption[: self.DESCRIPTION_LIMIT],
                "tags": request.overrides.get("tags", []),
                "categoryId": str(request.overrides.get("category_id", 22)),
            },
            "status": {
                "privacyStatus": request.overrides.get("privacy_status", "private"),
                "selfDeclaredMadeForKids": request.overrides.get(
                    "made_for_kids", False
                ),
            },
        }

        media = self._media_from_url(request.media_url)
        try:
            insert = youtube.videos().insert(
                part=",".join(body.keys()), body=body, media_body=media
            )
            response = self._resumable_upload(insert)
        except HttpError as exc:
            retryable = 500 <= exc.resp.status < 600 or exc.resp.status == 429
            raise PlatformError(
                f"youtube upload failed: {exc}", retryable=retryable
            ) from exc

        video_id = response["id"]
        if (thumb := request.overrides.get("thumbnail_url")):
            self._set_thumbnail(youtube, video_id, thumb)

        return PublishResult(
            external_post_id=video_id,
            permalink=f"https://www.youtube.com/watch?v={video_id}",
            raw=response,
        )

    @staticmethod
    def _media_from_url(url: str) -> MediaIoBaseUpload:
        with requests.get(url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            buf = io.BytesIO(resp.content)
        return MediaIoBaseUpload(buf, mimetype="video/*", chunksize=-1, resumable=True)

    @staticmethod
    def _resumable_upload(request_obj):
        response = None
        while response is None:
            _, response = request_obj.next_chunk()
        return response

    def fetch_insights(self, token, external_account_id, external_post_id):
        try:
            credentials = _credentials_from_token(token)
            data_api = build("youtube", "v3", credentials=credentials, cache_discovery=False)
            videos = data_api.videos().list(
                part="statistics,contentDetails", id=external_post_id
            ).execute()
        except HttpError:
            return None

        items = videos.get("items", [])
        if not items:
            return None
        stats = items[0].get("statistics", {})

        avg_pct = None
        watch_time = None
        try:
            analytics = build("youtubeAnalytics", "v2", credentials=credentials,
                              cache_discovery=False)
            report = analytics.reports().query(
                ids="channel==MINE",
                startDate="2005-01-01",
                endDate=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                metrics="averageViewPercentage,estimatedMinutesWatched",
                filters=f"video=={external_post_id}",
            ).execute()
            rows = report.get("rows", [])
            if rows:
                avg_pct = float(rows[0][0])
                watch_time = float(rows[0][1]) * 60
        except HttpError:
            pass

        return InsightsSnapshot(
            impressions=int(stats.get("viewCount", 0)) or None,
            plays=int(stats.get("viewCount", 0)) or None,
            likes=int(stats.get("likeCount", 0)) or None,
            comments=int(stats.get("commentCount", 0)) or None,
            avg_view_pct=avg_pct,
            watch_time_seconds=watch_time,
            raw={**stats, "analytics": {"avg_view_pct": avg_pct,
                                        "watch_time_seconds": watch_time}},
        )

    @staticmethod
    def _set_thumbnail(youtube, video_id: str, thumbnail_url: str) -> None:
        with requests.get(thumbnail_url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            buf = io.BytesIO(resp.content)
        media = MediaIoBaseUpload(buf, mimetype="image/jpeg")
        youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
