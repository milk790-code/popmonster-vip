"""IDOR / session-identity regressions for app/auth/routes.py.

These mirror the per-endpoint hardening already applied to the /api/* routes:
identity is taken ONLY from the authenticated session, and the cross-tenant
revoke is gated by an ownership check.

Covered:
- GET  /auth/<provider>/start   — login required; user_id derived from session,
                                  never from ?user_id=.
- POST /auth/<account_id>/revoke — login required; 403 when the target account
                                  belongs to another user (the original bug).
- POST /auth/tiktok/cookie      — login required; user_id derived from session,
                                  never from body user_id.
"""
from unittest.mock import MagicMock, patch

from app.auth import routes as auth_routes
from app.extensions import db
from app.models import Platform, SocialAccount, User

from .conftest import login_as


def _make_user(email: str) -> int:
    user = User(email=email, display_name=email.split("@", 1)[0])
    db.session.add(user)
    db.session.commit()
    return user.id


def _make_account(user_id: int, ext: str = "ext-1") -> int:
    acc = SocialAccount(
        user_id=user_id,
        platform=Platform.TIKTOK,
        external_account_id=ext,
        handle="h",
        access_token_enc=b"secret",
    )
    db.session.add(acc)
    db.session.commit()
    return acc.id


# -- /auth/<provider>/start -------------------------------------------

def test_start_requires_login(client):
    res = client.get("/auth/tiktok/start")
    assert res.status_code == 401


def test_start_ignores_query_user_id_and_uses_session(client, app):
    with app.app_context():
        victim = _make_user("victim-start@example.com")
        attacker = _make_user("attacker-start@example.com")

    login_as(client, attacker)
    fake_provider = MagicMock()
    fake_provider.authorization_url.return_value = "https://example.test/oauth"
    # Attacker tries to bind the flow to the victim via ?user_id=.
    with patch("app.auth.routes.get_oauth_provider", return_value=fake_provider):
        res = client.get(f"/auth/tiktok/start?user_id={victim}")
    assert res.status_code == 200
    state = res.get_json()["state"]
    # The signed state must carry the attacker's OWN id, not the victim's.
    payload = auth_routes._serializer().loads(state, max_age=600)
    assert payload["user_id"] == attacker
    assert payload["user_id"] != victim


# -- /auth/<account_id>/revoke ----------------------------------------

def test_revoke_requires_login(client, app):
    with app.app_context():
        owner = _make_user("owner-revoke@example.com")
        account_id = _make_account(owner)

    res = client.post(f"/auth/{account_id}/revoke")
    assert res.status_code == 401


def test_revoke_forbidden_for_other_users_account(client, app):
    """The original HIGH bug: any authed user could revoke ANYONE's account."""
    with app.app_context():
        owner = _make_user("owner2-revoke@example.com")
        attacker = _make_user("attacker-revoke@example.com")
        account_id = _make_account(owner)

    login_as(client, attacker)
    res = client.post(f"/auth/{account_id}/revoke")
    assert res.status_code == 403

    with app.app_context():
        acc = db.session.get(SocialAccount, account_id)
        assert acc.revoked_at is None  # untouched
        assert acc.access_token_enc == b"secret"


def test_revoke_succeeds_for_own_account(client, app):
    with app.app_context():
        owner = _make_user("owner3-revoke@example.com")
        account_id = _make_account(owner)

    login_as(client, owner)
    res = client.post(f"/auth/{account_id}/revoke")
    assert res.status_code == 200
    assert res.get_json()["revoked"] == account_id

    with app.app_context():
        acc = db.session.get(SocialAccount, account_id)
        assert acc.revoked_at is not None
        assert acc.access_token_enc == b""


# -- /auth/tiktok/cookie ----------------------------------------------

def test_tiktok_cookie_requires_login(client):
    res = client.post("/auth/tiktok/cookie", json={"sessionid": "abc"})
    assert res.status_code == 401


def test_tiktok_cookie_ignores_body_user_id_and_uses_session(client, app):
    with app.app_context():
        victim = _make_user("victim-cookie@example.com")
        attacker = _make_user("attacker-cookie@example.com")

    login_as(client, attacker)
    with patch(
        "app.platforms.tiktok.cookie_whoami",
        return_value={"open_id": "tt-open", "handle": "ttuser"},
    ):
        # Attacker supplies victim's user_id in the body — must be ignored.
        res = client.post(
            "/auth/tiktok/cookie",
            json={"user_id": victim, "sessionid": "valid-session"},
        )
    assert res.status_code == 200

    with app.app_context():
        acc = db.session.query(SocialAccount).filter_by(
            platform=Platform.TIKTOK, external_account_id="tt-open"
        ).one()
        # Account is bound to the AUTHENTICATED user, not the body user_id.
        assert acc.user_id == attacker
        assert acc.user_id != victim
