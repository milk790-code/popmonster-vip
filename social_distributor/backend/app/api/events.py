"""Server-Sent Events stream for real-time dashboard updates.

Note for production: gunicorn's default ``sync`` worker holds one request per
worker for the duration of the stream. Use ``--worker-class gevent`` (or
similar async worker) so SSE doesn't pin your whole pool.
"""
from __future__ import annotations

from flask import Blueprint, Response, request, stream_with_context

from ..utils.events import subscribe

bp = Blueprint("events", __name__, url_prefix="/api/events")


@bp.get("/stream")
def stream():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return {"error": "user_id required"}, 400

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
