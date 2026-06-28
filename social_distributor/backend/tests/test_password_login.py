"""Operator password login + bearer-token auth (single-operator convenience).

Covers POST /auth/login/password (503 when unconfigured, 401 on wrong
password, 200 + token on success) and that a signed operator bearer token is
accepted as a valid identity by the /api/* login guard.
"""
from app.config import config as app_config
from app.extensions import db
from app.models import User
from app.utils.auth import (
    issue_operator_token,
    verify_operator_token,
    request_has_operator,
)


# -- POST /auth/login/password ----------------------------------------

def test_password_login_not_configured_returns_503(client, monkeypatch):
    monkeypatch.setattr(app_config, "operator_password", None)
    res = client.post("/auth/login/password", json={"password": "whatever"})
    assert res.status_code == 503
    assert "not configured" in res.get_json()["error"]


def test_password_login_wrong_password_401(client, monkeypatch):
    monkeypatch.setattr(app_config, "operator_password", "correct-horse")
    res = client.post("/auth/login/password", json={"password": "nope"})
    assert res.status_code == 401


def test_password_login_correct_returns_token_and_user(client, app, monkeypatch):
    monkeypatch.setattr(app_config, "operator_password", "correct-horse")
    monkeypatch.setattr(app_config, "operator_email", "operator@local")
    res = client.post("/auth/login/password", json={"password": "correct-horse"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert isinstance(data["token"], str) and data["token"]
    assert isinstance(data["user_id"], int)
    # The token must decode back to the same user_id.
    with app.app_context():
        assert verify_operator_token(data["token"]) == data["user_id"]


def test_password_login_uses_lowest_id_existing_user(client, app, monkeypatch):
    monkeypatch.setattr(app_config, "operator_password", "pw")
    with app.app_context():
        db.session.add(
            User(email="boss@example.com", display_name="boss", timezone="UTC")
        )
        db.session.commit()
        expected_id = db.session.query(User.id).order_by(User.id).first()[0]
    res = client.post("/auth/login/password", json={"password": "pw"})
    assert res.status_code == 200
    # Logs into the lowest-id (i.e. the original operator) account, where the
    # existing data lives — not whichever user was added most recently.
    assert res.get_json()["user_id"] == expected_id


# -- bearer token is a valid operator identity -------------------------

def test_operator_token_round_trip(app):
    with app.app_context():
        tok = issue_operator_token(42)
        assert verify_operator_token(tok) == 42


def test_tampered_operator_token_rejected(app):
    with app.app_context():
        tok = issue_operator_token(42)
        bad = tok[:-2] + ("aa" if not tok.endswith("aa") else "bb")
        assert verify_operator_token(bad) is None


def test_empty_operator_token_rejected(app):
    with app.app_context():
        assert verify_operator_token("") is None


def test_request_has_operator_via_bearer(app):
    with app.app_context():
        tok = issue_operator_token(1)
    with app.test_request_context(headers={"Authorization": f"Bearer {tok}"}):
        assert request_has_operator() is True
    with app.test_request_context():
        assert request_has_operator() is False


def test_bearer_token_passes_api_login_guard(app, monkeypatch):
    """A protected /api/* route returns 401 without auth, but not with a
    valid operator bearer token (the login guard accepts the token).

    Uses fresh clients so the test client's cookie jar doesn't leak a session
    between the anonymous and bearer requests.
    """
    monkeypatch.setattr(app_config, "operator_password", "pw")
    token = app.test_client().post(
        "/auth/login/password", json={"password": "pw"}
    ).get_json()["token"]

    # Fresh client, no session cookie, no header → 401 from the /api login guard.
    anon = app.test_client().get("/api/accounts")
    assert anon.status_code == 401

    # Fresh client carrying ONLY the bearer token → must NOT 401 (the token is
    # accepted as a valid operator identity; endpoint 200s with an empty list).
    authed = app.test_client().get(
        "/api/accounts", headers={"Authorization": f"Bearer {token}"}
    )
    assert authed.status_code != 401


def test_bearer_bypasses_api_key_wall_when_api_key_set(monkeypatch):
    """Production parity: API_KEY is set on Railway. The X-API-Key wall must
    still let a logged-in operator (bearer token) through, while a request
    with neither key nor login is blocked. (X-API-Key stays for external use.)"""
    monkeypatch.setenv("API_KEY", "server-side-key-xyz")
    from app import create_app
    from app.config import config as cfg
    from app.extensions import db as _db

    prod_app = create_app()
    with prod_app.app_context():
        _db.create_all()
    monkeypatch.setattr(cfg, "operator_password", "pw")

    token = prod_app.test_client().post(
        "/auth/login/password", json={"password": "pw"}
    ).get_json()["token"]

    # No api key, no login → blocked by the X-API-Key wall.
    assert prod_app.test_client().get("/api/accounts").status_code == 401
    # Operator bearer token bypasses BOTH the api-key wall and the login guard.
    assert prod_app.test_client().get(
        "/api/accounts", headers={"Authorization": f"Bearer {token}"}
    ).status_code != 401
