"""Event publisher safety + SSE endpoint shape (no real Redis)."""
from unittest.mock import patch

from app.extensions import db
from app.models import User
from app.utils.events import publish_event

from .conftest import login_as


def test_publish_event_silent_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    with patch("app.utils.events._redis_client", None):
        # Must not raise even though no Redis is configured.
        publish_event(1, "target.status_changed", {"id": 1, "status": "succeeded"})


def test_sse_endpoint_requires_login(client):
    res = client.get("/api/events/stream")
    assert res.status_code == 401


def test_sse_endpoint_returns_event_stream_mime(client, app):
    """Without Redis the stream emits a single noop frame and closes."""
    with app.app_context():
        user = User(email="sse@example.com", display_name="sse")
        db.session.add(user)
        db.session.commit()
        uid = user.id
    login_as(client, uid)
    res = client.get("/api/events/stream")
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["Content-Type"]
    body = res.get_data(as_text=True)
    assert "retry: 5000" in body
    assert "noop" in body  # the no-redis fallback frame
