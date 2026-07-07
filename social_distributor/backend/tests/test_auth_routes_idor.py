"""IDOR / session-identity regressions for app/auth/routes.py.

These mirror the per-endpoint hardening already applied to the /api/* routes:
identity is taken ONLY from the authenticated session, and the cross-tenant
revoke is gated by an ownership check.

Covered:
- GET  /auth/<provider>/start-url
                                — login required; returns a browser-safe OAuth
                                  redirect URL after authenticated fetch.
- GET  /auth/<provider>/start   — login required; user_id derived from session,
                                  never from ?user_id=.
- POST /auth/<account_id>/revoke — login required; 403 when the target account
                                  belongs to another user (the original bug).
- POST /auth/tiktok/cookie      — login required; user_id derived from session,
                                  never from body user_id.
"""
from urllib.parse import parse_qs, urlparse
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


def test_start_url_requires_login(client):
    res = client.get("/auth/tiktok/start-url")
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


def test_start_url_ignores_query_user_id_and_uses_session(client, app):
    with app.app_context():
        victim = _make_user("victim-start-url@example.com")
        attacker = _make_user("attacker-start-url@example.com")

    login_as(client, attacker)
    fake_provider = MagicMock()
    fake_provider.authorization_url.return_value = "https://example.test/oauth"
    with patch("app.auth.routes.get_oauth_provider", return_value=fake_provider):
        res = client.get(f"/auth/tiktok/start-url?user_id={victim}")
    assert res.status_code == 200
    body = res.get_json()
    state = body["state"]
    assert body["redirect_url"] == "https://example.test/oauth"
    payload = auth_routes._serializer().loads(state, max_age=600)
    assert payload["user_id"] == attacker
    assert payload["user_id"] != victim


def test_start_url_rejects_missing_session_user(client):
    login_as(client, 999_999)
    res = client.get("/auth/tiktok/start-url")
    assert res.status_code == 401


def test_start_url_returns_oauth_urls_for_connect_buttons(client, app, monkeypatch):
    env = {
        "META_APP_ID": "meta-client-id",
        "META_APP_SECRET": "meta-client-secret",
        "META_REDIRECT_URI": "https://api.example.test/auth/meta/callback",
        "TIKTOK_CLIENT_KEY": "tiktok-client-key",
        "TIKTOK_CLIENT_SECRET": "tiktok-client-secret",
        "TIKTOK_REDIRECT_URI": "https://api.example.test/auth/tiktok/callback",
        "GOOGLE_CLIENT_ID": "google-client-id.apps.googleusercontent.com",
        "GOOGLE_CLIENT_SECRET": "google-client-secret",
        "GOOGLE_REDIRECT_URI": "https://api.example.test/auth/youtube/callback",
        "LINKEDIN_CLIENT_ID": "linkedin-client-id",
        "LINKEDIN_CLIENT_SECRET": "linkedin-client-secret",
        "LINKEDIN_REDIRECT_URI": "https://api.example.test/auth/linkedin/callback",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    with app.app_context():
        user_id = _make_user("oauth-start-url@example.com")
    login_as(client, user_id)

    expected_hosts = {
        "meta": "www.facebook.com",
        "tiktok": "www.tiktok.com",
        "youtube": "accounts.google.com",
        "linkedin": "www.linkedin.com",
    }

    for provider, expected_host in expected_hosts.items():
        res = client.get(f"/auth/{provider}/start-url")
        assert res.status_code == 200
        body = res.get_json()
        redirect_url = body["redirect_url"]
        parsed = urlparse(redirect_url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert parsed.netloc == expected_host
        assert params["state"][0] == body["state"]

        payload = auth_routes._serializer().loads(body["state"], max_age=600)
        assert payload == {"user_id": user_id, "provider": provider}


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
