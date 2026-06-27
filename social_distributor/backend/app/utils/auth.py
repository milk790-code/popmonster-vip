"""Session-based authentication helpers.

Magic-link flow:

1. ``POST /auth/login/request {email}`` — we sign a token (``MAGIC_LINK_TTL``
   default 30 min) with itsdangerous and email it via SendGrid (``notify``).
2. User clicks ``GET /auth/login/verify?token=...`` — we validate, find or
   create the User, set ``session['user_id']`` on a secure cookie, and
   redirect to the dashboard.
3. ``POST /auth/logout`` clears the cookie.

Why session cookies and not JWT bearer tokens? We don't have a separate
mobile app; the dashboard runs in the same origin as the API (or behind
nginx that proxies both), so cookies are the simpler primitive and gain us
``SameSite=Lax`` + ``HttpOnly`` for free.

Identity is ALWAYS taken from the authenticated session. The previous
``?user_id=`` / body ``user_id`` backcompat path was removed: it let any
caller impersonate any user with no authentication.
"""
from __future__ import annotations

import functools
import os
from typing import Callable

from flask import (
    g,
    has_request_context,
    jsonify,
    session,
)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..config import config
from ..extensions import db
from ..models import User

MAGIC_LINK_TTL = int(os.environ.get("MAGIC_LINK_TTL", str(30 * 60)))


def _signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.secret_key, salt="magic-link")


def issue_magic_token(email: str) -> str:
    return _signer().dumps({"email": email.strip().lower()})


def consume_magic_token(token: str) -> str:
    """Returns email if token valid; raises BadSignature/SignatureExpired."""
    payload = _signer().loads(token, max_age=MAGIC_LINK_TTL)
    return payload["email"]


def find_or_create_user(email: str) -> User:
    user = (
        db.session.query(User)
        .filter(User.email == email)
        .one_or_none()
    )
    if user is None:
        user = User(
            email=email,
            display_name=email.split("@", 1)[0],
            timezone="UTC",
        )
        db.session.add(user)
        db.session.commit()
    return user


def current_user_id() -> int | None:
    """Return the user_id for the current request, or None.

    Identity is taken ONLY from the authenticated session. The previous
    ``?user_id=`` / body ``user_id`` backcompat path was removed because it
    let any caller impersonate any user (no authentication at all).

    Order of precedence:
    1. ``g.user_id`` if pre-resolved by middleware
    2. Flask session
    """
    if not has_request_context():
        return None
    if hasattr(g, "user_id") and g.user_id is not None:
        return g.user_id
    sess_uid = session.get("user_id")
    if sess_uid is not None:
        g.user_id = int(sess_uid)
        return g.user_id
    return None


def login_required(fn: Callable) -> Callable:
    """Decorator: 401 if no current user."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        uid = current_user_id()
        if uid is None:
            return jsonify({"error": "authentication required"}), 401
        return fn(*args, **kwargs)
    return wrapper


def attach_user_id_middleware(app) -> None:
    """Resolve user_id once per request from the session and stash on flask.g.

    Identity comes from the authenticated session only. The ``?user_id=``
    backcompat path (and its Deprecation header) was removed: it allowed
    unauthenticated impersonation of any user.
    """
    @app.before_request
    def _resolve():
        sess_uid = session.get("user_id")
        g.user_id = int(sess_uid) if sess_uid is not None else None
