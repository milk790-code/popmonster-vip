"""Magic-link login + identity endpoints (C3).

Endpoints:
- ``POST /auth/login/request {email}`` — send the magic link.
- ``GET /auth/login/verify?token=...`` — set session cookie + redirect.
- ``POST /auth/logout`` — clear session.
- ``GET /api/me`` — return current user (or 401).

We always return 200 from ``/auth/login/request`` regardless of whether the
email exists; this prevents user enumeration. The audit log records the
request so legitimate operators can see what was attempted.
"""
from __future__ import annotations

import hmac
import os

from flask import Blueprint, jsonify, redirect, request, session
from itsdangerous import BadSignature, SignatureExpired

from ..config import config
from ..extensions import db
from ..models import User
from ..utils.audit import record as audit
from ..utils.auth import (
    consume_magic_token,
    find_or_create_user,
    issue_magic_token,
    issue_operator_token,
)
from ..utils.notify import send_failure_email

bp = Blueprint("login", __name__, url_prefix="/auth")

_DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "/")


@bp.post("/login/password")
def login_password():
    """Single-operator password login.

    Requires OPERATOR_PASSWORD to be set in the environment. On a correct
    password we log in as the operator user (the lowest-id existing user, or
    a freshly created OPERATOR_EMAIL user) by setting BOTH a session cookie
    (works same-origin) and returning a signed bearer token (works
    cross-origin, which is how the Railway frontend/api split is deployed).
    """
    expected = config.operator_password
    if not expected:
        return jsonify({"error": "password login not configured"}), 503

    body = request.get_json(force=True) or {}
    supplied = body.get("password") or ""
    if not hmac.compare_digest(
        supplied.encode("utf-8"), expected.encode("utf-8")
    ):
        audit("login.password.failed", "user", None, actor_user_id=None,
              detail={"ip": request.remote_addr})
        db.session.commit()
        return jsonify({"error": "invalid password"}), 401

    user = db.session.query(User).order_by(User.id).first()
    if user is None:
        user = find_or_create_user(config.operator_email)
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    token = issue_operator_token(user.id)
    audit("login.password.ok", "user", user.id, actor_user_id=user.id,
          detail={"ip": request.remote_addr})
    db.session.commit()
    return jsonify({"ok": True, "token": token, "user_id": user.id})


@bp.post("/login/request")
def request_login():
    body = request.get_json(force=True) or {}
    email = (body.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "valid email required"}), 400

    token = issue_magic_token(email)
    base = request.host_url.rstrip("/")
    link = f"{base}/auth/login/verify?token={token}"

    # Reuse the SendGrid plumbing notify.py already established. We use a
    # short helper here to keep the subject/body sane for magic links.
    _send_magic_link(email, link)
    audit("login.request", "user", None,
          actor_user_id=None, detail={"email_hash": _hash_email(email)})
    db.session.commit()
    return jsonify({"sent": True})


@bp.get("/login/verify")
def verify_login():
    token = request.args.get("token", "")
    if not token:
        return jsonify({"error": "token required"}), 400
    try:
        email = consume_magic_token(token)
    except SignatureExpired:
        return jsonify({"error": "magic link expired; request a new one"}), 400
    except BadSignature:
        return jsonify({"error": "invalid magic link"}), 400

    user = find_or_create_user(email)
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    audit("login.verified", "user", user.id, actor_user_id=user.id,
          detail={"email_hash": _hash_email(email)})
    db.session.commit()
    return redirect(_DASHBOARD_URL, code=302)


@bp.post("/logout")
def logout():
    uid = session.get("user_id")
    session.clear()
    if uid:
        audit("logout", "user", uid, actor_user_id=uid)
        db.session.commit()
    return jsonify({"ok": True})


@bp.get("/me")
def me():
    """Quick identity probe used by the dashboard at startup."""
    uid = session.get("user_id")
    if not uid:
        return jsonify({"authenticated": False}), 401
    user = db.session.get(User, uid)
    if not user:
        session.clear()
        return jsonify({"authenticated": False}), 401
    return jsonify({
        "authenticated": True,
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "timezone": user.timezone,
    })


def _send_magic_link(email: str, link: str) -> None:
    body = (
        f"Click to sign in to Social Distributor:\n\n{link}\n\n"
        f"This link is valid for 30 minutes. If you didn't request it, ignore this email."
    )
    send_failure_email(
        to=[email],
        subject="Sign in to Social Distributor",
        body=body,
    )


def _hash_email(email: str) -> str:
    import hashlib
    return hashlib.sha256(email.encode()).hexdigest()[:16]
