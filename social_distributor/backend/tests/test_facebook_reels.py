"""Video goes out as a Reel, because a video post reaches nobody.

A ``/videos`` post is delivered to the Page's followers. These Pages have
almost none, so every video published that way was a broadcast to an empty
room -- the "not a single play" symptom. Reels are the one surface Facebook
still gives away to non-followers.

The rule these tests hold down: trying for the better surface must never
cost us the post. If Facebook refuses the Reel, the video still goes up the
old way, and the downgrade is recorded rather than swallowed.
"""
from unittest.mock import patch

import pytest

from app.platforms.base import PlatformError, PublishRequest, TokenBundle
from app.platforms.facebook import FacebookPublisher

REEL_START = {
    "video_id": "v-123",
    "upload_url": "https://rupload.facebook.com/video-upload/v20.0/v-123",
}
REEL_FINISH = {"success": True, "post_id": "page-1_987"}


def _request(kind="video"):
    return PublishRequest(
        caption="洗完沒吹乾就打蠟，等於把水鎖在裡面",
        media_url="https://media.example.test/clip.mp4",
        media_kind=kind,
    )


def _token():
    return TokenBundle(access_token="page-token")


@pytest.fixture(autouse=True)
def _no_first_comment(monkeypatch):
    """The first comment is a separate feature; keep it out of these calls."""
    monkeypatch.delenv("FB_FIRST_COMMENT", raising=False)


def test_video_is_published_as_a_reel_by_default(monkeypatch):
    monkeypatch.delenv("FB_REELS", raising=False)
    calls = []

    def fake(method, url, **kwargs):
        calls.append((url, kwargs.get("data") or {}, kwargs.get("headers") or {}))
        if url.endswith("/video_reels"):
            phase = (kwargs.get("data") or {}).get("upload_phase")
            return REEL_START if phase == "start" else REEL_FINISH
        return {"id": "should-not-be-used"}

    with patch("app.platforms.facebook.request_json", side_effect=fake):
        result = FacebookPublisher().publish(_token(), "page-1", _request())

    assert result.surface == "reel"
    assert result.external_post_id == "page-1_987"
    assert result.surface_fallback_error == ""
    # The plain video endpoint must not be touched at all -- publishing to
    # both would double-post, not merely waste a call.
    assert not any("/videos" in url for url, _, _ in calls)

    start_url, start_body, _ = calls[0]
    assert start_url.endswith("/page-1/video_reels")
    assert start_body["upload_phase"] == "start"

    # Phase 2 is the odd one: credentials and source URL ride as headers.
    upload_url, upload_body, upload_headers = calls[1]
    assert upload_url == REEL_START["upload_url"]
    assert upload_headers["Authorization"] == "OAuth page-token"
    assert upload_headers["file_url"] == "https://media.example.test/clip.mp4"
    assert not upload_body

    _, finish_body, _ = calls[2]
    assert finish_body["upload_phase"] == "finish"
    assert finish_body["video_state"] == "PUBLISHED"
    assert finish_body["video_id"] == "v-123"
    assert finish_body["description"] == "洗完沒吹乾就打蠟，等於把水鎖在裡面"


def test_a_refused_reel_still_gets_published_as_a_video(monkeypatch):
    """Reels have format rules we cannot check from a URL. Landscape or
    over-length clips get refused, and losing the post over that would be
    strictly worse than the behaviour we are replacing."""
    monkeypatch.delenv("FB_REELS", raising=False)

    def fake(method, url, **kwargs):
        if url.endswith("/video_reels"):
            raise PlatformError("(#100) Video does not meet Reels spec",
                                retryable=False)
        if "/videos" in url:
            return {"id": "vid-456"}
        raise AssertionError(f"unexpected call to {url}")

    with patch("app.platforms.facebook.request_json", side_effect=fake):
        result = FacebookPublisher().publish(_token(), "page-1", _request())

    assert result.external_post_id == "vid-456"
    assert result.surface == "video"
    # Recorded, not swallowed: a fleet that had quietly stopped qualifying
    # for Reels would otherwise look exactly like one that never stopped.
    assert "does not meet Reels spec" in result.surface_fallback_error


def test_a_start_phase_without_an_upload_url_falls_back_rather_than_crashing():
    """Graph can answer 200 with a body that is missing what we need. Reading
    that as success would post nothing at all and report success."""
    def fake(method, url, **kwargs):
        if url.endswith("/video_reels"):
            return {"video_id": "v-123"}          # no upload_url
        if "/videos" in url:
            return {"id": "vid-789"}
        raise AssertionError(f"unexpected call to {url}")

    with patch("app.platforms.facebook.request_json", side_effect=fake):
        result = FacebookPublisher().publish(_token(), "page-1", _request())

    assert result.external_post_id == "vid-789"
    assert result.surface == "video"
    assert "no upload target" in result.surface_fallback_error


def test_finish_without_post_id_keeps_the_video_id_as_the_handle(monkeypatch):
    """Older responses only confirm success. The video id is still a handle
    we can fetch insights against, so it beats returning ``None``."""
    monkeypatch.delenv("FB_REELS", raising=False)

    def fake(method, url, **kwargs):
        if url.endswith("/video_reels"):
            phase = (kwargs.get("data") or {}).get("upload_phase")
            return REEL_START if phase == "start" else {"success": True}
        return {}

    with patch("app.platforms.facebook.request_json", side_effect=fake):
        result = FacebookPublisher().publish(_token(), "page-1", _request())

    assert result.external_post_id == "v-123"
    assert result.surface == "reel"


def test_the_switch_can_force_the_old_path(monkeypatch):
    monkeypatch.setenv("FB_REELS", "0")

    def fake(method, url, **kwargs):
        if url.endswith("/video_reels"):
            raise AssertionError("reels path must be skipped entirely")
        return {"id": "vid-000"}

    with patch("app.platforms.facebook.request_json", side_effect=fake):
        result = FacebookPublisher().publish(_token(), "page-1", _request())

    assert result.surface == "video"
    assert result.surface_fallback_error == ""


def test_photos_and_text_are_untouched(monkeypatch):
    """The Reels change must not leak into the other two publish paths."""
    monkeypatch.delenv("FB_REELS", raising=False)
    seen = []

    def fake(method, url, **kwargs):
        seen.append(url)
        return {"id": "x-1", "post_id": "x-1"}

    with patch("app.platforms.facebook.request_json", side_effect=fake):
        photo = FacebookPublisher().publish(_token(), "page-1", _request("image"))
        text = FacebookPublisher().publish(
            _token(), "page-1",
            PublishRequest(caption="純文字", media_url=None, media_kind=None),
        )

    assert photo.surface == ""
    assert text.surface == ""
    assert not any("video_reels" in url for url in seen)
