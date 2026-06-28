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


# --- Operator bearer-token auth --------------------------------------
# The dashboard and API live on different Railway domains, so a SameSite
# session cookie is not sent cross-site. The password login therefore also
# mints a signed bearer token the frontend stores and sends as
# ``Authorization: Bearer <token>`` (or ``?op_token=`` for EventSource SSE,
# which cannot set headers). The token is signed with SECRET_KEY, so it is
# unforgeable, and is treated as a valid operator identity by the guards.
OPERATOR_TOKEN_TTL = int(os.environ.get("OPERATOR_TOKEN_TTL", str(60 * 60 * 24 * 30)))


def _operator_signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.secret_key, salt="operator-session")


def issue_operator_token(user_id: int) -> str:
    return _operator_signer().dumps({"uid": int(user_id)})


def verify_operator_token(token: str) -> int | None:
    """Return the user_id encoded in a valid token, else None."""
    if not token:
        return None
    try:
        data = _operator_signer().loads(token, max_age=OPERATOR_TOKEN_TTL)
        return int(data["uid"])
    except (BadSignature, SignatureExpired, KeyError, ValueError, TypeError):
        return None


def _bearer_user_id() -> int | None:
    """Resolve operator user_id from the Authorization header or ?op_token=."""
    if not has_request_context():
        return None
    from flask import request
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    if not token:
        token = request.args.get("op_token", "")
    return verify_operator_token(token)


def request_has_operator() -> bool:
    """True if the request carries a valid operator session OR bearer token.

    Reads session/headers directly (not flask.g) so it is correct regardless
    of before_request ordering — the api-key guard can call it before the
    user-id middleware has run.
    """
    if not has_request_context():
        return False
    if session.get("user_id") is not None:
        return True
    return _bearer_user_id() is not None


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
    bid = _bearer_user_id()
    if bid is not None:
        g.user_id = bid
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
        if sess_uid is not None:
            g.user_id = int(sess_uid)
        else:
            g.user_id = _bearer_user_id()
