"""Ask Graph what a token can actually do, instead of trusting stored scopes."""
from unittest.mock import patch

from app.extensions import db
from app.models import Platform, SocialAccount, User
from app.utils.crypto import cipher

from .conftest import login_as


def _seed(app, *, platform=Platform.FACEBOOK, stored_scopes="pages_manage_posts"):
    with app.app_context():
        user = User(email="gp@example.com", display_name="g")
        db.session.add(user)
        db.session.flush()
        account = SocialAccount(
            user_id=user.id,
            platform=platform,
            external_account_id="page-1",
            handle="@page",
            access_token_enc=cipher().encrypt("page-token-secret"),
            scopes=stored_scopes,
        )
        db.session.add(account)
        db.session.commit()
        return user.id, account.id


DEBUG_OK = {
    "data": {
        "is_valid": True,
        "expires_at": 0,
        "scopes": [
            "pages_show_list",
            "pages_read_engagement",
            "pages_manage_posts",
            "pages_manage_engagement",
        ],
        "granular_scopes": [
            {"scope": "pages_manage_posts", "target_ids": ["page-1", "page-2"]},
        ],
    }
}


def _configured_meta(monkeypatch):
    monkeypatch.setenv("META_APP_ID", "app-123")
    monkeypatch.setenv("META_APP_SECRET", "secret-456")
    monkeypatch.setenv("META_REDIRECT_URI", "https://example.test/cb")


def test_reports_what_graph_granted_not_what_we_stored(client, app, monkeypatch):
    """The stored value says only pages_manage_posts; Graph says the comment
    scope is there too. Believing the stored value would send the operator
    into a needless App Review."""
    _configured_meta(monkeypatch)
    user_id, account_id = _seed(app)
    login_as(client, user_id)

    with patch("app.api.graph_permissions.request_json", return_value=DEBUG_OK):
        res = client.get(f"/api/graph/permissions/{account_id}")

    assert res.status_code == 200, res.data
    body = res.get_json()
    assert body["stored_scopes"] == ["pages_manage_posts"]
    assert "pages_manage_engagement" in body["granted_scopes"]
    assert body["capabilities"]["首則留言／按讚"]["ok"] is True
    assert body["capabilities"]["改粉專簡介"]["ok"] is False
    assert body["capabilities"]["改粉專簡介"]["missing"] == ["pages_manage_metadata"]


def test_never_returns_the_token(client, app, monkeypatch):
    _configured_meta(monkeypatch)
    user_id, account_id = _seed(app)
    login_as(client, user_id)
    with patch("app.api.graph_permissions.request_json", return_value=DEBUG_OK):
        res = client.get(f"/api/graph/permissions/{account_id}")
    assert "page-token-secret" not in res.get_data(as_text=True)


def test_sends_the_app_token_not_the_page_token_as_caller(client, app, monkeypatch):
    """debug_token must be called *as the app*. Passing the page token as the
    caller leaks it into a second position for no benefit."""
    _configured_meta(monkeypatch)
    user_id, account_id = _seed(app)
    login_as(client, user_id)
    seen = {}

    def fake(method, url, **kwargs):
        seen.update(kwargs.get("params") or {})
        return DEBUG_OK

    with patch("app.api.graph_permissions.request_json", side_effect=fake):
        client.get(f"/api/graph/permissions/{account_id}")

    assert seen["input_token"] == "page-token-secret"
    assert seen["access_token"] == "app-123|secret-456"


def test_surfaces_a_rejected_token_as_502_not_500(client, app, monkeypatch):
    from app.platforms.base import PlatformError

    _configured_meta(monkeypatch)
    user_id, account_id = _seed(app)
    login_as(client, user_id)
    with patch("app.api.graph_permissions.request_json",
               side_effect=PlatformError("token revoked")):
        res = client.get(f"/api/graph/permissions/{account_id}")
    assert res.status_code == 502
    assert "token revoked" in res.get_json()["detail"]


def test_is_owner_scoped(client, app, monkeypatch):
    _configured_meta(monkeypatch)
    user_id, account_id = _seed(app)
    with app.app_context():
        other = User(email="x@example.com", display_name="x")
        db.session.add(other)
        db.session.commit()
        other_id = other.id
    login_as(client, other_id)
    assert client.get(f"/api/graph/permissions/{account_id}").status_code == 403


def test_rejects_non_meta_platforms(client, app, monkeypatch):
    _configured_meta(monkeypatch)
    user_id, account_id = _seed(app, platform=Platform.YOUTUBE)
    login_as(client, user_id)
    assert client.get(f"/api/graph/permissions/{account_id}").status_code == 400
