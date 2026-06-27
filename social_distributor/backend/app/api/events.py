"""Server-Sent Events stream for real-time dashboard updates.

Note for production: gunicorn's default ``sync`` worker holds one request per
worker for the duration of the stream. Use ``--worker-class gevent`` (or
similar async worker) so SSE doesn't pin your whole pool.
"""
from __future__ import annotations

from flask import Blueprint, Response, stream_with_context

from ..utils.auth import current_user_id
from ..utils.events import subscribe

bp = Blueprint("events", __name__, url_prefix="/api/events")


@bp.get("/stream")
def stream():
    # EventSource carries the session cookie same-origin; identity is the
    # logged-in user, never a caller-supplied ?user_id=.
    user_id = current_user_id()
    if not user_id:
        return {"error": "authentication required"}, 401

    @stream_with_context
    def generator():
        yield "retry: 5000\n\n"  # tell EventSource to retry every 5s on disconnect
        yield from subscribe(user_id)

    return Response(
        generator(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
        },
    )
