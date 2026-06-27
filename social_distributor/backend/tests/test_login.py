"""C3: magic-link login + session + backcompat user_id deprecation."""
from unittest.mock import patch

from app.extensions import db
from app.models import User
from app.utils.auth import (
    consume_magic_token,
    find_or_create_user,
    issue_magic_token,
)


# -- token issue / consume round trip ---------------------------------

def test_issue_and_consume_magic_token_round_trip(app):
    with app.app_context():
        token = issue_magic_token("ALICE@example.com")
        email = consume_magic_token(token)
        assert email == "alice@example.com"  # normalised


def test_consume_invalid_token_raises(app):
    from itsdangerous import BadSignature
    with app.app_context():
        try:
            consume_magic_token("not-a-real-token")
        except BadSignature:
            return
        raise AssertionError("expected BadSignature")


# -- find_or_create_user -----------------------------------------------

def test_find_or_create_user_creates_new(app):
    with app.app_context():
        before = db.session.query(User).count()
        u = find_or_create_user("new@example.com")
        after = db.session.query(User).count()
        assert after == before + 1
        assert u.email == "new@example.com"


def test_find_or_create_user_reuses_existing(app):
    with app.app_context():
        first = find_or_create_user("dup@example.com")
        second = find_or_create_user("dup@example.com")
        assert first.id == second.id


# -- POST /auth/login/request -----------------------------------------

def test_login_request_returns_sent_for_any_email(client):
    """Always returns 200 sent=true to prevent enumeration."""
    with patch("app.api.login.send_failure_email") as send:
        res = client.post("/auth/login/request",
                          json={"email": "anyone@example.com"})
    assert res.status_code == 200
    assert res.get_json() == {"sent": True}
    send.assert_called_once()


def test_login_request_rejects_bad_email(client):
    res = client.post("/auth/login/request", json={"email": "not-an-email"})
    assert res.status_code == 400


# -- GET /auth/login/verify -------------------------------------------

def test_verify_creates_user_and_sets_session(client, app):
    with app.app_context():
        token = issue_magic_token("verify@example.com")

    res = client.get(f"/auth/login/verify?token={token}",
                     follow_redirects=False)
    assert res.status_code == 302  # redirect to dashboard
    # Check session cookie was set.
    cookie_header = res.headers.get("Set-Cookie", "")
    assert "session=" in cookie_header.lower()

    # Subsequent /api/me should now report authenticated.
    me = client.get("/auth/me")
    assert me.status_code == 200
    body = me.get_json()
    assert body["authenticated"] is True
    assert body["email"] == "verify@example.com"


def test_verify_rejects_bad_token(client):
    res = client.get("/auth/login/verify?token=garbage")
    assert res.status_code == 400


def test_me_unauthenticated_returns_401(client):
    res = client.get("/auth/me")
    assert res.status_code == 401
    assert res.get_json()["authenticated"] is False


def test_logout_clears_session(client, app):
    with app.app_context():
        token = issue_magic_token("logout@example.com")
    client.get(f"/auth/login/verify?token={token}")
    # Sanity check we're logged in
    assert client.get("/auth/me").status_code == 200

    res = client.post("/auth/logout")
    assert res.status_code == 200
    assert client.get("/auth/me").status_code == 401


# -- backcompat ?user_id= path is removed (security) ------------------

def test_query_user_id_no_longer_authenticates(client, app):
    """The ?user_id= impersonation backcompat path was removed.

    A request that supplies ?user_id= but has no session must be rejected with
    401 and must NOT emit the old Deprecation header.
    """
    with app.app_context():
        user = User(email="bc@example.com", display_name="bc")
        db.session.add(user); db.session.commit()
        uid = user.id

    res = client.get(f"/api/groups?user_id={uid}")
    assert res.status_code == 401
    assert "Deprecation" not in res.headers


def test_session_user_is_authenticated_for_api(client, app):
    with app.app_context():
        token = issue_magic_token("sessionuser@example.com")
    client.get(f"/auth/login/verify?token={token}")
    res = client.get("/api/groups")
    assert res.status_code == 200
    assert "Deprecation" not in res.headers


# -- audit trail ------------------------------------------------------

def test_login_request_writes_audit_with_hashed_email(client, app):
    from app.models import AuditLog

    with patch("app.api.login.send_failure_email"):
        client.post("/auth/login/request",
                    json={"email": "audit@example.com"})

    with app.app_context():
        row = (
            db.session.query(AuditLog)
            .filter_by(action="login.request")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert row is not None
        # Email should NOT be in plaintext anywhere in detail.
        assert "audit@example.com" not in str(row.detail)
        assert "email_hash" in row.detail
