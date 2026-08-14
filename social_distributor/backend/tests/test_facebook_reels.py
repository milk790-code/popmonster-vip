"""Video goes out as a Reel, because a video post reaches nobody.

A ``/videos`` post is delivered to the Page's followers. These Pages have
almost none, so every video published that way was a broadcast to an empty
room -- the "not a single play" symptom. Reels are the one surface Facebook
still gives away to non-followers.

Two rules these tests hold down:

1. Trying for the better surface must never cost us the post. If Facebook
   refuses the Reel, the video still goes up the old way.
2. ``finish`` answering 200 is NOT the refusal we are watching for. Aspect
   ratio, resolution, duration and frame rate are judged *after* finish, so a
   Reel can be accepted, encoded, and then dropped -- while our row says
   SUCCEEDED and the Page shows nothing. Every path below therefore ends at
   the status check, not at the finish call.
"""
from unittest.mock import patch

import pytest

from app.platforms import facebook as fb
from app.platforms.base import PlatformError, PublishRequest, TokenBundle
from app.platforms.facebook import FacebookPublisher

REEL_START = {
    "video_id": "v-123",
    "upload_url": "https://rupload.facebook.com/video-upload/v20.0/v-123",
}
REEL_FINISH = {"success": True, "post_id": "page-1_987"}


def _status(video_status):
    return {"status": {"video_status": video_status}}


def _request(kind="video"):
    return PublishRequest(
        caption="洗完沒吹乾就打蠟，等於把水鎖在裡面",
        media_url="https://media.example.test/clip.mp4",
        media_kind=kind,
    )


def _token():
    return TokenBundle(access_token="page-token")


@pytest.fixture(autouse=True)
def _fast_and_clean(monkeypatch):
    """No first comment (separate feature), and no real waiting."""
    monkeypatch.delenv("FB_FIRST_COMMENT", raising=False)
    monkeypatch.delenv("FB_REELS", raising=False)
    monkeypatch.setattr(fb, "REEL_POLL_INTERVAL", 0)
    monkeypatch.setattr(fb, "REEL_READY_TIMEOUT", 1)


def _fake_graph(*, finish=REEL_FINISH, statuses=("ready",), video_id="vid-fallback",
                resolved_post_id="page-1_555"):
    """A stand-in Graph API. ``statuses`` is consumed one poll at a time."""
    calls = []
    remaining = list(statuses)

    def fake(method, url, **kwargs):
        calls.append((method, url, kwargs.get("data") or {},
                      kwargs.get("headers") or {}, kwargs.get("params") or {}))
        if url.endswith("/video_reels"):
            phase = (kwargs.get("data") or {}).get("upload_phase")
            if phase == "start":
                return REEL_START
            if isinstance(finish, Exception):
                raise finish
            return finish
        if url.startswith("https://rupload."):
            return {"success": True}
        if "/videos" in url:
            return {"id": video_id}
        if method == "GET":
            fields = (kwargs.get("params") or {}).get("fields")
            if fields == "post_id":               # resolving the post handle
                return {"post_id": resolved_post_id} if resolved_post_id else {}
            return _status(remaining.pop(0) if remaining else "processing")
        raise AssertionError(f"unexpected call {method} {url}")

    return fake, calls


def test_video_is_published_as_a_reel_and_confirmed_live():
    fake, calls = _fake_graph(statuses=("processing", "ready"))
    with patch("app.platforms.facebook.request_json", side_effect=fake):
        result = FacebookPublisher().publish(_token(), "page-1", _request())

    assert result.surface == "reel"
    assert result.external_post_id == "page-1_987"
    assert result.surface_fallback_error == ""
    # Publishing to both surfaces would double-post, not merely waste a call.
    assert not any("/videos" in url for _, url, *_ in calls)

    _, start_url, start_body, _, _ = calls[0]
    assert start_url.endswith("/page-1/video_reels")
    assert start_body["upload_phase"] == "start"

    # Phase 2 is the odd one: credentials and source URL ride as headers.
    _, upload_url, upload_body, upload_headers, _ = calls[1]
    assert upload_url == REEL_START["upload_url"]
    assert upload_headers["Authorization"] == "OAuth page-token"
    assert upload_headers["file_url"] == "https://media.example.test/clip.mp4"
    assert upload_headers["Content-Type"] == "application/octet-stream"
    assert not upload_body

    _, _, finish_body, _, _ = calls[2]
    assert finish_body["upload_phase"] == "finish"
    assert finish_body["video_state"] == "PUBLISHED"
    assert finish_body["video_id"] == "v-123"

    # It kept asking until Facebook said ready -- one 'processing' was not
    # mistaken for done.
    assert sum(1 for m, _, _, _, _ in calls if m == "GET") == 2


def test_a_reel_dropped_after_encoding_falls_back_instead_of_lying():
    """The failure mode that matters: finish says 200, then the encode judges
    the format and drops it. Without the status check the row would read
    SUCCEEDED while the Page shows nothing at all."""
    fake, calls = _fake_graph(statuses=("processing", "error"))
    with patch("app.platforms.facebook.request_json", side_effect=fake):
        result = FacebookPublisher().publish(_token(), "page-1", _request())

    assert result.external_post_id == "vid-fallback"
    assert result.surface == "video"
    assert "video_status=error" in result.surface_fallback_error
    assert any("/videos" in url for _, url, *_ in calls)


def test_finish_answering_success_false_is_not_success():
    fake, _ = _fake_graph(finish={"success": False, "message": "bad ratio"})
    with patch("app.platforms.facebook.request_json", side_effect=fake):
        result = FacebookPublisher().publish(_token(), "page-1", _request())

    assert result.surface == "video"
    assert "bad ratio" in result.surface_fallback_error


def test_a_reel_stuck_in_processing_gives_up_and_falls_back():
    """Reels are known to sit in processing indefinitely. Waiting forever
    would wedge the worker; waiting nowhere would report a phantom post."""
    fake, _ = _fake_graph(statuses=("processing",) * 50)
    with patch("app.platforms.facebook.request_json", side_effect=fake):
        result = FacebookPublisher().publish(_token(), "page-1", _request())

    assert result.surface == "video"
    assert "still not ready" in result.surface_fallback_error


def test_a_finish_timeout_does_not_double_post():
    """If finish times out on our side but Facebook published anyway, falling
    straight back to /videos posts the same clip twice -- and a duplicate has
    to be deleted by hand. So the outcome is confirmed before deciding."""
    boom = PlatformError("network failure calling finish", retryable=True)
    fake, calls = _fake_graph(finish=boom, statuses=("processing", "ready"))
    with patch("app.platforms.facebook.request_json", side_effect=fake):
        result = FacebookPublisher().publish(_token(), "page-1", _request())

    assert result.surface == "reel"
    # No finish body to read the handle from, so it is looked up -- the same
    # path a normal publish takes when finish omits post_id.
    assert result.external_post_id == "page-1_555"
    assert not any("/videos" in url for _, url, *_ in calls)


def test_a_finish_timeout_on_a_reel_that_really_died_still_falls_back():
    boom = PlatformError("network failure calling finish", retryable=True)
    fake, calls = _fake_graph(finish=boom, statuses=("error",))
    with patch("app.platforms.facebook.request_json", side_effect=fake):
        result = FacebookPublisher().publish(_token(), "page-1", _request())

    assert result.surface == "video"
    assert any("/videos" in url for _, url, *_ in calls)


def test_a_start_phase_without_an_upload_url_falls_back_rather_than_crashing():
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


def test_finish_without_post_id_looks_the_post_up_instead_of_using_the_video_id():
    """A video id is not a post id, and only a post takes comments. The funnel
    link lives in the first comment, so settling for the video id silently
    drops the link off every Reel -- which is what "Object with ID does not
    exist" on 62 of the last 65 comment attempts actually was."""
    fake, calls = _fake_graph(finish={"success": True})
    with patch("app.platforms.facebook.request_json", side_effect=fake):
        result = FacebookPublisher().publish(_token(), "page-1", _request())

    assert result.external_post_id == "page-1_555"
    assert result.surface == "reel"
    assert any((p or {}).get("fields") == "post_id" for *_, p in calls)


def test_an_unreadable_post_id_still_returns_a_usable_handle():
    """Insights work off the video id, so falling back keeps something. The
    comment is the part that breaks, and it reports its own failure."""
    fake, _ = _fake_graph(finish={"success": True}, resolved_post_id=None)
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


def test_photos_and_text_are_untouched():
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


# ---- the derivative that would have made every Reel fail -----------------

def test_facebook_gets_the_portrait_derivative_when_reels_are_on(monkeypatch):
    """The dispatch layer swaps in a per-platform derivative before publishing.
    Facebook's preference was 16:9, and Reels reject anything wider than 9:16 --
    so the Reels path would have been refused on every single video while
    looking perfectly correct in isolation."""
    from app.scheduler.tasks import _preferred_aspect

    monkeypatch.delenv("FB_REELS", raising=False)
    assert _preferred_aspect("facebook") == "9:16"

    monkeypatch.setenv("FB_REELS", "0")
    assert _preferred_aspect("facebook") == "16:9"

    # Other platforms keep their own preference either way.
    assert _preferred_aspect("youtube") == "16:9"
    assert _preferred_aspect("tiktok") == "9:16"
