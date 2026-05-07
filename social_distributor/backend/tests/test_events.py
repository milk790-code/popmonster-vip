"""Event publisher safety + SSE endpoint shape (no real Redis)."""
from unittest.mock import patch

from app.utils.events import publish_event


def test_publish_event_silent_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    with patch("app.utils.events._redis_client", None):
        # Must not raise even though no Redis is configured.
        publish_event(1, "target.status_changed", {"id": 1, "status": "succeeded"})


def test_sse_endpoint_requires_user_id(client):
    res = client.get("/api/events/stream")
    assert res.status_code == 400


def test_sse_endpoint_returns_event_stream_mime(client):
    """Without Redis the stream emits a single noop frame and closes."""
    res = client.get("/api/events/stream?user_id=1")
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["Content-Type"]
    body = res.get_data(as_text=True)
    assert "retry: 5000" in body
    assert "noop" in body  # the no-redis fallback frame
